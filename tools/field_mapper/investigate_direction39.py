"""
Direction 39 - Extract three post-class-string fields for all 947 cats.

Fields to extract (all gated by save version 0x13, which is active):
  A. Byte-vector at CatData+0x8: serialized as u64 count + count*u8.
     Written by FUN_1402345e0(param_2, param_1+8) after the 5th equipment slot
     class string, the +0xc30 u32, +0xc50 u64, +0xc38 u64, +0xc40 u64.
  B. Three u8 bytes at CatData+0xc08/+0xc09/+0xc0a (gate v>0xf).
  C. 16-element u32 array at CatData+0x744..+0x780 (gate v>0x11).

Serializer write order after the class string (+0xc10):
  1. +0xc30  u32           (4 bytes)
  2. +0xc50  u64/f64       (8 bytes)
  3. +0xc38  u64/f64       (8 bytes, gate v>7 — active)
  4. +0xc40  u64/f64       (8 bytes, gate v>8 — active)
  5. FUN_1402345e0  u64 count + count bytes  (gate v>0xd — active) <- FIELD A
  6. +0xc34  u32           (4 bytes, gate v>0xe — active)
  7. +0xc00  u64/f64       (8 bytes, gate v>0xf — active)
  8. +0xc08  u8            (1 byte,  gate v>0xf — active)  <- FIELD B[0]
  9. +0xc09  u8            (1 byte,  gate v>0xf — active)  <- FIELD B[1]
  10. +0xc0a  u8           (1 byte,  gate v>0xf — active)  <- FIELD B[2]
  11. 16*u32 (+0x744..+0x780)  (64 bytes, gate v>0x11 — active)  <- FIELD C

Anchor: class string end (= class_prefix_start + 8 + len(class_name.encode())). Then read
in serializer order above.

Output: tools/field_mapper/direction39_results.txt
"""
from __future__ import annotations

import collections
import os
import sqlite3
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import BinaryReader, parse_save  # noqa: E402

DEFAULT_SAVE = ROOT / "test-saves" / "investigation" / "steamcampaign01_20260424_191107.sav"
SAVE = Path(os.environ.get("INVESTIGATION_SAVE", str(DEFAULT_SAVE)))
OUT = Path(__file__).parent / "direction39_results.txt"

FOCUS = {
    "Whommie": 853,
    "Kami": 840,
    "Bud": 887,
    "Petronij": 841,
    "Murisha": 852,
}
DEFECT_POSITIVE = {853, 887}
CLEAN_CONTROLS = {840, 841, 852}

# ---- blob-walking constants ----
U32_SIZE = 4
F64_SIZE = 8
BODY_PART_U32_COUNT = 73
EXTRA_BODY_PART_U32_COUNT = 2
STAT_RECORD_COUNT = 3
STAT_COUNT = 7
D100_FIXED_STREAM_SIZE = 14
CLASS_STRING_TAIL_OFFSET = 115
DEFAULT_MOVE_SCAN_BYTES = 700
ABILITY_RUN_LIMIT = 32
TAIL_SLOT_COUNT = 3
EQUIPMENT_SLOT_COUNT = 5
MAX_STRING_LENGTH = 20_000

# Post-class-string layout sizes
POST_CLASS_U32_C30 = 4       # +0xc30
POST_CLASS_F64_C50 = 8       # +0xc50
POST_CLASS_F64_C38 = 8       # +0xc38 (gate v>7)
POST_CLASS_F64_C40 = 8       # +0xc40 (gate v>8)
# FUN_1402345e0: u64 count + count bytes  (gate v>0xd)
POST_CLASS_U32_C34 = 4       # +0xc34 (gate v>0xe)
POST_CLASS_F64_C00 = 8       # +0xc00 (gate v>0xf)
U32_ARRAY_COUNT = 16         # +0x744..+0x780 (gate v>0x11)

BYTEVEC_FIRST_N = 16         # How many bytevec bytes to show in hex

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


def read_str8(raw: bytes, pos: int) -> tuple[Optional[str], int]:
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


def is_identifier(token: Optional[str]) -> bool:
    return bool(token) and (token[0].isalpha() or token[0] == "_") and all(
        char.isalnum() or char == "_"
        for char in token
    )


def locate_class_string_end(raw: bytes, cat) -> tuple[int, str]:
    """Walk to the class string and return (class_string_end_pos, class_name)."""
    after_d100 = locate_after_d100(raw, cat)

    marker = raw.find(b"DefaultMove", after_d100, after_d100 + DEFAULT_MOVE_SCAN_BYTES)
    if marker == -1:
        raise ValueError("DefaultMove marker not found")
    run_start = marker - 8

    reader = BinaryReader(raw, run_start)

    # Read ability run items
    for _ in range(ABILITY_RUN_LIMIT):
        saved = reader.pos
        item = reader.str()
        if not is_identifier(item):
            reader.seek(saved)
            break

    # passive tier u32
    reader.u32()

    # three tail (string, u32) slots
    for _ in range(TAIL_SLOT_COUNT):
        reader.str()
        reader.u32()

    equipment_start = reader.pos

    # Find class string by scanning forward from equipment_start
    # Class string format: u32 length + u32 zero + utf-8 bytes
    scan_end = max(equipment_start, len(raw) - CLASS_STRING_TAIL_OFFSET + 40)
    candidates = []
    for prefix_pos in range(equipment_start, min(scan_end, len(raw) - 11)):
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

    if not candidates:
        raise ValueError("Class string not found")

    class_prefix_start, class_name = candidates[-1]
    # class string end = prefix_pos + 4 (u32 length) + 4 (u32 zero) + len(class_name)
    class_end = class_prefix_start + 8 + len(class_name.encode("utf-8"))
    return class_end, class_name


@dataclass
class Direction39Result:
    db_key: int
    name: str
    class_name: str
    class_end_pos: int
    bytevec_size: int
    bytevec_first_bytes: bytes
    u8_a: int
    u8_b: int
    u8_c: int
    u32_array: tuple[int, ...]
    post_class_raw_hex: str  # first 128 bytes after class string for debugging


def extract_fields(raw: bytes, cat, name: str) -> Direction39Result:
    class_end, class_name = locate_class_string_end(raw, cat)

    pos = class_end
    blob_remaining = len(raw) - pos

    # Validate we have enough bytes for the minimum tail structure:
    # u32(4) + f64(8) + f64(8) + f64(8) + u64_count(8) = 36 bytes minimum before bytevec
    min_needed = 36
    if blob_remaining < min_needed:
        raise ValueError(
            f"Only {blob_remaining} bytes remain after class string "
            f"(need at least {min_needed}). Blob may be misaligned."
        )

    # Capture first 128 raw bytes after class string for debugging
    post_class_raw = raw[pos:pos + 128]

    # 1. +0xc30 u32
    if pos + U32_SIZE > len(raw):
        raise ValueError(f"Out of bounds reading u32 at blob+0x{pos:04x}")
    _u32_c30 = struct.unpack_from("<I", raw, pos)[0]
    pos += U32_SIZE

    # 2. +0xc50 u64/f64 (8 bytes)
    if pos + F64_SIZE > len(raw):
        raise ValueError(f"Out of bounds reading f64 at blob+0x{pos:04x}")
    pos += F64_SIZE

    # 3. +0xc38 u64/f64 (8 bytes, gate v>7 — active)
    if pos + F64_SIZE > len(raw):
        raise ValueError(f"Out of bounds reading f64(c38) at blob+0x{pos:04x}")
    pos += F64_SIZE

    # 4. +0xc40 u64/f64 (8 bytes, gate v>8 — active)
    if pos + F64_SIZE > len(raw):
        raise ValueError(f"Out of bounds reading f64(c40) at blob+0x{pos:04x}")
    pos += F64_SIZE

    # 5. FUN_1402345e0: u64 count + count bytes (gate v>0xd — active)
    if pos + 8 > len(raw):
        raise ValueError(f"Out of bounds reading bytevec u64 at blob+0x{pos:04x}")
    bytevec_size = struct.unpack_from("<Q", raw, pos)[0]
    pos += 8
    if bytevec_size > 1_000_000:
        raise ValueError(
            f"bytevec_size {bytevec_size} is implausible at blob+0x{pos - 8:04x}; "
            f"raw bytes at that offset: {raw[pos-8:pos+16].hex(' ')}"
        )
    bytevec_first_bytes = raw[pos:pos + BYTEVEC_FIRST_N]
    pos += int(bytevec_size)

    # 6. +0xc34 u32 (gate v>0xe — active)
    if pos + U32_SIZE > len(raw):
        raise ValueError(f"Out of bounds reading u32(c34) at blob+0x{pos:04x}")
    _u32_c34 = struct.unpack_from("<I", raw, pos)[0]
    pos += U32_SIZE

    # 7. +0xc00 u64/f64 (8 bytes, gate v>0xf — active)
    if pos + F64_SIZE > len(raw):
        raise ValueError(f"Out of bounds reading f64(c00) at blob+0x{pos:04x}")
    pos += F64_SIZE

    # 8-10. +0xc08, +0xc09, +0xc0a u8 (gate v>0xf — active)
    if pos + 3 > len(raw):
        raise ValueError(f"Out of bounds reading u8 bytes at blob+0x{pos:04x}")
    u8_a = raw[pos]
    u8_b = raw[pos + 1]
    u8_c = raw[pos + 2]
    pos += 3

    # 11. 16 x u32 (+0x744..+0x780, gate v>0x11 — active)
    u32_array_bytes = U32_ARRAY_COUNT * U32_SIZE
    if pos + u32_array_bytes > len(raw):
        raise ValueError(
            f"Out of bounds reading 16-u32 array at blob+0x{pos:04x} "
            f"(need {u32_array_bytes} bytes, have {len(raw) - pos})"
        )
    u32_array = struct.unpack_from(f"<{U32_ARRAY_COUNT}I", raw, pos)
    pos += u32_array_bytes

    # Sanity: we should now be at or very near the end of the blob
    remaining = len(raw) - pos
    if remaining > 20:
        raise ValueError(
            f"Unexpected {remaining} bytes remaining after 16-u32 array "
            f"(expected <=20). Offset sync may be wrong. "
            f"Next 20 bytes: {raw[pos:pos+20].hex(' ')}"
        )

    return Direction39Result(
        db_key=cat.db_key,
        name=name,
        class_name=class_name,
        class_end_pos=class_end,
        bytevec_size=int(bytevec_size),
        bytevec_first_bytes=bytevec_first_bytes,
        u8_a=u8_a,
        u8_b=u8_b,
        u8_c=u8_c,
        u32_array=tuple(u32_array),
        post_class_raw_hex=post_class_raw.hex(" "),
    )


def format_u32_array(arr: tuple[int, ...]) -> str:
    return " ".join(f"{v:08x}" for v in arr)


def dump_focus(all_cats, conn: sqlite3.Connection) -> dict[int, Direction39Result]:
    out("\n=== Focus Cats ===")
    results: dict[int, Direction39Result] = {}
    for label, db_key in FOCUS.items():
        cat = next((c for c in all_cats if c.db_key == db_key), None)
        if cat is None:
            out(f"\n{label} (db_key={db_key}): not found in parsed cats")
            continue
        raw = raw_blob(conn, db_key)
        marker = "[DEFECT+]" if db_key in DEFECT_POSITIVE else "[CONTROL]"
        try:
            result = extract_fields(raw, cat, label)
        except ValueError as exc:
            out(f"\n{label} (db_key={db_key}) {marker}: EXTRACTION FAILED — {exc}")
            out(f"  blob length: {len(raw)} bytes")
            continue
        results[db_key] = result

        first_hex = result.bytevec_first_bytes.hex(" ") if result.bytevec_first_bytes else "(empty)"
        out(f"\n{label} (db_key={db_key}) {marker}")
        out(f"  class_name: {result.class_name!r}  class_end: blob+0x{result.class_end_pos:04x}")
        out(f"  A. bytevec_size: {result.bytevec_size}  first_bytes: {first_hex}")
        out(f"  B. u8[a,b,c]: 0x{result.u8_a:02x}, 0x{result.u8_b:02x}, 0x{result.u8_c:02x}  ({result.u8_a}, {result.u8_b}, {result.u8_c})")
        out(f"  C. u32_array[16]: {format_u32_array(result.u32_array)}")
        out(f"  post-class raw (first 128 bytes): {result.post_class_raw_hex}")
    return results


def compare_focus(results: dict[int, Direction39Result]) -> None:
    out("\n=== Focus Comparison: defect-positive vs clean controls ===")
    defect_results = {k: v for k, v in results.items() if k in DEFECT_POSITIVE}
    control_results = {k: v for k, v in results.items() if k in CLEAN_CONTROLS}

    # Field A: bytevec size
    defect_sizes = {k: v.bytevec_size for k, v in defect_results.items()}
    control_sizes = {k: v.bytevec_size for k, v in control_results.items()}
    out(f"  A bytevec_size — defect: {defect_sizes}  controls: {control_sizes}")

    # Field B: u8 bytes
    defect_b = {k: (v.u8_a, v.u8_b, v.u8_c) for k, v in defect_results.items()}
    control_b = {k: (v.u8_a, v.u8_b, v.u8_c) for k, v in control_results.items()}
    out(f"  B u8[a,b,c]  — defect: {defect_b}  controls: {control_b}")

    # Field C: u32 array
    for k, v in defect_results.items():
        label = next((n for n, d in FOCUS.items() if d == k), str(k))
        out(f"  C u32_array  [{label}]: {format_u32_array(v.u32_array)}")
    for k, v in control_results.items():
        label = next((n for n, d in FOCUS.items() if d == k), str(k))
        out(f"  C u32_array  [{label}]: {format_u32_array(v.u32_array)}")

    differs_a = set(defect_sizes.values()) != set(control_sizes.values()) or any(
        s != 0 for s in defect_sizes.values()
    )
    differs_b = set(defect_b.values()) != set(control_b.values()) or any(
        t != (0, 0, 0) for t in defect_b.values()
    )
    differs_c = len({v.u32_array for v in defect_results.values()} |
                     {v.u32_array for v in control_results.values()}) > 1

    out(f"\n  A differs (defect vs control or nonzero): {differs_a}")
    out(f"  B differs (defect vs control or nonzero): {differs_b}")
    out(f"  C differs across focus cats: {differs_c}")


def roster_scan(all_cats, conn: sqlite3.Connection) -> dict[int, Direction39Result]:
    out("\n=== Roster Scan ===")
    all_results: dict[int, Direction39Result] = {}
    parse_failures: list[tuple[str, int, str]] = []

    bytevec_size_counter: collections.Counter = collections.Counter()
    u8_triple_counter: collections.Counter = collections.Counter()
    u32_array_counter: collections.Counter = collections.Counter()
    nonzero_bytevec_cats: list[tuple[str, int, int]] = []
    nonzero_u8_cats: list[tuple[str, int, int, int, int]] = []
    nonzero_u32_cats: list[tuple[str, int, tuple[int, ...]]] = []

    for cat in all_cats:
        raw = raw_blob(conn, cat.db_key)
        try:
            result = extract_fields(raw, cat, cat.name)
        except ValueError as exc:
            parse_failures.append((cat.name, cat.db_key, str(exc)))
            continue
        all_results[cat.db_key] = result

        bytevec_size_counter[result.bytevec_size] += 1
        u8_triple_counter[(result.u8_a, result.u8_b, result.u8_c)] += 1
        u32_array_counter[result.u32_array] += 1

        if result.bytevec_size > 0:
            nonzero_bytevec_cats.append((cat.name, cat.db_key, result.bytevec_size))
        if (result.u8_a, result.u8_b, result.u8_c) != (0, 0, 0):
            nonzero_u8_cats.append((cat.name, cat.db_key, result.u8_a, result.u8_b, result.u8_c))
        if any(v != 0 for v in result.u32_array):
            nonzero_u32_cats.append((cat.name, cat.db_key, result.u32_array))

    parsed_count = len(all_results)
    out(f"  parsed: {parsed_count} / {len(all_cats)}")
    out(f"  parse failures: {len(parse_failures)}")
    for cat_name, db_key, error in parse_failures[:20]:
        out(f"    failure {cat_name} key={db_key}: {error}")

    out(f"\n  A. bytevec_size distribution:")
    for size, count in bytevec_size_counter.most_common(10):
        out(f"    size={size}: {count} cats")

    out(f"\n  A. Nonzero bytevec cats ({len(nonzero_bytevec_cats)}):")
    for cat_name, db_key, size in nonzero_bytevec_cats[:30]:
        marker = "[DEFECT+]" if db_key in DEFECT_POSITIVE else ("[CONTROL]" if db_key in CLEAN_CONTROLS else "")
        out(f"    {cat_name} key={db_key} size={size} {marker}")
    if len(nonzero_bytevec_cats) > 30:
        out(f"    ... and {len(nonzero_bytevec_cats) - 30} more")

    out(f"\n  B. u8[a,b,c] triple distribution (top 10):")
    for triple, count in u8_triple_counter.most_common(10):
        out(f"    {triple}: {count} cats")

    out(f"\n  B. Nonzero u8 cats ({len(nonzero_u8_cats)}):")
    for cat_name, db_key, a, b, c in nonzero_u8_cats[:30]:
        marker = "[DEFECT+]" if db_key in DEFECT_POSITIVE else ("[CONTROL]" if db_key in CLEAN_CONTROLS else "")
        out(f"    {cat_name} key={db_key} u8=[0x{a:02x},0x{b:02x},0x{c:02x}] ({a},{b},{c}) {marker}")
    if len(nonzero_u8_cats) > 30:
        out(f"    ... and {len(nonzero_u8_cats) - 30} more")

    out(f"\n  C. u32_array distinct values: {len(u32_array_counter)}")
    out(f"  C. Most common u32 arrays (top 5):")
    for arr, count in u32_array_counter.most_common(5):
        out(f"    count={count}: {format_u32_array(arr)}")

    out(f"\n  C. Nonzero u32 array cats ({len(nonzero_u32_cats)}):")
    for cat_name, db_key, arr in nonzero_u32_cats[:30]:
        marker = "[DEFECT+]" if db_key in DEFECT_POSITIVE else ("[CONTROL]" if db_key in CLEAN_CONTROLS else "")
        out(f"    {cat_name} key={db_key} {marker}")
        out(f"      {format_u32_array(arr)}")
    if len(nonzero_u32_cats) > 30:
        out(f"    ... and {len(nonzero_u32_cats) - 30} more")

    return all_results


def main() -> None:
    out("Direction 39 - Extract bytevec (A), u8 flags (B), u32 array (C) for all cats")
    out(f"Save: {SAVE}")

    save_data = parse_save(str(SAVE))
    all_cats = save_data[0]
    out(f"Total cats parsed by save_parser: {len(all_cats)}")

    conn = sqlite3.connect(str(SAVE))
    try:
        focus_results = dump_focus(all_cats, conn)
        compare_focus(focus_results)
        roster_scan(all_cats, conn)
    finally:
        conn.close()

    OUT.write_text("\n".join(_lines), encoding="utf-8")
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
