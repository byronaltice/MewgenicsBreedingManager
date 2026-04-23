"""Direction #13 -- Full run_items dump and post-disorders blob analysis.

The save_parser reads run_items[1:6] as abilities and run_items[10:] as
passives, silently ignoring run_items[6:9]. Additionally, after reading
disorders + tiers the parser stops; bytes between that point and the blob
tail are unread.

This script:
1. Dumps ALL run_items (positions 0-31) for Whommie, Bud, Kami, Flekpus
   (Flekpus has DETECTED Eyebrow Birth Defect via brow=0xFFFFFFFE).
2. Dumps the r.pos after the run_items loop + disorder tiers.
3. Dumps all remaining blob bytes (pos → blob_end) for defective vs clean cats.
4. Does a roster-wide byte pattern search in the post-disorders region.

Hypothesis: birth defect variant data for the "missing part" cases (Whommie,
Bud) is encoded in run_items[6:9], in additional tail slots, or in the
unread post-disorders region.
"""
from __future__ import annotations

import re
import struct
import sqlite3
import sys
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
# Worktrees don't have test-saves; fall back to main repo root.
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]  # up from .claude/worktrees/<name>/
sys.path.insert(0, str(ROOT / "src"))

from save_parser import (  # noqa: E402
    parse_save, _VISUAL_MUTATION_FIELDS, GameData, set_visual_mut_data,
    BinaryReader,
)

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
GPAK = ROOT / "test-saves" / "resources.gpak"
OUT = Path(__file__).parent / "direction13_results.txt"

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_JUNK = frozenset({"none", "null", "", "defaultmove", "default_move"})

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


def replay_to_post_stats(raw: bytes, t_start: int) -> int:
    """Return r.pos after T + gender + stats (same as Cat.__init__ curr)."""
    r = BinaryReader(raw, t_start + 72 * 4)
    r.skip(12)  # 3 x u32 gender fields
    length = struct.unpack_from("<Q", raw, r.pos)[0]
    r.skip(8 + int(length))  # gender str (u64 length + bytes)
    r.skip(8)   # f64
    r.skip(7 * 4 * 3)  # stat_base, stat_mod, stat_sec (7 x u32 each x 3)
    return r.pos


def find_default_move(raw: bytes, start: int) -> int:
    marker = b"DefaultMove"
    idx = raw.find(marker, start, start + 700)
    return idx if idx != -1 else -1


def read_str_at(raw: bytes, pos: int) -> tuple[str | None, int]:
    """Read a u64-prefixed UTF-8 string. Returns (string, new_pos) or (None, pos)."""
    if pos + 8 > len(raw):
        return None, pos
    length = struct.unpack_from("<Q", raw, pos)[0]
    if length > 200:
        return None, pos
    end = pos + 8 + int(length)
    if end > len(raw):
        return None, pos
    try:
        s = raw[pos + 8:end].decode("utf-8")
        return s, end
    except Exception:
        return None, pos


def read_u32_at(raw: bytes, pos: int) -> tuple[int | None, int]:
    if pos + 4 > len(raw):
        return None, pos
    v = struct.unpack_from("<I", raw, pos)[0]
    return v, pos + 4


def dump_run_items_and_tail(name: str, cat, raw: bytes) -> int:
    """
    Dump full run_items and post-run bytes. Returns r.pos after disorders.
    """
    t_start = locate_t_start(raw, cat)
    curr = replay_to_post_stats(raw, t_start)
    dm = find_default_move(raw, curr)
    if dm == -1:
        out(f"  ERROR: DefaultMove not found for {name}")
        return curr

    run_start = dm - 8
    lo = struct.unpack_from("<I", raw, run_start)[0]
    hi = struct.unpack_from("<I", raw, run_start + 4)[0]
    if hi != 0 or not (1 <= lo <= 96):
        out(f"  ERROR: bad run_start prefix for {name}")
        return curr

    pos = run_start
    run_items: list[tuple[str, int]] = []  # (string, start_pos)
    for _ in range(32):
        s, new_pos = read_str_at(raw, pos)
        if s is None or not _IDENT_RE.match(s):
            break
        run_items.append((s, pos))
        pos = new_pos

    out(f"  {name}: {len(run_items)} run_items")
    for i, (s, sp) in enumerate(run_items):
        role = ""
        if i == 0:
            role = " [DefaultMove]"
        elif 1 <= i <= 5:
            role = f" [ability{i}]"
        elif 6 <= i <= 9:
            role = f" [SLOT{i}-UNKNOWN]"
        elif i >= 10:
            role = f" [passive/slot{i}]"
        out(f"    [{i:2d}] @0x{sp:x} {s!r:30s}{role}")

    # Now read passive1_tier
    passive1_tier, pos = read_u32_at(raw, pos)
    out(f"  passive1_tier: {passive1_tier} (at 0x{pos - 4:x})")

    # Read 3 tail slots
    for tail_idx in range(3):
        s, new_pos = read_str_at(raw, pos)
        tier, new_pos2 = read_u32_at(raw, new_pos)
        label = "passive2" if tail_idx == 0 else f"disorder{tail_idx}"
        out(f"  tail[{tail_idx}]: {s!r:20s} tier={tier}  @0x{pos:x}")
        if s is not None and _IDENT_RE.match(s):
            pos = new_pos2
        else:
            break

    out(f"  post-disorders pos: 0x{pos:x}  blob_len: 0x{len(raw):x}  remaining: {len(raw) - pos}")
    out(f"  remaining bytes (first 80): {raw[pos:pos + 80].hex()}")
    out("")
    return pos


def main() -> None:
    out("=" * 70)
    out("Direction #13 -- Full run_items dump + post-disorders blob analysis")
    out("=" * 70)
    out(f"Save: {SAVE}\n")

    gd = GameData.from_gpak(str(GPAK))
    set_visual_mut_data(gd.visual_mutation_data)

    save_data = parse_save(str(SAVE))
    cats = save_data.cats
    cat_map = {c.name: c for c in cats}
    key_map = {c.db_key: c for c in cats}

    conn = sqlite3.connect(str(SAVE))

    targets = [
        ("Whommie",   853, "MISSING Eye+Eyebrow defects"),
        ("Bud",       887, "MISSING Ear defect"),
        ("Kami",      840, "CLEAN control (eye=139, brow=23, same as Whommie)"),
        ("Flekpus",    68, "DETECTED Eyebrow defect (brow=0xFFFFFFFE)"),
        ("Petronij",  841, "CLEAN control"),
    ]

    out("=" * 70)
    out("STEP 1 -- Full run_items dump for each target cat")
    out("=" * 70)

    post_disorder_positions: dict[str, tuple[int, bytes]] = {}
    for name, db_key, label in targets:
        cat = key_map.get(db_key)
        if cat is None:
            out(f"  WARNING: {name} (db_key={db_key}) not in save")
            continue
        raw = raw_blob(conn, db_key)
        out(f"-- {name} (db_key={db_key}): {label} --")
        out(f"   detected defects: {cat.defects}")
        final_pos = dump_run_items_and_tail(name, cat, raw)
        post_disorder_positions[name] = (final_pos, raw)

    out("=" * 70)
    out("STEP 2 -- Byte-level diff of post-disorders region: Whommie vs controls")
    out("=" * 70)
    if "Whommie" in post_disorder_positions and "Kami" in post_disorder_positions:
        w_pos, w_raw = post_disorder_positions["Whommie"]
        for ctrl_name in ("Kami", "Petronij"):
            if ctrl_name not in post_disorder_positions:
                continue
            c_pos, c_raw = post_disorder_positions[ctrl_name]
            w_region = w_raw[w_pos:w_pos + 200]
            c_region = c_raw[c_pos:c_pos + 200]
            diffs = []
            for j in range(min(len(w_region), len(c_region))):
                if w_region[j] != c_region[j]:
                    diffs.append((j, w_region[j], c_region[j]))
            out(f"  Whommie vs {ctrl_name}: {len(diffs)} diffs in first 200 bytes")
            for offset, wb, cb in diffs[:20]:
                out(f"    +{offset:3d}: Whommie=0x{wb:02x} ({wb})  {ctrl_name}=0x{cb:02x} ({cb})")
        out("")

    out("=" * 70)
    out("STEP 3 -- Roster-wide: scan post-disorders region for defect signal")
    out("=" * 70)
    out("For each cat: find post-disorders pos, extract next 40 bytes.")
    out("Look for any byte position where defective cats consistently differ.")

    defective_regions: list[bytes] = []
    clean_regions: list[bytes] = []
    errors = 0

    for cat in cats:
        try:
            raw = raw_blob(conn, cat.db_key)
            t_start = locate_t_start(raw, cat)
            if t_start == -1:
                continue
            curr = replay_to_post_stats(raw, t_start)
            dm = find_default_move(raw, curr)
            if dm == -1:
                continue
            run_start = dm - 8
            lo = struct.unpack_from("<I", raw, run_start)[0]
            hi = struct.unpack_from("<I", raw, run_start + 4)[0]
            if hi != 0 or not (1 <= lo <= 96):
                continue

            pos = run_start
            for _ in range(32):
                s, new_pos = read_str_at(raw, pos)
                if s is None or not _IDENT_RE.match(s):
                    break
                pos = new_pos

            _, pos = read_u32_at(raw, pos)  # passive1_tier
            for _ in range(3):
                s, new_pos = read_str_at(raw, pos)
                _, new_pos2 = read_u32_at(raw, new_pos)
                if s is not None and _IDENT_RE.match(s):
                    pos = new_pos2
                else:
                    break

            region = raw[pos:pos + 40]
            if len(cat.defects) > len([d for d in cat.defects if "Fur" in d or "Leg" in d or "Arm" in d or "Body" in d or "Head" in d or "Tail" in d or "Mouth" in d]):
                # has eye/eyebrow/ear defect
                pass

            has_undetected_type = any(
                slot in cat.visual_mutation_slots
                for slot in ("eye_L", "eyebrow_L", "ear_L")
                if cat.visual_mutation_slots.get(slot, 0) < 300
            )
            # More useful: separate by whether cat has ANY defect
            if cat.defects:
                defective_regions.append(region)
            else:
                clean_regions.append(region)
        except Exception as e:
            errors += 1

    out(f"  Scanned: {len(defective_regions)} defective + {len(clean_regions)} clean cats  ({errors} errors)")

    # For each byte position 0..39, compare distributions
    out("  Byte positions with differing mode values (defective vs clean):")
    from collections import Counter
    for byte_pos in range(40):
        def_vals = Counter(r[byte_pos] for r in defective_regions if len(r) > byte_pos)
        clean_vals = Counter(r[byte_pos] for r in clean_regions if len(r) > byte_pos)
        def_mode = def_vals.most_common(1)[0] if def_vals else (None, 0)
        clean_mode = clean_vals.most_common(1)[0] if clean_vals else (None, 0)
        if def_mode[0] != clean_mode[0]:
            out(f"    byte[{byte_pos:2d}]: defective_mode={def_mode[0]:3} ({def_mode[1]}x)  clean_mode={clean_mode[0]:3} ({clean_mode[1]}x)")

    out("")
    out("=" * 70)
    out("STEP 4 -- Dump full post-disorders hex for Whommie and Flekpus (detected)")
    out("  Flekpus has DETECTED Eyebrow defect, Whommie has UNDETECTED.")
    out("  Compare their post-disorders structure directly.")
    out("=" * 70)
    for name in ("Whommie", "Flekpus", "Bud", "Kami"):
        if name not in post_disorder_positions:
            continue
        pos, raw = post_disorder_positions[name]
        region = raw[pos:pos + 200]
        out(f"  {name} post-disorders ({len(raw) - pos} remaining bytes):")
        for chunk_start in range(0, min(len(region), 120), 16):
            chunk = region[chunk_start:chunk_start + 16]
            hex_str = " ".join(f"{b:02x}" for b in chunk)
            out(f"    0x{pos + chunk_start:04x}: {hex_str}")
    out("")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
