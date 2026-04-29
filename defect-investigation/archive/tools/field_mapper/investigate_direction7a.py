"""Direction 7a -- Does T extend past 72 elements?

Per CLAUDE.md, community reverse-engineering says birth defects are stored as
"part variants" in a parallel array. Sub-hypothesis (a): T is actually longer
than 72 u32s, and T[72..] is the variant array.

Compare T[72..79] for:
  - Whommie (db_key=853): 3 defects (eye Blind, eyebrow -2 CHA, fur) -- parser misses eye+eyebrow
  - Bud (db_key=887): ear defect (-2 DEX) -- parser misses
  - Kami (db_key=840): 0 defects, SAME eye/eyebrow base-shape IDs as Whommie (control)
  - Petronij, Romanoba: additional clean controls

If any T[72+] position has value 2 (or 0xFFFFFFFE) for Whommie's eye/eyebrow
slot positions but 0 for Kami's, that is the variant array.
"""
from __future__ import annotations

import sys
import struct
import sqlite3
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save, GameData, set_visual_mut_data

_TS = ROOT / "test-saves"
if not _TS.exists():
    _TS = Path(os.path.expandvars(r"%USERPROFILE%\gitprojects\MewgenicsBreedingManager\test-saves"))
SAVE = _TS / "steamcampaign01.sav"
GPAK = _TS / "resources.gpak"
OUT  = Path(__file__).parent / "direction7a_results.txt"

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


def dump_t_extended(name: str, cat, raw: bytes, extra: int = 32) -> list[int]:
    t_start = locate_t_start(raw, cat)
    if t_start < 0:
        out(f"  {name}: T start not found")
        return []
    total = 72 + extra
    t_ext = [struct.unpack_from("<I", raw, t_start + i * 4)[0] for i in range(total)]
    out(f"  {name} (db_key={cat.db_key})  defects={cat.defects}")
    out(f"    T start = 0x{t_start:x}")
    # Print T[68..72+extra] as that's the part we care about (last real slot + extension)
    for i in range(68, total):
        val = t_ext[i]
        marker = ""
        if val == 0xFFFFFFFE:
            marker = "  <-- 0xFFFFFFFE (missing-part sentinel)"
        elif val == 2:
            marker = "  <-- value 2 (canonical No Part defect ID)"
        out(f"    T[{i:2d}] = {val} (0x{val:08x}){marker}")
    return t_ext


def slot_index(field_name: str, fields_list) -> int | None:
    for f in fields_list:
        if f.name == field_name:
            return f.table_index
    return None


def main() -> None:
    out("=" * 70)
    out("Direction 7a -- Does T extend past 72 elements?")
    out("=" * 70)

    gd = GameData.from_gpak(str(GPAK))
    set_visual_mut_data(gd.visual_mutation_data)

    from save_parser import _VISUAL_MUTATION_FIELDS
    out("  Slot indices (for reference):")
    for f in _VISUAL_MUTATION_FIELDS:
        out(f"    {f[0]:20s} table_index={f[1]}")
    out()

    save_data = parse_save(str(SAVE))
    cat_map = {c.name: c for c in save_data.cats}
    conn = sqlite3.connect(str(SAVE))

    targets = ["Whommie", "Kami", "Bud", "Petronij", "Romanoba", "Murisha"]

    t_arrays: dict[str, list[int]] = {}
    for name in targets:
        cat = cat_map.get(name)
        if not cat:
            out(f"  {name}: MISSING from save")
            continue
        raw = raw_blob(conn, cat.db_key)
        t_ext = dump_t_extended(name, cat, raw, extra=32)
        if t_ext:
            t_arrays[name] = t_ext
        out()

    # Diff Whommie vs Kami (same base-shape IDs, different defects)
    out("=" * 70)
    out("Diff: Whommie (3 defects) vs Kami (0 defects, same eye/eyebrow base-shapes)")
    out("=" * 70)
    wh = t_arrays.get("Whommie")
    ka = t_arrays.get("Kami")
    if wh and ka:
        for i in range(min(len(wh), len(ka))):
            if wh[i] != ka[i]:
                out(f"  T[{i:2d}]: Whommie={wh[i]} (0x{wh[i]:08x})  Kami={ka[i]} (0x{ka[i]:08x})")

    out()
    out("=" * 70)
    out("Diff: Bud (ear defect) vs Kami (clean)")
    out("=" * 70)
    bu = t_arrays.get("Bud")
    if bu and ka:
        for i in range(min(len(bu), len(ka))):
            if bu[i] != ka[i]:
                out(f"  T[{i:2d}]: Bud={bu[i]} (0x{bu[i]:08x})  Kami={ka[i]} (0x{ka[i]:08x})")

    out()
    out("=" * 70)
    out("Looking for value 2 or 0xFFFFFFFE at T[72..] for defective cats:")
    out("=" * 70)
    for name, arr in t_arrays.items():
        hits = [(i, v) for i, v in enumerate(arr[72:], start=72) if v in (2, 0xFFFFFFFE)]
        out(f"  {name}: hits in T[72..] = {hits}")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
