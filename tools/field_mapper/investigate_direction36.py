"""
Direction 36 - Roster-scan the 10 pre-corridor strings at the DefaultMove run.

Direction 35 ruled out the +0x910..+0x9b0 effect-list corridor as the carrier
for Whommie/Bud's missing birth-defect effects. The remaining unmapped surface
that the parser actively touches (but filters) is the 10 strings preceding the
corridor. The parser walks them as part of a "DefaultMove" ability run and
silently rewinds and discards any token that fails ``_IDENT_RE`` or is in the
``_JUNK_STRINGS`` set.

This script reads each cat's blob, locates ``run_start = marker - 8`` (where
marker is the "DefaultMove" byte sequence), and sequentially decodes every
string in the run WITHOUT any identifier filter. We dump the raw decoded text
and a short categorisation tag so we can compare defect-positive cats
(Whommie 853, Bud 887) with clean controls (Kami 840, Petronij 841,
Murisha 852).

Slot layout being scanned:
  slot[0]      always literal "DefaultMove"
  slot[1..9]   the 9 trailing strings before the corridor (parser keeps the
               identifier-shaped ones as abilities/passives)
  slot[10]     corridor slot 0's string (kept by parser as passives[0])

Output: tools/field_mapper/direction36_results.txt
"""
from __future__ import annotations

import collections
import os
import re
import sqlite3
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import BinaryReader, parse_save  # noqa: E402

DEFAULT_SAVE = ROOT / "test-saves" / "investigation" / "steamcampaign01_20260424_191107.sav"
SAVE = Path(os.environ.get("INVESTIGATION_SAVE", str(DEFAULT_SAVE)))
OUT = Path(__file__).parent / "direction36_results.txt"

FOCUS = {
    "Whommie": 853,
    "Kami": 840,
    "Bud": 887,
    "Alaya": 861,
    "Petronij": 841,
    "Murisha": 852,
    "Flekpus": 68,
    "Lucyfer": 255,
}
DEFECT_POSITIVE = {853, 887}
CLEAN_CONTROLS = {840, 841, 852}

# Slots to dump per cat (the 10 "pre-corridor" strings + corridor slot 0).
SLOT_COUNT = 11
DEFAULT_MOVE_SCAN_BYTES = 700
U32_SIZE = 4
F64_SIZE = 8
BODY_PART_U32_COUNT = 73
EXTRA_BODY_PART_U32_COUNT = 2
STAT_RECORD_COUNT = 3
STAT_COUNT = 7
D100_FIXED_STREAM_SIZE = 14
MAX_STRING_LENGTH = 20_000

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_JUNK_LOWER = {"none", "defaultmove"}

_lines: list[str] = []


def out(message: str = "") -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", "replace").decode())
    _lines.append(message)


def raw_blob(conn: sqlite3.Connection, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    compressed = bytes(row[0])
    uncompressed_size = struct.unpack_from("<I", compressed, 0)[0]
    return lz4.block.decompress(compressed[U32_SIZE:], uncompressed_size=uncompressed_size)


def locate_t_start(raw: bytes, cat) -> int:
    texture_id = cat.body_parts["texture"]
    body_id = cat.body_parts["bodyShape"]
    head_id = cat.body_parts["headShape"]
    texture_bytes = struct.pack("<I", texture_id)
    for offset in range(0, len(raw) - 9 * U32_SIZE):
        if raw[offset:offset + U32_SIZE] != texture_bytes:
            continue
        body_value = struct.unpack_from("<I", raw, offset + 3 * U32_SIZE)[0]
        head_value = struct.unpack_from("<I", raw, offset + 8 * U32_SIZE)[0]
        if body_value == body_id and head_value == head_id:
            return offset
    return -1


def read_str8(raw: bytes, pos: int) -> tuple[str | None, int]:
    """Read a u64-length-prefixed UTF-8 string. Returns (text, new_pos)."""
    if pos + 8 > len(raw):
        return None, pos
    length = struct.unpack_from("<Q", raw, pos)[0]
    if length > MAX_STRING_LENGTH or pos + 8 + int(length) > len(raw):
        return None, pos
    start = pos + 8
    end = start + int(length)
    return raw[start:end].decode("utf-8", errors="replace"), end


def locate_after_d100(raw: bytes, cat) -> int:
    t_start = locate_t_start(raw, cat)
    if t_start < 0:
        raise ValueError("Could not locate T array")
    reader = BinaryReader(raw, t_start)
    reader.skip(BODY_PART_U32_COUNT * U32_SIZE)
    reader.skip(EXTRA_BODY_PART_U32_COUNT * U32_SIZE)
    if reader.str() is None:
        raise ValueError("Could not read gender string")
    reader.skip(F64_SIZE)
    reader.skip(STAT_RECORD_COUNT * STAT_COUNT * U32_SIZE)
    field_788, after_field_788 = read_str8(raw, reader.pos)
    if field_788 is None:
        raise ValueError("Could not read +0x788 string")
    return after_field_788 + D100_FIXED_STREAM_SIZE


def locate_run_start(raw: bytes, cat) -> int:
    after_d100 = locate_after_d100(raw, cat)
    marker = raw.find(b"DefaultMove", after_d100, after_d100 + DEFAULT_MOVE_SCAN_BYTES)
    if marker == -1:
        raise ValueError("DefaultMove marker not found")
    return marker - 8


@dataclass(frozen=True)
class SlotRead:
    text: str | None
    byte_length: int      # value of u64 length prefix
    span: int             # bytes consumed (8 + byte_length) or 0 on read failure
    parser_kept: bool     # would the parser keep this string?
    drop_reason: str      # "kept" / "junk_filler" / "non_identifier" / "empty" / "read_error"


def categorise(text: str | None) -> tuple[bool, str]:
    if text is None:
        return False, "read_error"
    if not text:
        return False, "empty"
    if not _IDENT_RE.match(text):
        return False, "non_identifier"
    if text.strip().lower() in _JUNK_LOWER:
        return False, "junk_filler"
    return True, "kept"


def read_slots(raw: bytes, run_start: int) -> tuple[list[SlotRead], int]:
    pos = run_start
    slots: list[SlotRead] = []
    for _ in range(SLOT_COUNT):
        if pos + 8 > len(raw):
            slots.append(SlotRead(None, -1, 0, False, "read_error"))
            continue
        length = struct.unpack_from("<Q", raw, pos)[0]
        if length > MAX_STRING_LENGTH or pos + 8 + int(length) > len(raw):
            slots.append(SlotRead(None, length, 0, False, "read_error"))
            continue
        text, new_pos = read_str8(raw, pos)
        kept, reason = categorise(text)
        slots.append(SlotRead(text, length, new_pos - pos, kept, reason))
        pos = new_pos
    return slots, pos


def display(text: str | None) -> str:
    if text is None:
        return "<read-error>"
    if text == "":
        return "<empty>"
    return repr(text)


def dump_focus(all_cats, conn: sqlite3.Connection) -> dict[int, list[SlotRead]]:
    out("\n=== Focus Cats: per-slot raw dump ===")
    focus_slots: dict[int, list[SlotRead]] = {}
    for name, db_key in FOCUS.items():
        cat = next((candidate for candidate in all_cats if candidate.db_key == db_key), None)
        if cat is None:
            out(f"\n{name} (db_key={db_key}): not found")
            continue
        try:
            raw = raw_blob(conn, cat.db_key)
            run_start = locate_run_start(raw, cat)
            slots, end_pos = read_slots(raw, run_start)
        except Exception as exc:
            out(f"\n{name} (db_key={db_key}): scan error: {exc}")
            continue
        focus_slots[db_key] = slots
        marker_tag = ""
        if db_key in DEFECT_POSITIVE:
            marker_tag = "  [DEFECT-POSITIVE]"
        elif db_key in CLEAN_CONTROLS:
            marker_tag = "  [CLEAN-CONTROL]"
        out(f"\n{name} (db_key={db_key}) run_start=blob+0x{run_start:04x}{marker_tag}")
        for index, slot in enumerate(slots):
            out(
                f"  slot[{index:2d}] len={slot.byte_length:>5} span={slot.span:>4} "
                f"reason={slot.drop_reason:<14} text={display(slot.text)}"
            )
        out(f"  end_pos=blob+0x{end_pos:04x}")
    return focus_slots


def roster_scan(all_cats, conn: sqlite3.Connection) -> None:
    out("\n=== Roster Scan ===")
    per_slot_token_counts: list[collections.Counter] = [
        collections.Counter() for _ in range(SLOT_COUNT)
    ]
    per_slot_drop_counts: list[collections.Counter] = [
        collections.Counter() for _ in range(SLOT_COUNT)
    ]
    defect_tokens_per_slot: list[set[str]] = [set() for _ in range(SLOT_COUNT)]
    control_tokens_per_slot: list[set[str]] = [set() for _ in range(SLOT_COUNT)]
    other_tokens_per_slot: list[set[str]] = [set() for _ in range(SLOT_COUNT)]
    suspicious_tokens: list[tuple[str, int, int, str, str]] = []
    parse_failures: list[tuple[str, int, str]] = []
    suspicious_pattern = re.compile(r"blind|defect|missing|birth|no_|deaf|mute|crippl|broken|disabled", re.IGNORECASE)

    for cat in all_cats:
        try:
            raw = raw_blob(conn, cat.db_key)
            run_start = locate_run_start(raw, cat)
            slots, _end_pos = read_slots(raw, run_start)
        except Exception as exc:
            parse_failures.append((cat.name, cat.db_key, str(exc)))
            continue
        for slot_index, slot in enumerate(slots):
            token_text = slot.text if slot.text is not None else "<read-error>"
            per_slot_token_counts[slot_index][token_text] += 1
            per_slot_drop_counts[slot_index][slot.drop_reason] += 1
            if cat.db_key in DEFECT_POSITIVE:
                defect_tokens_per_slot[slot_index].add(token_text)
            elif cat.db_key in CLEAN_CONTROLS:
                control_tokens_per_slot[slot_index].add(token_text)
            else:
                other_tokens_per_slot[slot_index].add(token_text)
            if slot.text and suspicious_pattern.search(slot.text):
                suspicious_tokens.append(
                    (cat.name, cat.db_key, slot_index, slot.drop_reason, slot.text)
                )

    out(f"  parsed cats: {len(all_cats) - len(parse_failures)} / {len(all_cats)}")
    out(f"  parse failures: {len(parse_failures)}")
    for name, db_key, error in parse_failures[:20]:
        out(f"    failure {name} key={db_key}: {error}")

    out("\n  Drop-reason distribution per slot (entries that the parser would silently discard):")
    out("  slot |  read_error  empty  non_identifier  junk_filler  kept  | unique-tokens")
    for slot_index in range(SLOT_COUNT):
        drops = per_slot_drop_counts[slot_index]
        unique_tokens = len(per_slot_token_counts[slot_index])
        out(
            f"    {slot_index:2d}   |  "
            f"{drops.get('read_error', 0):>10}  "
            f"{drops.get('empty', 0):>5}  "
            f"{drops.get('non_identifier', 0):>14}  "
            f"{drops.get('junk_filler', 0):>11}  "
            f"{drops.get('kept', 0):>4}  | {unique_tokens}"
        )

    out("\n  Top tokens per slot (top 10 each):")
    for slot_index in range(SLOT_COUNT):
        out(f"  -- slot[{slot_index}] --")
        for token, count in per_slot_token_counts[slot_index].most_common(10):
            out(f"     {count:>4}  {token!r}")

    out("\n  Defect-only tokens (in defect-positive but never in clean controls):")
    found_any_defect_only = False
    for slot_index in range(SLOT_COUNT):
        diff = defect_tokens_per_slot[slot_index] - control_tokens_per_slot[slot_index]
        if diff:
            found_any_defect_only = True
            out(f"    slot[{slot_index}]: {sorted(diff)}")
    if not found_any_defect_only:
        out("    (none — defect-positive cats share all tokens with clean controls)")

    out("\n  Defect-only tokens vs ENTIRE roster (defect-positive minus all other cats):")
    found_unique_to_defect = False
    for slot_index in range(SLOT_COUNT):
        full_other = control_tokens_per_slot[slot_index] | other_tokens_per_slot[slot_index]
        diff = defect_tokens_per_slot[slot_index] - full_other
        if diff:
            found_unique_to_defect = True
            out(f"    slot[{slot_index}]: {sorted(diff)}")
    if not found_unique_to_defect:
        out("    (none — defect-positive cats share all tokens with the rest of the roster)")

    out("\n  Suspicious tokens roster-wide (regex: blind|defect|missing|birth|no_|deaf|mute|crippl|broken|disabled):")
    if suspicious_tokens:
        for cat_name, db_key, slot_index, reason, text in suspicious_tokens[:60]:
            out(f"    {cat_name} (key={db_key}) slot[{slot_index}] reason={reason} text={text!r}")
        if len(suspicious_tokens) > 60:
            out(f"    ... and {len(suspicious_tokens) - 60} more")
    else:
        out("    (none)")


def compare_focus(focus_slots: dict[int, list[SlotRead]]) -> None:
    out("\n=== Focus comparison: defect-positive vs clean controls ===")
    if not focus_slots:
        out("  (no focus slots collected)")
        return
    for slot_index in range(SLOT_COUNT):
        defect_values: list[tuple[str, str | None]] = []
        control_values: list[tuple[str, str | None]] = []
        for name, db_key in FOCUS.items():
            slots = focus_slots.get(db_key)
            if slots is None or slot_index >= len(slots):
                continue
            entry = (name, slots[slot_index].text)
            if db_key in DEFECT_POSITIVE:
                defect_values.append(entry)
            elif db_key in CLEAN_CONTROLS:
                control_values.append(entry)
        defect_texts = {text for _, text in defect_values}
        control_texts = {text for _, text in control_values}
        if defect_texts == control_texts:
            continue
        out(f"  slot[{slot_index}]:")
        out(f"    defect-positive: {defect_values}")
        out(f"    clean controls:  {control_values}")


def main() -> None:
    out("Direction 36 - Roster-scan 10 pre-corridor strings + corridor slot 0")
    out(f"Save: {SAVE}")

    save_data = parse_save(str(SAVE))
    all_cats = save_data[0]
    out(f"Total cats parsed: {len(all_cats)}")

    conn = sqlite3.connect(str(SAVE))
    try:
        focus_slots = dump_focus(all_cats, conn)
        compare_focus(focus_slots)
        roster_scan(all_cats, conn)
    finally:
        conn.close()

    OUT.write_text("\n".join(_lines), encoding="utf-8")
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
