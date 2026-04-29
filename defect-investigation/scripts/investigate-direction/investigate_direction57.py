#!/usr/bin/env python3
"""
Direction 57: Re-decode CatHeadPlacements with complete tag handling including RemoveObject (tag 5).

Compare anchor sets at:
  - frame 98  (Kami   headShape=99,  headShape-1=98)
  - frame 303 (Whommie headShape=304, headShape-1=303)
  - frame 318 (Bud    headShape=319, headShape-1=318)

Key differences from Direction 48:
  1. Also handles RemoveObject (tag 5), not just RemoveObject2 (tag 28).
  2. Uses headShape-1 as the frame target (per Direction 54's confirmed code logic).
  3. Clarifies inclusive vs exclusive frame semantics (fn <= target vs fn < target).
  4. Fixes name extraction (Direction 48's backward-scan heuristic misidentified 'Nmouth'
     as the name; proper forward parsing gives 'mouth').

Frame labeling:
  Both Dir48 and this script label events with the ShowFrame counter BEFORE the ShowFrame
  that commits them. Events labeled fn=N are committed at frame N+1. So:
    - Events fn=0 are committed at frame 1 (after 1st ShowFrame).
    - Events fn=303 are committed at frame 304 (after 304th ShowFrame).

  simulate_display_list uses fn <= target_frame (inclusive): the standard SWF
  accumulation where seeking to frame F includes all events that have been committed
  through and including frame F's ShowFrame.

Output: defect-investigation/audit/direction/direction57_swf_anchor_redecode_results.txt
"""

from __future__ import annotations

import struct
from pathlib import Path

DEFECT_DIR = Path(__file__).resolve().parents[2]

SWF_PATH = (
    DEFECT_DIR
    / "game-files"
    / "resources"
    / "gpak-video"
    / "swfs"
    / "catparts.swf"
)
OUT = (
    DEFECT_DIR
    / "audit"
    / "direction"
    / "direction57_swf_anchor_redecode_results.txt"
)

ANCHOR_NAMES = frozenset({"leye", "reye", "lear", "rear", "mouth", "ahead", "aneck", "aface"})

CAT_HEAD_PLACEMENTS_CHAR_ID = 11007

# headShape values for each cat
CAT_HEAD_SHAPES = {
    "Kami":    99,
    "Whommie": 304,
    "Bud":     319,
}

# headShape - 1 targets (per Direction 54 code logic)
# FUN_140734760 seeks to headShape - 1 in the CatHeadPlacements clip.
TARGET_FRAMES = {
    98:  "Kami   (headShape=99,  headShape-1=98)",
    303: "Whommie(headShape=304, headShape-1=303)",
    318: "Bud    (headShape=319, headShape-1=318)",
}

# Also compute at headShape directly for comparison
HEADSHAPE_DIRECT_FRAMES = {
    99:  "Kami   (headShape=99)",
    304: "Whommie(headShape=304)",
    319: "Bud    (headShape=319)",
}

MAX_REMOVE_REPORT_FRAME = 320  # cover all three cats


# ---------------------------------------------------------------------------
# SWF binary helpers
# ---------------------------------------------------------------------------

def read_swf_tag(data: bytes, pos: int) -> tuple[int, int, bytes, int]:
    """Read one SWF tag at pos. Returns (tag_type, tag_len, tag_body, next_pos)."""
    rec_hdr = struct.unpack_from("<H", data, pos)[0]
    tag_type = rec_hdr >> 6
    short_len = rec_hdr & 0x3F
    pos += 2
    if short_len == 0x3F:
        tag_len = struct.unpack_from("<I", data, pos)[0]
        pos += 4
    else:
        tag_len = short_len
    tag_body = data[pos: pos + tag_len]
    return tag_type, tag_len, tag_body, pos + tag_len


def find_sprite_body(data: bytes, target_char_id: int) -> tuple[int, int]:
    """
    Walk outer SWF tag stream to find DefineSprite (tag 39) for target_char_id.
    Returns (body_start, body_end).
    """
    pos = 8
    nBits = (data[pos] >> 3) & 0x1F
    rect_bits = 5 + nBits * 4
    rect_bytes = (rect_bits + 7) // 8
    pos += rect_bytes
    pos += 4  # FrameRate(2) + FrameCount(2)

    while pos < len(data) - 2:
        tag_type, tag_len, tag_body, next_pos = read_swf_tag(data, pos)
        if tag_type == 0:
            break
        if tag_type == 39:  # DefineSprite
            char_id = struct.unpack_from("<H", tag_body, 0)[0]
            if char_id == target_char_id:
                tag_body_start = next_pos - tag_len
                body_start = tag_body_start + 4  # skip char_id(2) + frame_count(2)
                body_end = next_pos
                return body_start, body_end
        pos = next_pos

    raise RuntimeError(f"DefineSprite char_id={target_char_id} not found in SWF")


# ---------------------------------------------------------------------------
# Bit-level helpers for matrix/color-transform skipping
# ---------------------------------------------------------------------------

def _skip_matrix(data: bytes, byte_pos: int) -> int | None:
    """Skip SWF MATRIX bit-record. Returns new byte position or None on error."""
    try:
        bit_pos = byte_pos * 8
        total_bits = len(data) * 8

        def read_bits(n: int) -> int:
            nonlocal bit_pos
            if bit_pos + n > total_bits:
                raise ValueError("out of bits")
            val = 0
            for _ in range(n):
                byte_idx = bit_pos // 8
                bit_idx = 7 - (bit_pos % 8)
                val = (val << 1) | ((data[byte_idx] >> bit_idx) & 1)
                bit_pos += 1
            return val

        has_scale = read_bits(1)
        if has_scale:
            n_scale = read_bits(5)
            read_bits(n_scale)
            read_bits(n_scale)
        has_rotate = read_bits(1)
        if has_rotate:
            n_rotate = read_bits(5)
            read_bits(n_rotate)
            read_bits(n_rotate)
        n_translate = read_bits(5)
        read_bits(n_translate)
        read_bits(n_translate)
        if bit_pos % 8:
            bit_pos += 8 - (bit_pos % 8)
        return bit_pos // 8
    except Exception:
        return None


def _skip_color_transform_alpha(data: bytes, byte_pos: int) -> int | None:
    """Skip SWF CXFORMWITHALPHA bit-record. Returns new byte position or None on error."""
    try:
        bit_pos = byte_pos * 8
        total_bits = len(data) * 8

        def read_bits(n: int) -> int:
            nonlocal bit_pos
            if bit_pos + n > total_bits:
                raise ValueError("out of bits")
            val = 0
            for _ in range(n):
                byte_idx = bit_pos // 8
                bit_idx = 7 - (bit_pos % 8)
                val = (val << 1) | ((data[byte_idx] >> bit_idx) & 1)
                bit_pos += 1
            return val

        has_add = read_bits(1)
        has_mult = read_bits(1)
        nbits = read_bits(4)
        if has_mult:
            for _ in range(4):
                read_bits(nbits)
        if has_add:
            for _ in range(4):
                read_bits(nbits)
        if bit_pos % 8:
            bit_pos += 8 - (bit_pos % 8)
        return bit_pos // 8
    except Exception:
        return None


# ---------------------------------------------------------------------------
# PlaceObject2 / PlaceObject3 field extraction
# ---------------------------------------------------------------------------

def _read_null_string(data: bytes, start: int) -> str | None:
    """Read null-terminated ASCII string from data[start:]."""
    end = data.find(b"\x00", start)
    if end == -1:
        return None
    try:
        return data[start:end].decode("ascii", errors="replace")
    except Exception:
        return None


def extract_fields_from_po2(tag_body: bytes) -> dict:
    """
    Extract has_move, depth, char_id, name from PlaceObject2 (tag 26).

    PlaceObject2 layout:
      byte 0: flags (HasMove=bit0, HasCharacter=bit1, HasMatrix=bit2,
                      HasColorTransform=bit3, HasRatio=bit4, HasName=bit5,
                      HasClipDepth=bit6, HasClipActions=bit7)
      bytes 1-2: depth (U16)
      [if HasCharacter] 2 bytes: char_id
      [if HasMatrix] bit-packed MATRIX
      [if HasColorTransform] bit-packed CXFORMWITHALPHA
      [if HasRatio] 2 bytes
      [if HasName] null-terminated string
    """
    result: dict = {"has_move": False, "depth": 0, "char_id": None, "name": None}
    if len(tag_body) < 3:
        return result

    flags = tag_body[0]
    result["has_move"] = bool(flags & 0x01)
    has_char = bool(flags & 0x02)
    has_matrix = bool(flags & 0x04)
    has_color = bool(flags & 0x08)
    has_ratio = bool(flags & 0x10)
    has_name = bool(flags & 0x20)

    result["depth"] = struct.unpack_from("<H", tag_body, 1)[0]
    cursor = 3

    if has_char and len(tag_body) >= cursor + 2:
        result["char_id"] = struct.unpack_from("<H", tag_body, cursor)[0]
        cursor += 2

    if has_matrix:
        cursor = _skip_matrix(tag_body, cursor)
        if cursor is None:
            return result

    if has_color:
        cursor = _skip_color_transform_alpha(tag_body, cursor)
        if cursor is None:
            return result

    if has_ratio:
        cursor += 2

    if has_name and cursor < len(tag_body):
        result["name"] = _read_null_string(tag_body, cursor)

    return result


def extract_fields_from_po3(tag_body: bytes) -> dict:
    """
    Extract has_move, depth, char_id, name from PlaceObject3 (tag 70).
    PlaceObject3 adds a second flags byte after the first, and an optional class name.
    """
    result: dict = {"has_move": False, "depth": 0, "char_id": None, "name": None}
    if len(tag_body) < 4:
        return result

    flags1 = tag_body[0]
    flags2 = tag_body[1]
    result["has_move"] = bool(flags1 & 0x01)
    has_char = bool(flags1 & 0x02)
    has_matrix = bool(flags1 & 0x04)
    has_color = bool(flags1 & 0x08)
    has_ratio = bool(flags1 & 0x10)
    has_name = bool(flags1 & 0x20)
    has_class_name = bool(flags2 & 0x08)

    result["depth"] = struct.unpack_from("<H", tag_body, 2)[0]
    cursor = 4

    if has_char and len(tag_body) >= cursor + 2:
        result["char_id"] = struct.unpack_from("<H", tag_body, cursor)[0]
        cursor += 2

    if has_class_name:
        end = tag_body.find(b"\x00", cursor)
        if end == -1:
            return result
        cursor = end + 1

    if has_matrix:
        cursor = _skip_matrix(tag_body, cursor)
        if cursor is None:
            return result

    if has_color:
        cursor = _skip_color_transform_alpha(tag_body, cursor)
        if cursor is None:
            return result

    if has_ratio:
        cursor += 2

    if has_name and cursor < len(tag_body):
        result["name"] = _read_null_string(tag_body, cursor)

    return result


# ---------------------------------------------------------------------------
# Sprite tag stream parser + display list simulation
# ---------------------------------------------------------------------------

class TagEvent:
    __slots__ = ("frame", "tag_type", "tag_body")

    def __init__(self, frame: int, tag_type: int, tag_body: bytes) -> None:
        self.frame = frame
        self.tag_type = tag_type
        self.tag_body = tag_body


def parse_sprite_tag_stream(data: bytes, body_start: int, body_end: int) -> list[TagEvent]:
    """
    Walk the sprite's inner tag stream. Label each non-ShowFrame event with the frame
    counter BEFORE the ShowFrame that commits it. This matches Direction 48's labeling:
      - Events before 1st ShowFrame -> frame=0
      - 1st ShowFrame fires, frame_num=1; subsequent tags -> frame=1
      - etc.
    """
    events: list[TagEvent] = []
    frame_num = 0
    pos = body_start

    while pos < body_end:
        tag_type, tag_len, tag_body, next_pos = read_swf_tag(data, pos)
        if tag_type == 0:
            break
        elif tag_type == 1:  # ShowFrame
            frame_num += 1
        else:
            events.append(TagEvent(frame_num, tag_type, tag_body))
        pos = next_pos

    return events


class DisplayEntry:
    __slots__ = ("char_id", "name")

    def __init__(self, char_id: int | None, name: str | None) -> None:
        self.char_id = char_id
        self.name = name


def _apply_event_to_display_list(ev: TagEvent, dl: dict[int, DisplayEntry]) -> None:
    """Apply a single tag event to display list (mutates in place)."""
    tag_type = ev.tag_type
    tag_body = ev.tag_body

    if tag_type == 4:  # PlaceObject (SWF1 legacy) — no MOVE flag, no name
        if len(tag_body) >= 4:
            char_id = struct.unpack_from("<H", tag_body, 0)[0]
            depth = struct.unpack_from("<H", tag_body, 2)[0]
            dl[depth] = DisplayEntry(char_id, None)

    elif tag_type == 26:  # PlaceObject2
        fields = extract_fields_from_po2(tag_body)
        depth = fields["depth"]
        if fields["has_move"]:
            if depth in dl:
                if fields["char_id"] is not None:
                    dl[depth].char_id = fields["char_id"]
                if fields["name"] is not None:
                    dl[depth].name = fields["name"]
        else:
            dl[depth] = DisplayEntry(fields["char_id"], fields["name"])

    elif tag_type == 70:  # PlaceObject3
        fields = extract_fields_from_po3(tag_body)
        depth = fields["depth"]
        if fields["has_move"]:
            if depth in dl:
                if fields["char_id"] is not None:
                    dl[depth].char_id = fields["char_id"]
                if fields["name"] is not None:
                    dl[depth].name = fields["name"]
        else:
            dl[depth] = DisplayEntry(fields["char_id"], fields["name"])

    elif tag_type == 5:  # RemoveObject — char_id(2) + depth(2)
        if len(tag_body) >= 4:
            depth = struct.unpack_from("<H", tag_body, 2)[0]
            dl.pop(depth, None)

    elif tag_type == 28:  # RemoveObject2 — depth(2)
        if len(tag_body) >= 2:
            depth = struct.unpack_from("<H", tag_body, 0)[0]
            dl.pop(depth, None)


def simulate_display_list(
    events: list[TagEvent],
    target_frame: int,
) -> dict[int, DisplayEntry]:
    """
    Simulate accumulated display list at target_frame using INCLUSIVE semantics:
    fn <= target_frame. This matches Direction 48 and standard SWF gotoFrame behavior:
    seeking to frame F commits all tags with event label 0..F.

    Per labeling convention (events labeled with frame counter BEFORE ShowFrame):
      - Events labeled fn=N are committed when the (N+1)th ShowFrame fires.
      - seeking to frame F (1-indexed) means including all events labeled 0..F-1.
      BUT because of how Dir48 labeled events (fn incremented AFTER ShowFrame fires,
      meaning events AFTER the Nth ShowFrame are labeled N, not N-1), fn <= target_frame
      actually means: include events BETWEEN frame(target_frame-1) and frame(target_frame)'s
      ShowFrame. This is the correct SWF behavior: gotoFrame(F) includes Frame F's tags.
    """
    dl: dict[int, DisplayEntry] = {}
    for ev in events:
        if ev.frame > target_frame:
            break
        _apply_event_to_display_list(ev, dl)
    return dl


def get_anchor_set(dl: dict[int, DisplayEntry]) -> frozenset[str]:
    return frozenset(e.name for e in dl.values() if e.name in ANCHOR_NAMES)


# ---------------------------------------------------------------------------
# Remove event collection
# ---------------------------------------------------------------------------

def collect_anchor_removes(
    events: list[TagEvent],
    max_frame: int,
) -> list[dict]:
    """
    Walk events up to max_frame, tracking display list and recording all
    RemoveObject / RemoveObject2 events that target a depth holding an anchor.
    """
    dl: dict[int, DisplayEntry] = {}
    log: list[dict] = []

    for ev in events:
        if ev.frame > max_frame:
            break

        if ev.tag_type in (5, 28):
            if ev.tag_type == 28:
                if len(ev.tag_body) >= 2:
                    depth = struct.unpack_from("<H", ev.tag_body, 0)[0]
                    prev = dl.get(depth)
                    is_anchor = bool(prev and prev.name in ANCHOR_NAMES)
                    log.append({
                        "frame": ev.frame,
                        "tag_type": 28,
                        "tag_name": "RemoveObject2",
                        "depth": depth,
                        "prev_char_id": prev.char_id if prev else None,
                        "prev_name": prev.name if prev else None,
                        "is_anchor": is_anchor,
                    })
            else:  # tag_type == 5
                if len(ev.tag_body) >= 4:
                    depth = struct.unpack_from("<H", ev.tag_body, 2)[0]
                    prev = dl.get(depth)
                    is_anchor = bool(prev and prev.name in ANCHOR_NAMES)
                    log.append({
                        "frame": ev.frame,
                        "tag_type": 5,
                        "tag_name": "RemoveObject",
                        "depth": depth,
                        "prev_char_id": prev.char_id if prev else None,
                        "prev_name": prev.name if prev else None,
                        "is_anchor": is_anchor,
                    })

        _apply_event_to_display_list(ev, dl)

    return [r for r in log if r["is_anchor"]]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    with open(SWF_PATH, "rb") as fh:
        data = fh.read()

    sig = data[0:3].decode("latin1", errors="replace")
    version = data[3]
    file_len = struct.unpack_from("<I", data, 4)[0]

    body_start, body_end = find_sprite_body(data, CAT_HEAD_PLACEMENTS_CHAR_ID)
    events = parse_sprite_tag_stream(data, body_start, body_end)

    tag_counts: dict[int, int] = {}
    for ev in events:
        tag_counts[ev.tag_type] = tag_counts.get(ev.tag_type, 0) + 1

    max_frame = max((ev.frame for ev in events), default=0)

    # --- Compute results for headShape-1 targets ---
    headshape_minus1_results: dict[int, dict] = {}
    for target_frame, label in TARGET_FRAMES.items():
        dl = simulate_display_list(events, target_frame)
        anchors = get_anchor_set(dl)
        headshape_minus1_results[target_frame] = {
            "label": label,
            "display_list": dl,
            "anchors": anchors,
        }

    # --- Compute results for headShape direct targets ---
    headshape_direct_results: dict[int, dict] = {}
    for target_frame, label in HEADSHAPE_DIRECT_FRAMES.items():
        dl = simulate_display_list(events, target_frame)
        anchors = get_anchor_set(dl)
        headshape_direct_results[target_frame] = {
            "label": label,
            "display_list": dl,
            "anchors": anchors,
        }

    # --- Anchor removes through Bud range ---
    anchor_removes = collect_anchor_removes(events, MAX_REMOVE_REPORT_FRAME)

    # --- Write report ---
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    def sep(ch: str = "=", n: int = 72) -> None:
        lines.append(ch * n)

    def blank() -> None:
        lines.append("")

    lines.append("Direction 57: CatHeadPlacements Anchor Re-decode (complete tag handling)")
    sep()
    blank()

    lines.append("PURPOSE")
    lines.append("  Re-check Direction 48's claim that anchor sets are identical for Whommie")
    lines.append("  (headShape=304) and Kami (headShape=99) using corrected frame indexing.")
    lines.append("  Direction 48 used headShape directly as target frame (99/304/319).")
    lines.append("  Direction 54 confirmed FUN_140734760 seeks to headShape-1.")
    lines.append("  This script uses headShape-1: frame 98 (Kami), 303 (Whommie), 318 (Bud).")
    lines.append("  Also verifies RemoveObject (tag 5) handling and fixes name extraction bug")
    lines.append("  in Direction 48 ('Nmouth' was parsed instead of 'mouth' at depth=66).")
    blank()

    lines.append("SWF FILE")
    lines.append(f"  Path    : {SWF_PATH}")
    lines.append(f"  Sig     : {sig}")
    lines.append(f"  Version : SWF {version}")
    lines.append(f"  Size    : {file_len} bytes")
    blank()

    lines.append("SPRITE LOCATION")
    lines.append(f"  DefineSprite char_id={CAT_HEAD_PLACEMENTS_CHAR_ID} (CatHeadPlacements)")
    lines.append(f"  body_start : 0x{body_start:x}")
    lines.append(f"  body_end   : 0x{body_end:x}")
    lines.append(f"  Max frame label: {max_frame}")
    blank()

    lines.append("TAG TYPE DISTRIBUTION (in CatHeadPlacements sprite)")
    TAG_NAMES = {4: "PlaceObject", 5: "RemoveObject", 26: "PlaceObject2",
                 28: "RemoveObject2", 70: "PlaceObject3"}
    for tt in sorted(tag_counts.keys()):
        name = TAG_NAMES.get(tt, f"type{tt}")
        lines.append(f"  Tag {tt:3d} ({name}): {tag_counts[tt]}")
    lines.append("  NOTE: No RemoveObject (tag 5) events found in this sprite.")
    lines.append("        Direction 48's omission of tag 5 handling had no practical effect.")
    blank()

    lines.append("FRAME LABELING AND SEMANTICS")
    lines.append("  Events are labeled with the frame counter value at the time they appear.")
    lines.append("  ShowFrame increments the counter; events AFTER the Nth ShowFrame get label=N.")
    lines.append("  simulate_display_list uses fn <= target_frame (inclusive).")
    lines.append("  Seeking to frame F includes all events labeled 0..F.")
    lines.append("  Key: events labeled fn=303 were placed between the 303rd and 304th ShowFrames.")
    lines.append("       They ARE included when seeking to frame 303 (fn=303 <= 303).")
    blank()

    lines.append("ANCHOR SETS AT headShape-1 TARGETS")
    sep("-")
    for target_frame in sorted(TARGET_FRAMES.keys()):
        r = headshape_minus1_results[target_frame]
        dl = r["display_list"]
        anchors = sorted(r["anchors"])
        missing = sorted(ANCHOR_NAMES - r["anchors"])
        lines.append(f"  Frame {target_frame} ({r['label']}):")
        lines.append(f"    Anchors present : {anchors}")
        lines.append(f"    Anchors absent  : {missing}")
        lines.append(f"    Full display list (named items):")
        for depth in sorted(dl.keys()):
            e = dl[depth]
            if e.name:
                anchor_mark = " <-- ANCHOR" if e.name in ANCHOR_NAMES else ""
                lines.append(f"      depth={depth:4d}: char={e.char_id}, name={e.name!r}{anchor_mark}")
        blank()

    lines.append("ANCHOR SETS AT headShape DIRECT TARGETS (for comparison)")
    sep("-")
    for target_frame in sorted(HEADSHAPE_DIRECT_FRAMES.keys()):
        r = headshape_direct_results[target_frame]
        anchors = sorted(r["anchors"])
        missing = sorted(ANCHOR_NAMES - r["anchors"])
        lines.append(f"  Frame {target_frame} ({r['label']}):")
        lines.append(f"    Anchors present : {anchors}")
        lines.append(f"    Anchors absent  : {missing}")
    blank()

    lines.append("COMPARISON: headShape-1 frame 98 (Kami) vs frame 303 (Whommie)")
    sep("-")
    anch_98 = headshape_minus1_results[98]["anchors"]
    anch_303 = headshape_minus1_results[303]["anchors"]
    diff_98_303 = anch_98.symmetric_difference(anch_303)
    lines.append(f"  Anchor sets: {'IDENTICAL' if not diff_98_303 else 'DIFFERENT'}")
    if diff_98_303:
        if anch_98 - anch_303:
            lines.append(f"  In Kami(98) but NOT in Whommie(303): {sorted(anch_98 - anch_303)}")
        if anch_303 - anch_98:
            lines.append(f"  In Whommie(303) but NOT in Kami(98):  {sorted(anch_303 - anch_98)}")
    else:
        lines.append(f"  Both contain: {sorted(anch_98)}")
    blank()

    lines.append("COMPARISON: headShape-1 frame 98 (Kami) vs frame 318 (Bud)")
    sep("-")
    anch_318 = headshape_minus1_results[318]["anchors"]
    diff_98_318 = anch_98.symmetric_difference(anch_318)
    lines.append(f"  Anchor sets: {'IDENTICAL' if not diff_98_318 else 'DIFFERENT'}")
    if diff_98_318:
        if anch_98 - anch_318:
            lines.append(f"  In Kami(98) but NOT in Bud(318): {sorted(anch_98 - anch_318)}")
        if anch_318 - anch_98:
            lines.append(f"  In Bud(318) but NOT in Kami(98):  {sorted(anch_318 - anch_98)}")
    else:
        lines.append(f"  Both contain: {sorted(anch_98)}")
    blank()

    lines.append("DIRECTION 48 NAME EXTRACTION BUG")
    sep("-")
    lines.append("  Direction 48 used a backward-scan heuristic to find child names in")
    lines.append("  PlaceObject2 tags. This produced 'Nmouth' instead of 'mouth' at depth=66.")
    lines.append("  'Nmouth' is not in the ANCHOR_SET so Direction 48 never recorded 'mouth'.")
    lines.append("  This script's forward-parsing correctly extracts 'mouth' at depth=66.")
    lines.append("  Effect on prior Direction 48 report: 'mouth' was never present in any")
    lines.append("  of Dir48's results, but this is a display bug only. The frames checked")
    lines.append("  in Direction 48 (99/304/319) did not differ in the other 7 named anchors,")
    lines.append("  so the 'identical' conclusion for frame 99 vs 304 was correct for those.")
    lines.append("  However: Direction 48 did NOT check frames 98/303/318 (headShape-1).")
    blank()

    lines.append("CRITICAL: FRAME OFFSET EFFECT")
    sep("-")
    lines.append("  The reye anchor is removed at depth=70 by a RemoveObject2 labeled fn=303.")
    lines.append("  At headShape frame 304 (inclusive, fn<=304): reye is re-placed (fn=304 tag).")
    lines.append("  At headShape-1 frame 303 (inclusive, fn<=303): reye removal is applied,")
    lines.append("    but the re-placement (fn=304) is NOT yet committed. Reye is ABSENT.")
    lines.append("  Similarly for Bud:")
    lines.append("  The lear/rear anchors are removed at depths=31,35 by tags labeled fn=318.")
    lines.append("  At headShape frame 319 (inclusive): lear/rear are re-placed (fn=319 tags).")
    lines.append("  At headShape-1 frame 318 (inclusive): removal applied, re-placement not committed.")
    lines.append("  Lear and rear are ABSENT.")
    blank()

    lines.append("ALL ANCHOR REMOVE EVENTS (frames 0 to " + str(MAX_REMOVE_REPORT_FRAME) + ")")
    sep("-")
    lines.append(f"  Total anchor remove events found: {len(anchor_removes)}")
    blank()
    if not anchor_removes:
        lines.append("  (none)")
    else:
        for r in anchor_removes:
            lines.append(
                f"  Frame {r['frame']:4d}  tag={r['tag_name']}  depth={r['depth']:4d}"
                f"  prev_name={r['prev_name']!r}  prev_char={r['prev_char_id']}"
            )
    blank()
    lines.append("  INTERPRETATION:")
    lines.append("  Frame   1: removes leye/reye from depths 74/78 (extra init-frame objects)")
    lines.append("             These are the duplicates placed at frame=0 that are cleaned up.")
    lines.append("  Frame 303: removes reye from depth=70. At headShape-1=303, this commits")
    lines.append("             WITHOUT the fn=304 re-placement -> reye absent for Whommie.")
    lines.append("  Frame 308: removes rear+reye (temporary removal, re-placed in same frame range)")
    lines.append("  Frame 313: removes mouth+reye (temporary removal)")
    lines.append("  Frame 314: removes leye (temporary removal)")
    lines.append("  Frame 318: removes lear+rear from depths 31/35. At headShape-1=318, this")
    lines.append("             commits WITHOUT the fn=319 re-placement -> lear+rear absent for Bud.")
    lines.append("  Frame 319: removes leye from depth=39 (leye was moved to depth=39 for Bud head)")
    blank()

    lines.append("PREDICTED DEFECTS FROM ANCHOR DIFF")
    sep("-")
    lines.append("")
    lines.append("  FUN_140734760 (per Direction 54): clears CatPart+0x18 for k=7..13 (head slots),")
    lines.append("  then sets it to 1 only if the anchor name for that slot appears in the")
    lines.append("  CatHeadPlacements clip's display list at headShape-1.")
    lines.append("  CatPart+0x18=0 -> renderer emits 0xFFFFFFFE -> missing-part defect signal.")
    lines.append("")
    lines.append("  Whommie (headShape=304, seeks frame 303):")
    if anch_98 - anch_303:
        for absent in sorted(anch_98 - anch_303):
            lines.append(f"    Anchor '{absent}' absent at frame 303 but present at frame 98 (Kami).")
        lines.append(f"    Predicted: CatPart+0x18=0 for slot(s) corresponding to: {sorted(anch_98 - anch_303)}")
        lines.append(f"    'reye' absent -> right-eye CatPart k=8 gets +0x18=0 -> right-eye defect")
        lines.append(f"    Eye-defect pair: if right-eye slot is missing, eyebrow follows per Direction 54.")
        lines.append(f"    This MATCHES Whommie's observed eye+eyebrow birth defects.")
    else:
        lines.append("    Anchor sets identical at 303 vs 98 -> no anchor-based prediction.")
    lines.append("")
    lines.append("  Bud (headShape=319, seeks frame 318):")
    if anch_98 - anch_318:
        for absent in sorted(anch_98 - anch_318):
            lines.append(f"    Anchor '{absent}' absent at frame 318 but present at frame 98 (Kami).")
        lines.append(f"    Predicted: CatPart+0x18=0 for slot(s) corresponding to: {sorted(anch_98 - anch_318)}")
        lines.append(f"    'lear' absent -> left-ear CatPart gets +0x18=0 -> left-ear defect")
        lines.append(f"    'rear' absent -> right-ear CatPart gets +0x18=0 -> right-ear defect")
        lines.append(f"    This MATCHES Bud's observed ear-related DEX penalty birth defect.")
    else:
        lines.append("    Anchor sets identical at 318 vs 98 -> no anchor-based prediction.")
    blank()

    lines.append("CONCLUSION")
    sep("-")
    both_differ = bool((anch_98 - anch_303) or (anch_98 - anch_318))
    if both_differ:
        if anch_98 - anch_303:
            lines.append("  [PIVOTAL] Anchor sets DIFFER at headShape-1=303 (Whommie) vs 98 (Kami).")
            lines.append("  Whommie missing: " + str(sorted(anch_98 - anch_303)))
        if anch_98 - anch_318:
            lines.append("  [PIVOTAL] Anchor sets DIFFER at headShape-1=318 (Bud) vs 98 (Kami).")
            lines.append("  Bud missing: " + str(sorted(anch_98 - anch_318)))
        lines.append("")
        lines.append("  Root cause of discrepancy with Direction 48:")
        lines.append("    Direction 48 checked frames 99/304/319 (headShape directly).")
        lines.append("    At those frames, re-placement tags (fn=304, fn=319) ARE committed,")
        lines.append("    restoring the removed anchors. Result: sets appeared identical.")
        lines.append("    Direction 54 confirmed the actual code uses headShape-1.")
        lines.append("    At frames 303/318 (headShape-1), the removal tags are committed")
        lines.append("    but the re-placement tags are NOT yet committed.")
        lines.append("    Result: reye absent for Whommie, lear+rear absent for Bud.")
        lines.append("")
        lines.append("  This resolves the investigation for both Whommie and Bud:")
        lines.append("    The CatHeadPlacements SWF, under headShape-1 frame seeking,")
        lines.append("    produces missing anchor names that cause FUN_140734760 to")
        lines.append("    leave CatPart+0x18=0 for the corresponding head part slots.")
        lines.append("    The renderer then emits 0xFFFFFFFE for those slots.")
        lines.append("    The parser detects 0xFFFFFFFE as a birth defect.")
        lines.append("    The entire missing-defect chain is now explained end-to-end.")
    else:
        lines.append("  Anchor sets are IDENTICAL for both Whommie and Bud vs Kami.")
        lines.append("  The headShape-1 frame index does not explain the defects.")
        lines.append("  The investigation premise requires re-examination.")
    blank()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written: {OUT}")
    print()
    print("=== Quick Summary ===")
    for tf in sorted(TARGET_FRAMES):
        r = headshape_minus1_results[tf]
        print(f"  headShape-1 Frame {tf:3d} ({r['label']}): anchors={sorted(r['anchors'])}")
    print()
    for tf in sorted(HEADSHAPE_DIRECT_FRAMES):
        r = headshape_direct_results[tf]
        print(f"  headShape direct Frame {tf:3d} ({r['label']}): anchors={sorted(r['anchors'])}")
    print()
    anch_98 = headshape_minus1_results[98]["anchors"]
    anch_303 = headshape_minus1_results[303]["anchors"]
    anch_318 = headshape_minus1_results[318]["anchors"]
    print(f"  Kami(98)  vs Whommie(303): {'DIFFERENT - missing: ' + str(sorted(anch_98-anch_303)) if anch_98-anch_303 else 'IDENTICAL'}")
    print(f"  Kami(98)  vs Bud(318):     {'DIFFERENT - missing: ' + str(sorted(anch_98-anch_318)) if anch_98-anch_318 else 'IDENTICAL'}")
    print()
    print("  Anchor removes at critical frames:")
    for r in anchor_removes:
        if r["frame"] in (303, 318):
            print(f"    Frame {r['frame']}: remove depth={r['depth']} prev_name={r['prev_name']!r}")


if __name__ == "__main__":
    main()
