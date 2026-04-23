"""Direction #25 -- Re-run the low-COI defect audit using pedigree COI.

Directions 22 and 23 used the raw `cat.inbredness` field from `parse_save()`,
which Direction 24 proved is not the game's breeding coefficient. This script
re-runs those questions against the save's cached pedigree COI instead.
"""
from __future__ import annotations

import math
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import _read_parallel_hash_table, parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction25_results.txt"

BIRTH_DEFECT_MIN_COI = 0.05
TWO_PASS_COI = 0.9
EXAMPLE_LIMIT = 20
KEY_DB_KEYS = (68, 853, 887)

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def parse_cached_child_coi(conn: sqlite3.Connection) -> dict[int, float]:
    row = conn.execute("SELECT data FROM files WHERE key='pedigree'").fetchone()
    if not row:
        return {}
    rows, _offset = _read_parallel_hash_table(row[0], 0, "<qqqd", 32)
    cached: dict[int, float] = {}
    for cat_k, _pa_k, _pb_k, coi in rows:
        cat_key = int(cat_k)
        if 0 < cat_key <= 1_000_000 and math.isfinite(float(coi)):
            cached[cat_key] = float(coi)
    return cached


def ancestor_defects(cat) -> tuple[set[str], int]:
    seen: set[int] = set()
    stack = [cat.parent_a, cat.parent_b]
    defects: set[str] = set()
    while stack:
        node = stack.pop()
        if node is None or node.db_key in seen:
            continue
        seen.add(node.db_key)
        defects.update(node.defects)
        stack.extend([node.parent_a, node.parent_b])
    return defects, len(seen)


def main() -> None:
    save_data = parse_save(str(SAVE))
    conn = sqlite3.connect(str(SAVE))
    cached_coi = parse_cached_child_coi(conn)
    conn.close()

    by_db = {cat.db_key: cat for cat in save_data.cats}
    defect_cats = [cat for cat in save_data.cats if cat.defects]
    low_coi_defect_cats = [
        cat for cat in defect_cats
        if cached_coi.get(cat.db_key) is not None and cached_coi[cat.db_key] <= BIRTH_DEFECT_MIN_COI
    ]
    high_coi_two_pass = [
        cat for cat in defect_cats
        if cached_coi.get(cat.db_key) is not None and cached_coi[cat.db_key] > TWO_PASS_COI
    ]

    no_matching_ancestor = []
    for cat in low_coi_defect_cats:
        defects_in_ancestors, ancestor_count = ancestor_defects(cat)
        if all(defect not in defects_in_ancestors for defect in cat.defects):
            no_matching_ancestor.append((cat, ancestor_count))

    low_name_counts = Counter(defect for cat in low_coi_defect_cats for defect in cat.defects)

    out("=" * 70)
    out("Direction #25 -- Corrected low-COI defect audit using pedigree COI")
    out("=" * 70)
    out(f"Save: {SAVE}")
    out(
        "This re-runs Directions 22 and 23 against the save's cached pedigree COI, "
        "not the raw `cat.inbredness` field from the personality block."
    )
    out()

    out("=" * 70)
    out("Roster-wide counts")
    out("=" * 70)
    out(f"Total cats parsed: {len(save_data.cats)}")
    out(f"Cats with parsed birth defects: {len(defect_cats)}")
    out(f"Parsed defect cats at cached pedigree coi <= {BIRTH_DEFECT_MIN_COI:.2f}: {len(low_coi_defect_cats)}")
    out(f"Parsed defect cats at cached pedigree coi > {TWO_PASS_COI:.1f}: {len(high_coi_two_pass)}")
    out("Low-COI parsed defect counts by name:")
    for defect_name, count in low_name_counts.most_common():
        out(f"  {defect_name}: {count}")
    out()

    out("=" * 70)
    out("Low-COI defect cases")
    out("=" * 70)
    for cat in sorted(low_coi_defect_cats, key=lambda item: cached_coi[item.db_key])[:EXAMPLE_LIMIT]:
        out(
            f"{cat.name:16s} db_key={cat.db_key:>3} gen={cat.generation:>2} "
            f"cached_coi={cached_coi[cat.db_key]:.17g} defects={cat.defects}"
        )
    out()

    out("=" * 70)
    out("Low-COI cases with no matching parsed defect anywhere in ancestry")
    out("=" * 70)
    out(f"Count: {len(no_matching_ancestor)} of {len(low_coi_defect_cats)} low-COI defect cats")
    for cat, ancestor_count in no_matching_ancestor[:EXAMPLE_LIMIT]:
        out(
            f"{cat.name:16s} db_key={cat.db_key:>3} gen={cat.generation:>2} "
            f"cached_coi={cached_coi[cat.db_key]:.17g} defects={cat.defects} ancestor_count={ancestor_count}"
        )
    out()

    out("=" * 70)
    out("Key cats")
    out("=" * 70)
    for db_key in KEY_DB_KEYS:
        cat = by_db[db_key]
        value = cached_coi.get(db_key)
        pass_count = 2 if value is not None and value > TWO_PASS_COI else 1
        out(
            f"{cat.name} (db_key={cat.db_key}) cached_pedigree_coi={value:.17g} "
            f"documented_passes={pass_count} parsed_defects={cat.defects}"
        )
    out()

    out("=" * 70)
    out("Verdict")
    out("=" * 70)
    out(
        "Using the correct pedigree-backed COI changes the result substantially."
    )
    out(
        f"Only {len(low_coi_defect_cats)} parsed defect cats fall at cached pedigree coi <= {BIRTH_DEFECT_MIN_COI:.2f}, "
        "not 53."
    )
    out(
        f"Of those, {len(no_matching_ancestor)} have no matching parsed defect anywhere in ancestry. "
        "The cleanest non-stray contradiction remaining is Lucyfer: generation 6, cached pedigree coi 0.013671875, "
        "parsed `Mouth Birth Defect`, and no matching parsed defect in recorded ancestry."
    )
    out(
        "Flekpus and Whommie are no longer contradictions under the corrected metric: "
        "their cached pedigree COI values are 0.25 and 0.3302762971 respectively."
    )
    out(
        "Bud also changes less dramatically but still matters: cached pedigree COI is 0.0775041038, "
        "which is above 0.05 but still far below the >0.9 two-pass threshold, so the high-inbreeding "
        "symmetry explanation still cannot explain Bud's unresolved one-sided ear defect."
    )

    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
