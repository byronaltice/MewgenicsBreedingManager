"""Direction 7c -- Bitmask / byte-diff search for defect flag.

Since literal GON block IDs (2, 0xFFFFFFFE) don't appear in Whommie/Bud blobs,
try:
  1. Bitmask hypothesis: defects encoded as a bit per slot.
     Whommie candidate masks over various slot orderings.
     Bud candidate masks.
  2. Byte-level diff between Whommie and Kami (very similar cats,
     same eye/eyebrow base-shape IDs) to isolate defect-correlated bytes.
  3. Unaligned u16 search for value 2 or 0xFFFE.
  4. Dump Whommie's unique regions (not present in Kami).
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
OUT  = Path(__file__).parent / "direction7c_results.txt"

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


def scan_u32(raw: bytes, value: int) -> list[int]:
    target = struct.pack("<I", value & 0xFFFFFFFF)
    hits = []
    start = 0
    while True:
        p = raw.find(target, start)
        if p < 0:
            break
        hits.append(p)
        start = p + 1
    return hits


def scan_u16(raw: bytes, value: int) -> list[int]:
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


def scan_u8(raw: bytes, value: int) -> list[int]:
    hits = []
    for i, b in enumerate(raw):
        if b == (value & 0xFF):
            hits.append(i)
    return hits


def main() -> None:
    from save_parser import parse_save, GameData, set_visual_mut_data
    from save_parser import _VISUAL_MUTATION_FIELDS

    out("=" * 70)
    out("Direction 7c -- Bitmask / byte-diff / unaligned search")
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
        info[name] = {"cat": cat, "raw": raw, "t_start": t_start}

    # ---- STEP 1: bitmask hypothesis ----
    out("\nSTEP 1 -- Bitmask candidates")
    out("-" * 70)
    # Slot indices from _VISUAL_MUTATION_FIELDS list order:
    # 0=fur 1=body 2=head 3=tail 4=leg_L 5=leg_R 6=arm_L 7=arm_R
    # 8=eye_L 9=eye_R 10=eyebrow_L 11=eyebrow_R 12=ear_L 13=ear_R 14=mouth
    slot_labels = [f[0] for f in _VISUAL_MUTATION_FIELDS]
    out(f"  Slot order: {slot_labels}")

    # Whommie: Fur + Eye(L+R) + Eyebrow(L+R)
    wh_masks = {
        "fur+eyeL+eyeR+ebL+ebR":  (1 << 0) | (1 << 8) | (1 << 9) | (1 << 10) | (1 << 11),
        "eyeL+eyeR+ebL+ebR":      (1 << 8) | (1 << 9) | (1 << 10) | (1 << 11),
        "fur+eyeL+ebL":           (1 << 0) | (1 << 8) | (1 << 10),   # if symmetric stored once
        "eyeL+ebL":               (1 << 8) | (1 << 10),
        "fur+eyes_bit+ebrows_bit": (1 << 0) | (1 << 8) | (1 << 10),  # same as above
    }
    # Bud: Ear(L+R) + Legs(L+R) (Blob Legs already detected; suggests defect bit set)
    bud_masks = {
        "legL+legR+earL+earR":    (1 << 4) | (1 << 5) | (1 << 12) | (1 << 13),
        "earL+earR":              (1 << 12) | (1 << 13),
        "leg+ear_single":         (1 << 4) | (1 << 12),
    }

    for name, mask in wh_masks.items():
        wh_hits = scan_u32(info["Whommie"]["raw"], mask)
        ka_hits = scan_u32(info["Kami"]["raw"], mask)
        out(f"  Whommie mask {name}=0x{mask:x}: "
            f"Whommie_hits={len(wh_hits)} Kami_hits={len(ka_hits)}")
        if wh_hits and not ka_hits:
            out(f"    *** Whommie-unique! Offsets: {[hex(h) for h in wh_hits]}")

    for name, mask in bud_masks.items():
        bu_hits = scan_u32(info["Bud"]["raw"], mask)
        ka_hits = scan_u32(info["Kami"]["raw"], mask)
        out(f"  Bud mask {name}=0x{mask:x}: "
            f"Bud_hits={len(bu_hits)} Kami_hits={len(ka_hits)}")
        if bu_hits and not ka_hits:
            out(f"    *** Bud-unique! Offsets: {[hex(h) for h in bu_hits]}")

    # Also try u16 bitmasks (if only 15 slots, fits in u16)
    out("\n  u16 variants:")
    for name, mask in wh_masks.items():
        if mask > 0xFFFF:
            continue
        wh_hits = scan_u16(info["Whommie"]["raw"], mask)
        ka_hits = scan_u16(info["Kami"]["raw"], mask)
        if wh_hits and not ka_hits:
            out(f"  WH u16 mask {name}=0x{mask:x}: unique @ {[hex(h) for h in wh_hits]}")

    for name, mask in bud_masks.items():
        if mask > 0xFFFF:
            continue
        bu_hits = scan_u16(info["Bud"]["raw"], mask)
        ka_hits = scan_u16(info["Kami"]["raw"], mask)
        if bu_hits and not ka_hits:
            out(f"  BUD u16 mask {name}=0x{mask:x}: unique @ {[hex(h) for h in bu_hits]}")

    # ---- STEP 2: unaligned single-byte / u16 scans for 2 and 0xFFFE ----
    out("\nSTEP 2 -- Unaligned scans for value 2 and 0xFFFE")
    out("-" * 70)
    for val in [2, 0xFFFE]:
        wh = scan_u16(info["Whommie"]["raw"], val)
        ka = scan_u16(info["Kami"]["raw"], val)
        bu = scan_u16(info["Bud"]["raw"], val)
        out(f"  u16={val:#x}: Whommie={len(wh)} Kami={len(ka)} Bud={len(bu)}")

    # ---- STEP 3: Byte-diff Whommie vs Kami anchored from T_start ----
    out("\nSTEP 3 -- Byte diff: Whommie vs Kami, anchored at T_start")
    out("-" * 70)
    wh_raw = info["Whommie"]["raw"]
    wh_ts  = info["Whommie"]["t_start"]
    ka_raw = info["Kami"]["raw"]
    ka_ts  = info["Kami"]["t_start"]
    # Compare from T_start to end of shorter
    max_rel = min(len(wh_raw) - wh_ts, len(ka_raw) - ka_ts)
    # We already know T differs a lot because base-shape IDs differ.
    # Focus on AFTER T+stat section. T is 288 bytes. Gender fields + stats
    # take another ~100ish bytes. Look at rel_offset >= 400.
    diffs = []
    for rel in range(400, max_rel):
        if wh_raw[wh_ts + rel] != ka_raw[ka_ts + rel]:
            diffs.append(rel)
    out(f"  Bytes differing at T+>=400: {len(diffs)}")
    if diffs:
        # Cluster consecutive diffs
        clusters = []
        cur = [diffs[0]]
        for d in diffs[1:]:
            if d - cur[-1] <= 4:
                cur.append(d)
            else:
                clusters.append(cur)
                cur = [d]
        clusters.append(cur)
        out(f"  {len(clusters)} diff clusters:")
        for cl in clusters[:30]:
            rel = cl[0]
            w_abs = wh_ts + rel
            k_abs = ka_ts + rel
            w_hex = " ".join(f"{b:02x}" for b in wh_raw[w_abs:w_abs + min(16, len(cl) + 8)])
            k_hex = " ".join(f"{b:02x}" for b in ka_raw[k_abs:k_abs + min(16, len(cl) + 8)])
            out(f"    T+{rel:#x}..+{cl[-1]:#x} ({len(cl)} bytes)")
            out(f"      Whommie: {w_hex}")
            out(f"      Kami:    {k_hex}")

    # ---- STEP 4: Byte diff anchored from BLOB END ----
    out("\nSTEP 4 -- Byte diff: Whommie vs Kami, anchored from BLOB END")
    out("-" * 70)
    # Compare last N bytes
    N = min(len(wh_raw), len(ka_raw), 400)
    end_diffs = []
    for i in range(1, N + 1):
        if wh_raw[-i] != ka_raw[-i]:
            end_diffs.append(-i)
    end_diffs.sort()
    out(f"  Bytes differing in last {N} bytes: {len(end_diffs)}")
    if end_diffs:
        clusters = []
        cur = [end_diffs[0]]
        for d in end_diffs[1:]:
            if d - cur[-1] <= 4:
                cur.append(d)
            else:
                clusters.append(cur)
                cur = [d]
        clusters.append(cur)
        out(f"  {len(clusters)} diff clusters (end-anchored):")
        for cl in clusters[:30]:
            rel = cl[0]
            w_abs = len(wh_raw) + rel
            k_abs = len(ka_raw) + rel
            w_hex = " ".join(f"{b:02x}" for b in wh_raw[w_abs:w_abs + 16])
            k_hex = " ".join(f"{b:02x}" for b in ka_raw[k_abs:k_abs + 16])
            out(f"    end{rel}..{cl[-1]}")
            out(f"      Whommie: {w_hex}")
            out(f"      Kami:    {k_hex}")

    # ---- STEP 5: files table enumeration (Direction 7c from CLAUDE.md) ----
    out("\nSTEP 5 -- Full files table enumeration")
    out("-" * 70)
    cur = conn.cursor()
    try:
        rows = cur.execute("SELECT key, length(data) FROM files").fetchall()
        for k, ln in rows:
            out(f"  key={k!r}  size={ln}")
            # Check if the blob contains Whommie's UID (8 bytes)
            wh_cat = info["Whommie"]["cat"]
            wh_uid = struct.pack("<Q", wh_cat.uid & 0xFFFFFFFFFFFFFFFF) if hasattr(wh_cat, "uid") else None
            if wh_uid:
                raw_row = cur.execute("SELECT data FROM files WHERE key=?", (k,)).fetchone()
                data = bytes(raw_row[0])
                # Try lz4 decompress
                try:
                    uncomp = struct.unpack_from("<I", data, 0)[0]
                    blob = lz4.block.decompress(data[4:], uncompressed_size=uncomp)
                except Exception:
                    blob = data
                if wh_uid in blob:
                    out(f"    ** Whommie UID found in file {k!r}")
    except Exception as e:
        out(f"  files table error: {e}")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
