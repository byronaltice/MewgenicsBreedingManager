"""
Direction 27 — Locate FUN_14022cf90 data in the blob.

FUN_14022cf90 is called 3 times in SerializeCatData at CatData+0x6f0, +0x70c, +0x728.
Each call serializes 7 u32s (28 bytes = 0x1c). Together: 84 bytes total.

These records appear AFTER FUN_14022ce10 (T array = 73 u32s) in the blob.
Between T array and these records: conditional fields depending on version.

Goal: find which bytes after T_start correspond to these 3 x 7-u32 records,
and compare Whommie/Bud (defective) vs Kami (clean) to find defect signals.
"""
from __future__ import annotations

import struct
import sqlite3
import sys
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save, BinaryReader  # noqa: E402

SAVE = ROOT / "test-saves" / "investigation" / "steamcampaign01_20260424_191107.sav"
OUT  = Path(__file__).parent / "direction27_results.txt"

FOCUS = {
    'Whommie': 853,   # Eye Defect + Eyebrow Defect (UNDETECTED)
    'Kami':    840,   # Whommie's parent, clean
    'Bud':     887,   # Ear Defect (UNDETECTED)
    'Alaya':   861,   # Ear Defect DETECTED (ear_L=0xFFFFFFFE in T)
    'Petronij':841,   # Whommie's parent, clean
    'Murisha': None,  # Bud's parent, will look up
}

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


def dump_after_t(name: str, raw: bytes, t_start: int, num_u32s: int = 80):
    """Dump num_u32s u32s starting from t_start + 72*4 (after the T array)."""
    pos = t_start + 72 * 4
    out(f"\n  After T[72] ({num_u32s} u32s at blob+{pos:#x}):")
    for i in range(num_u32s):
        offset = pos + i * 4
        if offset + 4 > len(raw):
            break
        val = struct.unpack_from("<I", raw, offset)[0]
        flag = ""
        if val == 0xFFFFFFFE:
            flag = " *** NO_PART ***"
        elif val == 2:
            flag = " *** GON_BLOCK_2 ***"
        elif 700 <= val <= 710:
            flag = " *** DEFECT_RANGE ***"
        out(f"    T+{i:3d} (blob+{offset:#x}): {val:#010x} ({val:10d}){flag}")


def diff_cats(cat_a_name: str, raw_a: bytes, t_a: int,
              cat_b_name: str, raw_b: bytes, t_b: int,
              num_u32s: int = 120):
    """Show u32 differences between two cats after T[72]."""
    out(f"\n  DIFF {cat_a_name} vs {cat_b_name} (after T[72], {num_u32s} u32s):")
    pos_a = t_a + 72 * 4
    pos_b = t_b + 72 * 4
    diffs = []
    for i in range(num_u32s):
        va = struct.unpack_from("<I", raw_a, pos_a + i * 4)[0] if pos_a + i*4 + 4 <= len(raw_a) else None
        vb = struct.unpack_from("<I", raw_b, pos_b + i * 4)[0] if pos_b + i*4 + 4 <= len(raw_b) else None
        if va != vb:
            flag_a = " <NoPart>" if va == 0xFFFFFFFE else (" <gon2>" if va == 2 else "")
            flag_b = " <NoPart>" if vb == 0xFFFFFFFE else (" <gon2>" if vb == 2 else "")
            diffs.append(f"    i={i:3d}: {cat_a_name}={va:#010x}{flag_a}  {cat_b_name}={vb:#010x}{flag_b}")
    if diffs:
        for d in diffs:
            out(d)
    else:
        out(f"    (no differences in first {num_u32s} u32s)")
    return diffs


def main():
    out("Direction 27 — FUN_14022cf90 blob position analysis")
    out(f"Save: {SAVE}")

    result = parse_save(str(SAVE))
    all_cats = result[0]
    cat_by_name = {c.name: c for c in all_cats}

    conn = sqlite3.connect(str(SAVE))

    # Resolve Murisha's db_key
    murisha = cat_by_name.get('Murisha')
    if murisha:
        FOCUS['Murisha'] = murisha.db_key

    focus_cats = {}
    for name, db_key in FOCUS.items():
        if db_key is None:
            continue
        cat = next((c for c in all_cats if c.db_key == db_key), None)
        if cat is None:
            out(f"\n{name} (key={db_key}): NOT FOUND")
            continue
        raw = raw_blob(conn, db_key)
        if raw is None:
            out(f"\n{name}: NO BLOB")
            continue
        t_start = locate_t_start(raw, cat)
        if t_start < 0:
            out(f"\n{name}: CANNOT LOCATE T ARRAY")
            continue
        focus_cats[name] = (cat, raw, t_start)
        defects = list(cat.defects) if cat.defects else []
        out(f"\n{name} (db_key={db_key}): t_start={t_start:#x}  defects={defects}")

    out("\n" + "="*70)
    out("INDIVIDUAL DUMPS (first 30 u32s after T[72])")
    out("="*70)
    for name, (cat, raw, t_start) in focus_cats.items():
        out(f"\n--- {name} ---")
        dump_after_t(name, raw, t_start, num_u32s=30)

    out("\n" + "="*70)
    out("DIFFS vs KAMI")
    out("="*70)
    if 'Kami' in focus_cats:
        kami_cat, kami_raw, kami_t = focus_cats['Kami']
        for name in ('Whommie', 'Bud', 'Alaya', 'Petronij'):
            if name in focus_cats:
                cat, raw, t_start = focus_cats[name]
                diff_cats(name, raw, t_start, 'Kami', kami_raw, kami_t)

    out("\n" + "="*70)
    out("ROSTER-WIDE: look for 0xFFFFFFFE / GON block 2 in u32s after T[72]")
    out("="*70)
    hits = []
    for cat in all_cats:
        raw = raw_blob(conn, cat.db_key)
        if not raw:
            continue
        t_start = locate_t_start(raw, cat)
        if t_start < 0:
            continue
        pos = t_start + 72 * 4
        for i in range(120):
            offset = pos + i * 4
            if offset + 4 > len(raw):
                break
            val = struct.unpack_from("<I", raw, offset)[0]
            if val == 0xFFFFFFFE or val == 2:
                defects = list(cat.defects) if cat.defects else []
                hits.append((cat.name, cat.db_key, i, val, defects))

    out(f"\nTotal hits: {len(hits)}")
    for cat_name, db_key, idx, val, defects in hits[:50]:
        out(f"  {cat_name:20s} key={db_key:4d}  i={idx:3d}  val={val:#010x}  defects={defects}")

    conn.close()
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(_lines))
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
