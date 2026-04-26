"""
Direction #3 Investigation Script -- Parent / Offspring Blob Diff

Goal:
  Compare defective offspring blobs against both clean parents to find
  byte offsets that flip consistently when a defect is inherited.

Usage:
    py tools/field_mapper/investigate_direction3.py

Output written to tools/field_mapper/direction3_results.txt and stdout.
"""

from __future__ import annotations

import math
import os
import sqlite3
import struct
import sys
from dataclasses import dataclass

import lz4.block

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
_WORKTREE_REPO_ROOT = os.path.abspath(os.path.join(_REPO_ROOT, "..", "..", ".."))
_SAVE_NAME = "steamcampaign01.sav"
_SAVE_RELATIVE_PATH = os.path.join("test-saves", _SAVE_NAME)
_RESULTS_FILENAME = "direction3_results.txt"
_HEX_DUMP_WIDTH = 16
_PRE_T_F64_COUNT = 8
_PRE_T_BYTE_COUNT = _PRE_T_F64_COUNT * 8
_T_ENTRY_COUNT = 72
_U32_SIZE = 4
_T_BYTE_COUNT = _T_ENTRY_COUNT * _U32_SIZE
_TAIL_SIZE = 115
_DEFAULT_MOVE_TOKEN = b"DefaultMove"
_DEFAULT_MOVE_CONTEXT_BEFORE = 48
_DEFAULT_MOVE_CONTEXT_AFTER = 160
_OFFSET_CONTEXT_RADIUS = 16
_MAX_CANDIDATES_TO_DUMP = 80
_MIN_VALIDATION_SAMPLE_SIZE = 10

SAVE_PATH = (
    os.path.join(_REPO_ROOT, _SAVE_RELATIVE_PATH)
    if os.path.exists(os.path.join(_REPO_ROOT, _SAVE_RELATIVE_PATH))
    else os.path.join(_WORKTREE_REPO_ROOT, _SAVE_RELATIVE_PATH)
)

sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))
try:
    from save_parser import BinaryReader, parse_save
except ModuleNotFoundError:
    sys.path.insert(0, os.path.join(_WORKTREE_REPO_ROOT, "src"))
    from save_parser import BinaryReader, parse_save

TARGET_NAMES = ("Whommie", "Bud")
POSITIVE_NAMES = frozenset(TARGET_NAMES)


@dataclass(frozen=True)
class RegionCandidate:
    region: str
    offset: int
    pattern: str
    positive_values: tuple[int, ...]
    negative_values: tuple[int, ...]


@dataclass
class CatBlobInfo:
    name: str
    db_key: int
    uid: int
    parent_uid_a: int
    parent_uid_b: int
    parent_name_a: str | None
    parent_name_b: str | None
    blob: bytes
    pre_t_start: int
    pre_t_end: int
    t_end: int
    default_move_offset: int
    tail_start: int


def _format_parent_uid(parent_uid: int) -> str:
    return str(parent_uid) if parent_uid else "0"


def hex_dump(blob: bytes, base_offset: int = 0) -> list[str]:
    lines: list[str] = []
    for row_start in range(0, len(blob), _HEX_DUMP_WIDTH):
        chunk = blob[row_start:row_start + _HEX_DUMP_WIDTH]
        hex_part = " ".join(f"{value:02x}" for value in chunk)
        ascii_part = "".join(chr(value) if 32 <= value < 127 else "." for value in chunk)
        lines.append(f"  {base_offset + row_start:06x}: {hex_part:<47}  |{ascii_part}|")
    return lines


def decompress_blob(raw_blob: bytes) -> bytes:
    uncompressed_size = struct.unpack_from("<I", raw_blob, 0)[0]
    return lz4.block.decompress(raw_blob[4:], uncompressed_size=uncompressed_size)


def locate_structural_offsets(blob: bytes) -> tuple[int, int, int, int, int]:
    reader = BinaryReader(blob)
    reader.u32()
    reader.u64()
    reader.utf16str()
    reader.str()
    reader.u64()
    reader.u64()
    reader.str()
    reader.u32()
    pre_t_start = reader.pos
    pre_t_end = pre_t_start + _PRE_T_BYTE_COUNT
    t_end = pre_t_end + _T_BYTE_COUNT
    default_move_offset = blob.find(_DEFAULT_MOVE_TOKEN, t_end)
    tail_start = len(blob) - _TAIL_SIZE
    return pre_t_start, pre_t_end, t_end, default_move_offset, tail_start


def build_cat_blob_info(save_path: str) -> tuple[dict[str, CatBlobInfo], list]:
    save_data = parse_save(save_path)
    all_cats = save_data[0]
    conn = sqlite3.connect(save_path)
    try:
        info_by_name: dict[str, CatBlobInfo] = {}
        for cat in all_cats:
            row = conn.execute("SELECT data FROM cats WHERE key=?", (cat.db_key,)).fetchone()
            if row is None:
                continue
            blob = decompress_blob(bytes(row[0]))
            pre_t_start, pre_t_end, t_end, default_move_offset, tail_start = locate_structural_offsets(blob)
            info_by_name[cat.name] = CatBlobInfo(
                name=cat.name,
                db_key=int(cat.db_key),
                uid=int(cat._uid_int),
                parent_uid_a=int(cat._parent_uid_a),
                parent_uid_b=int(cat._parent_uid_b),
                parent_name_a=cat.parent_a.name if getattr(cat, "parent_a", None) is not None else None,
                parent_name_b=cat.parent_b.name if getattr(cat, "parent_b", None) is not None else None,
                blob=blob,
                pre_t_start=pre_t_start,
                pre_t_end=pre_t_end,
                t_end=t_end,
                default_move_offset=default_move_offset,
                tail_start=tail_start,
            )
        return info_by_name, all_cats
    finally:
        conn.close()


def values_at_region_offset(cat_info: CatBlobInfo, region_name: str, offset: int) -> int | None:
    if region_name == "pre_t":
        return cat_info.blob[cat_info.pre_t_start + offset]
    if region_name == "t_array":
        return cat_info.blob[cat_info.pre_t_end + offset]
    if region_name == "tail":
        return cat_info.blob[cat_info.tail_start + offset]
    if region_name == "defaultmove_window":
        if cat_info.default_move_offset < 0:
            return None
        start = max(0, cat_info.default_move_offset - _DEFAULT_MOVE_CONTEXT_BEFORE)
        end = min(len(cat_info.blob), cat_info.default_move_offset + _DEFAULT_MOVE_CONTEXT_AFTER)
        window = cat_info.blob[start:end]
        if offset >= len(window):
            return None
        return window[offset]
    return None


def scan_region_candidates(
    positive_infos: list[CatBlobInfo],
    negative_infos: list[CatBlobInfo],
    region_name: str,
    region_size: int,
) -> list[RegionCandidate]:
    candidates: list[RegionCandidate] = []
    for offset in range(region_size):
        positive_values = []
        negative_values = []
        missing_value = False

        for cat_info in positive_infos:
            value = values_at_region_offset(cat_info, region_name, offset)
            if value is None:
                missing_value = True
                break
            positive_values.append(value)
        if missing_value:
            continue

        for cat_info in negative_infos:
            value = values_at_region_offset(cat_info, region_name, offset)
            if value is None:
                missing_value = True
                break
            negative_values.append(value)
        if missing_value:
            continue

        positive_set = set(positive_values)
        negative_set = set(negative_values)

        if len(positive_set) == 1 and positive_set.isdisjoint(negative_set):
            candidates.append(
                RegionCandidate(
                    region=region_name,
                    offset=offset,
                    pattern="positives_constant_unique",
                    positive_values=tuple(positive_values),
                    negative_values=tuple(negative_values),
                )
            )
        elif all(value != 0 for value in positive_values) and all(value == 0 for value in negative_values):
            candidates.append(
                RegionCandidate(
                    region=region_name,
                    offset=offset,
                    pattern="positives_nonzero_negatives_zero",
                    positive_values=tuple(positive_values),
                    negative_values=tuple(negative_values),
                )
            )
        elif all(value == 0 for value in positive_values) and all(value != 0 for value in negative_values):
            candidates.append(
                RegionCandidate(
                    region=region_name,
                    offset=offset,
                    pattern="positives_zero_negatives_nonzero",
                    positive_values=tuple(positive_values),
                    negative_values=tuple(negative_values),
                )
            )
    return candidates


def scan_family_equal_parent_offsets(
    child_info: CatBlobInfo,
    parent_infos: tuple[CatBlobInfo, CatBlobInfo],
) -> dict[str, list[int]]:
    family_hits: dict[str, list[int]] = {
        "pre_t": [],
        "t_array": [],
        "tail": [],
        "defaultmove_window": [],
    }

    region_sizes = {
        "pre_t": _PRE_T_BYTE_COUNT,
        "t_array": _T_BYTE_COUNT,
        "tail": _TAIL_SIZE,
        "defaultmove_window": min(
            _DEFAULT_MOVE_CONTEXT_BEFORE + _DEFAULT_MOVE_CONTEXT_AFTER,
            min(
                len(child_info.blob),
                *(len(parent_info.blob) for parent_info in parent_infos),
            ),
        ),
    }

    for region_name, region_size in region_sizes.items():
        for offset in range(region_size):
            child_value = values_at_region_offset(child_info, region_name, offset)
            parent_a_value = values_at_region_offset(parent_infos[0], region_name, offset)
            parent_b_value = values_at_region_offset(parent_infos[1], region_name, offset)
            if child_value is None or parent_a_value is None or parent_b_value is None:
                continue
            if parent_a_value == parent_b_value and child_value != parent_a_value:
                family_hits[region_name].append(offset)

    return family_hits


def format_region_offset(cat_info: CatBlobInfo, region_name: str, offset: int) -> str:
    if region_name == "pre_t":
        return f"blob[0x{cat_info.pre_t_start + offset:04x}]"
    if region_name == "t_array":
        return f"blob[0x{cat_info.pre_t_end + offset:04x}]"
    if region_name == "tail":
        return f"blob[0x{cat_info.tail_start + offset:04x}]"
    if region_name == "defaultmove_window":
        start = max(0, cat_info.default_move_offset - _DEFAULT_MOVE_CONTEXT_BEFORE)
        return f"blob[0x{start + offset:04x}]"
    return f"offset+{offset}"


def describe_region(region_name: str, offset: int) -> str:
    if region_name == "pre_t":
        if offset % 8 == 0:
            return f"pre-T f64[{offset // 8}] byte+0"
        return f"pre-T f64[{offset // 8}] byte+{offset % 8}"
    if region_name == "t_array":
        entry_index = offset // _U32_SIZE
        byte_index = offset % _U32_SIZE
        return f"T[{entry_index}] byte+{byte_index}"
    if region_name == "tail":
        return f"tail+{offset}"
    if region_name == "defaultmove_window":
        return f"defaultmove_window+{offset}"
    return f"{region_name}+{offset}"


def validate_candidate_across_roster(
    candidate: RegionCandidate,
    info_by_name: dict[str, CatBlobInfo],
) -> tuple[int, int, list[str], list[str]]:
    false_positives: list[str] = []
    false_negatives: list[str] = []
    positive_values = set(candidate.positive_values)
    negative_values = set(candidate.negative_values)
    sample_count = 0

    for name, cat_info in info_by_name.items():
        value = values_at_region_offset(cat_info, candidate.region, candidate.offset)
        if value is None:
            continue
        sample_count += 1
        is_positive = name in POSITIVE_NAMES
        predicted_positive = False

        if candidate.pattern == "positives_constant_unique":
            predicted_positive = value in positive_values and value not in negative_values
        elif candidate.pattern == "positives_nonzero_negatives_zero":
            predicted_positive = value != 0
        elif candidate.pattern == "positives_zero_negatives_nonzero":
            predicted_positive = value == 0

        if predicted_positive and not is_positive:
            false_positives.append(f"{name}={value}")
        elif is_positive and not predicted_positive:
            false_negatives.append(f"{name}={value}")

    return sample_count, len(false_positives) + len(false_negatives), false_positives, false_negatives


def dump_context_for_candidate(out, cat_info: CatBlobInfo, candidate: RegionCandidate) -> None:
    absolute_desc = format_region_offset(cat_info, candidate.region, candidate.offset)
    out(f"    {cat_info.name}: {absolute_desc}  {describe_region(candidate.region, candidate.offset)}")

    if candidate.region == "defaultmove_window":
        window_start = max(0, cat_info.default_move_offset - _DEFAULT_MOVE_CONTEXT_BEFORE)
        context_start = max(window_start, window_start + candidate.offset - _OFFSET_CONTEXT_RADIUS)
        context_end = min(
            len(cat_info.blob),
            window_start + candidate.offset + _OFFSET_CONTEXT_RADIUS,
        )
    elif candidate.region == "pre_t":
        absolute_offset = cat_info.pre_t_start + candidate.offset
        context_start = max(cat_info.pre_t_start, absolute_offset - _OFFSET_CONTEXT_RADIUS)
        context_end = min(cat_info.pre_t_end, absolute_offset + _OFFSET_CONTEXT_RADIUS)
    elif candidate.region == "t_array":
        absolute_offset = cat_info.pre_t_end + candidate.offset
        context_start = max(cat_info.pre_t_end, absolute_offset - _OFFSET_CONTEXT_RADIUS)
        context_end = min(cat_info.t_end, absolute_offset + _OFFSET_CONTEXT_RADIUS)
    else:
        absolute_offset = cat_info.tail_start + candidate.offset
        context_start = max(cat_info.tail_start, absolute_offset - _OFFSET_CONTEXT_RADIUS)
        context_end = min(len(cat_info.blob), absolute_offset + _OFFSET_CONTEXT_RADIUS)

    for line in hex_dump(cat_info.blob[context_start:context_end], base_offset=context_start):
        out(line)


def main() -> None:
    output_lines: list[str] = []

    def out(line: str = "") -> None:
        print(line)
        output_lines.append(line)

    out("=" * 70)
    out("Direction #3 -- Parent / Offspring Blob Diff")
    out("=" * 70)
    out(f"Save: {SAVE_PATH}")

    info_by_name, all_cats = build_cat_blob_info(SAVE_PATH)
    missing_targets = [name for name in TARGET_NAMES if name not in info_by_name]
    if missing_targets:
        out()
        out(f"ERROR: target cats missing from save: {missing_targets}")
        out_path = os.path.join(_SCRIPT_DIR, _RESULTS_FILENAME)
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(output_lines))
        return

    out()
    out("-" * 70)
    out("STEP 1 -- Family resolution")
    out("-" * 70)

    family_infos: dict[str, tuple[CatBlobInfo, CatBlobInfo, CatBlobInfo]] = {}
    for target_name in TARGET_NAMES:
        child_info = info_by_name[target_name]
        if child_info.parent_name_a is None or child_info.parent_name_b is None:
            out(
                f"  {target_name}: parsed parent links missing; raw parent fields="
                f"({_format_parent_uid(child_info.parent_uid_a)}, {_format_parent_uid(child_info.parent_uid_b)})"
            )
            continue
        parent_info_a = info_by_name.get(child_info.parent_name_a)
        parent_info_b = info_by_name.get(child_info.parent_name_b)
        if parent_info_a is None or parent_info_b is None:
            out(f"  {target_name}: parent blob missing from cats table snapshot")
            continue
        family_infos[target_name] = (child_info, parent_info_a, parent_info_b)
        out(
            f"  {target_name}: db_key={child_info.db_key}, uid={child_info.uid}, "
            f"parents=({parent_info_a.name}, {parent_info_b.name})"
        )
        out(
            f"    pre_t=0x{child_info.pre_t_start:04x}, t_end=0x{child_info.t_end:04x}, "
            f"default_move=0x{child_info.default_move_offset:04x}, tail=0x{child_info.tail_start:04x}, "
            f"blob_len={len(child_info.blob)}"
        )

    out()
    out("-" * 70)
    out("STEP 2 -- Parent-equal / child-different offsets")
    out("-" * 70)

    family_hits_by_name: dict[str, dict[str, list[int]]] = {}
    for child_name, family in family_infos.items():
        child_info, parent_info_a, parent_info_b = family
        family_hits = scan_family_equal_parent_offsets(child_info, (parent_info_a, parent_info_b))
        family_hits_by_name[child_name] = family_hits
        out(f"  {child_name}:")
        for region_name, offsets in family_hits.items():
            out(f"    {region_name:18s} {len(offsets):4d} hits")
            if offsets:
                preview = offsets[:20]
                suffix = " ..." if len(offsets) > 20 else ""
                out(f"      {preview}{suffix}")

    out()
    out("-" * 70)
    out("STEP 3 -- Intersections across Whommie and Bud")
    out("-" * 70)

    region_names = ("pre_t", "t_array", "tail", "defaultmove_window")
    intersected_offsets: dict[str, list[int]] = {}
    for region_name in region_names:
        whommie_hits = set(family_hits_by_name.get("Whommie", {}).get(region_name, []))
        bud_hits = set(family_hits_by_name.get("Bud", {}).get(region_name, []))
        intersection = sorted(whommie_hits & bud_hits)
        intersected_offsets[region_name] = intersection
        out(f"  {region_name:18s} {len(intersection):4d} shared offsets")
        if intersection:
            preview = intersection[:40]
            suffix = " ..." if len(intersection) > 40 else ""
            out(f"    {preview}{suffix}")

    out()
    out("-" * 70)
    out("STEP 4 -- Candidate scan using both positives vs both clean parents")
    out("-" * 70)

    positive_infos = [family_infos[name][0] for name in TARGET_NAMES if name in family_infos]
    negative_infos = []
    for name in TARGET_NAMES:
        if name not in family_infos:
            continue
        negative_infos.extend([family_infos[name][1], family_infos[name][2]])

    if not positive_infos or not negative_infos:
        out("  Family resolution did not yield both positives and clean parents; skipping candidate scan.")
        all_candidates = []
    else:
        region_sizes = {
            "pre_t": _PRE_T_BYTE_COUNT,
            "t_array": _T_BYTE_COUNT,
            "tail": _TAIL_SIZE,
            "defaultmove_window": _DEFAULT_MOVE_CONTEXT_BEFORE + _DEFAULT_MOVE_CONTEXT_AFTER,
        }

        all_candidates = []
        for region_name, region_size in region_sizes.items():
            candidates = scan_region_candidates(positive_infos, negative_infos, region_name, region_size)
            all_candidates.extend(candidates)
            out(f"  {region_name:18s} {len(candidates):4d} raw candidates")

    out()
    out("-" * 70)
    out("STEP 5 -- Roster-wide validation")
    out("-" * 70)

    validated_candidates: list[tuple[RegionCandidate, int, list[str], list[str]]] = []
    for candidate in all_candidates:
        sample_count, error_count, false_positives, false_negatives = validate_candidate_across_roster(
            candidate,
            info_by_name,
        )
        if sample_count < _MIN_VALIDATION_SAMPLE_SIZE:
            continue
        if error_count == 0:
            validated_candidates.append((candidate, sample_count, false_positives, false_negatives))

    if not validated_candidates:
        out("  No zero-error candidates survived roster-wide validation.")
    else:
        for candidate, sample_count, _, _ in validated_candidates:
            out(
                f"  PASS  {candidate.region:18s} offset={candidate.offset:3d}  "
                f"pattern={candidate.pattern:31s} samples={sample_count}"
            )

    out()
    out("-" * 70)
    out("STEP 6 -- Top raw candidates with context")
    out("-" * 70)

    raw_candidates_with_scores: list[tuple[int, RegionCandidate, int, list[str], list[str]]] = []
    for candidate in all_candidates:
        sample_count, error_count, false_positives, false_negatives = validate_candidate_across_roster(
            candidate,
            info_by_name,
        )
        raw_candidates_with_scores.append(
            (error_count, candidate, sample_count, false_positives, false_negatives)
        )

    raw_candidates_with_scores.sort(
        key=lambda item: (
            item[0],
            item[1].region,
            item[1].offset,
            item[1].pattern,
        )
    )

    if not raw_candidates_with_scores:
        out("  No raw candidates found.")
    else:
        for error_count, candidate, sample_count, false_positives, false_negatives in raw_candidates_with_scores[:_MAX_CANDIDATES_TO_DUMP]:
            out(
                f"  {candidate.region:18s} offset={candidate.offset:3d}  "
                f"{describe_region(candidate.region, candidate.offset):28s}  "
                f"pattern={candidate.pattern:31s} errors={error_count:3d} samples={sample_count}"
            )
            out(
                f"    positives={list(candidate.positive_values)} negatives={list(candidate.negative_values)}"
            )
            if false_positives:
                out(f"    false_positives={false_positives[:8]}")
            if false_negatives:
                out(f"    false_negatives={false_negatives[:8]}")
            for cat_name in TARGET_NAMES:
                if cat_name not in family_infos:
                    continue
                child_info, parent_info_a, parent_info_b = family_infos[cat_name]
                dump_context_for_candidate(out, child_info, candidate)
                dump_context_for_candidate(out, parent_info_a, candidate)
                dump_context_for_candidate(out, parent_info_b, candidate)
            out()

    out()
    out("-" * 70)
    out("STEP 7 -- DefaultMove anchor windows")
    out("-" * 70)
    for target_name, family in family_infos.items():
        child_info, parent_info_a, parent_info_b = family
        out(
            f"  {target_name}: DefaultMove offsets child=0x{child_info.default_move_offset:04x}, "
            f"parent_a=0x{parent_info_a.default_move_offset:04x}, parent_b=0x{parent_info_b.default_move_offset:04x}"
        )

    out()
    out("=" * 70)
    out("SUMMARY")
    out("=" * 70)
    out(f"  Parsed cats: {len(all_cats)}")
    out(f"  Candidate count: {len(all_candidates)}")
    out(f"  Zero-error validated candidates: {len(validated_candidates)}")
    if validated_candidates:
        for candidate, sample_count, _, _ in validated_candidates:
            out(
                f"  VALIDATED: {candidate.region} offset={candidate.offset} "
                f"({describe_region(candidate.region, candidate.offset)}) "
                f"pattern={candidate.pattern} samples={sample_count}"
            )
    else:
        out("  No candidate currently meets the handoff success condition.")

    out_path = os.path.join(_SCRIPT_DIR, _RESULTS_FILENAME)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(output_lines))
    print(f"\nResults also written to: {out_path}")


if __name__ == "__main__":
    main()
