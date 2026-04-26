"""Direction #11 -- Parse with GPAK visual mutation data loaded.

Earlier direction7/8/9 scripts bypassed mewgenics.__init__ and therefore
ran against EMPTY _VISUAL_MUT_DATA. With the GPAK loaded, the parser's
is_defect detection should use the GPAK's tag birth_defect flag, which
catches IDs outside the legacy 700-706 range (like Blob Legs = 707,
No Ears = 2, etc.).

Goal: confirm the *current-save* defect list for Whommie and Bud with a
fully-initialized parser, and identify any real detection gaps.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import GameData, set_visual_mut_data, parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
GPAK = ROOT / "test-saves" / "resources.gpak"
OUT = Path(__file__).parent / "direction11_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def main() -> None:
    out("=" * 70)
    out("Direction #11 -- Parser with GPAK loaded")
    out("=" * 70)

    gd = GameData.from_gpak(str(GPAK))
    set_visual_mut_data(gd.visual_mutation_data)
    out(f"Loaded {sum(len(v) for v in gd.visual_mutation_data.values())} GPAK mutation entries")

    save_data = parse_save(str(SAVE))
    cats = save_data.cats
    cat_map = {c.name: c for c in cats}

    for name in ("Whommie", "Bud", "Kami", "Romanoba", "Petronij", "Murisha"):
        cat = cat_map.get(name)
        if cat is None:
            out(f"  (missing: {name})")
            continue
        out("")
        out(f"-- {name} (db_key={cat.db_key}) --")
        out(f"  visual_mutation_slots: {cat.visual_mutation_slots}")
        out(f"  mutations: {cat.mutations}")
        out(f"  defects:   {cat.defects}")

    # Scan all cats for defects containing specific strings
    out("")
    out("=" * 70)
    out("STEP 2 -- All cats with 'Eye' or 'Eyebrow' or 'Ear' Birth Defect")
    out("=" * 70)
    for cat in cats:
        relevant = [d for d in cat.defects if any(p in d for p in ("Eye", "Eyebrow", "Ear"))]
        if relevant:
            out(f"  {cat.name:20s} db_key={cat.db_key}  defects={cat.defects}  slots=eye:{cat.visual_mutation_slots.get('eye_L')} brow:{cat.visual_mutation_slots.get('eyebrow_L')} ear:{cat.visual_mutation_slots.get('ear_L')}")

    # Also count all defect-bearing cats
    out("")
    out("=" * 70)
    out("STEP 3 -- Summary of defects across 888+ cats")
    out("=" * 70)
    from collections import Counter
    counter: Counter = Counter()
    for cat in cats:
        for d in cat.defects:
            counter[d] += 1
    for d, n in counter.most_common():
        out(f"  {n:>5}  {d}")

    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
