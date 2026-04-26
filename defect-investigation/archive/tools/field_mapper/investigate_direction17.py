"""Direction #17 -- Discarded u32 after collar field.

In save_parser.py line 1204, after reading the collar string, the parser
calls r.u32() and throws the result away without storing it. This field
has never been examined as a potential defect flag.

This script:
1. Extracts the discarded u32 for all target cats + full roster.
2. Checks if it correlates with ANY defect presence (not just eye/ear/brow).
3. Also checks the full blob head region byte-by-byte for Whommie vs Kami.
4. Examines whether specific BIT positions within that u32 distinguish
   cats with undetected defects from clean cats.
"""
from __future__ import annotations

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

from save_parser import parse_save, BinaryReader  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction17_results.txt"

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


def parse_blob_head(raw: bytes) -> dict:
    """Parse blob head fields up to and including the discarded u32."""
    r = BinaryReader(raw)
    breed_id = r.u32()
    uid = r.u64()
    name = r.utf16str()
    name_tag = r.str() or ""
    personality_anchor = r.pos
    parent_uid_a = r.u64()
    parent_uid_b = r.u64()
    collar = r.str() or ""
    discarded_u32 = r.u32()
    pre_t_start = r.pos
    return {
        "breed_id": breed_id,
        "uid": uid,
        "name": name,
        "name_tag": name_tag,
        "personality_anchor": personality_anchor,
        "parent_uid_a": parent_uid_a,
        "parent_uid_b": parent_uid_b,
        "collar": collar,
        "discarded_u32": discarded_u32,
        "pre_t_start": pre_t_start,
        "pre_t_start_hex": hex(pre_t_start),
    }


def main() -> None:
    out("=" * 70)
    out("Direction #17 -- Discarded u32 after collar in blob head")
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
    out("STEP 1 -- Full blob head dump for target cats")
    out("=" * 70)
    for name, db_key, label in targets:
        raw = raw_blob(conn, db_key)
        h = parse_blob_head(raw)
        out(f"\n{name} (db_key={db_key}) — {label}")
        out(f"  breed_id       : {h['breed_id']}")
        out(f"  uid            : {h['uid']:#018x}")
        out(f"  name           : {h['name']!r}")
        out(f"  name_tag       : {h['name_tag']!r}")
        out(f"  parent_uid_a   : {h['parent_uid_a']:#018x}")
        out(f"  parent_uid_b   : {h['parent_uid_b']:#018x}")
        out(f"  collar         : {h['collar']!r}")
        out(f"  discarded_u32  : {h['discarded_u32']} (0x{h['discarded_u32']:08x})")
        out(f"  pre_t_start    : {h['pre_t_start_hex']}")
        cat = key_map.get(db_key)
        if cat:
            out(f"  detected defects: {cat.defects}")
        # Dump pre-T f64 block (8 × f64)
        out(f"  pre-T f64 values:")
        for i in range(8):
            offset = h["pre_t_start"] + i * 8
            v = struct.unpack_from("<d", raw, offset)[0]
            out(f"    f64[{i}] = {v}")

    out("\n" + "=" * 70)
    out("STEP 2 -- Roster-wide: discarded_u32 distribution")
    out("=" * 70)

    defect_vals: list[int] = []
    clean_vals: list[int] = []
    errors = 0

    for cat in cats:
        try:
            raw = raw_blob(conn, cat.db_key)
            h = parse_blob_head(raw)
            v = h["discarded_u32"]
            if cat.defects:
                defect_vals.append(v)
            else:
                clean_vals.append(v)
        except Exception as e:
            errors += 1

    out(f"Scanned {len(defect_vals)} defective + {len(clean_vals)} clean cats ({errors} errors)")
    out("")
    out("Defective cats — discarded_u32 value distribution (top 10):")
    for val, count in Counter(defect_vals).most_common(10):
        out(f"  0x{val:08x} ({val:10d}) : {count} cats")
    out("")
    out("Clean cats — discarded_u32 value distribution (top 10):")
    for val, count in Counter(clean_vals).most_common(10):
        out(f"  0x{val:08x} ({val:10d}) : {count} cats")

    out("")
    out("Unique values in defective only: " +
        str(sorted(set(defect_vals) - set(clean_vals))))
    out("Unique values in clean only: " +
        str(sorted(set(clean_vals) - set(defect_vals))[:20]))

    out("\n" + "=" * 70)
    out("STEP 3 -- Bitwise analysis: any single bit that separates defective from clean?")
    out("=" * 70)
    for bit in range(32):
        mask = 1 << bit
        def_set = sum(1 for v in defect_vals if v & mask)
        clean_set = sum(1 for v in clean_vals if v & mask)
        def_clear = len(defect_vals) - def_set
        clean_clear = len(clean_vals) - clean_set
        # Flag bits where defective cats mostly have it set/clear but clean cats don't
        def_pct = def_set / len(defect_vals) if defect_vals else 0
        clean_pct = clean_set / len(clean_vals) if clean_vals else 0
        if abs(def_pct - clean_pct) > 0.2:
            out(f"  bit {bit:2d}: defective={def_set}/{len(defect_vals)} ({def_pct:.0%}) "
                f"set,  clean={clean_set}/{len(clean_vals)} ({clean_pct:.0%}) set  "
                f"<-- DIFFERENCE {abs(def_pct - clean_pct):.0%}")

    out("\n" + "=" * 70)
    out("STEP 4 -- Full blob head hex dump: Whommie vs Kami (to pre-T)")
    out("=" * 70)
    for name, db_key, label in [("Whommie", 853, ""), ("Kami", 840, "")]:
        raw = raw_blob(conn, db_key)
        h = parse_blob_head(raw)
        end = h["pre_t_start"]
        out(f"\n{name} blob head (0x00..0x{end:02x}):")
        for chunk_start in range(0, end, 16):
            chunk = raw[chunk_start:chunk_start + 16]
            hex_str = " ".join(f"{b:02x}" for b in chunk)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            out(f"  0x{chunk_start:04x}: {hex_str:<47s}  {ascii_str}")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
