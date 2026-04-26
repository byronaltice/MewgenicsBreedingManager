"""Direction #14 -- Pedigree by db_key + GPAK disorder/birth_defect files.

Two parallel investigations:

A) GPAK file listing + disorders/birth_defects GON content.
   Direction #10 only checked eyes/eyebrows/ears/legs/arms.
   This script lists ALL GPAK files and parses any that mention
   'disorder', 'birth_defect', or 'defect' in their path/content.
   The community says "first a disorder roll, then a birth-defect-parts roll."
   There may be a top-level mapping file we haven't seen.

B) Pedigree blob search by db_key.
   Direction 7e searched by _uid_int and found nothing.
   This script searches for db_key (u32) in the pedigree blob,
   attempts to locate per-cat records, and diffs Whommie vs Kami.
"""
from __future__ import annotations

import re
import struct
import sqlite3
import sys
from pathlib import Path
from collections import Counter

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save, GameData  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
GPAK = ROOT / "test-saves" / "resources.gpak"
OUT = Path(__file__).parent / "direction14_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def raw_blob_from_db(conn, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    data = bytes(row[0])
    uncomp = struct.unpack_from("<I", data, 0)[0]
    return lz4.block.decompress(data[4:], uncompressed_size=uncomp)


# ── Part A: GPAK file listing and disorder/birth_defect content ──────────────

def load_gpak_directory(gpak_path: Path) -> tuple[list[tuple[str, int]], int]:
    """Return ([(name, size), ...], dir_end_offset)."""
    with open(gpak_path, "rb") as f:
        count = struct.unpack("<I", f.read(4))[0]
        entries = []
        for _ in range(count):
            name_len = struct.unpack("<H", f.read(2))[0]
            name = f.read(name_len).decode("utf-8", errors="replace")
            size = struct.unpack("<I", f.read(4))[0]
            entries.append((name, size))
        return entries, f.tell()


def read_gpak_file(gpak_path: Path, entries: list, dir_end: int, target_name: str) -> bytes | None:
    offset = dir_end
    for name, size in entries:
        if name == target_name:
            with open(gpak_path, "rb") as f:
                f.seek(offset)
                return f.read(size)
        offset += size
    return None


def part_a_gpak_analysis() -> None:
    out("=" * 70)
    out("PART A -- GPAK file listing and disorder/birth_defect content")
    out("=" * 70)

    entries, dir_end = load_gpak_directory(GPAK)
    out(f"Total GPAK files: {len(entries)}")
    out("")

    # List all files
    DEFECT_KEYWORDS = re.compile(
        r"(disorder|birth.?defect|defect|variant|no.?part|missing)", re.IGNORECASE
    )

    out("-- All GPAK file paths --")
    for name, size in entries:
        flag = " <-- DEFECT KEYWORD" if DEFECT_KEYWORDS.search(name) else ""
        out(f"  {name:60s} {size:6d} bytes{flag}")
    out("")

    out("-- Searching GPAK file CONTENTS for defect keywords --")
    offset = dir_end
    hits_in_content: list[str] = []
    with open(GPAK, "rb") as f:
        for name, size in entries:
            f.seek(offset)
            content = f.read(size)
            offset += size
            try:
                text = content.decode("utf-8", errors="replace")
                if DEFECT_KEYWORDS.search(text):
                    hits_in_content.append(name)
            except Exception:
                pass

    if hits_in_content:
        out(f"Files with defect keywords in content: {len(hits_in_content)}")
        for name in hits_in_content:
            out(f"  {name}")
    else:
        out("  (none found)")
    out("")

    out("-- Dumping mutation-related GON files not yet checked --")
    checked = {"eyes.gon", "eyebrows.gon", "ears.gon", "legs.gon", "arms.gon"}
    mutation_files = [
        name for name, _ in entries
        if name.startswith("data/mutations/") and name.endswith(".gon")
        and name.split("/")[-1] not in checked
    ]
    out(f"  Unchecked mutation files: {mutation_files}")
    for fname in mutation_files[:10]:
        content_bytes = read_gpak_file(GPAK, entries, dir_end, fname)
        if content_bytes:
            text = content_bytes.decode("utf-8", errors="replace")
            out(f"\n  === {fname} ({len(content_bytes)} bytes) ===")
            # Show first 2000 chars
            out(text[:2000])
    out("")

    out("-- Full content of any 'disorder' GON files found --")
    disorder_files = [name for name in hits_in_content if "disorder" in name.lower() or "defect" in name.lower()]
    for fname in disorder_files:
        content_bytes = read_gpak_file(GPAK, entries, dir_end, fname)
        if content_bytes:
            text = content_bytes.decode("utf-8", errors="replace")
            out(f"\n  === {fname} ===")
            out(text[:5000])


# ── Part B: Pedigree by db_key ────────────────────────────────────────────────

def part_b_pedigree_by_dbkey() -> None:
    out("=" * 70)
    out("PART B -- Pedigree blob search by db_key")
    out("=" * 70)

    conn = sqlite3.connect(str(SAVE))
    row = conn.execute("SELECT data FROM files WHERE key='pedigree'").fetchone()
    if not row:
        out("  ERROR: pedigree not found in files table")
        conn.close()
        return
    pedigree = bytes(row[0])
    out(f"  Pedigree blob size: {len(pedigree)} bytes")
    out(f"  Pedigree first 32 bytes: {pedigree[:32].hex()}")
    out("")

    # Target cats
    targets = [
        ("Whommie", 853, "MISSING Eye+Eyebrow defects"),
        ("Bud",     887, "MISSING Ear defect"),
        ("Kami",    840, "CLEAN control"),
        ("Flekpus",  68, "DETECTED Eyebrow defect"),
    ]

    out("-- Searching pedigree for db_key as u32 --")
    for name, db_key, label in targets:
        needle = struct.pack("<I", db_key)
        positions = []
        pos = 0
        while True:
            idx = pedigree.find(needle, pos)
            if idx == -1:
                break
            positions.append(idx)
            pos = idx + 1
        out(f"  {name} (db_key={db_key} = 0x{db_key:04x}): found at {positions[:10]}")
    out("")

    out("-- Searching pedigree for db_key as u64 --")
    for name, db_key, label in targets:
        needle = struct.pack("<Q", db_key)
        positions = []
        pos = 0
        while True:
            idx = pedigree.find(needle, pos)
            if idx == -1:
                break
            positions.append(idx)
            pos = idx + 1
        out(f"  {name} (db_key={db_key}): u64 found at {positions[:10]}")
    out("")

    out("-- Attempt to decode pedigree as fixed-size records --")
    # Common record sizes to try: 188, 192, 194, 196, 200
    cat_count = len(pedigree) // 188
    out(f"  Trying record_size=188: {cat_count} records @ 188 bytes")
    for record_size in [188, 192, 194, 196, 200]:
        out(f"\n  record_size={record_size}: check if Whommie db_key=853 appears in record {853 % (len(pedigree) // record_size)}")

    out("")
    out("-- Pedigree structure exploration: first 600 bytes --")
    for chunk_start in range(0, min(600, len(pedigree)), 16):
        chunk = pedigree[chunk_start:chunk_start + 16]
        hex_str = " ".join(f"{b:02x}" for b in chunk)
        # Try to interpret as u32 array
        u32s = [struct.unpack_from("<I", pedigree, chunk_start + j)[0]
                for j in range(0, min(16, len(pedigree) - chunk_start), 4)]
        out(f"  0x{chunk_start:04x}: {hex_str}  {u32s}")
    out("")

    out("-- Scan pedigree for known UIDs of target cats --")
    save_data = parse_save(str(SAVE))
    cats_list = save_data.cats
    cat_by_name = {c.name: c for c in cats_list}

    for name, db_key, label in targets:
        cat = cat_by_name.get(name)
        if cat is None:
            out(f"  {name}: not in save")
            continue
        uid = cat._uid_int
        needle = struct.pack("<Q", uid)
        positions = []
        pos = 0
        while True:
            idx = pedigree.find(needle, pos)
            if idx == -1:
                break
            positions.append(idx)
            pos = idx + 1
        out(f"  {name} uid={uid:#018x}: uid found at {positions[:10]}")
    out("")

    out("-- Check if pedigree has a header (count field) --")
    if len(pedigree) >= 8:
        u32_0 = struct.unpack_from("<I", pedigree, 0)[0]
        u32_1 = struct.unpack_from("<I", pedigree, 4)[0]
        u64_0 = struct.unpack_from("<Q", pedigree, 0)[0]
        out(f"  pedigree[0..3] as u32: {u32_0}")
        out(f"  pedigree[4..7] as u32: {u32_1}")
        out(f"  pedigree[0..7] as u64: {u64_0}")
        out(f"  888 cats × ? = {len(pedigree)} → per_cat ≈ {len(pedigree) / 888:.1f} bytes")
    out("")

    out("-- Diff pedigree regions for Whommie vs Kami (if db_key found) --")
    for name, db_key, label in targets[:2]:
        needle = struct.pack("<I", db_key)
        idx = pedigree.find(needle)
        if idx != -1:
            out(f"  {name} db_key found at 0x{idx:04x}: {pedigree[idx:idx + 64].hex()}")

    conn.close()


def main() -> None:
    out("=" * 70)
    out("Direction #14 -- Pedigree by db_key + GPAK disorder/birth_defect files")
    out("=" * 70)
    out(f"Save: {SAVE}")
    out(f"GPAK: {GPAK}")
    out("")

    part_a_gpak_analysis()
    part_b_pedigree_by_dbkey()

    OUT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
