"""Direction #15 -- Roster-wide pre-T seed comparison for defect-bearing slots.

Test whether the remaining unknown pre-T float fields (f64[3], f64[6], f64[7])
behave like threshold-style birth-defect roll seeds for slots that ever show a
detected birth defect somewhere in the roster.
"""
from __future__ import annotations

import math
import sqlite3
import struct
import sys
from collections import Counter
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import (  # noqa: E402
    GameData,
    _VISUAL_MUTATION_FIELDS,
    _VISUAL_MUTATION_PART_LABELS,
    parse_save,
    set_visual_mut_data,
)

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
GPAK = ROOT / "test-saves" / "resources.gpak"
OUT = Path(__file__).parent / "direction15_results.txt"

TARGET_NAMES = ("Whommie", "Bud", "Flekpus")
SEED_INDICES = (3, 6, 7)
PRE_T_FLOAT_COUNT = 8
LEFT_PREFERRED_SUFFIXES = ("_L", "")
TOP_SLOT_EXAMPLES = 8

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


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


def read_pre_t_floats(raw: bytes, t_start: int) -> list[float]:
    base = t_start - PRE_T_FLOAT_COUNT * 8
    return [struct.unpack_from("<d", raw, base + index * 8)[0] for index in range(PRE_T_FLOAT_COUNT)]


def is_slot_defect(slot_key: str, mutation_id: int, group_key: str, gpak_category: str) -> bool:
    if mutation_id in (0, 0xFFFF_FFFF):
        return False
    is_defect = (700 <= mutation_id <= 706) or mutation_id == 0xFFFF_FFFE
    _ = slot_key  # quiet unused-parameter lint in this script context
    lookup = _VISUAL_MUT_DATA.get(gpak_category, {}).get(mutation_id)
    if lookup:
        _, _, gpak_is_defect = lookup
        is_defect = is_defect or bool(gpak_is_defect)
    return is_defect


def separability(positive_values: list[float], negative_values: list[float]) -> str:
    pos_min = min(positive_values)
    pos_max = max(positive_values)
    neg_min = min(negative_values)
    neg_max = max(negative_values)
    if pos_min > neg_max:
        return f"YES: positives > negatives (threshold in ({neg_max:.6g}, {pos_min:.6g}))"
    if pos_max < neg_min:
        return f"YES: positives < negatives (threshold in ({pos_max:.6g}, {neg_min:.6g}))"
    return "NO: overlapping ranges"


def fmt_float(value: float) -> str:
    if math.isnan(value):
        return "NaN"
    return f"{value:.9g}"


gd = GameData.from_gpak(str(GPAK))
set_visual_mut_data(gd.visual_mutation_data)
_VISUAL_MUT_DATA = gd.visual_mutation_data


def main() -> None:
    out("=" * 70)
    out("Direction #15 -- Pre-T seed comparison for defect-bearing slots")
    out("=" * 70)
    out(f"Save: {SAVE}")
    out(f"GPAK: {GPAK}")
    out()

    save_data = parse_save(str(SAVE))
    cat_map = {cat.name: cat for cat in save_data.cats}
    conn = sqlite3.connect(str(SAVE))

    pre_t_by_name: dict[str, list[float]] = {}
    slot_positive_names: dict[str, list[str]] = {}
    slot_positive_values: dict[str, list[tuple[str, float]]] = {}
    slot_negative_values: dict[str, list[tuple[str, float]]] = {}
    slot_label_map: dict[str, str] = {}

    slot_field_map = {
        slot_key: (table_index, group_key, gpak_category, slot_label)
        for slot_key, table_index, group_key, gpak_category, _fallback_part, slot_label in _VISUAL_MUTATION_FIELDS
    }

    for cat in save_data.cats:
        raw = raw_blob(conn, cat.db_key)
        t_start = locate_t_start(raw, cat)
        if t_start < 0:
            continue
        pre_t_values = read_pre_t_floats(raw, t_start)
        pre_t_by_name[cat.name] = pre_t_values

        for slot_key, table_index, group_key, gpak_category, slot_label in (
            (key, *slot_field_map[key]) for key in slot_field_map
        ):
            mutation_id = cat.visual_mutation_slots.get(slot_key, 0)
            slot_label_map[slot_key] = _VISUAL_MUTATION_PART_LABELS.get(group_key, slot_label)
            slot_has_defect = is_slot_defect(slot_key, mutation_id, group_key, gpak_category)
            for seed_index in SEED_INDICES:
                bucket = slot_positive_values if slot_has_defect else slot_negative_values
                bucket.setdefault(f"{slot_key}:{seed_index}", []).append((cat.name, pre_t_values[seed_index]))
            if slot_has_defect:
                slot_positive_names.setdefault(slot_key, []).append(cat.name)

    out("=" * 70)
    out("Key cats")
    out("=" * 70)
    for name in TARGET_NAMES:
        cat = cat_map.get(name)
        if cat is None:
            out(f"{name}: MISSING")
            continue
        pre_t_values = pre_t_by_name.get(name)
        out(
            f"{name} (db_key={cat.db_key}) "
            f"eye_L={cat.visual_mutation_slots.get('eye_L')} "
            f"eyebrow_L={cat.visual_mutation_slots.get('eyebrow_L')} "
            f"ear_L={cat.visual_mutation_slots.get('ear_L')} "
            f"defects={cat.defects}"
        )
        if pre_t_values:
            out(
                "  seeds: "
                + ", ".join(f"f64[{index}]={fmt_float(pre_t_values[index])}" for index in SEED_INDICES)
            )
    out()

    defect_slots = sorted(slot_positive_names.keys())
    out("=" * 70)
    out("Defect-bearing slots found in roster")
    out("=" * 70)
    for slot_key in defect_slots:
        examples = slot_positive_names[slot_key][:TOP_SLOT_EXAMPLES]
        out(
            f"{slot_key:12s} part_label={slot_label_map.get(slot_key)!r} "
            f"positives={len(slot_positive_names[slot_key])} examples={examples}"
        )
    out()

    out("=" * 70)
    out("Seed comparisons by slot")
    out("=" * 70)
    for slot_key in defect_slots:
        out(f"{slot_key} ({slot_label_map.get(slot_key)})")
        for seed_index in SEED_INDICES:
            positive_pairs = slot_positive_values[f"{slot_key}:{seed_index}"]
            negative_pairs = slot_negative_values[f"{slot_key}:{seed_index}"]
            positive_values = [value for _, value in positive_pairs if not math.isnan(value)]
            negative_values = [value for _, value in negative_pairs if not math.isnan(value)]
            positive_nans = sum(1 for _, value in positive_pairs if math.isnan(value))
            negative_nans = sum(1 for _, value in negative_pairs if math.isnan(value))
            out(
                f"  f64[{seed_index}] positives={len(positive_pairs)} negatives={len(negative_pairs)} "
                f"pos_nan={positive_nans} neg_nan={negative_nans}"
            )
            if positive_values and negative_values:
                out(
                    f"    pos_range=[{min(positive_values):.9g}, {max(positive_values):.9g}] "
                    f"neg_range=[{min(negative_values):.9g}, {max(negative_values):.9g}]"
                )
                out(f"    threshold_test={separability(positive_values, negative_values)}")
                pos_counter = Counter(round(value, 9) for value in positive_values)
                neg_counter = Counter(round(value, 9) for value in negative_values)
                out(f"    top_pos_values={pos_counter.most_common(5)}")
                out(f"    top_neg_values={neg_counter.most_common(5)}")
            else:
                out("    threshold_test=insufficient finite values")
        out()

    out("=" * 70)
    out("Verdict")
    out("=" * 70)
    out(
        "Across all slot groups with detected birth defects elsewhere in the roster, "
        "f64[3], f64[6], and f64[7] were checked for threshold-like separation between "
        "cats where that slot is defect-positive and cats where it is not."
    )
    threshold_hits: list[str] = []
    for slot_key in defect_slots:
        for seed_index in SEED_INDICES:
            positive_pairs = slot_positive_values[f"{slot_key}:{seed_index}"]
            negative_pairs = slot_negative_values[f"{slot_key}:{seed_index}"]
            positive_values = [value for _, value in positive_pairs if not math.isnan(value)]
            negative_values = [value for _, value in negative_pairs if not math.isnan(value)]
            if positive_values and negative_values:
                decision = separability(positive_values, negative_values)
                if decision.startswith("YES:"):
                    threshold_hits.append(f"{slot_key} f64[{seed_index}] {decision}")
    if threshold_hits:
        out("Threshold-like separations found:")
        for line in threshold_hits:
            out(f"  {line}")
    else:
        out("No slot/seed pair produced a clean threshold separation; all finite ranges overlapped.")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
