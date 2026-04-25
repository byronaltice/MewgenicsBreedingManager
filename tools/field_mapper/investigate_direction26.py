"""
Direction 26 — Per-slot serialized body-part records in the post-run gap.

FUN_14022b1f0 (from glaiel::SerializeCatData) serializes 5 body-part slots.
Each slot writes:
  u32 version (=5 current)
  u8  presence  (0=absent, 1=present)
  [if present: utf16-str + optional utf16-str + 4x u32 + 2x u8]

5 absent slots = 05 00 00 00 00 * 5 = 25 bytes.
This matches the "empty payload" found in Direction 13.

Hypothesis:
  - Cats with NO mutations/defects in a given body part → slot absent (0)
  - Cats with a mutation/defect ITEM installed → slot present (1) with strings/IDs
  - "No Part" defect cats (Whommie eye/eyebrow, Bud ear) → either a special
    absent marker or a present slot with a "no part" item string

Goal:
  1. Parse the 5 post-run slots for focus cats.
  2. Roster-wide scan: which cats have any present slot?
  3. Cross-reference with T-array detections to understand the slot system.
"""
from __future__ import annotations

import re
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
OUT  = Path(__file__).parent / "direction26_results.txt"

FOCUS_NAMES = {'Whommie', 'Bud', 'Alaya', 'Cannelle', 'Kami',
               'Emine', 'Plurb', 'Rowan', 'Petronij', 'Flekpus'}

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
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


def post_stats_pos(raw: bytes, t_start: int) -> int:
    r = BinaryReader(raw, t_start + 72 * 4)
    r.skip(12)
    length = struct.unpack_from("<Q", raw, r.pos)[0]
    r.skip(8 + int(length))
    r.skip(8)
    r.skip(7 * 4 * 3)
    return r.pos


def read_str8(raw: bytes, pos: int):
    """Read u64-prefixed UTF-8 string. Returns (str|None, new_pos)."""
    if pos + 8 > len(raw):
        return None, pos
    length = struct.unpack_from("<Q", raw, pos)[0]
    if length == 0:
        return "", pos + 8
    if length > 200 or pos + 8 + length > len(raw):
        return None, pos
    try:
        return raw[pos + 8:pos + 8 + int(length)].decode("utf-8"), pos + 8 + int(length)
    except Exception:
        return None, pos


def post_run_pos(raw: bytes, cat) -> int | None:
    """Return byte position after abilities/disorders run (after_run)."""
    t_start = locate_t_start(raw, cat)
    if t_start < 0:
        return None
    curr = post_stats_pos(raw, t_start)

    marker = raw.find(b"DefaultMove", curr, curr + 700)
    if marker == -1:
        return None
    run_start = marker - 8

    pos = run_start
    for _ in range(32):
        s, new_pos = read_str8(raw, pos)
        if s is None or not _IDENT_RE.match(s):
            break
        pos = new_pos

    # passive1 tier u32
    if pos + 4 <= len(raw):
        pos += 4

    # 3 tail (str, u32) pairs
    for _ in range(3):
        s, new_pos = read_str8(raw, pos)
        if s is None or not _IDENT_RE.match(s):
            break
        if new_pos + 4 > len(raw):
            break
        pos = new_pos + 4

    return pos


# ---------------------------------------------------------------------------
# Slot parser — matches FUN_14022b1f0 (version 5 format)
# ---------------------------------------------------------------------------

def parse_one_slot(raw: bytes, pos: int):
    """
    Parse one slot record.
    Returns (bytes_consumed, version, present:bool, info:dict|None).
    """
    if pos + 5 > len(raw):
        return 0, None, False, None
    version = struct.unpack_from("<I", raw, pos)[0]
    presence = raw[pos + 4]

    if version > 20 or version == 0:
        # Sanity check: slot version should be small
        return 0, None, False, None

    if presence == 0:
        return 5, version, False, None
    if presence != 1:
        return 0, version, False, None

    # Present slot — parse fields
    info: dict = {}
    cur = pos + 5

    def r_utf16(p):
        if p + 8 > len(raw):
            return '<eof>', p
        length = struct.unpack_from("<Q", raw, p)[0]
        p += 8
        if length == 0:
            return '', p
        if length > 500 or p + length * 2 > len(raw):
            return f'<bad len={length}>', p
        s = raw[p:p + length * 2].decode('utf-16-le', errors='replace')
        return s, p + length * 2

    def r_u32(p):
        if p + 4 > len(raw):
            return None, p
        return struct.unpack_from("<I", raw, p)[0], p + 4

    def r_u8(p):
        if p >= len(raw):
            return None, p
        return raw[p], p + 1

    # str1 always (item category/name)
    info['str1'], cur = r_utf16(cur)
    # str2 if version >= 2
    if version >= 2:
        info['str2'], cur = r_utf16(cur)
    # 3 u32s always (indices in T array per prior research: mutation_id, fur_echo, unk)
    info['u32_a'], cur = r_u32(cur)   # param_1+9
    info['u32_b'], cur = r_u32(cur)   # param_1+0x4c
    info['u32_c'], cur = r_u32(cur)   # param_1+10
    if version >= 3:
        info['u32_d'], cur = r_u32(cur)  # param_1+0x54
    if version >= 4:
        info['u8_a'],  cur = r_u8(cur)   # param_1+0xb
    if version >= 5:
        info['u8_b'],  cur = r_u8(cur)   # param_1+0x5c

    return cur - pos, version, True, info


def parse_five_slots(raw: bytes, pos: int):
    """Parse 5 consecutive slot records. Returns list of (version, present, info)."""
    slots = []
    cur = pos
    for _ in range(5):
        n, version, present, info = parse_one_slot(raw, cur)
        if n == 0:
            slots.append(('ERROR', False, None))
            break
        slots.append((version, present, info))
        cur += n
    return slots, cur


# ---------------------------------------------------------------------------
# Focus cat analysis
# ---------------------------------------------------------------------------

def analyze_cat(name: str, cat, raw: bytes):
    out(f"\n=== {name} (db_key={cat.db_key}) ===")

    detected_defects = list(cat.defects) if cat.defects else []
    out(f"  detected defects: {detected_defects or 'none'}")

    # Show relevant T-array slots for context
    relevant = {}
    for slot_name, slot_info in cat.body_parts.items():
        if slot_name in ('eye_L', 'eye_R', 'eyebrow_L', 'eyebrow_R',
                         'ear_L', 'ear_R', 'mouth', 'texture'):
            relevant[slot_name] = slot_info
    out(f"  body_parts: {relevant}")

    ar = post_run_pos(raw, cat)
    if ar is None:
        out("  ERROR: could not locate after_run")
        return

    out(f"  after_run pos: {ar:#x}  blob_len: {len(raw):#x}")
    out(f"  first 40 bytes of gap: {raw[ar:ar+40].hex()}")

    slots, end_pos = parse_five_slots(raw, ar)
    for i, (ver, present, info) in enumerate(slots):
        if ver == 'ERROR':
            out(f"  slot[{i}]: PARSE ERROR")
        elif not present:
            out(f"  slot[{i}]: v={ver} ABSENT")
        else:
            out(f"  slot[{i}]: v={ver} PRESENT  {info}")

    remainder = raw[end_pos:end_pos + 20]
    out(f"  bytes after 5 slots: {remainder.hex()}")


# ---------------------------------------------------------------------------
# Roster scan
# ---------------------------------------------------------------------------

def roster_scan(all_cats, conn):
    out("\n\n=== ROSTER SCAN: cats with >=1 present slot ===")
    present_cats = []

    for cat in all_cats:
        raw = raw_blob(conn, cat.db_key)
        if not raw:
            continue
        ar = post_run_pos(raw, cat)
        if ar is None:
            continue
        # Quick check: is the first 5 bytes NOT the absent pattern?
        absent_5 = bytes([5, 0, 0, 0, 0])
        has_present = False
        pos = ar
        for _ in range(5):
            if pos + 5 > len(raw):
                break
            ver = struct.unpack_from("<I", raw, pos)[0]
            pres = raw[pos + 4] if pos + 4 < len(raw) else 0
            if ver > 20 or ver == 0:
                break
            if pres == 1:
                has_present = True
                break
            pos += 5  # skip absent slot

        if has_present:
            defect_str = ', '.join(str(d) for d in cat.defects) if cat.defects else 'none'
            muts = [f"{k}={v:#x}" for k, v in cat.body_parts.items()
                    if v not in (0, 0xFFFFFFFF) and k not in ('texture','bodyShape','headShape','fur_variant')]
            present_cats.append((cat.name, cat.db_key, defect_str, raw[ar:ar+60].hex()))

    out(f"Cats with present slot(s): {len(present_cats)}")
    for name, key, defects, gap_hex in present_cats[:80]:
        out(f"  {name:20s} key={key:4d}  defects=[{defects}]")
        out(f"    gap: {gap_hex}")


def main():
    out("Direction 26 — Post-run slot record analysis")
    out(f"Save: {SAVE}")

    result = parse_save(str(SAVE))
    all_cats = result[0]
    cat_by_name = {c.name: c for c in all_cats}

    conn = sqlite3.connect(str(SAVE))

    out("\n--- Focus cats ---")
    for name in sorted(FOCUS_NAMES):
        cat = cat_by_name.get(name)
        if cat is None:
            out(f"\n=== {name}: NOT IN SAVE ===")
            continue
        raw = raw_blob(conn, cat.db_key)
        if raw is None:
            out(f"\n=== {name}: NO BLOB ===")
            continue
        analyze_cat(name, cat, raw)

    roster_scan(all_cats, conn)
    conn.close()

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(_lines))
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
