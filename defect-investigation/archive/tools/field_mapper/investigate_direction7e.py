"""Direction 7e -- Targeted pedigree and string-search.

Community reverse-eng said birth defects "pass down like body parts". That
strongly implies pedigree storage. Check:
  1. Does Whommie's UID appear in the pedigree blob?
  2. If so, dump the surrounding bytes, diff against Kami's pedigree entry.
  3. Search all decompressed file blobs for defect-adjacent strings.
  4. Check if ANY blob (cats or files) contains the raw byte sequence
     "birth_defect" or eye/eyebrow/ear related words.
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
OUT  = Path(__file__).parent / "direction7e_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def decompress_maybe(data: bytes) -> bytes:
    try:
        uncomp = struct.unpack_from("<I", data, 0)[0]
        if 0 < uncomp < 100_000_000:
            return lz4.block.decompress(data[4:], uncompressed_size=uncomp)
    except Exception:
        pass
    return data


def main() -> None:
    from save_parser import parse_save, GameData, set_visual_mut_data

    out("=" * 70)
    out("Direction 7e -- Pedigree targeted + string search")
    out("=" * 70)

    gd = GameData.from_gpak(str(GPAK))
    set_visual_mut_data(gd.visual_mutation_data)
    save_data = parse_save(str(SAVE))
    cat_map = {c.name: c for c in save_data.cats}
    conn = sqlite3.connect(str(SAVE))

    wh = cat_map["Whommie"]
    ka = cat_map["Kami"]
    bu = cat_map["Bud"]
    pe = cat_map.get("Petronij")

    out(f"  Whommie uid={wh._uid_int:#x}  Kami uid={ka._uid_int:#x}  Bud uid={bu._uid_int:#x}")
    if pe:
        out(f"  Petronij uid={pe._uid_int:#x}")

    # ========== STEP 1: load pedigree and locate UIDs ==========
    out("\nSTEP 1 -- Pedigree: locate each cat's UID bytes")
    out("-" * 70)
    ped_row = conn.execute("SELECT data FROM files WHERE key='pedigree'").fetchone()
    ped = decompress_maybe(bytes(ped_row[0]))
    out(f"  Pedigree decompressed: {len(ped)} bytes")

    def find_all_occurrences(blob: bytes, needle: bytes) -> list[int]:
        offs = []
        start = 0
        while True:
            p = blob.find(needle, start)
            if p < 0:
                break
            offs.append(p)
            start = p + 1
        return offs

    for name, cat in [("Whommie", wh), ("Kami", ka), ("Bud", bu),
                      ("Petronij", pe) if pe else None]:
        if not cat:
            continue
        uid_b = struct.pack("<Q", cat._uid_int & 0xFFFFFFFFFFFFFFFF)
        offs = find_all_occurrences(ped, uid_b)
        out(f"  {name}: {len(offs)} pedigree offsets: "
            f"{[hex(o) for o in offs[:5]]}{'...' if len(offs) > 5 else ''}")

    # ========== STEP 2: dump surrounding bytes of first Whommie/Kami hit ==========
    out("\nSTEP 2 -- Bytes around each cat's FIRST pedigree entry")
    out("-" * 70)
    for name, cat in [("Whommie", wh), ("Kami", ka), ("Bud", bu)]:
        uid_b = struct.pack("<Q", cat._uid_int & 0xFFFFFFFFFFFFFFFF)
        p = ped.find(uid_b)
        if p < 0:
            out(f"  {name}: UID not found")
            continue
        lo = max(0, p - 16)
        hi = min(len(ped), p + 96)
        out(f"  {name} first hit at 0x{p:x}  defects={cat.defects}")
        for i in range(lo, hi, 16):
            chunk = ped[i:i + 16]
            marker = "  <-- UID" if lo <= p < i + 16 <= p + 8 or (i <= p < i + 16) else ""
            hx = " ".join(f"{b:02x}" for b in chunk)
            ascii_ = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            mark = " <--" if i <= p < i + 16 else ""
            out(f"    {i:06x}: {hx:<48}  {ascii_}{mark}")

    # ========== STEP 3: same-offset diff if Whommie vs Kami entries are aligned ==========
    out("\nSTEP 3 -- Structured per-cat record diff")
    out("-" * 70)
    # Find all UIDs for all cats to discover record stride
    all_uids = {c._uid_int: c.name for c in save_data.cats if hasattr(c, '_uid_int')}
    first_uid_offs = []
    for c in save_data.cats:
        uid_b = struct.pack("<Q", c._uid_int & 0xFFFFFFFFFFFFFFFF)
        p = ped.find(uid_b)
        if p >= 0:
            first_uid_offs.append((p, c.name))
    first_uid_offs.sort()
    out(f"  Cats with UID in pedigree: {len(first_uid_offs)}")
    if len(first_uid_offs) >= 2:
        # look at gap between successive offsets
        gaps = [first_uid_offs[i + 1][0] - first_uid_offs[i][0]
                for i in range(min(20, len(first_uid_offs) - 1))]
        out(f"  First 20 gaps between successive first-UID offsets: {gaps}")

    # For Whommie vs Kami: dump 64-byte windows starting at UID and diff
    wh_uid_b = struct.pack("<Q", wh._uid_int & 0xFFFFFFFFFFFFFFFF)
    ka_uid_b = struct.pack("<Q", ka._uid_int & 0xFFFFFFFFFFFFFFFF)
    wh_off = ped.find(wh_uid_b)
    ka_off = ped.find(ka_uid_b)
    if wh_off >= 0 and ka_off >= 0:
        LEN = 200
        wh_rec = ped[wh_off:wh_off + LEN]
        ka_rec = ped[ka_off:ka_off + LEN]
        diffs = []
        for i in range(min(len(wh_rec), len(ka_rec))):
            if wh_rec[i] != ka_rec[i]:
                diffs.append(i)
        out(f"  Whommie vs Kami first-record byte diffs (in first {LEN}): "
            f"{len(diffs)} bytes")
        # Show first 50 diffs with values
        for d in diffs[:50]:
            out(f"    +{d}: Whommie=0x{wh_rec[d]:02x}  Kami=0x{ka_rec[d]:02x}")

    # ========== STEP 4: Scan all blobs for defect-related strings ==========
    out("\nSTEP 4 -- Search all files-table blobs for defect-related strings")
    out("-" * 70)
    needles = [b"birth_defect", b"BIRTH_DEFECT", b"BirthDefect",
               b"defect", b"Defect", b"variant", b"no_part",
               b"MUTATION_EYES_M2", b"NoPart"]
    rows = conn.execute("SELECT key, data FROM files").fetchall()
    for key, data in rows:
        blob = decompress_maybe(bytes(data))
        for n in needles:
            if n in blob:
                out(f"  ** {key}: contains {n!r} at offset {blob.find(n)}")

    # Also check cat blobs
    cat_rows = conn.execute("SELECT key, data FROM cats").fetchall()
    hits_per_needle = {n: 0 for n in needles}
    for ckey, cdata in cat_rows:
        blob = decompress_maybe(bytes(cdata))
        for n in needles:
            if n in blob:
                hits_per_needle[n] += 1
    out(f"  cats-table hits by needle: {hits_per_needle}")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
