"""
Direction #2 Investigation Script -- Blob Tail Bitmap / Flag Hunt

Phases covered:
  1. Extract and hex-dump the 115-byte blob tail per cat.
  2. Byte-level diff to identify defect-correlated offsets.
  3. Bitmap interpretation test (2-byte u16, 4-byte u32 at every position).
  4. Per-slot byte/u16/u32 window test.
  5. Expanded scan over all unmapped blob regions.
  6. SQLite cross-table check.

Usage:
    py tools/field_mapper/investigate_blob_tail.py

Output written to tools/field_mapper/blob_tail_results.txt as well as stdout.
"""

import struct
import sqlite3
import sys
import os
import math
import io
import csv
import lz4.block

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..'))
_WORKTREE_REPO_ROOT = os.path.abspath(os.path.join(_REPO_ROOT, '..', '..', '..'))
SAVE_PATH = (
    os.path.join(_REPO_ROOT, 'test-saves', 'steamcampaign01.sav')
    if os.path.exists(os.path.join(_REPO_ROOT, 'test-saves', 'steamcampaign01.sav'))
    else os.path.join(_WORKTREE_REPO_ROOT, 'test-saves', 'steamcampaign01.sav')
)

sys.path.insert(0, os.path.join(_SCRIPT_DIR, '..', '..', 'src'))
from save_parser import BinaryReader, parse_save

TAIL_SIZE = 115  # _CLASS_STRING_TAIL_OFFSET

# Cats: name -> (role, expected defective slot indices per SLOT_NAMES order)
# Slot order: fur=0, body=1, head=2, tail=3, leg_L=4, leg_R=5, arm_L=6, arm_R=7,
#             eye_L=8, eye_R=9, eyebrow_L=10, eyebrow_R=11, ear_L=12, ear_R=13, mouth=14
TARGET_CATS = {
    'Whommie':  ('positive-2', [8, 9, 10, 11]),   # eye + eyebrow
    'Bud':      ('positive-1', [12, 13]),           # ear
    'Kami':     ('negative',   []),
    'Petronij': ('parent',     []),
    'Romanoba': ('control',    []),
}

SLOT_NAMES = [
    'fur', 'body', 'head', 'tail_slot',
    'leg_L', 'leg_R', 'arm_L', 'arm_R',
    'eye_L', 'eye_R', 'eyebrow_L', 'eyebrow_R',
    'ear_L', 'ear_R', 'mouth',
]
NUM_SLOTS = len(SLOT_NAMES)


def hex_dump(data: bytes, start_offset: int = 0, label: str = "") -> str:
    lines = []
    if label:
        lines.append(f"  [{label}]")
    for row in range(0, len(data), 16):
        chunk = data[row:row + 16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f"  {start_offset + row:04x}: {hex_part:<47}  |{ascii_part}|")
    return '\n'.join(lines)


def decompress_blob(raw_blob: bytes) -> bytes:
    uncomp_size = struct.unpack_from('<I', raw_blob, 0)[0]
    return lz4.block.decompress(raw_blob[4:], uncompressed_size=uncomp_size)


def get_blob_tail(blob: bytes) -> bytes:
    return blob[-TAIL_SIZE:]


def get_parsed_regions(blob: bytes):
    """
    Run BinaryReader up through the T array to know the consumed region.
    Returns (pre_t_end, t_end) as blob offsets.
    """
    r = BinaryReader(blob)
    r.u32()       # breed_id
    r.u64()       # uid
    r.utf16str()  # name
    r.str()       # name_tag
    r.u64()       # parent_uid_a
    r.u64()       # parent_uid_b
    r.str()       # collar
    r.u32()       # unnamed u32
    pre_t_end = r.pos + 64  # after skip(64)
    t_end = pre_t_end + 72 * 4  # after T[72]
    return pre_t_end, t_end


def check_bitmap_at_offset(tail: bytes, offset: int, width: int,
                           expected_defect_slots: list[int]) -> bool:
    """
    Return True if the value at tail[offset:offset+width] matches
    the expected_defect_slots bitmap (bit N set <=> slot N is defective).
    width is 1, 2, or 4 bytes.
    """
    if offset + width > len(tail):
        return False
    fmt = {1: '<B', 2: '<H', 4: '<I'}[width]
    val = struct.unpack_from(fmt, tail, offset)[0]
    if not expected_defect_slots:
        return val == 0
    expected_mask = sum(1 << s for s in expected_defect_slots)
    return val == expected_mask


def check_inverted_bitmap_at_offset(tail: bytes, offset: int, width: int,
                                    expected_defect_slots: list[int]) -> bool:
    """Same but inverted polarity: 0 bit = defective."""
    if offset + width > len(tail):
        return False
    fmt = {1: '<B', 2: '<H', 4: '<I'}[width]
    val = struct.unpack_from(fmt, tail, offset)[0]
    all_slots_mask = (1 << NUM_SLOTS) - 1
    expected_mask = all_slots_mask ^ sum(1 << s for s in expected_defect_slots)
    masked = val & all_slots_mask
    return masked == expected_mask


def main():
    output_lines = []

    def out(line=""):
        print(line)
        output_lines.append(line)

    out("=" * 70)
    out("Direction #2 -- Blob Tail Bitmap / Flag Hunt")
    out("=" * 70)

    # Load save and extract cat data
    result = parse_save(SAVE_PATH)
    all_cats = result[0]
    cat_map = {c.name: c for c in all_cats}

    conn = sqlite3.connect(SAVE_PATH)

    cat_data: dict[str, dict] = {}
    for name, (role, expected_slots) in TARGET_CATS.items():
        cat = cat_map.get(name)
        if cat is None:
            out(f"WARNING: cat '{name}' not found -- skipping")
            continue
        row = conn.execute("SELECT data FROM cats WHERE key=?", (cat.db_key,)).fetchone()
        blob = decompress_blob(bytes(row[0]))
        tail = get_blob_tail(blob)
        tail_offset = len(blob) - TAIL_SIZE
        pre_t_end, t_end = get_parsed_regions(blob)
        cat_data[name] = {
            'cat': cat,
            'blob': blob,
            'tail': tail,
            'tail_offset': tail_offset,
            'pre_t_end': pre_t_end,
            't_end': t_end,
            'role': role,
            'expected_slots': expected_slots,
        }

    # ── Phase 1: Hex dumps of tail ────────────────────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 1 -- 115-byte Blob Tail Hex Dumps")
    out("-" * 70)

    for name, d in cat_data.items():
        out()
        out(f"  {name}  [{d['role']}]  (tail starts at blob[0x{d['tail_offset']:04x}],"
            f"  blob_len={len(d['blob'])})")
        out(hex_dump(d['tail'], start_offset=0, label="tail offset 0..114"))

        # Annotate known fields within the tail
        out("  Known tail sub-fields:")
        f64_val = struct.unpack_from('<d', d['tail'], 4)[0]
        out(f"    +4  f64        = {f64_val:.8f}  (0x{struct.unpack_from('<Q', d['tail'], 4)[0]:016x})")
        creation_day = struct.unpack_from('<I', d['tail'], 12)[0]
        out(f"    +12 creation_day u32 = {creation_day}")
        constant_region = d['tail'][20:28]
        out(f"    +20 constant 8 bytes = {constant_region.hex()}")

    # ── Phase 1b: Full tail as u32 array ─────────────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 1b -- Tail as u32 array (28 full u32s)")
    out("-" * 70)
    for name, d in cat_data.items():
        u32s = list(struct.unpack_from('<28I', d['tail'], 0))
        out(f"  {name}: {u32s}")

    # ── Phase 2: Byte-level diff ──────────────────────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 2 -- Byte-level Diff Across Cats")
    out("-" * 70)

    names = list(cat_data.keys())
    positive_names = [n for n, d in cat_data.items() if d['expected_slots']]
    negative_names = [n for n, d in cat_data.items() if not d['expected_slots']]

    out(f"  Defective cats: {positive_names}")
    out(f"  Clean cats: {negative_names}")
    out()
    out("  Bytes that differ between ANY defective cat and ANY clean cat:")
    out(f"  {'Offset':>7}  " + "  ".join(f"{n:>10}" for n in names) +
        "  (dec values)")

    defect_correlated = []
    for i in range(TAIL_SIZE):
        pos_vals = {cat_data[n]['tail'][i] for n in positive_names if n in cat_data}
        neg_vals  = {cat_data[n]['tail'][i] for n in negative_names if n in cat_data}
        all_vals  = {cat_data[n]['tail'][i] for n in names if n in cat_data}
        if len(all_vals) == 1:
            continue  # completely constant -- skip
        # Check if at least one positive differs from all negatives
        if pos_vals & neg_vals != pos_vals:  # positives not fully contained in negatives
            row_vals = "  ".join(f"{'0x'+format(cat_data[n]['tail'][i], '02x'):>10}"
                                 for n in names if n in cat_data)
            out(f"  +{i:>5}  {row_vals}")
            defect_correlated.append(i)

    if not defect_correlated:
        out("  (none found -- all varying bytes appear in both defective and clean cats)")
    else:
        out(f"\n  {len(defect_correlated)} defect-correlated offsets: {defect_correlated}")

    # ── Phase 2b: All varying bytes (regardless of defect correlation) ────────
    out()
    out("  All varying bytes in tail (including non-defect-correlated):")
    out(f"  {'Offset':>7}  " + "  ".join(f"{n:>10}" for n in names))
    all_varying = []
    for i in range(TAIL_SIZE):
        vals = [cat_data[n]['tail'][i] for n in names if n in cat_data]
        if len(set(vals)) > 1:
            all_varying.append(i)
            row_vals = "  ".join(f"{'0x'+format(cat_data[n]['tail'][i], '02x'):>10}"
                                 for n in names if n in cat_data)
            out(f"  +{i:>5}  {row_vals}")

    # ── Phase 3: Bitmap scan ──────────────────────────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 3 -- Bitmap Interpretation Scan")
    out("-" * 70)
    out("  Scanning every u8/u16/u32 position in the tail for a bitmap")
    out("  matching expected defect slots...")
    out()

    # Expected bitmasks per cat
    expected_masks = {n: sum(1 << s for s in d['expected_slots'])
                      for n, d in cat_data.items()}
    all_slots_mask = (1 << NUM_SLOTS) - 1

    bitmap_hits = []
    for width in (1, 2, 4):
        fmt = {1: '<B', 2: '<H', 4: '<I'}[width]
        stride = width
        for offset in range(0, TAIL_SIZE - width + 1, stride):
            # Check normal polarity: 1 bit = defective
            match = True
            for name, d in cat_data.items():
                val = struct.unpack_from(fmt, d['tail'], offset)[0]
                expected = expected_masks[name]
                if width < 4:
                    if val != expected:
                        match = False
                        break
                else:
                    # For u32, only check low NUM_SLOTS bits
                    if (val & all_slots_mask) != expected:
                        match = False
                        break
            if match:
                sample_val = struct.unpack_from(fmt, cat_data[names[0]]['tail'], offset)[0]
                out(f"  HIT (normal) u{width*8} at tail+{offset}: "
                    f"matches expected defect bitmask per cat!")
                for name in names:
                    val = struct.unpack_from(fmt, cat_data[name]['tail'], offset)[0]
                    out(f"    {name}: 0x{val:0{width*2}x} = {bin(val)}")
                bitmap_hits.append(('normal', width * 8, offset))

            # Check inverted polarity: 0 bit = defective
            inv_match = True
            for name, d in cat_data.items():
                val = struct.unpack_from(fmt, d['tail'], offset)[0]
                expected_inv = all_slots_mask ^ expected_masks[name]
                if (val & all_slots_mask) != expected_inv:
                    inv_match = False
                    break
            if inv_match:
                out(f"  HIT (inverted) u{width*8} at tail+{offset}: "
                    f"matches INVERTED defect bitmask per cat!")
                for name in names:
                    val = struct.unpack_from(fmt, cat_data[name]['tail'], offset)[0]
                    out(f"    {name}: 0x{val:0{width*2}x} = {bin(val)}")
                bitmap_hits.append(('inverted', width * 8, offset))

    if not bitmap_hits:
        out("  No bitmap matches found at any position.")

    # ── Phase 4: Per-slot byte/u16/u32 window scan ────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 4 -- Per-Slot Array Window Scan")
    out("-" * 70)
    out("  Scanning every N-byte window for a per-slot array where defective")
    out("  slots are non-zero (defective cat) or zero (clean cat)...")
    out()

    per_slot_hits = []
    for element_size in (1, 2, 4):
        window_size = NUM_SLOTS * element_size
        fmt = {1: '<B', 2: '<H', 4: '<I'}[element_size]
        for window_start in range(0, TAIL_SIZE - window_size + 1):
            all_match = True
            for name, d in cat_data.items():
                values = [
                    struct.unpack_from(fmt, d['tail'], window_start + i * element_size)[0]
                    for i in range(NUM_SLOTS)
                ]
                expected = d['expected_slots']
                # Defective slots should be non-zero, clean slots should be zero
                defect_ok = all(values[s] != 0 for s in expected)
                clean_ok  = all(values[s] == 0 for s in range(NUM_SLOTS) if s not in expected)
                if not (defect_ok and clean_ok):
                    all_match = False
                    break
            if all_match:
                out(f"  HIT u{element_size*8} window at tail+{window_start}:")
                for name, d in cat_data.items():
                    values = [
                        struct.unpack_from(fmt, d['tail'], window_start + i * element_size)[0]
                        for i in range(NUM_SLOTS)
                    ]
                    out(f"    {name}: {list(zip(SLOT_NAMES, values))}")
                per_slot_hits.append((element_size, window_start))

    if not per_slot_hits:
        out("  No per-slot array window matches found.")

    # ── Phase 5: Expanded full-blob unmapped-region scan ─────────────────────
    out()
    out("-" * 70)
    out("PHASE 5 -- Expanded Scan: Unmapped Blob Regions")
    out("-" * 70)
    out("  Scanning regions outside the pre-T block and T array...")
    out()

    expanded_hits = []
    # For each cat, the mapped regions are:
    #   [0, pre_t_end)  -- header + pre-T block
    #   [pre_t_end, t_end)  -- T array (known but not the defect source)
    #   [len(blob)-TAIL_SIZE, len(blob))  -- blob tail
    # Everything between t_end and (len-TAIL_SIZE) is "middle" -- abilities, etc.
    # We scan that middle region for bitmap/per-slot hits.

    # Build per-cat middle blobs
    middle_data: dict[str, bytes] = {}
    for name, d in cat_data.items():
        middle_start = d['t_end']
        middle_end   = d['tail_offset']
        middle_data[name] = d['blob'][middle_start:middle_end]
        out(f"  {name}: middle region blob[0x{middle_start:04x}:0x{middle_end:04x}]"
            f"  ({middle_end - middle_start} bytes)")

    # Align all cats to same middle length for scanning
    min_middle = min(len(v) for v in middle_data.values())

    # Bitmap scan over middle region
    out()
    out("  Bitmap scan over middle region:")
    middle_bitmap_hits = []
    for width in (1, 2, 4):
        fmt = {1: '<B', 2: '<H', 4: '<I'}[width]
        stride = width
        for offset in range(0, min_middle - width + 1, stride):
            match = True
            for name, d in cat_data.items():
                mbytes = middle_data[name]
                if offset + width > len(mbytes):
                    match = False
                    break
                val = struct.unpack_from(fmt, mbytes, offset)[0]
                expected = expected_masks[name]
                if (val & all_slots_mask) != expected:
                    match = False
                    break
            if match:
                out(f"  HIT u{width*8} at middle+{offset}:")
                for name in names:
                    val = struct.unpack_from(fmt, middle_data[name], offset)[0]
                    mid_blob_offset = cat_data[name]['t_end'] + offset
                    out(f"    {name}: 0x{val:0{width*2}x} = {bin(val)}"
                        f"  (blob offset 0x{mid_blob_offset:04x})")
                middle_bitmap_hits.append(('normal', width * 8, offset))

    if not middle_bitmap_hits:
        out("  No bitmap hits in middle region.")

    # Per-slot scan over middle region
    out()
    out("  Per-slot window scan over middle region:")
    middle_slot_hits = []
    for element_size in (1, 2, 4):
        window_size = NUM_SLOTS * element_size
        fmt = {1: '<B', 2: '<H', 4: '<I'}[element_size]
        for window_start in range(0, min_middle - window_size + 1):
            all_match = True
            for name, d in cat_data.items():
                mbytes = middle_data[name]
                if window_start + window_size > len(mbytes):
                    all_match = False
                    break
                values = [
                    struct.unpack_from(fmt, mbytes, window_start + i * element_size)[0]
                    for i in range(NUM_SLOTS)
                ]
                expected = d['expected_slots']
                defect_ok = all(values[s] != 0 for s in expected)
                clean_ok  = all(values[s] == 0 for s in range(NUM_SLOTS) if s not in expected)
                if not (defect_ok and clean_ok):
                    all_match = False
                    break
            if all_match:
                abs_offset = cat_data[names[0]]['t_end'] + window_start
                out(f"  HIT u{element_size*8} window at middle+{window_start}"
                    f"  (approx blob offset 0x{abs_offset:04x}):")
                for name, d in cat_data.items():
                    mbytes = middle_data[name]
                    values = [
                        struct.unpack_from(fmt, mbytes, window_start + i * element_size)[0]
                        for i in range(NUM_SLOTS)
                    ]
                    out(f"    {name}: {list(zip(SLOT_NAMES, values))}")
                middle_slot_hits.append((element_size, window_start))

    if not middle_slot_hits:
        out("  No per-slot window hits in middle region.")

    # ── Phase 6: SQLite cross-table check ─────────────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 6 -- SQLite Cross-Table Check")
    out("-" * 70)

    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    out(f"  Tables in save: {[t[0] for t in tables]}")
    out()

    for (table_name,) in tables:
        if table_name == 'cats':
            # Check schema
            cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            out(f"  {table_name}: columns = {[(c[1], c[2]) for c in cols]}")
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            out(f"  {table_name}: row_count = {row_count}")
        else:
            cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            out(f"  {table_name}: columns = {[(c[1], c[2]) for c in cols]},  rows = {row_count}")
            if row_count > 0 and row_count < 20:
                rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
                for row in rows:
                    out(f"    {row}")

    conn.close()

    # ── Summary ────────────────────────────────────────────────────────────────
    out()
    out("=" * 70)
    out("SUMMARY")
    out("=" * 70)

    out(f"  Tail bitmap hits:          {bitmap_hits or 'none'}")
    out(f"  Tail per-slot hits:        {per_slot_hits or 'none'}")
    out(f"  Middle bitmap hits:        {middle_bitmap_hits or 'none'}")
    out(f"  Middle per-slot hits:      {middle_slot_hits or 'none'}")
    out(f"  Defect-correlated offsets: {defect_correlated or 'none'}")
    out()

    if not any([bitmap_hits, per_slot_hits, middle_bitmap_hits, middle_slot_hits]):
        out("  CONCLUSION: No standard bitmap/per-slot encoding found.")
        out("  Recommend pivoting to Direction #3 (parent-blob byte diff).")
        out("  Also worth examining: defect-correlated byte offsets above,")
        out("  and checking whether the game stores defect info at creation time")
        out("  in a non-slot-indexed structure (e.g. compact pair list, RLE).")
    else:
        out("  CONCLUSION: Candidate(s) found -- proceed to Phase 7 (full-roster validation).")

    # Write results file
    out_path = os.path.join(_SCRIPT_DIR, 'blob_tail_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    print(f"\nResults also written to: {out_path}")


if __name__ == '__main__':
    main()
