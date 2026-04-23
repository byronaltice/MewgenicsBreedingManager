"""Direction #12 -- Structured parse of gap between stat_sec-end and DefaultMove.

The parser reads T[72], then gender fields, a str, f64, then 3x7 stat arrays.
After that it sets curr=r.pos and jumps to DefaultMove-8. The bytes between
curr and DefaultMove are UNREAD and uncharacterized.

This script:
1. Reproduces the parser's read sequence up to curr
2. Dumps the gap region for Whommie (3 defects) vs Kami (0 defects)
3. Attempts to interpret the gap as structured arrays (u32 lists, str lists)
4. Looks for any value that correlates with the missing eye/eyebrow defects
"""
from __future__ import annotations

import sys
import struct
import sqlite3
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import (
    parse_save, _VISUAL_MUTATION_FIELDS, GameData, set_visual_mut_data,
    BinaryReader,
)

SAVE  = ROOT / "test-saves" / "steamcampaign01.sav"
GPAK  = ROOT / "test-saves" / "resources.gpak"
OUT   = Path(__file__).parent / "direction12_results.txt"

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


def find_default_move(raw: bytes, start: int) -> int:
    marker = b"DefaultMove"
    idx = raw.find(marker, start, start + 700)
    return idx if idx != -1 else -1


def replay_reader_to_curr(raw: bytes, t_start: int) -> int:
    """Return the r.pos after T + gender fields + gender str + f64 + stats."""
    pos = t_start + 72 * 4   # end of T array

    # gender_token_fields: 3 x u32
    pos += 12

    # raw_gender: str() reads u64 length then that many bytes
    length = struct.unpack_from("<Q", raw, pos)[0]
    if length < 0 or length > 10_000:
        # BinaryReader.str() would bail, not advance
        pass
    else:
        pos += 8 + length

    # f64
    pos += 8

    # stat_base (7 x u32), stat_mod (7 x i32), stat_sec (7 x i32)
    pos += 7 * 4 + 7 * 4 + 7 * 4

    return pos


def try_parse_as_u32_array(raw: bytes, start: int, end: int) -> list[int]:
    result = []
    pos = start
    while pos + 4 <= end:
        result.append(struct.unpack_from("<I", raw, pos)[0])
        pos += 4
    return result


def try_parse_as_str_array(raw: bytes, start: int, end: int) -> list[str | None]:
    """Try to parse region as a sequence of u64-prefixed strings."""
    results = []
    pos = start
    while pos + 8 < end:
        length = struct.unpack_from("<Q", raw, pos)[0]
        if length == 0 or length > 200:
            break
        s_bytes = raw[pos + 8: pos + 8 + length]
        try:
            s = s_bytes.decode("utf-8")
        except Exception:
            s = repr(s_bytes)
        results.append(s)
        pos += 8 + length
    return results


def analyze_gap(name: str, raw: bytes, cat, t_start: int) -> dict:
    curr = replay_reader_to_curr(raw, t_start)
    dm_pos = find_default_move(raw, curr)
    if dm_pos == -1:
        out(f"  {name}: DefaultMove NOT found after curr=0x{curr:x}")
        return {}

    run_start = dm_pos - 8  # the u64 ability count is 8 bytes before "DefaultMove"
    gap_start = curr
    gap_end   = run_start
    gap_size  = gap_end - gap_start

    out(f"  {name}: curr=0x{curr:x}  DefaultMove=0x{dm_pos:x}  gap={gap_size} bytes")

    gap = raw[gap_start:gap_end]
    hex_lines = []
    for i in range(0, len(gap), 16):
        chunk = gap[i:i + 16]
        hex_str = " ".join(f"{b:02x}" for b in chunk)
        hex_lines.append(f"    {gap_start+i:4x}: {hex_str}")
    for hl in hex_lines:
        out(hl)

    u32s = try_parse_as_u32_array(raw, gap_start, gap_end)
    out(f"  As u32[]: {u32s}")

    strs = try_parse_as_str_array(raw, gap_start, gap_end)
    out(f"  As str[]: {strs}")
    out()

    return {"gap_start": gap_start, "gap_end": gap_end, "gap": gap, "u32s": u32s}


def main() -> None:
    out("=" * 70)
    out("Direction #12 -- Gap between stat_sec-end and DefaultMove")
    out("=" * 70)

    gd = GameData.from_gpak(str(GPAK))
    set_visual_mut_data(gd.visual_mutation_data)

    save_data = parse_save(str(SAVE))
    cat_map   = {c.name: c for c in save_data.cats}
    conn      = sqlite3.connect(str(SAVE))

    targets = ["Whommie", "Kami", "Bud", "Romanoba", "Petronij", "Murisha"]

    out("=" * 70)
    out("STEP 1 -- Gap dump for each target cat")
    out("=" * 70)

    gap_data: dict[str, dict] = {}
    for name in targets:
        cat = cat_map.get(name)
        if cat is None:
            out(f"  {name}: MISSING")
            continue
        raw = raw_blob(conn, cat.db_key)
        t_start = locate_t_start(raw, cat)
        if t_start < 0:
            out(f"  {name}: T array not found")
            continue
        out(f"  defects={cat.defects}")
        gap_data[name] = analyze_gap(name, raw, cat, t_start)

    out("=" * 70)
    out("STEP 2 -- Byte-level diff: Whommie vs controls at gap offsets")
    out("=" * 70)
    wh = gap_data.get("Whommie")
    if wh:
        for ctrl_name in ["Kami", "Romanoba", "Petronij"]:
            ctrl = gap_data.get(ctrl_name)
            if not ctrl:
                continue
            wh_u = wh["u32s"]
            ct_u = ctrl["u32s"]
            diffs = [(i, wh_u[i], ct_u[i]) for i in range(min(len(wh_u), len(ct_u))) if wh_u[i] != ct_u[i]]
            out(f"  Whommie vs {ctrl_name} u32 diffs: {diffs}")

    out("=" * 70)
    out("STEP 3 -- Try interpreting gap as: u64-count + array of u64-strings")
    out("=" * 70)
    for name in targets:
        cat = cat_map.get(name)
        if cat is None:
            continue
        raw = raw_blob(conn, cat.db_key)
        t_start = locate_t_start(raw, cat)
        if t_start < 0:
            continue
        curr = replay_reader_to_curr(raw, t_start)
        dm_pos = find_default_move(raw, curr)
        if dm_pos == -1:
            continue
        run_start = dm_pos - 8
        pos = curr
        # Try reading as: count (u64) then count strings
        if pos + 8 > run_start:
            out(f"  {name}: gap too small for count-prefix array")
            continue
        count = struct.unpack_from("<Q", raw, pos)[0]
        out(f"  {name}: first u64={count}")
        if 0 < count <= 20:
            pos += 8
            items = []
            ok = True
            for _ in range(count):
                if pos + 8 > run_start:
                    ok = False
                    break
                item_len = struct.unpack_from("<Q", raw, pos)[0]
                if item_len == 0 or item_len > 200:
                    ok = False
                    break
                s = raw[pos + 8: pos + 8 + item_len].decode("utf-8", errors="replace")
                items.append(s)
                pos += 8 + item_len
            if ok:
                out(f"    -> items: {items}")
            else:
                out(f"    -> parse failed after partial: {items}")

    out("=" * 70)
    out("STEP 4 -- Roster-wide: collect gap u32 arrays and look for correlated values")
    out("=" * 70)
    from collections import Counter, defaultdict
    all_gaps: list[tuple[str, list[int], list[str]]] = []
    for cat in save_data.cats:
        try:
            raw = raw_blob(conn, cat.db_key)
            t_start = locate_t_start(raw, cat)
            if t_start < 0:
                continue
            curr = replay_reader_to_curr(raw, t_start)
            dm_pos = find_default_move(raw, curr)
            if dm_pos == -1:
                continue
            run_start = dm_pos - 8
            u32s = try_parse_as_u32_array(raw, curr, run_start)
            all_gaps.append((cat.name, u32s, cat.defects))
        except Exception:
            pass

    out(f"  Processed {len(all_gaps)} cats")

    # Distribution of gap sizes (number of u32s)
    size_counter: Counter = Counter(len(u) for _, u, _ in all_gaps)
    out(f"  Gap u32 count distribution: {dict(size_counter.most_common(10))}")

    # For cats with known defects, what are their gap u32 values?
    out("  Sample defective cats gap u32s:")
    for name, u32s, defects in all_gaps:
        if defects:
            out(f"    {name:20s} defects={defects}  u32s={u32s[:8]}")
        if sum(1 for _, _, d in all_gaps if d and name in [n for n,_,_ in all_gaps]) > 10:
            break

    # Non-zero values at each u32 position
    out("  Non-zero values at each u32 position across defective cats:")
    max_len = max((len(u) for _, u, _ in all_gaps), default=0)
    for pos_idx in range(min(max_len, 8)):
        defect_vals = Counter(u[pos_idx] for _, u, d in all_gaps if d and len(u) > pos_idx and u[pos_idx] != 0)
        clean_vals  = Counter(u[pos_idx] for _, u, d in all_gaps if not d and len(u) > pos_idx and u[pos_idx] != 0)
        if defect_vals:
            out(f"    u32[{pos_idx}] defective non-zero: {dict(defect_vals.most_common(5))}")
            out(f"    u32[{pos_idx}] clean     non-zero: {dict(clean_vals.most_common(5))}")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
