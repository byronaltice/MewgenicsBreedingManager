"""
Direction #1 Investigation Script — Pre-T 64-byte Block Analysis

Phases covered:
  1. Capture the 64-byte pre-T block for each target cat.
  2. Structural analysis (print as u32s, u64s, u16s; diff across cats).
  3. Scan for 0xFFFFFFFE sentinel (the "missing part" marker).
  4. Fallback: whole-blob 0xFFFFFFFE scan excluding known T positions.

Usage:
    py tools/field_mapper/investigate_pre_t_block.py

Expected output is a detailed hex dump + scan report written to stdout
and to tools/field_mapper/pre_t_block_results.txt.
"""

import struct
import sqlite3
import sys
import os
import lz4.block

# Allow importing save_parser from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from save_parser import BinaryReader, parse_save

# test-saves lives in the main repo root, not the worktree
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..'))
# If running from a worktree, test-saves is two extra levels up
_WORKTREE_REPO_ROOT = os.path.abspath(os.path.join(_REPO_ROOT, '..', '..', '..'))
SAVE_PATH = (
    os.path.join(_REPO_ROOT, 'test-saves', 'steamcampaign01.sav')
    if os.path.exists(os.path.join(_REPO_ROOT, 'test-saves', 'steamcampaign01.sav'))
    else os.path.join(_WORKTREE_REPO_ROOT, 'test-saves', 'steamcampaign01.sav')
)

# Cats to examine: name -> (role, expected_defect_slots)
TARGET_CATS = {
    'Whommie':  ('positive-2',  ['eye_L', 'eye_R', 'eyebrow_L', 'eyebrow_R']),
    'Bud':      ('positive-1',  ['ear_L', 'ear_R']),
    'Kami':     ('negative',    []),
    'Petronij': ('parent',      []),
    'Romanoba': ('control',     []),
}

# Slot order from _VISUAL_MUTATION_FIELDS (index 0..14)
SLOT_NAMES = [
    'fur', 'body', 'head', 'tail',
    'leg_L', 'leg_R', 'arm_L', 'arm_R',
    'eye_L', 'eye_R', 'eyebrow_L', 'eyebrow_R',
    'ear_L', 'ear_R', 'mouth',
]

SENTINEL = 0xFFFFFFFE
SENTINEL_BYTES = b'\xfe\xff\xff\xff'

# T array: 72 u32s = 288 bytes. Slot windows are at T indices 3,8,13,...68.
# Primary T indices (T[slot+0]) for defect-bearing slots:
T_PRIMARY_INDICES = {
    'fur': 0, 'body': 3, 'head': 8, 'tail': 13,
    'leg_L': 18, 'leg_R': 23, 'arm_L': 28, 'arm_R': 33,
    'eye_L': 38, 'eye_R': 43, 'eyebrow_L': 48, 'eyebrow_R': 53,
    'ear_L': 58, 'ear_R': 63, 'mouth': 68,
}


def hex_dump(data: bytes, start_offset: int = 0, label: str = "") -> str:
    """Return a formatted hex dump string, 16 bytes per row."""
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
    """Decompress an LZ4-compressed cat blob from the save file."""
    uncomp_size = struct.unpack_from('<I', raw_blob, 0)[0]
    return lz4.block.decompress(raw_blob[4:], uncompressed_size=uncomp_size)


def read_pre_t_block(blob: bytes) -> tuple[bytes, int]:
    """
    Parse the blob up to the pre-T skip and return the 64 bytes + the
    byte offset where the 64-byte block starts.
    """
    r = BinaryReader(blob)
    r.u32()          # breed_id
    r.u64()          # _uid_int
    r.utf16str()     # name
    r.str()          # name_tag
    r.u64()          # _parent_uid_a
    r.u64()          # _parent_uid_b
    r.str()          # collar
    r.u32()          # unnamed u32

    pre_t_offset = r.pos
    pre_t_block = blob[r.pos:r.pos + 64]
    r.skip(64)

    # Also read T for comparison
    T = [r.u32() for _ in range(72)]
    return pre_t_block, pre_t_offset, T


def scan_sentinel_in_block(data: bytes) -> list[int]:
    """Return byte offsets of all 0xFFFFFFFE occurrences at u32 alignment."""
    hits = []
    for i in range(0, len(data) - 3, 4):
        val = struct.unpack_from('<I', data, i)[0]
        if val == SENTINEL:
            hits.append(i)
    return hits


def scan_sentinel_anywhere(data: bytes) -> list[int]:
    """Return ALL byte offsets (any alignment) where SENTINEL_BYTES appears."""
    hits = []
    offset = 0
    while True:
        idx = data.find(SENTINEL_BYTES, offset)
        if idx == -1:
            break
        hits.append(idx)
        offset = idx + 1
    return hits


def t_range_for_blob(pre_t_offset: int) -> tuple[int, int]:
    """Return (start, end) byte offsets of the T array within the blob."""
    t_start = pre_t_offset + 64
    t_end = t_start + 72 * 4  # 288 bytes
    return t_start, t_end


def analyse_as_structs(data: bytes) -> dict:
    """Parse 64-byte block as various interpretations."""
    u32s  = list(struct.unpack_from('<16I', data))
    u64s  = list(struct.unpack_from('<8Q', data))
    u16s  = list(struct.unpack_from('<32H', data))
    return {'u32s': u32s, 'u64s': u64s, 'u16s': u16s}


def main():
    output_lines = []

    def out(line=""):
        print(line)
        output_lines.append(line)

    # ── Load save ────────────────────────────────────────────────────────────
    out("=" * 70)
    out("Direction #1 — Pre-T 64-byte Block Investigation")
    out("=" * 70)

    result = parse_save(SAVE_PATH)
    all_cats = result[0]
    cat_map = {c.name: c for c in all_cats}

    conn = sqlite3.connect(SAVE_PATH)

    cat_data: dict[str, dict] = {}
    for name, (role, expected_defect_slots) in TARGET_CATS.items():
        cat = cat_map.get(name)
        if cat is None:
            out(f"WARNING: cat '{name}' not found in save — skipping")
            continue
        row = conn.execute("SELECT data FROM cats WHERE key=?", (cat.db_key,)).fetchone()
        blob = decompress_blob(bytes(row[0]))
        pre_t, pre_t_offset, T = read_pre_t_block(blob)
        t_start, t_end = t_range_for_blob(pre_t_offset)
        cat_data[name] = {
            'cat': cat,
            'blob': blob,
            'pre_t': pre_t,
            'pre_t_offset': pre_t_offset,
            't_start': t_start,
            't_end': t_end,
            'T': T,
            'role': role,
            'expected_defect_slots': expected_defect_slots,
        }
    conn.close()

    # ── Phase 1: Hex dumps ───────────────────────────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 1 — Pre-T 64-byte Block Hex Dumps")
    out("-" * 70)

    for name, d in cat_data.items():
        out()
        out(f"  {name}  [{d['role']}]  (blob_offset=0x{d['pre_t_offset']:04x})")
        out(hex_dump(d['pre_t'], start_offset=d['pre_t_offset']))

    # ── Phase 2: Structural analysis ─────────────────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 2 — Structural Interpretation (u32 / u64 / u16)")
    out("-" * 70)

    for name, d in cat_data.items():
        s = analyse_as_structs(d['pre_t'])
        fur_id = d['T'][0]
        # Interpret as f64s (IEEE 754 double)
        f64s = list(struct.unpack_from('<8d', d['pre_t']))
        f64_strs = []
        for v in f64s:
            import math
            if math.isnan(v) or math.isinf(v):
                f64_strs.append(repr(v))
            else:
                f64_strs.append(f"{v:.6f}")
        out()
        out(f"  {name}  (fur_id T[0]={fur_id})")
        out(f"    u32s: {s['u32s']}")
        out(f"    u64s: {[hex(v) for v in s['u64s']]}")
        out(f"    f64s: {f64_strs}")
        # Flag NaN entries — 0xFFFFFFFFFFFFFFFF = special null/sentinel value
        nan_positions = [i for i, v in enumerate(f64s) if math.isnan(v)]
        if nan_positions:
            out(f"    *** NaN f64s at positions {nan_positions} (0xFFFFFFFFFFFFFFFF = possible sentinel)")

    # ── Phase 2b: Byte-level diff across cats ────────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 2b — Byte-level Diff (which bytes vary across cats)")
    out("-" * 70)

    names = list(cat_data.keys())
    if len(names) >= 2:
        ref_name = names[0]
        ref_block = cat_data[ref_name]['pre_t']
        varying_offsets = []
        for i in range(64):
            vals = {cat_data[n]['pre_t'][i] for n in names}
            if len(vals) > 1:
                varying_offsets.append(i)

        out(f"  Reference cat: {ref_name}")
        out(f"  Varying byte offsets (relative to block start): {varying_offsets}")
        out()
        out(f"  {'Byte':>5}  " + "  ".join(f"{n:>10}" for n in names))
        for i in varying_offsets:
            row_vals = "  ".join(f"{'0x'+format(cat_data[n]['pre_t'][i],'02x'):>10}" for n in names)
            out(f"  {i:>5}  {row_vals}")

    # ── Phase 3: Sentinel scan in pre-T block ────────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 3 — 0xFFFFFFFE Sentinel Scan in Pre-T Block")
    out("-" * 70)

    phase3_verdict = {}
    for name, d in cat_data.items():
        hits = scan_sentinel_in_block(d['pre_t'])
        out(f"  {name:12s}  hits at u32-aligned offsets: {hits if hits else 'NONE'}")
        phase3_verdict[name] = hits

    sentinel_in_whommie = bool(phase3_verdict.get('Whommie'))
    sentinel_in_bud     = bool(phase3_verdict.get('Bud'))
    sentinel_in_kami    = bool(phase3_verdict.get('Kami'))

    if sentinel_in_whommie and sentinel_in_bud and not sentinel_in_kami:
        out()
        out("  >>> HIT — sentinel found in defective cats but not control. Proceeding to Phase 5.")
        phase3_result = 'HIT'
    else:
        out()
        out("  >>> MISS — sentinel not found as expected. Proceeding to Phase 4 (whole-blob scan).")
        phase3_result = 'MISS'

    # ── Phase 4: Whole-blob sentinel scan (fallback) ─────────────────────────
    out()
    out("-" * 70)
    out("PHASE 4 — Whole-Blob 0xFFFFFFFE Scan (any alignment, excluding T array)")
    out("-" * 70)

    blob_hits: dict[str, list[int]] = {}
    for name, d in cat_data.items():
        t_start, t_end = d['t_start'], d['t_end']
        all_hits = scan_sentinel_anywhere(d['blob'])
        # Exclude hits inside T array
        outside_T = [h for h in all_hits if not (t_start <= h < t_end)]
        inside_T  = [h for h in all_hits if t_start <= h < t_end]
        blob_hits[name] = outside_T
        out(f"  {name:12s}  total hits={len(all_hits)}  inside_T={len(inside_T)}  outside_T={len(outside_T)}")
        if outside_T:
            for h in outside_T:
                in_pre_t = d['pre_t_offset'] <= h < d['pre_t_offset'] + 64
                region = "PRE-T" if in_pre_t else f"offset_0x{h:04x}"
                out(f"              → blob[0x{h:04x}] = 0x{struct.unpack_from('<I', d['blob'], h)[0]:08x}  ({region})")

    # Delta analysis: positions in defective cats NOT in clean cats
    out()
    out("  Delta analysis (Whommie vs Kami):")
    whommie_hits = set(blob_hits.get('Whommie', []))
    kami_hits    = set(blob_hits.get('Kami', []))
    bud_hits     = set(blob_hits.get('Bud', []))
    roman_hits   = set(blob_hits.get('Romanoba', []))

    whommie_delta = sorted(whommie_hits - kami_hits)
    bud_delta     = sorted(bud_hits - roman_hits)

    out(f"  Whommie-only offsets (not in Kami): {whommie_delta}")
    out(f"  Bud-only offsets (not in Romanoba): {bud_delta}")

    if whommie_delta or bud_delta:
        out()
        out("  Candidate defect-flag offsets found in Phase 4.")

    # ── Phase 5: Slot-to-offset mapping ──────────────────────────────────────
    out()
    out("-" * 70)
    out("PHASE 5 — Slot-to-Offset Mapping Verification")
    out("-" * 70)

    # Collect all candidate offsets from Phase 3 or 4
    candidate_offsets: list[int] = []
    if phase3_result == 'HIT':
        # Use offsets from the pre-T block (relative to block start → add pre_t_offset)
        for name in ('Whommie', 'Bud'):
            d = cat_data.get(name)
            if d:
                for rel_off in phase3_verdict.get(name, []):
                    candidate_offsets.append(d['pre_t_offset'] + rel_off)
    else:
        candidate_offsets = sorted(set(whommie_delta) | set(bud_delta))

    if not candidate_offsets:
        out("  No candidates to map — investigation inconclusive at Phase 5.")
        out("  Recommend: Direction #2 (blob tail bitmap) or Direction #3 (parent diff).")
    else:
        out(f"  Candidate blob offsets: {[hex(o) for o in candidate_offsets]}")
        out()
        out("  Attempting slot mapping:")
        # For each cat with expected defects, check which T slot the candidate
        # offset would correspond to if the structure is a 15-element u32 array
        # starting at pre_t_offset.
        for name in ('Whommie', 'Bud'):
            d = cat_data.get(name)
            if not d:
                continue
            out(f"  {name}:")
            for abs_off in candidate_offsets:
                rel = abs_off - d['pre_t_offset']
                if 0 <= rel < 64 and rel % 4 == 0:
                    slot_idx = rel // 4
                    slot_name = SLOT_NAMES[slot_idx] if slot_idx < len(SLOT_NAMES) else f"idx_{slot_idx}"
                    val = struct.unpack_from('<I', d['blob'], abs_off)[0]
                    out(f"    blob[0x{abs_off:04x}] rel={rel:2d} slot_idx={slot_idx} → {slot_name:15s} value=0x{val:08x}")
                else:
                    out(f"    blob[0x{abs_off:04x}] (not in pre-T block for this cat)")

    # ── Summary ───────────────────────────────────────────────────────────────
    out()
    out("=" * 70)
    out("SUMMARY")
    out("=" * 70)
    out(f"  Phase 3 sentinel scan result: {phase3_result}")
    out(f"  Whommie unique sentinel offsets (vs Kami): {[hex(o) for o in whommie_delta]}")
    out(f"  Bud unique sentinel offsets (vs Romanoba): {[hex(o) for o in bud_delta]}")

    # Print T values for affected slots to confirm parser's current reading
    out()
    out("  Current T values for defect-bearing slots:")
    for name in ('Whommie', 'Bud', 'Kami'):
        d = cat_data.get(name)
        if not d:
            continue
        T = d['T']
        out(f"  {name}:")
        for slot in ['eye_L', 'eye_R', 'eyebrow_L', 'eyebrow_R', 'ear_L', 'ear_R']:
            idx = T_PRIMARY_INDICES.get(slot)
            if idx is not None and idx < len(T):
                out(f"    T[{idx:2d}] {slot:15s} = {T[idx]:12} (0x{T[idx]:08x})")

    out()
    out("  Detected defects (from parser):")
    for name, d in cat_data.items():
        defects = [e['name'] for e in d['cat'].visual_mutation_entries if e.get('is_defect')]
        out(f"  {name:12s}: {defects or 'none'}")

    # Write results to file
    out_path = os.path.join(os.path.dirname(__file__), 'pre_t_block_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    print(f"\nResults also written to: {out_path}")


if __name__ == '__main__':
    main()
