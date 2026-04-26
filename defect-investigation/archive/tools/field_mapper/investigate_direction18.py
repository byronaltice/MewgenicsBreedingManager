"""Direction #18 -- Discarded f64 after gender string.

In save_parser.py line 1236, after reading the gender string, the parser
calls r.f64() and throws the result away. This field has never been examined
as a potential defect flag.

The position is: T[72] → gender_token_fields (3×u32) → gender_str → f64(DISCARD) → stats.

This script:
1. Extracts the discarded f64 for all target cats.
2. Checks if its raw u64 bit pattern encodes defect slot information.
3. Roster-wide: compares value distributions for defective vs clean cats.
4. Checks if the value (interpreted as int) is a bitmask over the 15 body-part slots.
"""
from __future__ import annotations

import math
import struct
import sqlite3
import sys
from pathlib import Path
from collections import Counter

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save, BinaryReader, _VISUAL_MUTATION_FIELDS  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction18_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def raw_blob(conn, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    data = bytes(row[0])
    uncomp = struct.unpack_from("<I", data, 0)[0]
    return lz4.block.decompress(data[4:], uncompressed_size=uncomp)


def locate_t_start(raw: bytes, cat) -> int:
    fur = cat.body_parts["texture"]
    body = cat.body_parts["bodyShape"]
    head = cat.body_parts["headShape"]
    target = struct.pack("<I", fur)
    for i in range(0, len(raw) - 9 * 4):
        if raw[i:i + 4] == target:
            if struct.unpack_from("<I", raw, i + 3 * 4)[0] == body and \
               struct.unpack_from("<I", raw, i + 8 * 4)[0] == head:
                return i
    return -1


def extract_post_gender_f64(raw: bytes, cat) -> float | None:
    """Extract the discarded f64 at save_parser.py:1236."""
    t_start = locate_t_start(raw, cat)
    if t_start == -1:
        return None
    r = BinaryReader(raw, t_start + 72 * 4)
    r.skip(12)               # gender_token_fields: 3 × u32
    gender_str = r.str()     # gender string (u64-prefixed UTF-8)
    if gender_str is None:
        return None
    return r.f64()           # the discarded value


def main() -> None:
    out("=" * 70)
    out("Direction #18 -- Discarded f64 after gender string")
    out("=" * 70)
    out(f"Save: {SAVE}\n")

    save_data = parse_save(str(SAVE))
    cats = save_data.cats
    key_map = {c.db_key: c for c in cats}
    conn = sqlite3.connect(str(SAVE))

    targets = [
        ("Whommie",  853, "MISSING Eye+Eyebrow defects"),
        ("Bud",      887, "MISSING Ear defect"),
        ("Kami",     840, "CLEAN (Whommie's parent, eye=139 brow=23)"),
        ("Petronij", 841, "CLEAN (Whommie's parent)"),
        ("Flekpus",   68, "DETECTED Eyebrow defect (brow=0xFFFFFFFE)"),
        ("Romanoba",  96, "CLEAN control"),
    ]

    out("=" * 70)
    out("STEP 1 -- Discarded f64 for target cats")
    out("=" * 70)
    for name, db_key, label in targets:
        cat = key_map.get(db_key)
        if cat is None:
            out(f"  {name}: not in save")
            continue
        raw = raw_blob(conn, db_key)
        v = extract_post_gender_f64(raw, cat)
        if v is None:
            out(f"  {name}: extraction failed")
            continue
        raw_u64 = struct.pack("<d", v)
        u64_val = struct.unpack("<Q", raw_u64)[0]
        out(f"  {name:12s} ({label})")
        out(f"    f64 = {v}")
        out(f"    u64 = 0x{u64_val:016x} ({u64_val})")
        if math.isfinite(v) and v == int(v):
            out(f"    as_int = {int(v)}")
        out(f"    defects = {cat.defects}")

    out("\n" + "=" * 70)
    out("STEP 2 -- Roster-wide distribution: defective vs clean cats")
    out("=" * 70)

    defect_vals: list[tuple[float, int]] = []   # (f64, db_key)
    clean_vals: list[tuple[float, int]] = []
    errors = 0

    for cat in cats:
        try:
            raw = raw_blob(conn, cat.db_key)
            v = extract_post_gender_f64(raw, cat)
            if v is None:
                errors += 1
                continue
            if cat.defects:
                defect_vals.append((v, cat.db_key))
            else:
                clean_vals.append((v, cat.db_key))
        except Exception:
            errors += 1

    out(f"Scanned: {len(defect_vals)} defective + {len(clean_vals)} clean ({errors} errors)")
    out("")

    def_floats = [v for v, _ in defect_vals]
    clean_floats = [v for v, _ in clean_vals]

    out("Defective cats — f64 value distribution (top 10):")
    def_counter = Counter(def_floats)
    for val, count in def_counter.most_common(10):
        out(f"  {val!r:30s} : {count} cats")

    out("")
    out("Clean cats — f64 value distribution (top 10):")
    clean_counter = Counter(clean_floats)
    for val, count in clean_counter.most_common(10):
        out(f"  {val!r:30s} : {count} cats")

    out("")
    unique_to_defective = set(def_floats) - set(clean_floats)
    out(f"Values unique to defective cats: {sorted(unique_to_defective)[:20]}")
    unique_to_clean = set(clean_floats) - set(def_floats)
    out(f"Values unique to clean cats (first 20): {sorted(unique_to_clean)[:20]}")

    out("\n" + "=" * 70)
    out("STEP 3 -- Bitmask analysis: does the f64-as-integer encode defect slots?")
    out("=" * 70)
    # Defect slots: eye_L=0, eyebrow_L=1, ear_L=2, mouth_L=3, legs_L=4, arms_L=5...
    # For each cat with known defects, check if int(f64) has the right bits set
    slot_names = [field[0] for field in _VISUAL_MUTATION_FIELDS]
    out(f"Slot order: {slot_names}")
    out("")
    for name, db_key, label in targets:
        cat = key_map.get(db_key)
        if cat is None:
            continue
        raw = raw_blob(conn, db_key)
        v = extract_post_gender_f64(raw, cat)
        if v is None:
            continue
        try:
            u64_val = struct.unpack("<Q", struct.pack("<d", v))[0]
            if math.isfinite(v) and 0 < v < 2**32:
                as_int = int(v)
                bits = [i for i in range(32) if as_int & (1 << i)]
                out(f"  {name}: f64={v}, bits set={bits}, defects={cat.defects}")
            else:
                out(f"  {name}: f64={v!r} (non-integer or out of range), defects={cat.defects}")
        except Exception as e:
            out(f"  {name}: error {e}")

    out("\n" + "=" * 70)
    out("STEP 4 -- Check: cats with undetected defects (Whommie/Bud class)")
    out("  Compare their f64 against cats with detected defects of the same slot type")
    out("=" * 70)
    undetected = [c for c in cats
                  if any(c.visual_mutation_slots.get(s, 0) < 300
                         for s in ("eye_L", "eyebrow_L", "ear_L")
                         if s in c.visual_mutation_slots)]
    # This gets cats where eye/brow/ear slot values are base shapes (< 300),
    # but we want to compare against cats where the same slots are detected defects
    detected_same_type = [c for c in cats
                          if any(c.visual_mutation_slots.get(s, 0) >= 300
                                 for s in ("eye_L", "eyebrow_L", "ear_L"))]
    for c in [key_map.get(853), key_map.get(887)]:
        if c is None:
            continue
        raw = raw_blob(conn, c.db_key)
        v = extract_post_gender_f64(raw, c)
        out(f"  {c.name}: post-gender f64 = {v}")

    out("")
    # Compare with a few detected-defect cats of same slot type
    out("  Cats with detected Eye/Eyebrow/Ear defects (first 6):")
    count = 0
    for c in cats:
        if count >= 6:
            break
        slots = c.visual_mutation_slots
        has_ee = any(slots.get(s, 0) >= 300 for s in ("eye_L", "eyebrow_L", "ear_L"))
        if has_ee and c.defects:
            raw = raw_blob(conn, c.db_key)
            v = extract_post_gender_f64(raw, c)
            out(f"  {c.name:12s} db_key={c.db_key}: f64={v}, defects={c.defects[:2]}")
            count += 1

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
