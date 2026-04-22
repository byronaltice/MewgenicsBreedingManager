"""Direction #7 -- Structured exploration of passives, abilities, disorders,
stat_mod for Whommie and Bud vs. clean controls.

Hypothesis: Since byte-level diffs have been exhausted, the defect flag may be
encoded as a *value* in a structured field (passive ability string, stat_mod,
disorder string) rather than at a fixed byte offset.

This script dumps parsed fields side-by-side for defective and clean cats and
searches for value-level differentiators.
"""
from __future__ import annotations

import os
import sys
import struct
import sqlite3
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from save_parser import parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction7_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    print(msg)
    _lines.append(msg)


DEFECTIVE_NAMES = ["Whommie", "Bud"]
# Known clean cats with matching base-shape IDs (eye=139, eyebrow=23, ear=132)
CONTROL_NAMES = ["Kami", "Romanoba", "Petronij", "Murisha"]


def raw_blob_for(conn, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    if not row:
        return b""
    data = bytes(row[0])
    uncomp = struct.unpack_from("<I", data, 0)[0]
    return lz4.block.decompress(data[4:], uncompressed_size=uncomp)


def dump_cat(cat, label: str, raw: bytes) -> None:
    out(f"-- {label}: {cat.name} (db_key={cat.db_key}, breed={cat.breed_id}) --")
    out(f"  blob_len={len(raw)}")
    out(f"  abilities ({len(cat.abilities)}): {cat.abilities}")
    out(f"  passives ({len(cat.passive_abilities)}): {cat.passive_abilities}")
    out(f"  passive_tiers: {cat.passive_tiers}")
    out(f"  disorders ({len(cat.disorders)}): {cat.disorders}")
    out(f"  stat_base: {cat.stat_base}")
    out(f"  stat_mod:  {cat.stat_mod}")
    out(f"  stat_sec:  {cat.stat_sec}")
    out(f"  mutations: {cat.mutations}")
    out(f"  defects:   {cat.defects}")
    out(f"  visual_mutation_slots: {cat.visual_mutation_slots}")


def all_strings_in_blob(raw: bytes) -> set[str]:
    """Extract plausible identifier strings from a raw blob.

    GON-format save strings are u32 length + u32 zero-pad + UTF-8 bytes.
    Scan the blob for (length, 0) pairs followed by a valid identifier.
    """
    found: set[str] = set()
    i = 0
    while i + 8 < len(raw):
        length = struct.unpack_from("<I", raw, i)[0]
        zero = struct.unpack_from("<I", raw, i + 4)[0]
        if 0 < length < 128 and zero == 0 and i + 8 + length <= len(raw):
            try:
                candidate = raw[i + 8:i + 8 + length].decode("utf-8")
                if candidate and all(32 <= ord(c) < 127 for c in candidate):
                    found.add(candidate)
                    i += 8 + length
                    continue
            except UnicodeDecodeError:
                pass
        i += 1
    return found


def main() -> None:
    out("=" * 70)
    out("Direction #7 -- Structured field comparison")
    out("=" * 70)
    out(f"Save: {SAVE}")
    out("")

    save_data = parse_save(str(SAVE))
    cats = save_data.cats
    errors = save_data.errors
    if errors:
        out(f"Parser errors: {errors[:3]}")
    cat_map = {c.name: c for c in cats}

    conn = sqlite3.connect(str(SAVE))

    defective = [cat_map[n] for n in DEFECTIVE_NAMES if n in cat_map]
    controls = [cat_map[n] for n in CONTROL_NAMES if n in cat_map]

    out(f"Found {len(defective)} defective cats and {len(controls)} controls\n")

    out("=" * 70)
    out("STEP 1 -- Per-cat dump")
    out("=" * 70)
    for cat in defective + controls:
        raw = raw_blob_for(conn, cat.db_key)
        dump_cat(cat, "DEFECT" if cat in defective else "CLEAN ", raw)
        out("")

    out("=" * 70)
    out("STEP 2 -- Passive/disorder/ability strings unique to defective cats")
    out("=" * 70)
    defect_strings: set[str] = set()
    for cat in defective:
        for lst in (cat.passive_abilities, cat.disorders, cat.abilities):
            defect_strings.update(lst)
    control_strings: set[str] = set()
    for cat in controls:
        for lst in (cat.passive_abilities, cat.disorders, cat.abilities):
            control_strings.update(lst)
    only_in_defect = defect_strings - control_strings
    only_in_clean = control_strings - defect_strings
    out(f"Strings unique to defective cats: {sorted(only_in_defect)}")
    out(f"Strings unique to clean controls: {sorted(only_in_clean)}")
    out("")

    out("=" * 70)
    out("STEP 3 -- ALL plausible strings inside raw blobs")
    out("=" * 70)
    defect_blob_strings: dict[str, set[str]] = {}
    for cat in defective:
        raw = raw_blob_for(conn, cat.db_key)
        defect_blob_strings[cat.name] = all_strings_in_blob(raw)
    control_blob_strings: dict[str, set[str]] = {}
    for cat in controls:
        raw = raw_blob_for(conn, cat.db_key)
        control_blob_strings[cat.name] = all_strings_in_blob(raw)

    shared_defect = set.intersection(*defect_blob_strings.values()) if defect_blob_strings else set()
    any_control = set.union(*control_blob_strings.values()) if control_blob_strings else set()
    candidate = shared_defect - any_control
    out(f"Strings shared by ALL defective cats but NOT found in ANY control: {sorted(candidate)}")
    out("")
    for name, strings in defect_blob_strings.items():
        only_this = strings - any_control
        out(f"  Strings unique to {name}'s blob (vs all controls): {sorted(only_this)}")
    out("")

    out("=" * 70)
    out("STEP 4 -- stat_mod / stat_sec patterns")
    out("=" * 70)
    STATS = ["STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK"]
    out("  Whommie should have -2 CHA from eyebrow defect")
    out("  Bud should have -2 DEX from ear defect")
    out("")
    for cat in defective + controls:
        out(f"  {cat.name:12s} stat_mod={dict(zip(STATS, cat.stat_mod))}")
    out("")

    conn.close()

    OUT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
