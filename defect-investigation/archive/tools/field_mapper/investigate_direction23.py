"""Direction #23 -- Test the inherited-defect fallback against ancestry.

Direction 22 showed many low-COI cats with parsed birth defects, which could
still be explained if birth defects simply pass down as ordinary part variants.
This script checks whether low-COI defect cats actually have matching defects
anywhere in their recorded ancestry.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction23_results.txt"

BIRTH_DEFECT_MIN_COI = 0.05
EXAMPLE_LIMIT = 20
KEY_DB_KEYS = (68, 853, 887)

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def ancestor_rows(cat) -> list[tuple[int, object]]:
    seen: set[int] = set()
    stack = [(cat.parent_a, 1), (cat.parent_b, 1)]
    rows: list[tuple[int, object]] = []
    while stack:
        node, depth = stack.pop()
        if node is None or node.db_key in seen:
            continue
        seen.add(node.db_key)
        rows.append((depth, node))
        stack.append((node.parent_a, depth + 1))
        stack.append((node.parent_b, depth + 1))
    return rows


def main() -> None:
    save_data = parse_save(str(SAVE))
    cats = save_data.cats
    by_db = {cat.db_key: cat for cat in cats}

    low_coi_defect_cats = [cat for cat in cats if cat.defects and cat.inbredness <= BIRTH_DEFECT_MIN_COI]
    no_matching_ancestor = []
    for cat in low_coi_defect_cats:
        ancestors = ancestor_rows(cat)
        ancestor_defects = {defect for _, ancestor in ancestors for defect in ancestor.defects}
        if all(defect not in ancestor_defects for defect in cat.defects):
            no_matching_ancestor.append((cat, ancestors, ancestor_defects))

    no_matching_defect_counts = Counter(
        defect
        for cat, _ancestors, _ancestor_defects in no_matching_ancestor
        for defect in cat.defects
    )

    out("=" * 70)
    out("Direction #23 -- Ancestor check for low-COI birth defects")
    out("=" * 70)
    out(f"Save: {SAVE}")
    out(
        f"Scope: cats with parsed birth defects and current coi <= {BIRTH_DEFECT_MIN_COI:.2f}, "
        "testing whether a matching parsed defect exists anywhere in recorded ancestry."
    )
    out()

    out("=" * 70)
    out("Roster-wide counts")
    out("=" * 70)
    out(f"Low-COI parsed defect cats: {len(low_coi_defect_cats)}")
    out(f"No matching parsed defect anywhere in ancestry: {len(no_matching_ancestor)}")
    out("Defect-name counts among the no-matching-ancestor cases:")
    for defect_name, count in no_matching_defect_counts.most_common():
        out(f"  {defect_name}: {count}")
    out()

    out("=" * 70)
    out("Examples with no matching ancestor defect")
    out("=" * 70)
    for cat, ancestors, ancestor_defects in no_matching_ancestor[:EXAMPLE_LIMIT]:
        out(
            f"{cat.name:16s} db_key={cat.db_key:>3} gen={cat.generation:>2} "
            f"coi={cat.inbredness:.9g} defects={cat.defects} ancestor_count={len(ancestors)}"
        )
        if ancestor_defects:
            out(f"  other ancestor defects={sorted(ancestor_defects)}")
        else:
            out("  other ancestor defects=[]")
    out()

    out("=" * 70)
    out("Key cats")
    out("=" * 70)
    for db_key in KEY_DB_KEYS:
        cat = by_db[db_key]
        ancestors = ancestor_rows(cat)
        matching_ancestors = []
        for depth, ancestor in ancestors:
            if any(defect in ancestor.defects for defect in cat.defects):
                matching_ancestors.append((depth, ancestor))
        out(
            f"{cat.name} (db_key={cat.db_key}) gen={cat.generation} "
            f"coi={cat.inbredness:.9g} parsed_defects={cat.defects}"
        )
        out(f"  total_ancestors={len(ancestors)} matching_defect_ancestors={len(matching_ancestors)}")
        for depth, ancestor in matching_ancestors[:EXAMPLE_LIMIT]:
            out(
                f"  depth={depth} ancestor={ancestor.name} (db_key={ancestor.db_key}) "
                f"defects={ancestor.defects}"
            )
    out()

    out("=" * 70)
    out("Verdict")
    out("=" * 70)
    out(
        "The simple inherited-defect fallback is also too weak to explain the low-COI cases by itself."
    )
    out(
        f"Among the {len(low_coi_defect_cats)} cats with parsed birth defects at coi <= 0.05, "
        f"{len(no_matching_ancestor)} have no matching parsed defect anywhere in recorded ancestry."
    )
    out(
        "That means these cases are not explained by a plainly visible ancestral line of the same "
        "expressed defect part being passed down through the family tree."
    )
    out(
        "Flekpus remains the clearest example: generation 3, coi=0.0410294675, parsed `Eyebrow Birth Defect`, "
        "and zero matching parsed defects anywhere in recorded ancestry."
    )
    out(
        "Whommie's recorded fur defect likewise has no matching parsed defect anywhere in recorded ancestry. "
        "Bud still has no parsed defect at all, and no ancestor with a matching ear defect."
    )
    out(
        "This does not rule out hidden carrier state or a more complex genotype-level inheritance model, "
        "but it rules out the simplest phenotype-only ancestry explanation."
    )

    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
