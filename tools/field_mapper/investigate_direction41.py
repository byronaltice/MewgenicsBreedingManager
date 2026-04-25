"""
Direction 41 — Check whether stat_mod already encodes hidden defect penalties.

Hypothesis: the game applies birth-defect stat penalties (e.g. -2 CHA for Eyebrow
Birth Defect, -2 DEX for Ear Birth Defect) at breed/save time and writes them into
stat_mod[]. If so, the parser already reads those deltas via stat_base/stat_mod/stat_sec;
we just need to verify that "actual stat_mod - expected stat_mod from visible mutations"
reveals the hidden -2 CHA (Whommie) and -2 DEX (Bud).

Five reference cats:
  Whommie  db_key=853  defect+  (expected hidden: -2 CHA blind)
  Bud      db_key=887  defect+  (expected hidden: -2 DEX)
  Kami     db_key=840  control
  Petronij db_key=841  control
  Murisha  db_key=852  control

Also checks Cat attributes for any "blind"-like status on Whommie.

Output: tools/field_mapper/direction41_results.txt
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import STAT_NAMES, parse_save  # noqa: E402

DEFAULT_SAVE = ROOT / "test-saves" / "investigation" / "steamcampaign01_20260424_191107.sav"
SAVE = Path(os.environ.get("INVESTIGATION_SAVE", str(DEFAULT_SAVE)))
OUT = Path(__file__).parent / "direction41_results.txt"

FOCUS: dict[str, int] = {
    "Whommie":  853,
    "Bud":      887,
    "Kami":     840,
    "Petronij": 841,
    "Murisha":  852,
}
DEFECT_POSITIVE = {853, 887}
CLEAN_CONTROLS  = {840, 841, 852}

# Regex: capture signed integer + stat name (case-insensitive, GON aliases included)
# e.g. "-2 CHA", "+1 STR", "-2 dex", "1 str"
_STAT_DELTA_RE = re.compile(
    r"([+-]?\d+)\s*(STR|DEX|CON|INT|SPD|CHA|LCK|speed|spd)\b",
    re.IGNORECASE,
)
_STAT_ALIAS: dict[str, str] = {
    "str": "STR", "dex": "DEX", "con": "CON", "int": "INT",
    "spd": "SPD", "speed": "SPD", "cha": "CHA", "lck": "LCK",
}

_lines: list[str] = []


def out(message: str = "") -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", "replace").decode())
    _lines.append(message)


def parse_stat_deltas_from_desc(stat_desc: str) -> dict[str, int]:
    """Extract per-stat deltas from a mutation's stat_desc string."""
    result: dict[str, int] = {s: 0 for s in STAT_NAMES}
    for match in _STAT_DELTA_RE.finditer(stat_desc):
        value_str, stat_raw = match.group(1), match.group(2)
        canonical = _STAT_ALIAS.get(stat_raw.lower(), stat_raw.upper())
        if canonical in result:
            result[canonical] += int(value_str)
    return result


def expected_stat_mod_from_mutations(cat) -> dict[str, int]:
    """
    Sum stat deltas from all visible mutations (entries with non-empty detail).
    Also include class stat_mods if loaded.
    Skips entries whose detail is blank or purely descriptive (no numeric deltas).
    """
    totals: dict[str, int] = {s: 0 for s in STAT_NAMES}

    entries = getattr(cat, "visual_mutation_entries", []) or []
    for entry in entries:
        detail = str(entry.get("detail", "")).strip()
        if not detail:
            continue
        deltas = parse_stat_deltas_from_desc(detail)
        for stat, delta in deltas.items():
            totals[stat] += delta

    # Class stat mods are also applied to stat_mod in-game (per Direction 29 / parser code)
    class_mods: dict[str, int] = getattr(cat, "class_stat_mods", {}) or {}
    for stat, delta in class_mods.items():
        if stat in totals:
            totals[stat] += delta

    return totals


def check_blind_attributes(cat) -> list[str]:
    """Return any attribute names/values that hint at 'blind' or vision impairment."""
    hits: list[str] = []
    for attr_name in dir(cat):
        if attr_name.startswith("__"):
            continue
        if "blind" in attr_name.lower() or "vision" in attr_name.lower():
            try:
                val = getattr(cat, attr_name)
                hits.append(f"  attr '{attr_name}' = {val!r}")
            except Exception:
                pass

    # Also scan string-valued attributes for the word "blind"
    for attr_name in ("passive_abilities", "abilities", "disorders", "defects", "mutations"):
        val = getattr(cat, attr_name, None)
        if isinstance(val, (list, tuple)):
            for item in val:
                if isinstance(item, str) and "blind" in item.lower():
                    hits.append(f"  {attr_name} contains {item!r}")
        elif isinstance(val, str) and "blind" in val.lower():
            hits.append(f"  attr '{attr_name}' = {val!r}")

    # Check passive_tiers for blind-related keys
    passive_tiers: dict = getattr(cat, "passive_tiers", {}) or {}
    for key in passive_tiers:
        if "blind" in str(key).lower():
            hits.append(f"  passive_tiers key {key!r} = {passive_tiers[key]!r}")

    return hits


def dump_cat(cat, label: str) -> None:
    actual   = {s: cat.stat_mod[i]  for i, s in enumerate(STAT_NAMES)}
    expected = expected_stat_mod_from_mutations(cat)
    delta    = {s: actual[s] - expected[s] for s in STAT_NAMES}

    marker = "[DEFECT+]" if cat.db_key in DEFECT_POSITIVE else "[CONTROL]"
    out(f"\n{'='*60}")
    out(f"{label} (db_key={cat.db_key}) {marker}  class={cat.cat_class!r}")

    out(f"\n  Visible mutation entries ({len(getattr(cat, 'visual_mutation_entries', []))} total):")
    entries = getattr(cat, "visual_mutation_entries", []) or []
    if entries:
        for entry in entries:
            out(f"    slot={entry['slot_key']}  id={entry['mutation_id']}  "
                f"name={entry['name']!r}  detail={entry['detail']!r}  "
                f"defect={entry['is_defect']}")
    else:
        out("    (none)")

    out(f"\n  Class stat_mods: {getattr(cat, 'class_stat_mods', {})}")

    header = f"  {'Stat':<6} {'actual':>8} {'expected':>9} {'delta':>7}"
    out(header)
    out(f"  {'-'*34}")
    nonzero_deltas: list[str] = []
    for stat in STAT_NAMES:
        a, e, d = actual[stat], expected[stat], delta[stat]
        flag = "  <<< UNEXPLAINED" if d != 0 else ""
        out(f"  {stat:<6} {a:>8} {e:>9} {d:>7}{flag}")
        if d != 0:
            nonzero_deltas.append(f"{stat}:{d:+d}")

    if nonzero_deltas:
        out(f"\n  Non-zero deltas: {', '.join(nonzero_deltas)}")
    else:
        out(f"\n  All deltas zero.")

    blind_hits = check_blind_attributes(cat)
    if blind_hits:
        out(f"\n  Blind/vision-related attributes found:")
        for h in blind_hits:
            out(h)
    else:
        out(f"\n  No blind/vision attributes found.")

    out(f"\n  stat_base : {cat.stat_base}")
    out(f"  stat_mod  : {cat.stat_mod}")
    out(f"  stat_sec  : {cat.stat_sec}")


def summary(all_cats) -> None:
    out("\n\n" + "="*60)
    out("SUMMARY")
    out("="*60)

    cat_map: dict[int, object] = {c.db_key: c for c in all_cats}
    whommie = cat_map.get(853)
    bud     = cat_map.get(887)

    for label in ("Whommie / CHA (expected -2)", "Bud / DEX (expected -2)"):
        out(f"\n  {label}")

    if whommie:
        expected_w = expected_stat_mod_from_mutations(whommie)
        delta_cha  = whommie.stat_mod[STAT_NAMES.index("CHA")] - expected_w["CHA"]
        out(f"  Whommie CHA: actual={whommie.stat_mod[STAT_NAMES.index('CHA')]}  "
            f"expected={expected_w['CHA']}  delta={delta_cha:+d}")
        out(f"  Whommie CHA unexplained -2? {'YES' if delta_cha == -2 else 'NO'} (delta={delta_cha:+d})")
    else:
        out("  Whommie not found")

    if bud:
        expected_b = expected_stat_mod_from_mutations(bud)
        delta_dex  = bud.stat_mod[STAT_NAMES.index("DEX")] - expected_b["DEX"]
        out(f"  Bud DEX: actual={bud.stat_mod[STAT_NAMES.index('DEX')]}  "
            f"expected={expected_b['DEX']}  delta={delta_dex:+d}")
        out(f"  Bud DEX unexplained -2? {'YES' if delta_dex == -2 else 'NO'} (delta={delta_dex:+d})")
    else:
        out("  Bud not found")

    # Controls: any nonzero delta?
    out(f"\n  Control deltas:")
    for db_key, label in [(840, "Kami"), (841, "Petronij"), (852, "Murisha")]:
        cat = cat_map.get(db_key)
        if not cat:
            out(f"    {label}: not found")
            continue
        expected = expected_stat_mod_from_mutations(cat)
        deltas = {s: cat.stat_mod[i] - expected[s] for i, s in enumerate(STAT_NAMES)}
        nonzero = {s: d for s, d in deltas.items() if d != 0}
        if nonzero:
            out(f"    {label}: NON-ZERO deltas: {nonzero}")
        else:
            out(f"    {label}: all deltas zero")


def main() -> None:
    out("Direction 41 — stat_mod vs expected-from-visible-mutations delta check")
    out(f"Save: {SAVE}")

    save_data = parse_save(str(SAVE))
    all_cats = save_data[0] if isinstance(save_data, tuple) else save_data.cats
    out(f"Total cats: {len(all_cats)}")

    cat_map: dict[int, object] = {c.db_key: c for c in all_cats}

    for label, db_key in FOCUS.items():
        cat = cat_map.get(db_key)
        if cat is None:
            out(f"\n{label} (db_key={db_key}): NOT FOUND")
            continue
        dump_cat(cat, label)

    summary(all_cats)

    OUT.write_text("\n".join(_lines), encoding="utf-8")
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
