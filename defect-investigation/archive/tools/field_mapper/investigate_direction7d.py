"""Direction 7d -- Targeted follow-ups from 7c:
  1. Inspect `save_file_cat` (936 bytes, previously unchecked).
  2. Unaligned 0x0002 hits: find T-relative offsets unique to Whommie vs Kami.
  3. Slot-reordered bitmask search (try every permutation of slot->bit mapping).
"""
from __future__ import annotations

import sys
import struct
import sqlite3
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
_TS = ROOT / "test-saves"
if not _TS.exists():
    _TS = Path(os.path.expandvars(r"%USERPROFILE%\gitprojects\MewgenicsBreedingManager\test-saves"))
SAVE = _TS / "steamcampaign01.sav"
GPAK = _TS / "resources.gpak"
OUT  = Path(__file__).parent / "direction7d_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def raw_blob_cats(conn, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    data = bytes(row[0])
    uncomp = struct.unpack_from("<I", data, 0)[0]
    return lz4.block.decompress(data[4:], uncompressed_size=uncomp)


def raw_blob_file(conn, key: str) -> bytes:
    row = conn.execute("SELECT data FROM files WHERE key=?", (key,)).fetchone()
    if not row:
        return b""
    data = bytes(row[0])
    try:
        uncomp = struct.unpack_from("<I", data, 0)[0]
        return lz4.block.decompress(data[4:], uncompressed_size=uncomp)
    except Exception:
        return data


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


def scan_u16_all(raw: bytes, value: int) -> list[int]:
    target = struct.pack("<H", value & 0xFFFF)
    hits = []
    start = 0
    while True:
        p = raw.find(target, start)
        if p < 0:
            break
        hits.append(p)
        start = p + 1
    return hits


def main() -> None:
    from save_parser import parse_save, GameData, set_visual_mut_data

    out("=" * 70)
    out("Direction 7d -- save_file_cat + unaligned 0x0002 diff + reorder bitmask")
    out("=" * 70)

    gd = GameData.from_gpak(str(GPAK))
    set_visual_mut_data(gd.visual_mutation_data)
    save_data = parse_save(str(SAVE))
    cat_map = {c.name: c for c in save_data.cats}
    conn = sqlite3.connect(str(SAVE))

    # ========== STEP 1: save_file_cat inspection ==========
    out("\nSTEP 1 -- save_file_cat blob")
    out("-" * 70)
    sfc = raw_blob_file(conn, "save_file_cat")
    out(f"  decompressed size: {len(sfc)}")

    # Hex-dump first 256 bytes
    out("  First 256 bytes:")
    for i in range(0, min(256, len(sfc)), 16):
        chunk = sfc[i:i + 16]
        hx = " ".join(f"{b:02x}" for b in chunk)
        ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out(f"    {i:04x}: {hx:<48}  {ascii_}")

    # Check if Whommie's UID appears in save_file_cat
    wh = cat_map.get("Whommie")
    if wh and hasattr(wh, "uid"):
        wh_uid_bytes = struct.pack("<Q", wh.uid & 0xFFFFFFFFFFFFFFFF)
        if wh_uid_bytes in sfc:
            out(f"  ** Whommie UID FOUND in save_file_cat at offset "
                f"{sfc.index(wh_uid_bytes)}")
        else:
            out("  Whommie UID not in save_file_cat")

    # Check all target cats' UIDs
    for name in ["Whommie", "Kami", "Bud"]:
        cat = cat_map.get(name)
        if cat and hasattr(cat, "uid"):
            uid_b = struct.pack("<Q", cat.uid & 0xFFFFFFFFFFFFFFFF)
            present = uid_b in sfc
            out(f"  {name} UID in save_file_cat: {present}")

    # ========== STEP 2: Unaligned 0x0002 offset diff ==========
    out("\nSTEP 2 -- Unaligned 0x0002 offsets (T-anchored), Whommie vs Kami")
    out("-" * 70)
    targets = ["Whommie", "Kami", "Bud", "Petronij", "Romanoba", "Murisha"]
    info: dict[str, dict] = {}
    for name in targets:
        cat = cat_map.get(name)
        if not cat:
            continue
        raw = raw_blob_cats(conn, cat.db_key)
        t_start = locate_t_start(raw, cat)
        hits = scan_u16_all(raw, 0x0002)
        rel_hits = [(h - t_start) for h in hits]
        info[name] = {"cat": cat, "raw": raw, "t_start": t_start,
                      "rel_hits": set(rel_hits), "hits": hits}
        out(f"  {name}: {len(hits)} unaligned 0x0002 hits  "
            f"(defects={cat.defects})")

    wh_rel = info["Whommie"]["rel_hits"]
    ka_rel = info["Kami"]["rel_hits"]
    wh_only = sorted(wh_rel - ka_rel)
    out(f"\n  Whommie-only (not at same T-rel offset in Kami): {len(wh_only)}")
    out(f"    rel offsets: {[hex(o) for o in wh_only]}")

    # Cross-check: are those offsets PRESENT in Bud (another defective cat)?
    bu_rel = info["Bud"]["rel_hits"]
    in_bud = [o for o in wh_only if o in bu_rel]
    out(f"  Whommie-only offsets that are also in Bud: {in_bud}")
    # For signals to be defect-correlated they should also be in Bud
    # since Bud has ear+leg defects (different slots)

    # Also: Whommie+Bud vs all clean cats
    clean_rel = set.intersection(
        *(info[n]["rel_hits"] for n in ["Kami", "Petronij", "Romanoba", "Murisha"]
          if n in info)
    ) if all(n in info for n in ["Kami", "Petronij", "Romanoba", "Murisha"]) else set()
    defect_common = wh_rel & bu_rel
    defect_unique = defect_common - clean_rel
    out(f"  Offsets in BOTH defective cats but in NONE of 4 clean cats: "
        f"{sorted(defect_unique)}")

    # ========== STEP 3: Slot-reorder bitmask search ==========
    out("\nSTEP 3 -- Bitmask with alternate slot orderings")
    out("-" * 70)
    # Try different orderings and also shorter (e.g., just one bit per part type)
    wh_raw = info["Whommie"]["raw"]
    ka_raw = info["Kami"]["raw"]
    bu_raw = info["Bud"]["raw"]

    # Part-category order (10 types): fur,body,head,tail,legs,arms,eyes,eyebrows,ears,mouth
    # Whommie defective: fur(0), eyes(6), eyebrows(7)
    # Bud defective: legs(4), ears(8)
    part_cat_masks = {
        "part10 W fur+eyes+ebrows": (1 << 0) | (1 << 6) | (1 << 7),
        "part10 B legs+ears":       (1 << 4) | (1 << 8),
    }

    def find_u32_u16(raw: bytes, value: int) -> tuple[int, int]:
        u32_count = len([1 for p in range(0, len(raw) - 3) if
                         struct.unpack_from("<I", raw, p)[0] == value])
        u16_count = len([1 for p in range(0, len(raw) - 1) if
                         struct.unpack_from("<H", raw, p)[0] == (value & 0xFFFF)])
        return u32_count, u16_count

    for name, mask in part_cat_masks.items():
        wh_u32, wh_u16 = find_u32_u16(wh_raw, mask)
        ka_u32, ka_u16 = find_u32_u16(ka_raw, mask)
        bu_u32, bu_u16 = find_u32_u16(bu_raw, mask)
        out(f"  {name}=0x{mask:x}: Wh(u32={wh_u32},u16={wh_u16}) "
            f"Ka(u32={ka_u32},u16={ka_u16}) Bu(u32={bu_u32},u16={bu_u16})")

    # ========== STEP 4: Look at what IS unique in Whommie's blob vs Kami ==========
    # Find all u32 values unique to Whommie (not in Kami's blob at all).
    out("\nSTEP 4 -- U32 values present in Whommie but NOT in Kami at all")
    out("-" * 70)
    wh_u32s = set()
    for p in range(0, len(wh_raw) - 3):
        wh_u32s.add(struct.unpack_from("<I", wh_raw, p)[0])
    ka_u32s = set()
    for p in range(0, len(ka_raw) - 3):
        ka_u32s.add(struct.unpack_from("<I", ka_raw, p)[0])
    bu_u32s = set()
    for p in range(0, len(bu_raw) - 3):
        bu_u32s.add(struct.unpack_from("<I", bu_raw, p)[0])

    # Values in Whommie AND Bud but NOT in Kami (possible defect marker)
    wh_bu_not_ka = (wh_u32s & bu_u32s) - ka_u32s
    # Exclude obvious noise (super large, or zero-ish)
    interesting = sorted(v for v in wh_bu_not_ka
                         if v not in (0,) and (v < 1_000_000 or v > 0xF0000000))
    out(f"  Values in BOTH Whommie and Bud (not Kami): {len(interesting)}")
    out(f"  First 40: {interesting[:40]}")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
