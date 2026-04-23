"""Direction #15a -- Family-line check for the runtime-only hypothesis.

If the missing "No Part" defects are reconstructed from genetics at load time
rather than serialized as explicit per-slot IDs, the relevant parent pairs may
show informative family patterns. This script inspects offspring of:

- Kami + Petronij  (Whommie's line)
- Kami + Murisha   (Bud's line)

It lists the offspring, their visible eye/eyebrow/ear slot values, and any
detected defects to see whether Whommie/Bud are isolated anomalies or part of a
broader inherited pattern.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction15a_results.txt"

TARGET_PAIRS = (
    ("Kami", "Petronij", "Whommie line"),
    ("Kami", "Murisha", "Bud line"),
)
SLOT_KEYS = ("eye_L", "eyebrow_L", "ear_L")
SLOT_DEFECT_LABELS = {
    "eye_L": "Eye Birth Defect",
    "eyebrow_L": "Eyebrow Birth Defect",
    "ear_L": "Ear Birth Defect",
}

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def main() -> None:
    out("=" * 70)
    out("Direction #15a -- Family-line check for runtime/genetics hypothesis")
    out("=" * 70)
    out(f"Save: {SAVE}")
    out()

    save_data = parse_save(str(SAVE))
    cats = save_data.cats
    cat_map = {cat.name: cat for cat in cats}

    for parent_a_name, parent_b_name, label in TARGET_PAIRS:
        parent_a = cat_map[parent_a_name]
        parent_b = cat_map[parent_b_name]
        offspring = [
            cat for cat in cats
            if {getattr(cat.parent_a, "name", None), getattr(cat.parent_b, "name", None)}
            == {parent_a_name, parent_b_name}
        ]

        out("=" * 70)
        out(f"{label}: {parent_a_name} + {parent_b_name}")
        out("=" * 70)
        out(
            f"Parent {parent_a_name}: "
            f"eye={parent_a.visual_mutation_slots.get('eye_L')} "
            f"brow={parent_a.visual_mutation_slots.get('eyebrow_L')} "
            f"ear={parent_a.visual_mutation_slots.get('ear_L')} "
            f"defects={parent_a.defects}"
        )
        out(
            f"Parent {parent_b_name}: "
            f"eye={parent_b.visual_mutation_slots.get('eye_L')} "
            f"brow={parent_b.visual_mutation_slots.get('eyebrow_L')} "
            f"ear={parent_b.visual_mutation_slots.get('ear_L')} "
            f"defects={parent_b.defects}"
        )
        out(f"Offspring count: {len(offspring)}")
        out()

        if not offspring:
            out("  (no offspring found)")
            out()
            continue

        for cat in sorted(offspring, key=lambda item: (item.generation, item.name.lower())):
            slot_summary = " ".join(f"{slot}={cat.visual_mutation_slots.get(slot)}" for slot in SLOT_KEYS)
            out(
                f"  {cat.name:16s} gen={cat.generation:<2d} "
                f"{slot_summary} defects={cat.defects}"
            )
        out()

        for slot_key in SLOT_KEYS:
            defect_label = SLOT_DEFECT_LABELS[slot_key]
            slot_counter = Counter(cat.visual_mutation_slots.get(slot_key) for cat in offspring)
            defect_names = [cat.name for cat in offspring if defect_label in cat.defects]
            out(f"{slot_key} distribution: {dict(slot_counter)}")
            out(f"{defect_label} offspring: {defect_names if defect_names else '(none)'}")
        out()

    out("=" * 70)
    out("Verdict")
    out("=" * 70)
    out(
        "These family-line summaries do not prove runtime reconstruction by themselves, "
        "but they tell us whether the missing defects sit inside a repeatable parental "
        "pattern or are isolated anomalies in the current save."
    )

    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
