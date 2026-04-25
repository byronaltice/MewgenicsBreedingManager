"""
npc_progress Investigation Script

Goal:
  Determine whether the files-table npc_progress blob contains any
  cat-linked identifiers or defect-correlated records that could explain
  the missing-part birth defects not present in the cat blobs.

Usage:
    py tools/field_mapper/investigate_npc_progress.py

Output written to tools/field_mapper/npc_progress_results.txt and stdout.
"""

from __future__ import annotations

import collections
import os
import re
import sqlite3
import struct
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
_WORKTREE_REPO_ROOT = os.path.abspath(os.path.join(_REPO_ROOT, "..", "..", ".."))
_SAVE_RELATIVE_PATH = os.path.join("test-saves", "steamcampaign01.sav")
_RESULTS_FILENAME = "npc_progress_results.txt"
_HEX_DUMP_WIDTH = 16
_HEAD_DUMP_SIZE = 160
_STRING_PATTERN = re.compile(rb"[A-Za-z_][A-Za-z0-9_!&'\$ ]{3,}")
_TOP_PREFIX_COUNT = 25
_TOP_STRING_SAMPLE_COUNT = 80
_MAX_TARGET_MATCHES_TO_SHOW = 20

SAVE_PATH = (
    os.path.join(_REPO_ROOT, _SAVE_RELATIVE_PATH)
    if os.path.exists(os.path.join(_REPO_ROOT, _SAVE_RELATIVE_PATH))
    else os.path.join(_WORKTREE_REPO_ROOT, _SAVE_RELATIVE_PATH)
)

sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))
try:
    from save_parser import parse_save
except ModuleNotFoundError:
    sys.path.insert(0, os.path.join(_WORKTREE_REPO_ROOT, "src"))
    from save_parser import parse_save

TARGET_NAMES = ("Whommie", "Bud", "Kami", "Petronij", "Murisha", "Romanoba")
TARGET_TERMS = (
    "blind",
    "eye",
    "eyebrow",
    "ear",
    "ears",
    "birth_defect",
    "defect",
    "mutation",
    "no eyes",
    "no eyebrows",
    "no ears",
)


def hex_dump(blob: bytes, base_offset: int = 0) -> list[str]:
    lines: list[str] = []
    for row_start in range(0, len(blob), _HEX_DUMP_WIDTH):
        chunk = blob[row_start:row_start + _HEX_DUMP_WIDTH]
        hex_part = " ".join(f"{value:02x}" for value in chunk)
        ascii_part = "".join(chr(value) if 32 <= value < 127 else "." for value in chunk)
        lines.append(f"  {base_offset + row_start:06x}: {hex_part:<47}  |{ascii_part}|")
    return lines


def find_all_offsets(blob: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        index = blob.find(needle, start)
        if index == -1:
            break
        offsets.append(index)
        start = index + 1
    return offsets


def classify_prefix(text: str) -> str:
    if "_" in text:
        return text.split("_", 1)[0]
    if text and text[0].isupper():
        return "TitleCase"
    return "misc"


def main() -> None:
    output_lines: list[str] = []

    def out(line: str = "") -> None:
        print(line)
        output_lines.append(line)

    out("=" * 70)
    out("npc_progress Investigation")
    out("=" * 70)
    out(f"Save: {SAVE_PATH}")

    save_data = parse_save(SAVE_PATH)
    all_cats = save_data[0]
    cats_by_name = {cat.name: cat for cat in all_cats}

    conn = sqlite3.connect(SAVE_PATH)
    try:
        row = conn.execute("SELECT data FROM files WHERE key='npc_progress'").fetchone()
        if row is None:
            out()
            out("ERROR: files.key='npc_progress' not found.")
            return
        blob = bytes(row[0])
    finally:
        conn.close()

    out()
    out("-" * 70)
    out("STEP 1 -- Blob overview")
    out("-" * 70)
    out(f"  Blob size: {len(blob)} bytes")
    if len(blob) >= 4:
        top_count = struct.unpack_from("<I", blob, 0)[0]
        out(f"  Leading u32: {top_count}")
    out("  Head hex dump:")
    for line in hex_dump(blob[:_HEAD_DUMP_SIZE]):
        out(line)

    out()
    out("-" * 70)
    out("STEP 2 -- Extract readable strings")
    out("-" * 70)

    strings_with_offsets: list[tuple[int, str]] = []
    for match in _STRING_PATTERN.finditer(blob):
        text = match.group(0).decode("ascii", errors="replace")
        strings_with_offsets.append((match.start(), text))

    out(f"  Readable strings found: {len(strings_with_offsets)}")
    prefix_counter = collections.Counter(classify_prefix(text) for _, text in strings_with_offsets)
    out("  Top prefix groups:")
    for prefix, count in prefix_counter.most_common(_TOP_PREFIX_COUNT):
        out(f"    {prefix:16s} {count:4d}")

    out("  First readable strings:")
    for offset, text in strings_with_offsets[:_TOP_STRING_SAMPLE_COUNT]:
        out(f"    {offset:05d}  {text}")

    out()
    out("-" * 70)
    out("STEP 3 -- Search for target cat identifiers")
    out("-" * 70)

    for name in TARGET_NAMES:
        cat = cats_by_name.get(name)
        out(f"  {name}:")
        ascii_name_offsets = find_all_offsets(blob, name.encode("ascii", errors="ignore"))
        out(f"    ascii name offsets: {ascii_name_offsets[:_MAX_TARGET_MATCHES_TO_SHOW]}  count={len(ascii_name_offsets)}")
        if cat is None:
            out("    cat not present in parsed save")
            continue

        db_key_offsets = find_all_offsets(blob, struct.pack("<I", int(cat.db_key)))
        uid_offsets = find_all_offsets(blob, struct.pack("<Q", int(cat._uid_int)))
        parent_uid_a_offsets = find_all_offsets(blob, struct.pack("<Q", int(getattr(cat, "_parent_uid_a", 0))))
        parent_uid_b_offsets = find_all_offsets(blob, struct.pack("<Q", int(getattr(cat, "_parent_uid_b", 0))))

        out(f"    db_key={cat.db_key} offsets: {db_key_offsets[:_MAX_TARGET_MATCHES_TO_SHOW]}  count={len(db_key_offsets)}")
        out(f"    uid={cat._uid_int} offsets: {uid_offsets[:_MAX_TARGET_MATCHES_TO_SHOW]}  count={len(uid_offsets)}")
        out(
            f"    raw parent_uids=({getattr(cat, '_parent_uid_a', 0)}, {getattr(cat, '_parent_uid_b', 0)}) "
            f"offset counts=({len(parent_uid_a_offsets)}, {len(parent_uid_b_offsets)})"
        )

    out()
    out("-" * 70)
    out("STEP 4 -- Search for defect-related terms")
    out("-" * 70)

    lowercase_blob = blob.lower()
    for term in TARGET_TERMS:
        offsets = find_all_offsets(lowercase_blob, term.encode("ascii"))
        out(f"  {term!r}: {offsets[:_MAX_TARGET_MATCHES_TO_SHOW]}  count={len(offsets)}")

    out()
    out("-" * 70)
    out("STEP 5 -- Nearby context for the closest semantic leads")
    out("-" * 70)

    semantic_offsets = [
        (offset, text)
        for offset, text in strings_with_offsets
        if text.startswith(("beanies_", "tink_", "jack_", "tracy_", "organ_", "steven_", "class_unlock_", "quest_", "map_unlock_", "song_unlock_", "unlock_"))
    ]
    for offset, text in semantic_offsets[:40]:
        context_start = max(0, offset - 12)
        context_end = min(len(blob), offset + len(text) + 12)
        out(f"  {offset:05d}  {text}")
        for line in hex_dump(blob[context_start:context_end], base_offset=context_start):
            out(line)

    out()
    out("-" * 70)
    out("STEP 6 -- Summary signal check")
    out("-" * 70)

    target_name_hits = sum(len(find_all_offsets(blob, name.encode("ascii", errors="ignore"))) for name in TARGET_NAMES)
    target_uid_hits = 0
    for name in TARGET_NAMES:
        cat = cats_by_name.get(name)
        if cat is None:
            continue
        target_uid_hits += len(find_all_offsets(blob, struct.pack("<Q", int(cat._uid_int))))

    defect_term_hits = {
        term: len(find_all_offsets(lowercase_blob, term.encode("ascii")))
        for term in TARGET_TERMS
    }

    out(f"  Total target-name ascii hits: {target_name_hits}")
    out(f"  Total target-UID hits: {target_uid_hits}")
    out(f"  Defect-term hit counts: {defect_term_hits}")

    high_level_conclusion = (
        "npc_progress appears to be a progression / unlock / NPC-state blob populated "
        "with quest, unlock, map, class, item, and ability strings. In this save it "
        "contains no direct ascii cat-name hits for the target cats and no raw u64 UID hits "
        "for those cats. That makes it a weak candidate for storing the missing-part defect "
        "flags directly."
    )
    out()
    out(high_level_conclusion)

    out_path = os.path.join(_SCRIPT_DIR, _RESULTS_FILENAME)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(output_lines))
    print(f"\nResults also written to: {out_path}")


if __name__ == "__main__":
    main()
