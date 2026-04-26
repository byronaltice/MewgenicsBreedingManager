"""Direction 7b -- Search for a parallel variant array elsewhere in the blob.

Hypothesis: a 15-entry (or similar) variant array exists where:
  - Whommie has defect values at eye_L/eyebrow_L positions (values 2 or 0xFFFFFFFE)
  - Kami (same base-shape IDs, clean) has 0 at those positions
  - Bud has defect value at ear positions

GON "No Part" defect IDs:
  eyes block -2 / 2  -> -2 CHA, blind
  eyebrows block -2 / 2 -> -2 CHA
  ears block -2 / 2 -> -2 DEX

The ID stored could be 2 (block number), 0xFFFFFFFE (-2 block), or possibly
the GON stat value (e.g., -2 = 0xFFFFFFFE for CHA modifier).

Strategy:
  1. Scan all u32-aligned offsets in each target blob.
  2. At each offset, find locations of `2` or `0xFFFFFFFE`.
  3. Compare Whommie's offsets with Kami's: values present in Whommie
     but NOT in Kami (anchored by offset from T_start or blob-end).
  4. Then try interpreting nearby bytes as a 15-entry variant array
     matching the _VISUAL_MUTATION_FIELDS order.
"""
from __future__ import annotations

import sys
import struct
import sqlite3
from pathlib import Path
from collections import defaultdict

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
_TS = ROOT / "test-saves"
if not _TS.exists():
    _TS = Path(r"C:\Users\Byron\gitprojects\MewgenicsBreedingManager\test-saves")
SAVE = _TS / "steamcampaign01.sav"
GPAK = _TS / "resources.gpak"
OUT  = Path(__file__).parent / "direction7b_results.txt"

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
    fur  = cat.body_parts["texture"]
    body = cat.body_parts["bodyShape"]
    head = cat.body_parts["headShape"]
    target = struct.pack("<I", fur)
    for i in range(0, len(raw) - 9 * 4):
        if raw[i:i + 4] == target:
            if struct.unpack_from("<I", raw, i + 3 * 4)[0] == body and \
               struct.unpack_from("<I", raw, i + 8 * 4)[0] == head:
                return i
    return -1


def find_all_values(raw: bytes, t_start: int, values: set[int]) -> list[tuple[int, int]]:
    """Return list of (offset_relative_to_t_start, value) for u32-aligned matches."""
    hits: list[tuple[int, int]] = []
    # Scan u32-aligned offsets throughout the blob
    for pos in range(0, len(raw) - 4, 4):
        v = struct.unpack_from("<I", raw, pos)[0]
        if v in values:
            hits.append((pos - t_start, v))
    return hits


def main() -> None:
    from save_parser import parse_save, GameData, set_visual_mut_data
    from save_parser import _VISUAL_MUTATION_FIELDS

    out("=" * 70)
    out("Direction 7b -- Parallel variant array search")
    out("=" * 70)

    gd = GameData.from_gpak(str(GPAK))
    set_visual_mut_data(gd.visual_mutation_data)
    save_data = parse_save(str(SAVE))
    cat_map = {c.name: c for c in save_data.cats}
    conn = sqlite3.connect(str(SAVE))

    targets = ["Whommie", "Kami", "Bud", "Petronij", "Romanoba", "Murisha"]
    info: dict[str, dict] = {}

    for name in targets:
        cat = cat_map.get(name)
        if not cat:
            continue
        raw = raw_blob(conn, cat.db_key)
        t_start = locate_t_start(raw, cat)
        info[name] = {
            "cat": cat,
            "raw": raw,
            "t_start": t_start,
            "blob_len": len(raw),
        }
        out(f"  {name}: blob_len={len(raw)}  t_start=0x{t_start:x}  "
            f"defects={cat.defects}")
    out()

    # Step 1: find all `2` and `0xFFFFFFFE` occurrences, anchored to T_start
    SENTINELS = {2, 0xFFFFFFFE}
    hits_by_cat: dict[str, set[tuple[int, int]]] = {}
    for name, d in info.items():
        hits = find_all_values(d["raw"], d["t_start"], SENTINELS)
        hits_by_cat[name] = set(hits)
        # Count hits outside the T array (T runs from 0..288)
        outside = [h for h in hits if not (0 <= h[0] < 72 * 4)]
        out(f"  {name}: {len(hits)} total hits, {len(outside)} outside T array")

    out()
    out("=" * 70)
    out("STEP 1: Whommie hits MINUS Kami hits (same rel-offset AND value)")
    out("=" * 70)
    wh = hits_by_cat.get("Whommie", set())
    ka = hits_by_cat.get("Kami", set())
    whommie_unique = wh - ka
    # Filter to positions outside the T array (past offset 72*4 = 288)
    whommie_unique_past_t = sorted([h for h in whommie_unique if h[0] >= 72 * 4])
    out(f"  Whommie has {len(whommie_unique_past_t)} unique sentinel hits after T-end:")
    for rel_off, val in whommie_unique_past_t[:50]:
        out(f"    rel_offset=+0x{rel_off:x} ({rel_off} bytes past T_start)  value=0x{val:08x}")

    out()
    out("=" * 70)
    out("STEP 2: Bud hits MINUS Kami hits (for ear defect)")
    out("=" * 70)
    bu = hits_by_cat.get("Bud", set())
    bud_unique = bu - ka
    bud_unique_past_t = sorted([h for h in bud_unique if h[0] >= 72 * 4])
    out(f"  Bud has {len(bud_unique_past_t)} unique sentinel hits after T-end:")
    for rel_off, val in bud_unique_past_t[:50]:
        out(f"    rel_offset=+0x{rel_off:x}  value=0x{val:08x}")

    out()
    out("=" * 70)
    out("STEP 3: Candidate offsets = Whommie-unique AND Bud-unique")
    out("        (a true variant array would be at a consistent rel-offset")
    out("         across all cats; defect cats have sentinels, clean ones 0)")
    out("=" * 70)
    # Check offsets where BOTH Whommie and Bud have a sentinel but Kami does NOT
    wh_offsets = {h[0] for h in whommie_unique_past_t}
    bu_offsets = {h[0] for h in bud_unique_past_t}
    shared = wh_offsets & bu_offsets
    out(f"  Shared offsets (Whommie+Bud, not in Kami): {len(shared)}")
    for off in sorted(shared)[:20]:
        wh_vals = [v for o, v in hits_by_cat["Whommie"] if o == off]
        bu_vals = [v for o, v in hits_by_cat["Bud"] if o == off]
        out(f"    +0x{off:x}  Whommie={wh_vals}  Bud={bu_vals}")

    out()
    out("=" * 70)
    out("STEP 4: Also anchor from BLOB END (defect array may be near tail)")
    out("=" * 70)
    # Re-find hits anchored from blob end
    def hits_from_end(raw: bytes, values: set[int]) -> set[tuple[int, int]]:
        s = set()
        for pos in range(0, len(raw) - 4, 4):
            v = struct.unpack_from("<I", raw, pos)[0]
            if v in values:
                s.add((pos - len(raw), v))  # negative offset from end
        return s

    end_hits = {n: hits_from_end(d["raw"], SENTINELS) for n, d in info.items()}
    wh_end = end_hits.get("Whommie", set())
    ka_end = end_hits.get("Kami", set())
    bu_end = end_hits.get("Bud", set())
    wh_end_unique = {o for o, v in (wh_end - ka_end)}
    bu_end_unique = {o for o, v in (bu_end - ka_end)}
    shared_end = wh_end_unique & bu_end_unique
    out(f"  Shared end-anchored offsets (Whommie+Bud, not Kami): {len(shared_end)}")
    for off in sorted(shared_end)[:20]:
        wh_vals = [v for o, v in wh_end if o == off]
        bu_vals = [v for o, v in bu_end if o == off]
        ka_vals = [v for o, v in ka_end if o == off]
        out(f"    end{off}  Whommie={wh_vals}  Bud={bu_vals}  Kami={ka_vals}")

    out()
    out("=" * 70)
    out("STEP 5: Look for a 15-u32 block where slot pattern matches defects")
    out("        Whommie: slots eye_L(8), eye_R(9), eyebrow_L(10), eyebrow_R(11)")
    out("                 should be non-zero; fur(0) might also be non-zero.")
    out("        Bud: slots ear_L(12), ear_R(13) should be non-zero;")
    out("             legs(4,5) non-zero (Blob Legs is detected already).")
    out("=" * 70)
    # Iterate u32-aligned positions, read 15 u32s, check pattern
    SLOT_NAMES = [f[0] for f in _VISUAL_MUTATION_FIELDS]
    # Whommie expected defect slots: eye_L=8, eye_R=9, eyebrow_L=10, eyebrow_R=11, fur=0
    WH_DEFECT_SLOTS = {0, 8, 9, 10, 11}
    BUD_DEFECT_SLOTS = {4, 5, 12, 13}  # leg_L/R, ear_L/R

    def scan_for_pattern(name: str, raw: bytes, defect_slots: set[int],
                         window: int = 15) -> list[int]:
        """Find offsets where the 15-entry window has non-zero at defect_slots
        and zero elsewhere (allowing the defect slots to hold any non-zero)."""
        candidates = []
        for pos in range(0, len(raw) - window * 4, 4):
            vals = [struct.unpack_from("<I", raw, pos + i * 4)[0] for i in range(window)]
            nonzero_slots = {i for i, v in enumerate(vals) if v != 0}
            if nonzero_slots == defect_slots:
                candidates.append(pos)
        return candidates

    wh_raw = info["Whommie"]["raw"]
    wh_candidates = scan_for_pattern("Whommie", wh_raw, WH_DEFECT_SLOTS)
    out(f"  Whommie 15-u32 windows with non-zero EXACTLY at {WH_DEFECT_SLOTS}: "
        f"{len(wh_candidates)} candidates")
    for pos in wh_candidates[:10]:
        vals = [struct.unpack_from("<I", wh_raw, pos + i * 4)[0] for i in range(15)]
        out(f"    pos=0x{pos:x}  vals={vals}")

    bu_raw = info["Bud"]["raw"]
    bu_candidates = scan_for_pattern("Bud", bu_raw, BUD_DEFECT_SLOTS)
    out(f"  Bud 15-u32 windows with non-zero EXACTLY at {BUD_DEFECT_SLOTS}: "
        f"{len(bu_candidates)} candidates")
    for pos in bu_candidates[:10]:
        vals = [struct.unpack_from("<I", bu_raw, pos + i * 4)[0] for i in range(15)]
        out(f"    pos=0x{pos:x}  vals={vals}")

    # Also try LOOSER pattern: non-zero AT LEAST at defect_slots (others can be anything)
    out()
    out("  Looser: windows where defect_slots are all non-zero AND all defect")
    out("  slot values are in {2, 0xFFFFFFFE, or small integers <= 10}:")
    def looser_scan(raw: bytes, defect_slots: set[int], window: int = 15) -> list[int]:
        cands = []
        for pos in range(0, len(raw) - window * 4, 4):
            vals = [struct.unpack_from("<I", raw, pos + i * 4)[0] for i in range(window)]
            ok = True
            for s in defect_slots:
                v = vals[s]
                if v == 0:
                    ok = False
                    break
                if not (v in (2, 0xFFFFFFFE) or 0 < v <= 10):
                    ok = False
                    break
            if ok:
                # also require non-defect slots are small/zero (no huge values)
                for i in range(window):
                    if i in defect_slots:
                        continue
                    if vals[i] > 100 and vals[i] != 0:
                        ok = False
                        break
                if ok:
                    cands.append(pos)
        return cands

    wh_loose = looser_scan(wh_raw, WH_DEFECT_SLOTS)
    out(f"  Whommie looser candidates: {len(wh_loose)}")
    for pos in wh_loose[:10]:
        vals = [struct.unpack_from("<I", wh_raw, pos + i * 4)[0] for i in range(15)]
        out(f"    pos=0x{pos:x}  vals={vals}")

    bu_loose = looser_scan(bu_raw, BUD_DEFECT_SLOTS)
    out(f"  Bud looser candidates: {len(bu_loose)}")
    for pos in bu_loose[:10]:
        vals = [struct.unpack_from("<I", bu_raw, pos + i * 4)[0] for i in range(15)]
        out(f"    pos=0x{pos:x}  vals={vals}")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
