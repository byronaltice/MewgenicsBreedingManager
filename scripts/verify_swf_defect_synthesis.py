#!/usr/bin/env python3
"""
Verify that SWF-anchor-path birth defect synthesis works correctly.

Loads the test save, iterates all parsed cats, and checks:
  - Whommie (db_key=853) now has Eye + Eyebrow birth defects.
  - Bud (db_key=887) now has Ear birth defects.
  - The 17 known sentinel-path cats still have their defects, with no duplicates.
  - Reports any synthesized-defect slots that already had an is_defect entry (dedup check).

Usage:
    python scripts/verify_swf_defect_synthesis.py
"""

from __future__ import annotations

import sys
import os

# Ensure src/ is on the path so save_parser etc. are importable.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)

import save_parser
from swf_anchor_walker import (
    parse_cat_head_placements,
    missing_anchors_for_head_shape,
    ANCHOR_NAMES,
    CAT_HEAD_PLACEMENTS_CHAR_ID,
)

# ── Paths ────────────────────────────────────────────────────────────────────

SAVE_PATH = os.path.join(
    REPO_ROOT, "test-saves", "investigation",
    "steamcampaign01_20260424_191107.sav",
)

# Expected gpak path (same approach as the app uses)
_POSSIBLE_GPAK_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Mewgenics\resources.gpak"),
    os.path.join(REPO_ROOT, "defect-investigation", "game-files",
                 "resources", "resources.gpak"),
    "/mnt/c/Users/{}/.local/share/Mewgenics/resources.gpak".format(
        os.environ.get("USER", "")
    ),
]

# ── Known sentinel-path cat db_keys (from direction53 audit lines 128-150) ──

SENTINEL_DB_KEYS = frozenset({
    68, 255, 345, 492, 617, 624, 693, 711, 789, 832, 858, 861, 867, 878, 879, 885, 895,
})

# ── Canonical defect cats ────────────────────────────────────────────────────

WHOMMIE_DB_KEY = 853
BUD_DB_KEY = 887


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_gpak_path() -> str | None:
    for candidate in _POSSIBLE_GPAK_PATHS:
        if os.path.exists(candidate):
            return candidate
    return None


def _defect_slot_keys(cat) -> list[str]:
    return [str(e["slot_key"]) for e in cat.visual_mutation_entries if e.get("is_defect")]


def _defect_group_keys(cat) -> list[str]:
    return [str(e["group_key"]) for e in cat.visual_mutation_entries if e.get("is_defect")]


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 72)
    print("SWF Defect Synthesis Verification")
    print("=" * 72)

    # ── Load gpak and wire up SWF anchor data ────────────────────────────────
    gpak_path = _find_gpak_path()
    if gpak_path:
        print(f"\nGPAK found : {gpak_path}")
        game_data = save_parser.GameData.from_gpak(gpak_path)
        save_parser.set_visual_mut_data(game_data.visual_mutation_data)
        save_parser.set_class_stat_mods(game_data.class_stat_mods)
        save_parser.set_cat_head_placements_per_frame(
            game_data.cat_head_placements_per_frame
        )
        frame_count = len(game_data.cat_head_placements_per_frame)
        print(f"CatHeadPlacements frames loaded: {frame_count}")
        if frame_count == 0:
            print("WARNING: No per-frame anchor data loaded. SWF may not be in gpak.")
            print("         Synthesis will not produce any new defects.")
    else:
        print("\nWARNING: GPAK not found. Running without game data (synthesis disabled).")
        print("Checked:")
        for p in _POSSIBLE_GPAK_PATHS:
            print(f"  {p}")

    # ── Parse save ───────────────────────────────────────────────────────────
    print(f"\nSave       : {SAVE_PATH}")
    save_data = save_parser.parse_save(SAVE_PATH)
    cats = save_data.cats
    errors = save_data.errors
    print(f"Cats parsed: {len(cats)}")
    if errors:
        print(f"Parse errors: {len(errors)}")
        for err in errors[:5]:
            print(f"  {err}")

    # ── Index cats by db_key ─────────────────────────────────────────────────
    cats_by_key: dict[int, save_parser.Cat] = {cat.db_key: cat for cat in cats}

    # ── Collect overall defect statistics ────────────────────────────────────
    total_with_defects = sum(
        1 for cat in cats
        if any(e.get("is_defect") for e in cat.visual_mutation_entries)
    )
    defect_type_counts: dict[str, int] = {}
    for cat in cats:
        for entry in cat.visual_mutation_entries:
            if entry.get("is_defect"):
                group_key = str(entry["group_key"])
                defect_type_counts[group_key] = defect_type_counts.get(group_key, 0) + 1

    print(f"\nCats with at least one defect entry : {total_with_defects}")
    print("Defect counts by group_key:")
    for group_key, count in sorted(defect_type_counts.items()):
        print(f"  {group_key:12s}: {count}")

    # ── Check for cats that gained synthesized defects ───────────────────────
    # We define "synthesized" as any cat that has an is_defect entry with
    # mutation_id == 0xFFFFFFFE whose db_key is NOT in SENTINEL_DB_KEYS.
    synthesized_cats: list[tuple[int, str, list[str]]] = []
    for cat in cats:
        synth_entries = [
            e for e in cat.visual_mutation_entries
            if e.get("is_defect") and int(e["mutation_id"]) == 0xFFFF_FFFE
        ]
        if synth_entries and cat.db_key not in SENTINEL_DB_KEYS:
            # Show slot_key + name so visually-identical names are distinguishable
            slot_summaries = [f"{e['slot_key']}:{e['name']}" for e in synth_entries]
            synthesized_cats.append((cat.db_key, cat.name, slot_summaries))

    print(f"\nCats with synthesized (SWF-path) defects: {len(synthesized_cats)}")
    for db_key, name, slot_summaries in sorted(synthesized_cats):
        print(f"  db_key={db_key:4d}  name={name!r:20s}  defects={slot_summaries}")

    # ── Verify Whommie ───────────────────────────────────────────────────────
    print(f"\n--- Whommie (db_key={WHOMMIE_DB_KEY}) ---")
    whommie = cats_by_key.get(WHOMMIE_DB_KEY)
    whommie_ok = True
    if whommie is None:
        print("  NOT FOUND in save.")
        whommie_ok = False
    else:
        defect_entries = [e for e in whommie.visual_mutation_entries if e.get("is_defect")]
        defect_groups = {str(e["group_key"]) for e in defect_entries}
        print(f"  head_shape     : {whommie.body_parts.get('headShape')}")
        print(f"  defect entries : {[(str(e['slot_key']), str(e['name'])) for e in defect_entries]}")
        has_eye_defect = "eyes" in defect_groups
        has_eyebrow_defect = "eyebrows" in defect_groups
        print(f"  has Eye defect     : {has_eye_defect}")
        print(f"  has Eyebrow defect : {has_eyebrow_defect}")
        if not has_eye_defect:
            print("  ASSERTION FAILED: Whommie missing Eye birth defect")
            whommie_ok = False
        if not has_eyebrow_defect:
            print("  ASSERTION FAILED: Whommie missing Eyebrow birth defect")
            whommie_ok = False
        if whommie_ok:
            print("  PASS")

    # ── Verify Bud ───────────────────────────────────────────────────────────
    print(f"\n--- Bud (db_key={BUD_DB_KEY}) ---")
    bud = cats_by_key.get(BUD_DB_KEY)
    bud_ok = True
    if bud is None:
        print("  NOT FOUND in save.")
        bud_ok = False
    else:
        defect_entries = [e for e in bud.visual_mutation_entries if e.get("is_defect")]
        defect_groups = {str(e["group_key"]) for e in defect_entries}
        print(f"  head_shape     : {bud.body_parts.get('headShape')}")
        print(f"  defect entries : {[(str(e['slot_key']), str(e['name'])) for e in defect_entries]}")
        has_ear_defect = "ears" in defect_groups
        print(f"  has Ear defect : {has_ear_defect}")
        if not has_ear_defect:
            print("  ASSERTION FAILED: Bud missing Ear birth defect")
            bud_ok = False
        if bud_ok:
            print("  PASS")

    # ── Verify sentinel-path cats still have their defects, no duplicates ────
    print(f"\n--- Sentinel-path cats ({len(SENTINEL_DB_KEYS)} expected) ---")
    sentinel_failures: list[str] = []
    duplicate_flags: list[str] = []
    for db_key in sorted(SENTINEL_DB_KEYS):
        cat = cats_by_key.get(db_key)
        if cat is None:
            sentinel_failures.append(f"db_key={db_key}: NOT FOUND in save")
            continue
        defect_entries = [e for e in cat.visual_mutation_entries if e.get("is_defect")]
        if not defect_entries:
            sentinel_failures.append(f"db_key={db_key}: has NO defect entries (expected at least 1)")
            continue
        # Check for duplicate slot_keys within the defect entries
        slot_keys_seen: list[str] = []
        for entry in defect_entries:
            sk = str(entry["slot_key"])
            if sk in slot_keys_seen:
                duplicate_flags.append(
                    f"db_key={db_key}: duplicate defect slot_key={sk!r}"
                )
            else:
                slot_keys_seen.append(sk)

    if sentinel_failures:
        print(f"  FAILURES ({len(sentinel_failures)}):")
        for msg in sentinel_failures:
            print(f"    {msg}")
    else:
        print(f"  All {len(SENTINEL_DB_KEYS)} sentinel cats have defect entries. PASS")

    if duplicate_flags:
        print(f"  DUPLICATE defect entries detected ({len(duplicate_flags)}):")
        for msg in duplicate_flags:
            print(f"    {msg}")
    else:
        print(f"  No duplicate defect slots in sentinel cats. PASS")

    # ── Check for any cat with duplicate defect slot_keys (global) ──────────
    global_duplicates: list[str] = []
    for cat in cats:
        defect_entries = [e for e in cat.visual_mutation_entries if e.get("is_defect")]
        slot_keys_seen: list[str] = []
        for entry in defect_entries:
            sk = str(entry["slot_key"])
            if sk in slot_keys_seen:
                global_duplicates.append(
                    f"db_key={cat.db_key} name={cat.name!r}: duplicate slot_key={sk!r}"
                )
            else:
                slot_keys_seen.append(sk)
    if global_duplicates:
        print(f"\nGLOBAL DUPLICATE DEFECT SLOTS ({len(global_duplicates)}):")
        for msg in global_duplicates:
            print(f"  {msg}")
    else:
        print(f"\nNo duplicate defect slots across all {len(cats)} cats. PASS")

    # ── Final assertion summary ───────────────────────────────────────────────
    print("\n" + "=" * 72)
    all_ok = (
        whommie_ok
        and bud_ok
        and not sentinel_failures
        and not duplicate_flags
        and not global_duplicates
    )
    if all_ok:
        print("ALL ASSERTIONS PASSED")
    else:
        print("ONE OR MORE ASSERTIONS FAILED — see above")
        sys.exit(1)


if __name__ == "__main__":
    main()
