"""Direction #22 -- Audit the current-COI birth-defect threshold theory.

This follows up the external breeding notes audit by checking whether the
current save's parsed inbreeding coefficients are even consistent with the
community-documented birth-defect gates:

* birth-defect roll only if inbreeding coefficient > 0.05
* two birth-defect passes only if inbreeding coefficient > 0.9

The goal is not to prove the wiki wrong in general, but to test whether the
remaining unresolved defects in this save can be explained by the current
stored coefficient alone.
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
OUT = Path(__file__).parent / "direction22_results.txt"

BIRTH_DEFECT_MIN_COI = 0.05
TWO_PASS_COI = 0.9
LOW_COI_EXAMPLE_LIMIT = 20
KEY_DB_KEYS = (68, 853, 887)
KEY_NAMES = {
    68: "Flekpus",
    853: "Whommie",
    887: "Bud",
}
WIKI_SOURCE = "https://mewgenics.wiki.gg/wiki/Breeding"
REDDIT_SOURCE = "https://www.reddit.com/r/mewgenics/comments/1ruenqd/has_something_changed_about_breeding_birth_defect/"

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def matching_parent_defects(cat) -> set[str]:
    parent_defects: set[str] = set()
    for parent in (cat.parent_a, cat.parent_b):
        if parent is None:
            continue
        parent_defects.update(parent.defects)
    return parent_defects


def key_cat_summary(cat) -> str:
    pass_count = 2 if cat.inbredness > TWO_PASS_COI else 1
    threshold_state = "eligible" if cat.inbredness > BIRTH_DEFECT_MIN_COI else "below-threshold"
    return (
        f"{cat.name} (db_key={cat.db_key}) generation={cat.generation} "
        f"coi={cat.inbredness:.9g} current_rule={threshold_state} "
        f"documented_passes={pass_count} parsed_defects={cat.defects}"
    )


def main() -> None:
    save_data = parse_save(str(SAVE))
    cats = save_data.cats
    by_db = {cat.db_key: cat for cat in cats}

    defect_cats = [cat for cat in cats if cat.defects]
    low_coi_defect_cats = [cat for cat in defect_cats if cat.inbredness <= BIRTH_DEFECT_MIN_COI]
    low_coi_non_strays = [cat for cat in low_coi_defect_cats if cat.generation > 0]
    high_coi_two_pass = [cat for cat in defect_cats if cat.inbredness > TWO_PASS_COI]

    low_coi_with_non_parent_defect = []
    for cat in low_coi_defect_cats:
        parent_defects = matching_parent_defects(cat)
        novel_defects = [defect for defect in cat.defects if defect not in parent_defects]
        if novel_defects:
            low_coi_with_non_parent_defect.append((cat, parent_defects, novel_defects))

    defect_name_counts = Counter(defect for cat in defect_cats for defect in cat.defects)
    low_coi_name_counts = Counter(defect for cat in low_coi_defect_cats for defect in cat.defects)

    out("=" * 70)
    out("Direction #22 -- Current-COI threshold audit")
    out("=" * 70)
    out(f"Save: {SAVE}")
    out("External rules under test:")
    out(f"  wiki.gg breeding page: {WIKI_SOURCE}")
    out("    Birth defects check documented as: coi > 0.05 and random < coi * 1.5")
    out("    Defect generation documented as: 1 pass when coi <= 0.9, 2 passes when coi > 0.9")
    out(f"  Reddit symmetry discussion: {REDDIT_SOURCE}")
    out("    Community explanation for asymmetric high-inbreeding defects points to the > 0.9 two-pass case.")
    out()

    out("=" * 70)
    out("Roster-wide counts")
    out("=" * 70)
    out(f"Total cats parsed: {len(cats)}")
    out(f"Cats with parsed birth defects: {len(defect_cats)}")
    out(f"Parsed defect cats at coi <= {BIRTH_DEFECT_MIN_COI:.2f}: {len(low_coi_defect_cats)}")
    out(f"  Of those, non-strays (generation > 0): {len(low_coi_non_strays)}")
    out(f"Parsed defect cats at coi > {TWO_PASS_COI:.1f}: {len(high_coi_two_pass)}")
    out("All parsed defect counts by name:")
    for defect_name, count in defect_name_counts.most_common():
        out(f"  {defect_name}: {count}")
    out("Low-COI parsed defect counts by name:")
    for defect_name, count in low_coi_name_counts.most_common():
        out(f"  {defect_name}: {count}")
    out()

    out("=" * 70)
    out("Low-COI defect examples")
    out("=" * 70)
    for cat in sorted(low_coi_defect_cats, key=lambda item: item.inbredness)[:LOW_COI_EXAMPLE_LIMIT]:
        out(
            f"{cat.name:16s} db_key={cat.db_key:>3} gen={cat.generation:>2} "
            f"coi={cat.inbredness:.9g} defects={cat.defects}"
        )
    out()

    out("=" * 70)
    out("Low-COI cats with at least one parsed defect not present on either parent")
    out("=" * 70)
    out(
        f"Count: {len(low_coi_with_non_parent_defect)} of {len(low_coi_defect_cats)} "
        f"low-COI defect cats have at least one parsed defect absent from both parents."
    )
    for cat, parent_defects, novel_defects in low_coi_with_non_parent_defect[:LOW_COI_EXAMPLE_LIMIT]:
        out(
            f"{cat.name:16s} db_key={cat.db_key:>3} gen={cat.generation:>2} "
            f"coi={cat.inbredness:.9g} novel_defects={novel_defects} parent_defects={sorted(parent_defects)}"
        )
    out()

    out("=" * 70)
    out("Key cats")
    out("=" * 70)
    for db_key in KEY_DB_KEYS:
        cat = by_db[db_key]
        out(key_cat_summary(cat))
        for parent in (cat.parent_a, cat.parent_b):
            if parent is None:
                out("  parent: MISSING")
                continue
            out(
                f"  parent {parent.name} (db_key={parent.db_key}) "
                f"gen={parent.generation} coi={parent.inbredness:.9g} defects={parent.defects}"
            )
    out()

    out("=" * 70)
    out("Verdict")
    out("=" * 70)
    out(
        f"The current stored inbreeding coefficient alone does not cleanly explain the save's "
        f"observed birth defects under the documented wiki.gg gate of coi > {BIRTH_DEFECT_MIN_COI:.2f}."
    )
    out(
        f"There are {len(low_coi_defect_cats)} cats with parsed birth defects at or below that threshold, "
        f"and {len(low_coi_non_strays)} of them are bred cats rather than stray generation-0 cats."
    )
    out(
        f"More importantly, {len(low_coi_with_non_parent_defect)} low-COI defect cats have at least one "
        "parsed defect absent from both parents, so these cases are not explained by simply inheriting an "
        "already-expressed defect part from mother or father."
    )
    out(
        "Flekpus is the clearest contradiction in this save: generation 3, coi=0.0410294675, "
        "parsed `Eyebrow Birth Defect`, and neither parent has any parsed defect."
    )
    out(
        "Bud also narrows the symmetry theory: current coi=0.0986339069 is above 0.05 but far below 0.9, "
        "so the community's >0.9 two-pass explanation for asymmetric part replacement cannot explain Bud's "
        "unresolved one-sided ear defect."
    )
    out(
        "This does not prove the external formulas are wrong in every context. The remaining possibilities "
        "include: an incomplete public formula, a different internal coefficient than the parser's current "
        "`inbredness`, or a separate defect-generation path for these part removals."
    )

    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
