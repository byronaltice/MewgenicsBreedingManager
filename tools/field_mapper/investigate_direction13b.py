"""Direction #13 -- Re-audit remaining pedigree and post-run blob leads.

This script captures three follow-up checks after Directions 8-12:

1. Verify the pedigree blob is fully consumed by the three known hash tables.
2. Dump and classify the unread bytes between the parsed ability run and the
   class-string prefix near the blob tail.
3. Re-check the pre-T block using same-type controls (eye=139, brow=23,
   ear=132) to see whether Whommie/Bud share a distinctive seed pattern.
"""
from __future__ import annotations

import collections
import math
import re
import sqlite3
import struct
import sys
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import (  # noqa: E402
    BinaryReader,
    _CLASS_STRING_TAIL_OFFSET,
    _read_parallel_hash_table,
    parse_save,
)

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction13_results.txt"

TARGET_NAMES = ("Whommie", "Bud", "Kami", "Petronij", "Romanoba", "Murisha")
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
JUNK_STRINGS = frozenset({"none", "null", "", "defaultmove", "default_move"})
T_ARRAY_LEN = 72
PRE_T_FLOAT_COUNT = 8
STAT_COUNT = 7
MAX_CLASS_NAME_LEN = 30
TARGET_GAP_EXAMPLE_HEX_LEN = 128
TOP_GAP_PATTERNS = 8

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def _valid_str(value: str | None) -> bool:
    return bool(value) and value.strip().lower() not in JUNK_STRINGS


def raw_blob(conn: sqlite3.Connection, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    data = bytes(row[0])
    uncomp = struct.unpack_from("<I", data, 0)[0]
    return lz4.block.decompress(data[4:], uncompressed_size=uncomp)


def locate_t_start(raw: bytes, cat) -> int:
    fur = cat.body_parts["texture"]
    body = cat.body_parts["bodyShape"]
    head = cat.body_parts["headShape"]
    target = struct.pack("<I", fur)
    for offset in range(0, len(raw) - 9 * 4):
        if raw[offset:offset + 4] != target:
            continue
        if struct.unpack_from("<I", raw, offset + 3 * 4)[0] != body:
            continue
        if struct.unpack_from("<I", raw, offset + 8 * 4)[0] != head:
            continue
        return offset
    return -1


def replay_to_after_run(raw: bytes) -> tuple[int, int, int, int, str]:
    """Return curr, run_start, after_run, class_prefix, class_name."""
    reader = BinaryReader(raw)

    reader.u32()
    reader.u64()
    reader.utf16str()
    reader.str()
    reader.u64()
    reader.u64()
    reader.str()
    reader.u32()
    reader.skip(64)
    for _ in range(T_ARRAY_LEN):
        reader.u32()

    for _ in range(3):
        reader.u32()
    reader.str()
    reader.f64()
    for _ in range(STAT_COUNT):
        reader.u32()
    for _ in range(STAT_COUNT):
        reader.i32()
    for _ in range(STAT_COUNT):
        reader.i32()

    curr = reader.pos
    marker = reader.find("DefaultMove", start=curr, end=min(curr + 600, len(raw)))
    run_start = marker - 8
    reader.seek(run_start)

    for _ in range(32):
        saved = reader.pos
        item = reader.str()
        if item is None or not IDENT_RE.match(item):
            reader.seek(saved)
            break

    try:
        reader.u32()
    except Exception:
        pass

    for _ in range(3):
        try:
            reader.str()
        except Exception:
            break
        try:
            reader.u32()
        except Exception:
            break

    after_run = reader.pos

    class_end = len(raw) - _CLASS_STRING_TAIL_OFFSET
    class_prefix = -1
    class_name = ""
    for class_len in range(3, MAX_CLASS_NAME_LEN):
        prefix = class_end - class_len - 8
        if prefix < 0:
            break
        length = struct.unpack_from("<I", raw, prefix)[0]
        zero = struct.unpack_from("<I", raw, prefix + 4)[0]
        if length == class_len and zero == 0:
            class_prefix = prefix
            class_name = raw[prefix + 8:prefix + 8 + class_len].decode("utf-8", errors="replace")
            break

    return curr, run_start, after_run, class_prefix, class_name


def pre_t_pattern(raw: bytes, t_start: int) -> tuple[str, ...]:
    patterns: list[str] = []
    base = t_start - PRE_T_FLOAT_COUNT * 8
    for index in range(PRE_T_FLOAT_COUNT):
        value = struct.unpack_from("<d", raw, base + index * 8)[0]
        if math.isnan(value):
            patterns.append("NaN")
        elif value == 0.0:
            patterns.append("zero")
        elif abs(value - 0.5) < 1e-12:
            patterns.append("0.5")
        elif abs(value - 0.25) < 1e-12:
            patterns.append("0.25")
        elif 0 < abs(value) < 1e-300:
            patterns.append("subnormal")
        else:
            patterns.append("other")
    return tuple(patterns)


def main() -> None:
    out("=" * 70)
    out("Direction #13 -- Remaining pedigree and post-run blob leads")
    out("=" * 70)

    save_data = parse_save(str(SAVE))
    cat_map = {cat.name: cat for cat in save_data.cats}
    conn = sqlite3.connect(str(SAVE))

    out("=" * 70)
    out("STEP 1 -- Verify pedigree blob boundaries")
    out("=" * 70)
    pedigree_data = bytes(conn.execute("SELECT data FROM files WHERE key='pedigree'").fetchone()[0])
    rows1, offset1 = _read_parallel_hash_table(pedigree_data, 0, "<qqqd", 32)
    rows2, offset2 = _read_parallel_hash_table(pedigree_data, offset1, "<qqd", 24)
    rows3, offset3 = _read_parallel_hash_table(pedigree_data, offset2, "<q", 8)
    out(f"Pedigree blob size: {len(pedigree_data)} bytes")
    out(f"Table 1 child->parents rows: {len(rows1)}  next_offset={offset1}")
    out(f"Table 2 COI memo rows:       {len(rows2)}  next_offset={offset2}")
    out(f"Table 3 accessible rows:     {len(rows3)}  next_offset={offset3}")
    out(f"Leftover bytes after table 3: {len(pedigree_data) - offset3}")
    if offset3 == len(pedigree_data):
        out("Result: pedigree is fully consumed by the 3 known hash tables; there is no hidden tail section.")
    else:
        out("Result: unexpected leftover bytes remain after the 3 known hash tables.")
    out()

    out("=" * 70)
    out("STEP 2 -- Dump unread bytes between ability parse and class prefix")
    out("=" * 70)
    gap_counter: collections.Counter[tuple[int, str]] = collections.Counter()
    gap_examples: dict[tuple[int, str], str] = {}

    for cat in save_data.cats:
        raw = raw_blob(conn, cat.db_key)
        _, _, after_run, class_prefix, _ = replay_to_after_run(raw)
        if class_prefix < after_run:
            continue
        gap = raw[after_run:class_prefix]
        key = (len(gap), gap.hex())
        gap_counter[key] += 1
        gap_examples.setdefault(key, cat.name)

    for name in TARGET_NAMES:
        cat = cat_map[name]
        raw = raw_blob(conn, cat.db_key)
        curr, run_start, after_run, class_prefix, class_name = replay_to_after_run(raw)
        gap = raw[after_run:class_prefix]
        out(f"{name}: len(raw)={len(raw)} curr=0x{curr:x} run_start=0x{run_start:x} after_run=0x{after_run:x}")
        out(f"  class_prefix=0x{class_prefix:x} class={class_name!r} gap_len={len(gap)}")
        out(f"  gap_hex={gap.hex()[:TARGET_GAP_EXAMPLE_HEX_LEN]}")
    out()

    out("Top roster-wide post-run gap patterns:")
    for (gap_len, gap_hex), count in gap_counter.most_common(TOP_GAP_PATTERNS):
        out(f"  count={count:3d} gap_len={gap_len:3d} example={gap_examples[(gap_len, gap_hex)]} hex={gap_hex}")
    out()

    out("=" * 70)
    out("STEP 3 -- Same-type control check for pre-T patterns")
    out("=" * 70)

    control_specs = [
        ("Eye Birth Defect", "Whommie", "eye_L", 139),
        ("Eyebrow Birth Defect", "Whommie", "eyebrow_L", 23),
        ("Ear Birth Defect", "Bud", "ear_L", 132),
    ]
    for defect_name, target_name, slot_key, slot_value in control_specs:
        target_cat = cat_map[target_name]
        target_raw = raw_blob(conn, target_cat.db_key)
        target_t_start = locate_t_start(target_raw, target_cat)
        target_pattern = pre_t_pattern(target_raw, target_t_start)

        matched_controls = [
            cat for cat in save_data.cats
            if cat.visual_mutation_slots.get(slot_key) == slot_value and defect_name not in cat.defects
        ]
        pattern_counter: collections.Counter[tuple[str, ...]] = collections.Counter()
        for control in matched_controls:
            control_raw = raw_blob(conn, control.db_key)
            control_t_start = locate_t_start(control_raw, control)
            pattern_counter[pre_t_pattern(control_raw, control_t_start)] += 1

        out(f"{defect_name}: target={target_name} slot={slot_key} value={slot_value}")
        out(f"  matched clean controls: {len(matched_controls)}")
        out(f"  target pre-T pattern: {target_pattern}")
        out(f"  clean controls with same pattern: {pattern_counter[target_pattern]}")
        out(f"  top clean patterns: {pattern_counter.most_common(5)}")
        out()

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
