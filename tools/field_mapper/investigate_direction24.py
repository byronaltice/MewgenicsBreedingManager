"""Direction #24 -- Validate our COI numbers against the save's cached pedigree COI.

The online formulas refer to the game's inbreeding coefficient. Before using
those thresholds locally, verify that our derived ancestry math matches the COI
cached in the save's pedigree blob.
"""
from __future__ import annotations

import math
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import (  # noqa: E402
    _read_parallel_hash_table,
    _resolve_parent_uids,
    kinship_coi,
    parse_save,
)

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction24_results.txt"

MAX_KEY = 1_000_000
EPSILON_TIGHT = 1e-12
EPSILON_LOOSE = 1e-9
TOP_MISMATCHES = 20
KEY_DB_KEYS = (68, 853, 887)

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def parse_pedigree_child_rows(conn: sqlite3.Connection) -> tuple[dict[int, tuple[int | None, int | None]], dict[int, float]]:
    row = conn.execute("SELECT data FROM files WHERE key='pedigree'").fetchone()
    if not row:
        return {}, {}
    data = row[0]
    rows, _offset = _read_parallel_hash_table(data, 0, "<qqqd", 32)
    ped_map: dict[int, tuple[int | None, int | None]] = {}
    child_coi: dict[int, float] = {}
    for cat_k, pa_k, pb_k, coi in rows:
        cat_key = int(cat_k)
        if cat_key <= 0 or cat_key > MAX_KEY:
            continue
        pa = int(pa_k) if 0 < int(pa_k) <= MAX_KEY else None
        pb = int(pb_k) if 0 < int(pb_k) <= MAX_KEY else None
        existing = ped_map.get(cat_key)
        if existing is None:
            ped_map[cat_key] = (pa, pb)
        else:
            ped_map[cat_key] = (
                pa if pa is not None else existing[0],
                pb if pb is not None else existing[1],
            )
        if math.isfinite(float(coi)):
            child_coi[cat_key] = float(coi)
    return ped_map, child_coi


def main() -> None:
    save_data = parse_save(str(SAVE))
    key_to_cat = {cat.db_key: cat for cat in save_data.cats}

    conn = sqlite3.connect(str(SAVE))
    ped_map, child_coi = parse_pedigree_child_rows(conn)
    conn.close()

    comparisons: list[tuple[float, int, str, float, float, float, int | None, int | None]] = []
    exact_match_count = 0
    loose_match_count = 0
    no_cached_count = 0
    no_parent_count = 0
    no_parent_obj_count = 0
    raw_field_examples: list[tuple[int, str, float, float]] = []

    for cat in save_data.cats:
        cached = child_coi.get(cat.db_key)
        if cached is None:
            no_cached_count += 1
            continue

        pa_key, pb_key = _resolve_parent_uids(cat, ped_map)
        if pa_key is None or pb_key is None:
            no_parent_count += 1
            continue

        parent_a = key_to_cat.get(pa_key)
        parent_b = key_to_cat.get(pb_key)
        if parent_a is None or parent_b is None:
            no_parent_obj_count += 1
            continue

        derived = kinship_coi(parent_a, parent_b)
        diff = abs(cached - derived)
        comparisons.append((diff, cat.db_key, cat.name, cached, derived, cat.inbredness, pa_key, pb_key))
        if diff <= EPSILON_TIGHT:
            exact_match_count += 1
        if diff <= EPSILON_LOOSE:
            loose_match_count += 1

        if len(raw_field_examples) < TOP_MISMATCHES and abs(cat.inbredness - cached) > EPSILON_LOOSE:
            raw_field_examples.append((cat.db_key, cat.name, cat.inbredness, cached))

    comparisons.sort(reverse=True)
    compared_count = len(comparisons)
    max_diff = comparisons[0][0] if comparisons else 0.0

    out("=" * 70)
    out("Direction #24 -- Pedigree cached COI versus derived kinship COI")
    out("=" * 70)
    out(f"Save: {SAVE}")
    out("Goal: verify whether our local COI math matches the save's cached pedigree COI.")
    out()

    out("=" * 70)
    out("Roster-wide counts")
    out("=" * 70)
    out(f"Total cats parsed: {len(save_data.cats)}")
    out(f"Cats with cached per-child pedigree COI: {len(child_coi)}")
    out(f"Cats compared against derived kinship_coi(parent_a, parent_b): {compared_count}")
    out(f"No cached COI row: {no_cached_count}")
    out(f"Cached COI row but unresolved parent keys: {no_parent_count}")
    out(f"Cached COI row but parent objects missing from roster: {no_parent_obj_count}")
    out(f"Exact matches (|diff| <= {EPSILON_TIGHT}): {exact_match_count}")
    out(f"Loose matches (|diff| <= {EPSILON_LOOSE}): {loose_match_count}")
    out(f"Maximum absolute difference: {max_diff:.17g}")
    out()

    out("=" * 70)
    out("Key cats")
    out("=" * 70)
    for db_key in KEY_DB_KEYS:
        cat = key_to_cat[db_key]
        cached = child_coi.get(db_key)
        pa_key, pb_key = _resolve_parent_uids(cat, ped_map)
        parent_a = key_to_cat.get(pa_key) if pa_key is not None else None
        parent_b = key_to_cat.get(pb_key) if pb_key is not None else None
        derived = kinship_coi(parent_a, parent_b) if parent_a is not None and parent_b is not None else None
        out(
            f"{cat.name} (db_key={cat.db_key}) raw_cat_inbredness={cat.inbredness:.17g} "
            f"cached_pedigree_coi={cached if cached is not None else 'MISSING'} "
            f"derived_kinship_coi={derived if derived is not None else 'MISSING'}"
        )
    out()

    out("=" * 70)
    out("Largest cached-versus-derived differences")
    out("=" * 70)
    for diff, db_key, name, cached, derived, raw_field, pa_key, pb_key in comparisons[:TOP_MISMATCHES]:
        out(
            f"{name:16s} db_key={db_key:>3} diff={diff:.17g} "
            f"cached={cached:.17g} derived={derived:.17g} raw_field={raw_field:.17g} "
            f"parents=({pa_key}, {pb_key})"
        )
    out()

    out("=" * 70)
    out("Examples showing raw cat.inbredness differs from cached pedigree COI")
    out("=" * 70)
    for db_key, name, raw_field, cached in raw_field_examples:
        out(
            f"{name:16s} db_key={db_key:>3} raw_cat_inbredness={raw_field:.17g} "
            f"cached_pedigree_coi={cached:.17g}"
        )
    out()

    out("=" * 70)
    out("Verdict")
    out("=" * 70)
    if compared_count and loose_match_count == compared_count:
        out(
            "Our derived `kinship_coi(parent_a, parent_b)` matches the save's cached per-child pedigree COI "
            "roster-wide to floating-point tolerance."
        )
    else:
        out(
            "Our derived `kinship_coi(parent_a, parent_b)` does NOT fully match the save's cached per-child pedigree COI."
        )
    out(
        "The raw `cat.inbredness` value coming straight from `parse_save()` is not the same source of truth; "
        "it differs from cached pedigree COI for many cats and should not be used as the game's breeding coefficient."
    )
    out(
        "For testing online COI thresholds locally, the correct comparison target is the pedigree blob's cached "
        "per-child COI (or a derived formula validated against it), not the raw personality-block field."
    )

    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
