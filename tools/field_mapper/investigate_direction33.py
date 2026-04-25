"""
Direction 33 - Map saved body-part T indices to CatPart fields.

Ghidra showed:
  FUN_14022ce10(CatData+0x60, serializer)
    writes CatData+0x78, +0x7c, +0x80 as the first three u32s
    then calls FUN_14022cd00 for 14 CatPart records

  FUN_14022cd00(CatPart, serializer)
    writes CatPart+0x04, +0x08, +0x0c, +0x10, +0x14

The birth-defect breeding helper FUN_1400a5390 checks CatPart+0x18, but that
field is just past the serialized five-u32 CatPart window. This script records
the exact map and dumps the affected focus slots from the fixed save snapshot.
"""
from __future__ import annotations

import struct
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "investigation" / "steamcampaign01_20260424_191107.sav"
OUT = Path(__file__).parent / "direction33_results.txt"

CATDATA_BODY_PARTS_BASE = 0x60
TOP_LEVEL_SAVED_OFFSETS = [0x18, 0x1C, 0x20]
CATPART_BASE_OFFSETS = [
    0x2C,
    0x80,
    0xD4,
    0x128,
    0x17C,
    0x1D0,
    0x224,
    0x278,
    0x2CC,
    0x320,
    0x374,
    0x3C8,
    0x41C,
    0x470,
]
CATPART_SAVED_OFFSETS = [0x04, 0x08, 0x0C, 0x10, 0x14]
CATPART_SAVED_FIELD_NAMES = ["part_id", "texture_echo", "field_0c", "field_10", "field_14"]
CATPART_MISSING_FLAG_OFFSET = 0x18

SLOTS = [
    ("fur", 0),
    ("body", 3),
    ("head", 8),
    ("tail", 13),
    ("leg_L", 18),
    ("leg_R", 23),
    ("arm_L", 28),
    ("arm_R", 33),
    ("eye_L", 38),
    ("eye_R", 43),
    ("eyebrow_L", 48),
    ("eyebrow_R", 53),
    ("ear_L", 58),
    ("ear_R", 63),
    ("mouth", 68),
]

FOCUS_KEYS = {
    "Whommie": 853,
    "Kami": 840,
    "Bud": 887,
    "Petronij": 841,
    "Romanoba": 847,
    "Alaya": 861,
}

FOCUS_SLOT_NAMES = ["eye_L", "eye_R", "eyebrow_L", "eyebrow_R", "ear_L", "ear_R"]

_lines: list[str] = []


@dataclass(frozen=True)
class SavedField:
    t_index: int
    slot_name: str
    catdata_offset: int
    catpart_base: int | None
    catpart_offset: int | None


def out(message: str = "") -> None:
    print(message)
    _lines.append(message)


def raw_blob(conn: sqlite3.Connection, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    if row is None:
        raise KeyError(db_key)
    data = bytes(row[0])
    uncompressed_size = struct.unpack_from("<I", data, 0)[0]
    return lz4.block.decompress(data[4:], uncompressed_size=uncompressed_size)


def locate_t_start(raw: bytes, cat) -> int:
    fur = cat.body_parts["texture"]
    body = cat.body_parts["bodyShape"]
    head = cat.body_parts["headShape"]
    target = struct.pack("<I", fur)
    for offset in range(0, len(raw) - 9 * 4):
        if raw[offset:offset + 4] != target:
            continue
        if (
            struct.unpack_from("<I", raw, offset + 3 * 4)[0] == body
            and struct.unpack_from("<I", raw, offset + 8 * 4)[0] == head
        ):
            return offset
    raise ValueError(f"could not locate T array for {cat.name}")


def read_t(raw: bytes, t_start: int, count: int = 73) -> list[int]:
    return [struct.unpack_from("<I", raw, t_start + index * 4)[0] for index in range(count)]


def build_saved_field_map() -> list[SavedField]:
    fields: list[SavedField] = []
    for index, offset in enumerate(TOP_LEVEL_SAVED_OFFSETS):
        fields.append(
            SavedField(
                t_index=index,
                slot_name="fur_top",
                catdata_offset=CATDATA_BODY_PARTS_BASE + offset,
                catpart_base=None,
                catpart_offset=offset,
            )
        )
    for part_index, catpart_relative_base in enumerate(CATPART_BASE_OFFSETS):
        slot_name = SLOTS[part_index + 1][0]
        catpart_absolute_base = CATDATA_BODY_PARTS_BASE + catpart_relative_base
        t_start = 3 + part_index * len(CATPART_SAVED_OFFSETS)
        for field_index, catpart_offset in enumerate(CATPART_SAVED_OFFSETS):
            fields.append(
                SavedField(
                    t_index=t_start + field_index,
                    slot_name=slot_name,
                    catdata_offset=catpart_absolute_base + catpart_offset,
                    catpart_base=catpart_absolute_base,
                    catpart_offset=catpart_offset,
                )
            )
    return fields


def format_value(value: int, *, is_primary_part_id: bool = True) -> str:
    label = ""
    if value == 0xFFFFFFFE:
        label = " NO_PART_LITERAL"
    elif value == 0xFFFFFFFF:
        label = " UINT_MAX"
    elif is_primary_part_id and 700 <= value <= 710:
        label = " DEFECT_RANGE"
    return f"{value:#010x} ({value}){label}"


def format_slot_window(values: list[int]) -> str:
    parts = []
    for field_name, value in zip(CATPART_SAVED_FIELD_NAMES, values):
        parts.append(f"{field_name}={format_value(value, is_primary_part_id=field_name == 'part_id')}")
    return "; ".join(parts)


def dump_static_map(fields: list[SavedField]) -> None:
    out("Direction 33 - Body-part serializer field map")
    out(f"Save: {SAVE}")
    out("")
    out("Saved T-index map from Ghidra:")
    for field in fields:
        if field.catpart_base is None:
            out(
                f"  T[{field.t_index:02d}] {field.slot_name:10s} "
                f"CatData+0x{field.catdata_offset:03x}  top-level body-part field"
            )
        else:
            out(
                f"  T[{field.t_index:02d}] {field.slot_name:10s} "
                f"CatData+0x{field.catdata_offset:03x}  "
                f"CatPartBase+0x{field.catpart_offset:02x}"
            )
    out("")
    out("Important negative finding:")
    out(
        "  FUN_1400a5390 checks CatPartBase+0x18 for the missing-part state, "
        "but FUN_14022cd00 serializes only CatPartBase+0x04..0x14."
    )
    out("  Therefore CatPartBase+0x18 is not present in the saved T array.")


def dump_focus_slots(cats_by_key: dict[int, object], conn: sqlite3.Connection) -> None:
    slot_lookup = dict(SLOTS)
    out("")
    out("Focus slot dumps:")
    for name, db_key in FOCUS_KEYS.items():
        cat = cats_by_key.get(db_key)
        if cat is None:
            out(f"\n{name} key={db_key}: missing")
            continue
        raw = raw_blob(conn, db_key)
        t_start = locate_t_start(raw, cat)
        table = read_t(raw, t_start)
        out(f"\n{name} key={db_key} t_start=0x{t_start:x} parsed_defects={list(cat.defects)}")
        for slot_name in FOCUS_SLOT_NAMES:
            start_index = slot_lookup[slot_name]
            values = table[start_index:start_index + 5]
            joined = format_slot_window(values)
            out(f"  {slot_name:10s} T[{start_index:02d}..{start_index + 4:02d}]: {joined}")


def compare_controls(cats_by_key: dict[int, object], conn: sqlite3.Connection) -> None:
    slot_lookup = dict(SLOTS)
    comparisons = [
        ("Whommie", 853, "Kami", 840, ["eye_L", "eye_R", "eyebrow_L", "eyebrow_R"]),
        ("Bud", 887, "Romanoba", 847, ["ear_L", "ear_R"]),
        ("Bud", 887, "Kami", 840, ["ear_L", "ear_R"]),
    ]
    out("")
    out("Affected-slot comparisons:")
    for left_name, left_key, right_name, right_key, slot_names in comparisons:
        left_cat = cats_by_key.get(left_key)
        right_cat = cats_by_key.get(right_key)
        if left_cat is None or right_cat is None:
            continue
        left_table = read_t(raw_blob(conn, left_key), locate_t_start(raw_blob(conn, left_key), left_cat))
        right_table = read_t(raw_blob(conn, right_key), locate_t_start(raw_blob(conn, right_key), right_cat))
        out(f"\n{left_name} vs {right_name}")
        for slot_name in slot_names:
            start_index = slot_lookup[slot_name]
            left_values = left_table[start_index:start_index + 5]
            right_values = right_table[start_index:start_index + 5]
            marker = "same" if left_values == right_values else "different"
            out(f"  {slot_name:10s}: {marker}")
            out(f"    {left_name:8s}: {format_slot_window(left_values)}")
            out(f"    {right_name:8s}: {format_slot_window(right_values)}")


def main() -> None:
    save_data = parse_save(str(SAVE))
    cats_by_key = {cat.db_key: cat for cat in save_data[0]}
    conn = sqlite3.connect(str(SAVE))
    try:
        fields = build_saved_field_map()
        dump_static_map(fields)
        dump_focus_slots(cats_by_key, conn)
        compare_controls(cats_by_key, conn)
    finally:
        conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
