"""
Direction 30 - Decode the post-stat gap before DefaultMove.

Ghidra order after the three FUN_14022cf90 stat records:

  string at CatData+0x788
  FUN_14022d100(CatData+0x7a8)
  string fields at +0x7d0/+0x7f0/... later become the ability run

For the current save, the bytes between stat_sec and DefaultMove were already
observed as a fixed 26-byte gap. This script decodes that gap as:

  u64-prefixed string at +0x788
  d100 header: u32, u8, u8, u32, list_count

and scans the roster for non-empty d100 lists.
"""
from __future__ import annotations

import collections
import struct
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import BinaryReader, parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "investigation" / "steamcampaign01_20260424_191107.sav"
OUT = Path(__file__).parent / "direction30_results.txt"

FOCUS = {
    "Whommie": 853,
    "Kami": 840,
    "Bud": 887,
    "Alaya": 861,
    "Petronij": 841,
    "Murisha": 852,
    "Flekpus": 68,
    "Lucyfer": 255,
}

BODY_PART_U32_COUNT = 73
EXTRA_BODY_PART_U32_COUNT = 2
U32_SIZE = 4
F64_SIZE = 8
STAT_RECORD_COUNT = 3
STAT_COUNT = 7
D100_FIXED_STREAM_SIZE = 14
DEFAULT_MOVE_SCAN_BYTES = 700
MAX_STRING_LENGTH = 20_000

_lines: list[str] = []


@dataclass(frozen=True)
class PostStatGap:
    gap_start: int
    default_move_run_start: int
    field_788: str
    d100_header0: int
    d100_flag4: int
    d100_flag5: int
    d100_header8: int
    d100_count: int
    parsed_end: int
    raw_hex: str


def out(message: str = "") -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", "replace").decode())
    _lines.append(message)


def raw_blob(conn: sqlite3.Connection, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    compressed = bytes(row[0])
    uncompressed_size = struct.unpack_from("<I", compressed, 0)[0]
    return lz4.block.decompress(compressed[U32_SIZE:], uncompressed_size=uncompressed_size)


def locate_t_start(raw: bytes, cat) -> int:
    texture_id = cat.body_parts["texture"]
    body_id = cat.body_parts["bodyShape"]
    head_id = cat.body_parts["headShape"]
    texture_bytes = struct.pack("<I", texture_id)
    for offset in range(0, len(raw) - 9 * U32_SIZE):
        if raw[offset:offset + U32_SIZE] != texture_bytes:
            continue
        body_value = struct.unpack_from("<I", raw, offset + 3 * U32_SIZE)[0]
        head_value = struct.unpack_from("<I", raw, offset + 8 * U32_SIZE)[0]
        if body_value == body_id and head_value == head_id:
            return offset
    return -1


def read_str8(raw: bytes, pos: int) -> tuple[str | None, int]:
    if pos + 8 > len(raw):
        return None, pos
    length = struct.unpack_from("<Q", raw, pos)[0]
    if length > MAX_STRING_LENGTH or pos + 8 + length > len(raw):
        return None, pos
    start = pos + 8
    end = start + int(length)
    return raw[start:end].decode("utf-8", errors="replace"), end


def locate_after_stats(raw: bytes, cat) -> int:
    t_start = locate_t_start(raw, cat)
    if t_start < 0:
        raise ValueError("Could not locate T array")
    reader = BinaryReader(raw, t_start)
    reader.skip(BODY_PART_U32_COUNT * U32_SIZE)
    reader.skip(EXTRA_BODY_PART_U32_COUNT * U32_SIZE)
    if reader.str() is None:
        raise ValueError("Could not read gender string")
    reader.skip(F64_SIZE)
    reader.skip(STAT_RECORD_COUNT * STAT_COUNT * U32_SIZE)
    return reader.pos


def locate_default_move_run(raw: bytes, start: int) -> int:
    marker = raw.find(b"DefaultMove", start, start + DEFAULT_MOVE_SCAN_BYTES)
    if marker == -1:
        raise ValueError("DefaultMove not found")
    return marker - 8


def parse_post_stat_gap(raw: bytes, cat) -> PostStatGap:
    gap_start = locate_after_stats(raw, cat)
    run_start = locate_default_move_run(raw, gap_start)
    field_788, pos = read_str8(raw, gap_start)
    if field_788 is None:
        raise ValueError("Could not read +0x788 string")

    if pos + D100_FIXED_STREAM_SIZE > run_start:
        raise ValueError("Not enough bytes for d100 fixed stream")

    d100_header0 = struct.unpack_from("<I", raw, pos)[0]
    d100_flag4 = raw[pos + 4]
    d100_flag5 = raw[pos + 5]
    d100_header8 = struct.unpack_from("<I", raw, pos + 6)[0]
    d100_count = struct.unpack_from("<I", raw, pos + 10)[0]
    parsed_end = pos + D100_FIXED_STREAM_SIZE

    return PostStatGap(
        gap_start=gap_start,
        default_move_run_start=run_start,
        field_788=field_788,
        d100_header0=d100_header0,
        d100_flag4=d100_flag4,
        d100_flag5=d100_flag5,
        d100_header8=d100_header8,
        d100_count=d100_count,
        parsed_end=parsed_end,
        raw_hex=raw[gap_start:run_start].hex(" "),
    )


def analyze_focus(all_cats, conn: sqlite3.Connection) -> None:
    out("\n=== Focus Cats ===")
    for name, db_key in FOCUS.items():
        cat = next((candidate for candidate in all_cats if candidate.db_key == db_key), None)
        if cat is None:
            out(f"\n{name} (db_key={db_key}): not found")
            continue
        gap = parse_post_stat_gap(raw_blob(conn, cat.db_key), cat)
        out(f"\n{name} (db_key={cat.db_key})")
        out(f"  gap: blob+0x{gap.gap_start:04x}..0x{gap.default_move_run_start:04x} ({gap.default_move_run_start - gap.gap_start} bytes)")
        out(f"  +0x788 string: {gap.field_788!r}")
        out(
            "  d100 header: "
            f"u32@+0={gap.d100_header0:#010x}, "
            f"u8@+4={gap.d100_flag4:#04x}, "
            f"u8@+5={gap.d100_flag5:#04x}, "
            f"u32@+8={gap.d100_header8:#010x}, "
            f"count={gap.d100_count}"
        )
        out(f"  parsed_end matches DefaultMove run_start: {gap.parsed_end == gap.default_move_run_start}")
        out(f"  raw gap: {gap.raw_hex}")


def roster_scan(all_cats, conn: sqlite3.Connection) -> None:
    out("\n=== Roster Scan ===")
    gap_sizes = collections.Counter()
    field_values = collections.Counter()
    d100_headers = collections.Counter()
    non_empty = []
    parse_failures = []

    for cat in all_cats:
        try:
            gap = parse_post_stat_gap(raw_blob(conn, cat.db_key), cat)
        except Exception as exc:
            parse_failures.append((cat.name, cat.db_key, str(exc)))
            continue
        gap_sizes[gap.default_move_run_start - gap.gap_start] += 1
        field_values[gap.field_788] += 1
        d100_headers[(gap.d100_header0, gap.d100_flag4, gap.d100_flag5, gap.d100_header8, gap.d100_count)] += 1
        if gap.d100_count:
            non_empty.append((cat.name, cat.db_key, gap))

    out(f"  parsed cats: {len(all_cats) - len(parse_failures)} / {len(all_cats)}")
    out(f"  parse failures: {len(parse_failures)}")
    for name, db_key, error in parse_failures[:12]:
        out(f"    failure {name} key={db_key}: {error}")

    out("  gap size distribution:")
    for size, count in gap_sizes.most_common():
        out(f"    {size} bytes: {count}")

    out("  +0x788 string distribution:")
    for value, count in field_values.most_common(12):
        out(f"    {value!r}: {count}")

    out("  d100 fixed header distribution:")
    for header, count in d100_headers.most_common(12):
        header0, flag4, flag5, header8, d100_count = header
        out(
            f"    ({header0:#010x}, {flag4:#04x}, {flag5:#04x}, "
            f"{header8:#010x}, count={d100_count}): {count}"
        )

    out(f"  cats with non-empty d100 list: {len(non_empty)}")
    for name, db_key, gap in non_empty[:40]:
        defects = next((cat.defects for cat in all_cats if cat.db_key == db_key), [])
        out(
            f"    {name:20s} key={db_key:4d} count={gap.d100_count} "
            f"field={gap.field_788!r} defects={list(defects) if defects else []}"
        )


def main() -> None:
    out("Direction 30 - Decode post-stat gap and d100 fixed header")
    out(f"Save: {SAVE}")

    save_data = parse_save(str(SAVE))
    all_cats = save_data[0]
    conn = sqlite3.connect(str(SAVE))
    try:
        analyze_focus(all_cats, conn)
        roster_scan(all_cats, conn)
    finally:
        conn.close()

    OUT.write_text("\n".join(_lines), encoding="utf-8")
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
