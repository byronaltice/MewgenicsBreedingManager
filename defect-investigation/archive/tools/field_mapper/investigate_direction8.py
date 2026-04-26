"""Direction #8 -- Per-slot T array deep dive.

For each body-part slot, dump T[index], T[index+1], T[index+2], T[index+3],
T[index+4] for Whommie, Bud, and clean controls. The claim in CLAUDE.md is
that T[+1..+4] are constants or fur-echoes. This script verifies that claim
for EXACTLY the defective slots (Whommie eye/eyebrow, Bud ear) vs. clean
controls with identical T[index+0].

Also dumps the 64-byte pre-T block as 8 f64s for each cat for a direct
visual comparison.
"""
from __future__ import annotations

import sys
import struct
import sqlite3
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save, _VISUAL_MUTATION_FIELDS  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction8_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    print(msg)
    _lines.append(msg)


def raw_blob(conn, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    data = bytes(row[0])
    uncomp = struct.unpack_from("<I", data, 0)[0]
    return lz4.block.decompress(data[4:], uncompressed_size=uncomp)


def locate_t_array(raw: bytes, cat) -> int:
    """Return the absolute byte offset in `raw` where T[0] begins.

    Uses the same structure logic as Cat.__init__: the T array starts after
    name, name_tag, parent UIDs, collar, a u32, and a 64-byte skip block.
    We locate T[0] by searching for fur ID (known) at the expected spot.
    """
    # Use Cat's parsed slots as ground truth and the personality_anchor-style
    # approach. We'll just brute-search for a position where:
    #   T[0] (fur) and T[3] (body) and T[8] (head) match known values
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


def main() -> None:
    out("=" * 70)
    out("Direction #8 -- T array per-slot deep dive + pre-T f64 block")
    out("=" * 70)
    out(f"Save: {SAVE}\n")

    save_data = parse_save(str(SAVE))
    cats = save_data.cats
    cat_map = {c.name: c for c in cats}

    conn = sqlite3.connect(str(SAVE))

    targets = {
        "Whommie": [("eye_L", "DEFECT"), ("eye_R", "DEFECT"),
                    ("eyebrow_L", "DEFECT"), ("eyebrow_R", "DEFECT")],
        "Bud":     [("ear_L", "DEFECT"), ("ear_R", "DEFECT")],
        "Kami":    [("eye_L", "CLEAN"), ("eyebrow_L", "CLEAN"), ("ear_L", "CLEAN")],
        "Petronij": [("eye_L", "CLEAN"), ("eyebrow_L", "CLEAN"), ("ear_L", "CLEAN")],
        "Romanoba": [("eye_L", "CLEAN"), ("eyebrow_L", "CLEAN"), ("ear_L", "CLEAN")],
        "Murisha": [("ear_L", "CLEAN")],
    }

    slot_index = {name: idx for name, idx, *_ in _VISUAL_MUTATION_FIELDS}

    t_data: dict[str, tuple[list[int], int]] = {}  # name -> (T array, t_start)
    for name in targets:
        if name not in cat_map:
            out(f"WARNING: {name} not in save")
            continue
        cat = cat_map[name]
        raw = raw_blob(conn, cat.db_key)
        t_start = locate_t_array(raw, cat)
        T = [struct.unpack_from("<I", raw, t_start + 4 * i)[0] for i in range(72)]
        t_data[name] = (T, t_start)

    out("=" * 70)
    out("STEP 1 -- Per-slot T[index..index+4] dump")
    out("=" * 70)
    out(f"{'cat':10s} {'slot':10s} {'label':6s} {'[0]':>10s} {'[+1]':>10s} {'[+2]':>10s} {'[+3]':>10s} {'[+4]':>10s}")
    for name, slots in targets.items():
        if name not in t_data:
            continue
        T, _ = t_data[name]
        for slot_key, label in slots:
            idx = slot_index[slot_key]
            row = [T[idx + i] if idx + i < 72 else -1 for i in range(5)]
            out(f"{name:10s} {slot_key:10s} {label:6s} "
                f"{row[0]:>10d} {row[1]:>10d} {row[2]:>10d} {row[3]:>10d} {row[4]:>10d}")
        out("")

    out("=" * 70)
    out("STEP 2 -- Pre-T 64-byte block as 8 f64 values")
    out("=" * 70)
    for name in targets:
        if name not in cat_map:
            continue
        cat = cat_map[name]
        raw = raw_blob(conn, cat.db_key)
        _, t_start = t_data[name]
        pre_t_start = t_start - 64
        floats = [struct.unpack_from("<d", raw, pre_t_start + 8 * i)[0] for i in range(8)]
        hex_vals = [raw[pre_t_start + 8 * i:pre_t_start + 8 * i + 8].hex() for i in range(8)]
        out(f"  {name}:")
        for i, (f, h) in enumerate(zip(floats, hex_vals)):
            out(f"    f64[{i}] = {f!r:30s}  raw={h}")
        out("")

    out("=" * 70)
    out("STEP 3 -- Check +/- 4 bytes around each defective slot's T[index+0]")
    out("=" * 70)
    out("Searches for any byte position near the defective slot where")
    out("Whommie/Bud differ from clean controls with matching T[idx+0].")
    out("")
    # For Whommie eye_L (idx=38), T[38]=139. Kami also has T[38]=139.
    # Compare all nearby bytes.
    for def_name, slot_key in [("Whommie", "eye_L"), ("Whommie", "eye_R"),
                                ("Whommie", "eyebrow_L"), ("Whommie", "eyebrow_R"),
                                ("Bud", "ear_L"), ("Bud", "ear_R")]:
        if def_name not in t_data:
            continue
        def_cat = cat_map[def_name]
        def_raw = raw_blob(conn, def_cat.db_key)
        _, def_t_start = t_data[def_name]
        idx = slot_index[slot_key]
        slot_t_pos = def_t_start + 4 * idx  # absolute position of T[idx] in blob

        # Controls matching same T[idx] value
        controls = ["Kami", "Petronij", "Romanoba"] if slot_key.startswith(("eye", "eyebrow")) \
            else ["Kami", "Petronij", "Murisha"]
        same_value = []
        for c_name in controls:
            if c_name not in t_data:
                continue
            c_T, c_t_start = t_data[c_name]
            if c_T[idx] == def_cat.visual_mutation_slots[slot_key]:
                same_value.append((c_name, c_t_start + 4 * idx))

        if not same_value:
            continue

        # Look at 40 bytes before and 40 bytes after slot_t_pos
        WINDOW = 40
        def_slice = def_raw[slot_t_pos - WINDOW:slot_t_pos + WINDOW + 4]
        out(f"  {def_name}.{slot_key} at blob offset 0x{slot_t_pos:x} (T[{idx}]={def_cat.visual_mutation_slots[slot_key]})")
        out(f"    defect bytes (±{WINDOW}B): {def_slice.hex()}")
        for c_name, c_pos in same_value:
            c_cat = cat_map[c_name]
            c_raw = raw_blob(conn, c_cat.db_key)
            c_slice = c_raw[c_pos - WINDOW:c_pos + WINDOW + 4]
            out(f"    {c_name:10s} bytes (±{WINDOW}B): {c_slice.hex()}")
            # Diff byte by byte in the window
            diffs = []
            for j in range(len(def_slice)):
                if j < len(c_slice) and def_slice[j] != c_slice[j]:
                    offset_from_slot = j - WINDOW
                    diffs.append((offset_from_slot, def_slice[j], c_slice[j]))
            out(f"    diffs vs {c_name}: {diffs[:10]}")
        out("")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
