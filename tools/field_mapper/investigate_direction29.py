"""
Direction 29 - Identify FUN_14022cf90 records.

Ghidra shows FUN_14022cf90 is called immediately after the gender string and
body-scale f64, at CatData+0x6f0/+0x70c/+0x728. Each call serializes 7 u32s.

This script validates the save-side interpretation: those three records are
the already-parsed stat arrays:

  CatData+0x6f0 -> stat_base[7]
  CatData+0x70c -> stat_mod[7]
  CatData+0x728 -> stat_sec[7]
"""
from __future__ import annotations

import struct
import sqlite3
import sys
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import BinaryReader, STAT_NAMES, parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "investigation" / "steamcampaign01_20260424_191107.sav"
OUT = Path(__file__).parent / "direction29_results.txt"

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
STAT_COUNT = 7
STAT_RECORD_COUNT = 3

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


def locate_stat_records(raw: bytes, cat) -> tuple[int, str, float]:
    t_start = locate_t_start(raw, cat)
    if t_start < 0:
        raise ValueError("Could not locate T array")

    reader = BinaryReader(raw, t_start)
    reader.skip(BODY_PART_U32_COUNT * U32_SIZE)
    reader.skip(EXTRA_BODY_PART_U32_COUNT * U32_SIZE)
    gender = reader.str() or ""
    scale = reader.f64()
    return reader.pos, gender, scale


def read_u32_record(raw: bytes, pos: int) -> list[int]:
    return [
        struct.unpack_from("<I", raw, pos + stat_index * U32_SIZE)[0]
        for stat_index in range(STAT_COUNT)
    ]


def read_i32_record(raw: bytes, pos: int) -> list[int]:
    return [
        struct.unpack_from("<i", raw, pos + stat_index * U32_SIZE)[0]
        for stat_index in range(STAT_COUNT)
    ]


def format_stat_record(values: list[int]) -> str:
    return ", ".join(
        f"{stat_name}={value}"
        for stat_name, value in zip(STAT_NAMES, values)
    )


def analyze_cat(cat, raw: bytes) -> bool:
    records_start, gender, scale = locate_stat_records(raw, cat)
    base_pos = records_start
    mod_pos = base_pos + STAT_COUNT * U32_SIZE
    sec_pos = mod_pos + STAT_COUNT * U32_SIZE

    base_record = read_u32_record(raw, base_pos)
    mod_record = read_i32_record(raw, mod_pos)
    sec_record = read_i32_record(raw, sec_pos)

    matches = (
        base_record == list(cat.stat_base)
        and mod_record == list(cat.stat_mod)
        and sec_record == list(cat.stat_sec)
    )

    out(f"\n=== {cat.name} (db_key={cat.db_key}) ===")
    out(f"  gender token: {gender!r}, scale={scale:.8f}, records_start=blob+0x{records_start:04x}")
    out(f"  CatData+0x6f0 / stat_base: {format_stat_record(base_record)}")
    out(f"  CatData+0x70c / stat_mod:  {format_stat_record(mod_record)}")
    out(f"  CatData+0x728 / stat_sec:  {format_stat_record(sec_record)}")
    out(f"  matches parser stat arrays: {matches}")
    return matches


def main() -> None:
    out("Direction 29 - Identify FUN_14022cf90 as stat arrays")
    out(f"Save: {SAVE}")

    save_data = parse_save(str(SAVE))
    all_cats = save_data[0]
    conn = sqlite3.connect(str(SAVE))
    try:
        all_match = True
        for name, db_key in FOCUS.items():
            cat = next((candidate for candidate in all_cats if candidate.db_key == db_key), None)
            if cat is None:
                out(f"\n{name} (db_key={db_key}): not found")
                all_match = False
                continue
            all_match = analyze_cat(cat, raw_blob(conn, cat.db_key)) and all_match

        out("\nConclusion:")
        if all_match:
            out("  FUN_14022cf90 serializes the three stat arrays already parsed by save_parser.")
            out("  It is not a hidden missing-part defect structure.")
        else:
            out("  At least one focus cat did not match; inspect the records above.")
    finally:
        conn.close()

    OUT.write_text("\n".join(_lines), encoding="utf-8")
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
