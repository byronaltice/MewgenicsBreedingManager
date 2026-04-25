"""
Direction 28 - Locate the 3 x 7-u32 FUN_14022cf90 records.

Direction 27 showed that the records are not immediately after the T array.
This probe follows the parser cursor through:

  T[73] + two body-part container fields
  gender string + body scale
  stat_base/stat_mod/stat_sec
  ability/disorder run
  five empty equipment slots (25-byte trailer in the current snapshot)

Then it dumps and scores the remaining post-run region before the class/tail
block, looking for three consecutive 28-byte records.
"""
from __future__ import annotations

import collections
import re
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
OUT = Path(__file__).parent / "direction28_results.txt"

FOCUS = {
    "Whommie": 853,
    "Kami": 840,
    "Bud": 887,
    "Alaya": 861,
    "Petronij": 841,
    "Murisha": 852,
    "Lucyfer": None,
    "Flekpus": None,
}

TAIL_SIZE = 115
BODY_PART_U32_COUNT = 73
POST_BODY_PART_TOKEN_U32_COUNT = 2
STAT_BLOCK_U32_COUNT = 7
STAT_BLOCK_COUNT = 3
U32_SIZE = 4
F64_SIZE = 8
STRING_PREFIX_SIZE = 8
EQUIPMENT_SLOT_COUNT = 5
ABSENT_EQUIPMENT_SLOT_SIZE = 5
CF90_RECORD_U32_COUNT = 7
CF90_RECORD_COUNT = 3
CF90_RECORD_SIZE = CF90_RECORD_U32_COUNT * U32_SIZE
CF90_GROUP_SIZE = CF90_RECORD_COUNT * CF90_RECORD_SIZE
MAX_STRING_LENGTH = 20_000
ABILITY_SCAN_BYTES = 700
ABILITY_RUN_LIMIT = 32
TAIL_SLOT_COUNT = 3
CLASS_MIN_LEN = 3
CLASS_MAX_LEN = 29
TOP_CANDIDATE_COUNT = 12
HEX_PREVIEW_BYTES = 128
PHASE_SCAN_LABELS = (
    "after_stats_to_run",
    "run_to_after_run",
    "after_run_to_class",
    "after_stats_to_class",
)

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFECT_SENTINEL = 0xFFFF_FFFE

_lines: list[str] = []


@dataclass(frozen=True)
class CursorMap:
    t_start: int
    after_body_parts: int
    after_token_fields: int
    after_gender: int
    after_scale: int
    after_stats: int
    run_start: int
    after_ability_run: int
    after_equipment_slots: int
    class_prefix: int
    tail_start: int


@dataclass(frozen=True)
class CatBlob:
    name: str
    db_key: int
    cat: object
    raw: bytes
    cursor: CursorMap


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
    if pos + STRING_PREFIX_SIZE > len(raw):
        return None, pos
    length = struct.unpack_from("<Q", raw, pos)[0]
    if length > MAX_STRING_LENGTH or pos + STRING_PREFIX_SIZE + length > len(raw):
        return None, pos
    start = pos + STRING_PREFIX_SIZE
    end = start + int(length)
    try:
        return raw[start:end].decode("utf-8"), end
    except UnicodeDecodeError:
        return None, pos


def locate_class_prefix(raw: bytes) -> int:
    class_str_end = len(raw) - TAIL_SIZE
    for class_len in range(CLASS_MIN_LEN, CLASS_MAX_LEN + 1):
        prefix_pos = class_str_end - class_len - STRING_PREFIX_SIZE
        if prefix_pos < 0:
            continue
        length = struct.unpack_from("<I", raw, prefix_pos)[0]
        zero = struct.unpack_from("<I", raw, prefix_pos + U32_SIZE)[0]
        if length == class_len and zero == 0:
            return prefix_pos
    return class_str_end


def locate_after_stats(raw: bytes, t_start: int) -> tuple[int, int, int, int]:
    reader = BinaryReader(raw, t_start)
    reader.skip(BODY_PART_U32_COUNT * U32_SIZE)
    after_body_parts = reader.pos
    reader.skip(POST_BODY_PART_TOKEN_U32_COUNT * U32_SIZE)
    after_token_fields = reader.pos
    gender_token = reader.str()
    if gender_token is None:
        raise ValueError(f"Could not read gender token at 0x{after_token_fields:x}")
    after_gender = reader.pos
    reader.skip(F64_SIZE)
    after_scale = reader.pos
    reader.skip(STAT_BLOCK_COUNT * STAT_BLOCK_U32_COUNT * U32_SIZE)
    return after_body_parts, after_token_fields, after_gender, after_scale, reader.pos


def locate_after_ability_run(raw: bytes, after_stats: int) -> tuple[int, int]:
    marker = raw.find(b"DefaultMove", after_stats, after_stats + ABILITY_SCAN_BYTES)
    if marker == -1:
        raise ValueError("DefaultMove marker not found")
    run_start = marker - STRING_PREFIX_SIZE

    pos = run_start
    for _ in range(ABILITY_RUN_LIMIT):
        item, new_pos = read_str8(raw, pos)
        if item is None or not IDENT_RE.match(item):
            break
        pos = new_pos

    pos += U32_SIZE
    for _ in range(TAIL_SLOT_COUNT):
        item, new_pos = read_str8(raw, pos)
        if item is None or not IDENT_RE.match(item):
            break
        pos = new_pos + U32_SIZE
    return run_start, pos


def locate_after_equipment_slots(raw: bytes, after_ability_run: int) -> int:
    pos = after_ability_run
    for _ in range(EQUIPMENT_SLOT_COUNT):
        if raw[pos:pos + ABSENT_EQUIPMENT_SLOT_SIZE] != b"\x05\x00\x00\x00\x00":
            return pos
        pos += ABSENT_EQUIPMENT_SLOT_SIZE
    return pos


def build_cursor_map(raw: bytes, cat) -> CursorMap:
    t_start = locate_t_start(raw, cat)
    if t_start < 0:
        raise ValueError("Could not locate T array")
    (
        after_body_parts,
        after_token_fields,
        after_gender,
        after_scale,
        after_stats,
    ) = locate_after_stats(raw, t_start)
    run_start, after_ability_run = locate_after_ability_run(raw, after_stats)
    after_equipment_slots = locate_after_equipment_slots(raw, after_ability_run)
    return CursorMap(
        t_start=t_start,
        after_body_parts=after_body_parts,
        after_token_fields=after_token_fields,
        after_gender=after_gender,
        after_scale=after_scale,
        after_stats=after_stats,
        run_start=run_start,
        after_ability_run=after_ability_run,
        after_equipment_slots=after_equipment_slots,
        class_prefix=locate_class_prefix(raw),
        tail_start=len(raw) - TAIL_SIZE,
    )


def read_u32s(raw: bytes, pos: int, count: int) -> list[int]:
    return [struct.unpack_from("<I", raw, pos + i * U32_SIZE)[0] for i in range(count)]


def format_u32s(values: list[int]) -> str:
    return " ".join(f"{value:08x}" for value in values)


def hex_preview(raw: bytes, start: int, end: int) -> str:
    preview_end = min(end, start + HEX_PREVIEW_BYTES)
    return raw[start:preview_end].hex(" ")


def is_ascii_heavy(raw: bytes, pos: int, size: int) -> bool:
    sample = raw[pos:pos + size]
    printable = sum(1 for byte in sample if 0x20 <= byte <= 0x7E)
    return printable > size // 2


def score_candidate(raw: bytes, pos: int) -> int:
    values = read_u32s(raw, pos, CF90_RECORD_COUNT * CF90_RECORD_U32_COUNT)
    zero_count = values.count(0)
    small_count = sum(1 for value in values if value <= 1000)
    tiny_count = sum(1 for value in values if value <= 20)
    defectish_count = sum(
        1
        for value in values
        if value == DEFECT_SENTINEL or value == 2 or 700 <= value <= 710
    )
    score = zero_count * 2 + small_count + tiny_count + defectish_count * 6
    if is_ascii_heavy(raw, pos, CF90_GROUP_SIZE):
        score -= 20
    return score


def dump_candidate(blob: CatBlob, pos: int) -> None:
    rel = pos - blob.cursor.after_equipment_slots
    rel_after_stats = pos - blob.cursor.after_stats
    score = score_candidate(blob.raw, pos)
    out(
        f"  candidate blob+0x{pos:04x}  "
        f"rel_after_stats={rel_after_stats:+d}  "
        f"rel_after_equipment={rel:+d}  score={score}"
    )
    for record_index in range(CF90_RECORD_COUNT):
        record_pos = pos + record_index * CF90_RECORD_SIZE
        values = read_u32s(blob.raw, record_pos, CF90_RECORD_U32_COUNT)
        out(f"    rec[{record_index}] @ +0x{record_pos:04x}: {format_u32s(values)}")


def dump_phase_candidates(blob: CatBlob, label: str, start: int, end: int) -> None:
    size = end - start
    out(f"  phase {label}: blob[0x{start:04x}:0x{end:04x}] size={size}")
    if size <= 0:
        return
    out(f"    preview: {hex_preview(blob.raw, start, end)}")
    if size < CF90_GROUP_SIZE:
        out(f"    no room for {CF90_GROUP_SIZE}-byte cf90 group")
        return
    candidates = [
        (score_candidate(blob.raw, pos), pos)
        for pos in range(start, end - CF90_GROUP_SIZE + 1)
    ]
    candidates.sort(reverse=True)
    for _, pos in candidates[:TOP_CANDIDATE_COUNT]:
        dump_candidate(blob, pos)


def dump_cat_map(blob: CatBlob) -> None:
    cursor = blob.cursor
    out(f"\n=== {blob.name} (db_key={blob.db_key}) ===")
    out(f"  defects parsed: {list(blob.cat.defects) if blob.cat.defects else []}")
    out(
        "  landmarks: "
        f"T=0x{cursor.t_start:04x}, "
        f"after_T73=0x{cursor.after_body_parts:04x}, "
        f"after_tokens=0x{cursor.after_token_fields:04x}, "
        f"after_gender=0x{cursor.after_gender:04x}, "
        f"after_scale=0x{cursor.after_scale:04x}, "
        f"after_stats=0x{cursor.after_stats:04x}, "
        f"run=0x{cursor.run_start:04x}, "
        f"after_run=0x{cursor.after_ability_run:04x}, "
        f"after_equipment=0x{cursor.after_equipment_slots:04x}, "
        f"class_prefix=0x{cursor.class_prefix:04x}, "
        f"tail=0x{cursor.tail_start:04x}, "
        f"len=0x{len(blob.raw):04x}"
    )
    region_start = cursor.after_ability_run
    region_end = cursor.class_prefix
    out(f"  post-run region bytes: {region_end - region_start}")
    out(f"  post-run preview: {hex_preview(blob.raw, region_start, region_end)}")

    dump_phase_candidates(blob, PHASE_SCAN_LABELS[0], cursor.after_stats, cursor.run_start)
    dump_phase_candidates(blob, PHASE_SCAN_LABELS[1], cursor.run_start, cursor.after_ability_run)
    dump_phase_candidates(blob, PHASE_SCAN_LABELS[2], cursor.after_ability_run, cursor.class_prefix)
    dump_phase_candidates(blob, PHASE_SCAN_LABELS[3], cursor.after_stats, cursor.class_prefix)


def compare_same_relative_offset(blobs: dict[str, CatBlob], relative_offset: int) -> None:
    out(f"\n=== Same relative offset compare: after_stats + {relative_offset} ===")
    for name in ("Whommie", "Bud", "Kami", "Alaya", "Petronij", "Murisha"):
        blob = blobs.get(name)
        if blob is None:
            continue
        pos = blob.cursor.after_stats + relative_offset
        if pos + CF90_GROUP_SIZE > blob.cursor.class_prefix:
            out(f"  {name:10s}: not enough bytes")
            continue
        out(f"\n  {name}:")
        dump_candidate(blob, pos)


def compare_known_window(blobs: dict[str, CatBlob]) -> None:
    offsets = collections.Counter()
    for blob in blobs.values():
        scan_start = blob.cursor.after_stats
        scan_end = blob.cursor.class_prefix
        if scan_end - scan_start < CF90_GROUP_SIZE:
            continue
        best_pos = max(
            range(scan_start, scan_end - CF90_GROUP_SIZE + 1),
            key=lambda pos: score_candidate(blob.raw, pos),
        )
        offsets[best_pos - scan_start] += 1

    out("\n=== Best relative offsets across focus cats ===")
    if not offsets:
        out("  no focus cat had enough post-stats bytes for a cf90 group")
        return
    for relative_offset, count in offsets.most_common():
        out(f"  rel_after_stats={relative_offset:+d}: {count} cat(s)")
    for relative_offset, _ in offsets.most_common(3):
        compare_same_relative_offset(blobs, relative_offset)


def load_focus_blobs(all_cats, conn: sqlite3.Connection) -> dict[str, CatBlob]:
    cat_by_name = {cat.name: cat for cat in all_cats}
    blobs: dict[str, CatBlob] = {}
    for name, db_key in FOCUS.items():
        cat = next((cat for cat in all_cats if cat.db_key == db_key), None) if db_key else cat_by_name.get(name)
        if cat is None:
            out(f"\n{name}: not found")
            continue
        raw = raw_blob(conn, cat.db_key)
        try:
            cursor = build_cursor_map(raw, cat)
        except Exception as exc:
            out(f"\n{name}: cursor map failed: {exc}")
            continue
        blobs[name] = CatBlob(name=name, db_key=cat.db_key, cat=cat, raw=raw, cursor=cursor)
    return blobs


def main() -> None:
    out("Direction 28 - FUN_14022cf90 record locator")
    out(f"Save: {SAVE}")

    save_data = parse_save(str(SAVE))
    all_cats = save_data[0]
    conn = sqlite3.connect(str(SAVE))
    try:
        blobs = load_focus_blobs(all_cats, conn)
        for blob in blobs.values():
            dump_cat_map(blob)
        compare_known_window(blobs)
    finally:
        conn.close()

    OUT.write_text("\n".join(_lines), encoding="utf-8")
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
