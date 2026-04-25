"""
Direction 31 - Map the ability tail through equipment and class string.

Direction 30 mapped the post-stat gap up to the DefaultMove run. This script
continues from DefaultMove through:

  ability/passive string run
  passive tier u32
  three tail string + u32 slots
  five equipment-ish u8/u32 slots
  class string ending 115 bytes before blob end

The goal is to check whether an unmapped hidden missing-part flag remains in
the ability/equipment/class corridor.
"""
from __future__ import annotations

import collections
import struct
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import BinaryReader, parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "investigation" / "steamcampaign01_20260424_191107.sav"
OUT = Path(__file__).parent / "direction31_results.txt"

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

BODY_PART_U32_COUNT = 73
EXTRA_BODY_PART_U32_COUNT = 2
U32_SIZE = 4
F64_SIZE = 8
STAT_RECORD_COUNT = 3
STAT_COUNT = 7
D100_FIXED_STREAM_SIZE = 14
CLASS_STRING_TAIL_OFFSET = 115
DEFAULT_MOVE_SCAN_BYTES = 700
ABILITY_RUN_LIMIT = 32
TAIL_SLOT_COUNT = 3
EQUIPMENT_SLOT_COUNT = 5
EMPTY_EQUIPMENT_SLOT_SIZE = 5
MAX_STRING_LENGTH = 20_000

_lines: list[str] = []


@dataclass(frozen=True)
class TailMap:
    run_start: int
    run_items: tuple[str, ...]
    passive_tier: int
    tail_slots: tuple[tuple[str, int], ...]
    equipment_start: int
    class_prefix_start: int
    class_name: str
    equipment_slots: tuple[tuple[int, int], ...]
    equipment_is_empty_slot_format: bool
    parsed_end: int
    raw_equipment_hex: str


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
    if pos + 8 > len(raw):
        return None, pos
    length = struct.unpack_from("<Q", raw, pos)[0]
    if length > MAX_STRING_LENGTH or pos + 8 + length > len(raw):
        return None, pos
    start = pos + 8
    end = start + int(length)
    return raw[start:end].decode("utf-8", errors="replace"), end


def is_identifier(token: str | None) -> bool:
    return bool(token) and (token[0].isalpha() or token[0] == "_") and all(
        char.isalnum() or char == "_"
        for char in token
    )


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


def locate_default_move_run(raw: bytes, start: int) -> int:
    marker = raw.find(b"DefaultMove", start, start + DEFAULT_MOVE_SCAN_BYTES)
    if marker == -1:
        raise ValueError("DefaultMove not found")
    return marker - 8


def locate_class_prefix(raw: bytes, min_start: int) -> tuple[int, str]:
    scan_end = max(min_start, len(raw) - CLASS_STRING_TAIL_OFFSET + 40)
    candidates = []
    for prefix_pos in range(min_start, min(scan_end, len(raw) - 11)):
        length = struct.unpack_from("<I", raw, prefix_pos)[0]
        zero = struct.unpack_from("<I", raw, prefix_pos + 4)[0]
        if zero != 0 or not (3 <= length <= 30):
            continue
        string_start = prefix_pos + 8
        string_end = string_start + length
        if string_end > len(raw):
            continue
        class_name = raw[string_start:string_end].decode("utf-8", errors="replace")
        if is_identifier(class_name) and class_name != "None":
            candidates.append((prefix_pos, class_name))
    if candidates:
        return candidates[-1]
    raise ValueError("Class string not found")


def parse_tail(raw: bytes, cat) -> TailMap:
    after_d100 = locate_after_d100(raw, cat)
    run_start = locate_default_move_run(raw, after_d100)
    reader = BinaryReader(raw, run_start)

    run_items = []
    for _ in range(ABILITY_RUN_LIMIT):
        saved = reader.pos
        item = reader.str()
        if not is_identifier(item):
            reader.seek(saved)
            break
        run_items.append(item)

    passive_tier = reader.u32()
    tail_slots = []
    for _ in range(TAIL_SLOT_COUNT):
        item = reader.str()
        slot_tier = reader.u32()
        tail_slots.append((item or "", slot_tier))

    equipment_start = reader.pos
    class_prefix_start, class_name = locate_class_prefix(raw, equipment_start)
    if class_prefix_start < equipment_start:
        raise ValueError("Class string starts before equipment section")
    equipment_raw = raw[equipment_start:class_prefix_start]
    equipment_slots = []
    equipment_is_empty_slot_format = len(equipment_raw) % EMPTY_EQUIPMENT_SLOT_SIZE == 0
    if equipment_is_empty_slot_format:
        for slot_index in range(0, len(equipment_raw), EMPTY_EQUIPMENT_SLOT_SIZE):
            slot_start = equipment_start + slot_index
            slot_flag = raw[slot_start]
            slot_value = struct.unpack_from("<I", raw, slot_start + 1)[0]
            equipment_slots.append((slot_flag, slot_value))

    return TailMap(
        run_start=run_start,
        run_items=tuple(run_items),
        passive_tier=passive_tier,
        tail_slots=tuple(tail_slots),
        equipment_start=equipment_start,
        class_prefix_start=class_prefix_start,
        class_name=class_name,
        equipment_slots=tuple(equipment_slots),
        equipment_is_empty_slot_format=equipment_is_empty_slot_format,
        parsed_end=class_prefix_start + 8 + len(class_name),
        raw_equipment_hex=equipment_raw.hex(" "),
    )


def analyze_focus(all_cats, conn: sqlite3.Connection) -> None:
    out("\n=== Focus Cats ===")
    for name, db_key in FOCUS.items():
        cat = next((candidate for candidate in all_cats if candidate.db_key == db_key), None)
        if cat is None:
            out(f"\n{name} (db_key={db_key}): not found")
            continue
        tail = parse_tail(raw_blob(conn, cat.db_key), cat)
        out(f"\n{name} (db_key={cat.db_key})")
        out(f"  run_start: blob+0x{tail.run_start:04x}; run item count={len(tail.run_items)}")
        out(f"  run items: {list(tail.run_items)}")
        out(f"  passive tier: {tail.passive_tier}")
        out(f"  tail slots: {list(tail.tail_slots)}")
        out(
            f"  equipment: blob+0x{tail.equipment_start:04x}..0x{tail.class_prefix_start:04x} "
            f"({tail.class_prefix_start - tail.equipment_start} bytes)"
        )
        out(f"  equipment slots: {list(tail.equipment_slots)}")
        out(f"  empty-slot format: {tail.equipment_is_empty_slot_format}")
        out(f"  class: {tail.class_name!r}; parsed_end before fixed tail: blob+0x{tail.parsed_end:04x}")
        out(f"  raw equipment: {tail.raw_equipment_hex}")


def roster_scan(all_cats, conn: sqlite3.Connection) -> None:
    out("\n=== Roster Scan ===")
    run_lengths = collections.Counter()
    class_names = collections.Counter()
    equipment_patterns = collections.Counter()
    equipment_sizes = collections.Counter()
    tail_patterns = collections.Counter()
    parse_failures = []

    for cat in all_cats:
        try:
            tail = parse_tail(raw_blob(conn, cat.db_key), cat)
        except Exception as exc:
            parse_failures.append((cat.name, cat.db_key, str(exc)))
            continue
        run_lengths[len(tail.run_items)] += 1
        class_names[tail.class_name] += 1
        equipment_sizes[tail.class_prefix_start - tail.equipment_start] += 1
        equipment_patterns[tail.equipment_slots] += 1
        tail_patterns[tail.tail_slots] += 1

    out(f"  parsed cats: {len(all_cats) - len(parse_failures)} / {len(all_cats)}")
    out(f"  parse failures: {len(parse_failures)}")
    for name, db_key, error in parse_failures[:12]:
        out(f"    failure {name} key={db_key}: {error}")

    out("  ability run length distribution:")
    for run_length, count in run_lengths.most_common():
        out(f"    {run_length}: {count}")

    out("  class distribution:")
    for class_name, count in class_names.most_common(12):
        out(f"    {class_name!r}: {count}")

    out("  equipment pattern distribution:")
    for equipment_slots, count in equipment_patterns.most_common(8):
        out(f"    {list(equipment_slots)}: {count}")

    out("  equipment byte-size distribution:")
    for equipment_size, count in equipment_sizes.most_common(12):
        out(f"    {equipment_size}: {count}")

    out("  tail slot pattern distribution:")
    for tail_slots, count in tail_patterns.most_common(8):
        out(f"    {list(tail_slots)}: {count}")


def main() -> None:
    out("Direction 31 - Map ability tail through equipment and class string")
    out(f"Save: {SAVE}")

    save_data = parse_save(str(SAVE))
    all_cats = save_data[0]
    conn = sqlite3.connect(str(SAVE))
    try:
        analyze_focus(all_cats, conn)
        roster_scan(all_cats, conn)
    finally:
        conn.close()

    OUT.write_text("\n".join(_lines), encoding="utf-8")
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
