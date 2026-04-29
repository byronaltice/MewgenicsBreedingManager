"""
SWF anchor walker for CatHeadPlacements defect detection.

Parses the CatHeadPlacements DefineSprite (char_id=11007) from catparts.swf
and simulates its cumulative display list to determine which named anchor
children are present at each frame.  Missing anchors among ANCHOR_NAMES at
frame (headShape - 1) correspond to birth defects that the game's runtime
renderer emits as missing-part signals (0xFFFFFFFE).

Algorithm lifted from defect-investigation/scripts/investigate-direction/
investigate_direction57.py.  No Qt dependencies.
"""

from __future__ import annotations

import struct

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

ANCHOR_NAMES: frozenset[str] = frozenset(
    {"leye", "reye", "lear", "rear", "mouth", "ahead", "aneck", "aface"}
)

CAT_HEAD_PLACEMENTS_CHAR_ID: int = 11007

# SWF tag type constants
_TAG_PLACE_OBJECT: int = 4
_TAG_REMOVE_OBJECT: int = 5
_TAG_SHOW_FRAME: int = 1
_TAG_END_OF_SPRITE: int = 0
_TAG_PLACE_OBJECT2: int = 26
_TAG_REMOVE_OBJECT2: int = 28
_TAG_DEFINE_SPRITE: int = 39
_TAG_PLACE_OBJECT3: int = 70


# ---------------------------------------------------------------------------
# SWF binary helpers (private)
# ---------------------------------------------------------------------------

def _read_swf_tag(data: bytes, pos: int) -> tuple[int, int, bytes, int]:
    """Read one SWF record-header tag at pos.

    Returns (tag_type, tag_len, tag_body, next_pos).
    """
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


def _find_sprite_body(data: bytes, target_char_id: int) -> tuple[int, int] | None:
    """Walk the outer SWF tag stream to find DefineSprite for target_char_id.

    Returns (body_start, body_end) or None if not found.
    body_start skips the char_id(2) + frame_count(2) fields so the caller
    gets the raw inner tag stream.
    """
    pos = 8  # skip SWF file header (Signature[3] + Version[1] + FileLength[4])
    # Skip RECT (variable-length bit-packed bounding box)
    n_bits = (data[pos] >> 3) & 0x1F
    rect_bits = 5 + n_bits * 4
    rect_bytes = (rect_bits + 7) // 8
    pos += rect_bytes
    pos += 4  # FrameRate(2) + FrameCount(2)

    while pos < len(data) - 2:
        tag_type, tag_len, tag_body, next_pos = _read_swf_tag(data, pos)
        if tag_type == _TAG_END_OF_SPRITE:
            break
        if tag_type == _TAG_DEFINE_SPRITE:
            char_id = struct.unpack_from("<H", tag_body, 0)[0]
            if char_id == target_char_id:
                tag_body_start = next_pos - tag_len
                # +4 skips char_id(2) + frame_count(2) at start of DefineSprite body
                body_start = tag_body_start + 4
                body_end = next_pos
                return body_start, body_end
        pos = next_pos

    return None


# ---------------------------------------------------------------------------
# Bit-level matrix/color-transform helpers (private)
# ---------------------------------------------------------------------------

def _skip_matrix(data: bytes, byte_pos: int) -> int | None:
    """Skip SWF MATRIX bit-record. Returns new byte position, or None on error."""
    try:
        bit_pos = byte_pos * 8
        total_bits = len(data) * 8

        def _read_bits(n: int) -> int:
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

        has_scale = _read_bits(1)
        if has_scale:
            n_scale = _read_bits(5)
            _read_bits(n_scale)
            _read_bits(n_scale)
        has_rotate = _read_bits(1)
        if has_rotate:
            n_rotate = _read_bits(5)
            _read_bits(n_rotate)
            _read_bits(n_rotate)
        n_translate = _read_bits(5)
        _read_bits(n_translate)
        _read_bits(n_translate)
        # byte-align
        if bit_pos % 8:
            bit_pos += 8 - (bit_pos % 8)
        return bit_pos // 8
    except Exception:
        return None


def _skip_color_transform_alpha(data: bytes, byte_pos: int) -> int | None:
    """Skip SWF CXFORMWITHALPHA bit-record. Returns new byte position, or None on error."""
    try:
        bit_pos = byte_pos * 8
        total_bits = len(data) * 8

        def _read_bits(n: int) -> int:
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

        has_add = _read_bits(1)
        has_mult = _read_bits(1)
        nbits = _read_bits(4)
        if has_mult:
            for _ in range(4):
                _read_bits(nbits)
        if has_add:
            for _ in range(4):
                _read_bits(nbits)
        if bit_pos % 8:
            bit_pos += 8 - (bit_pos % 8)
        return bit_pos // 8
    except Exception:
        return None


# ---------------------------------------------------------------------------
# PlaceObject2 / PlaceObject3 field extraction (private)
# ---------------------------------------------------------------------------

def _read_null_string(data: bytes, start: int) -> str | None:
    """Read a null-terminated ASCII string from data[start:]."""
    end = data.find(b"\x00", start)
    if end == -1:
        return None
    try:
        return data[start:end].decode("ascii", errors="replace")
    except Exception:
        return None


def _extract_place_object2_fields(tag_body: bytes) -> dict:
    """Extract has_move, depth, char_id, name from PlaceObject2 (tag 26).

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


def _extract_place_object3_fields(tag_body: bytes) -> dict:
    """Extract has_move, depth, char_id, name from PlaceObject3 (tag 70).

    PlaceObject3 adds a second flags byte and an optional class name before
    the MATRIX field.
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
# Sprite tag stream parsing + display list simulation (private)
# ---------------------------------------------------------------------------

class _TagEvent:
    """A single non-ShowFrame tag event with its committed frame label."""
    __slots__ = ("frame", "tag_type", "tag_body")

    def __init__(self, frame: int, tag_type: int, tag_body: bytes) -> None:
        self.frame = frame
        self.tag_type = tag_type
        self.tag_body = tag_body


class _DisplayEntry:
    """One entry in the sprite display list (depth → char_id + optional name)."""
    __slots__ = ("char_id", "name")

    def __init__(self, char_id: int | None, name: str | None) -> None:
        self.char_id = char_id
        self.name = name


def _parse_sprite_tag_stream(
    data: bytes,
    body_start: int,
    body_end: int,
) -> list[_TagEvent]:
    """Walk a sprite's inner tag stream and label events by their committed frame.

    Events are labeled with the frame counter BEFORE the ShowFrame that
    commits them.  ShowFrame increments the counter, so events between the
    Nth and (N+1)th ShowFrame are labeled N.  Seeking to frame F includes all
    events with label 0 .. F (inclusive).
    """
    events: list[_TagEvent] = []
    frame_num = 0
    pos = body_start

    while pos < body_end:
        tag_type, tag_len, tag_body, next_pos = _read_swf_tag(data, pos)
        if tag_type == _TAG_END_OF_SPRITE:
            break
        elif tag_type == _TAG_SHOW_FRAME:
            frame_num += 1
        else:
            events.append(_TagEvent(frame_num, tag_type, tag_body))
        pos = next_pos

    return events


def _apply_event_to_display_list(
    event: _TagEvent,
    display_list: dict[int, _DisplayEntry],
) -> None:
    """Apply a single tag event to a display list (mutates in place)."""
    tag_type = event.tag_type
    tag_body = event.tag_body

    if tag_type == _TAG_PLACE_OBJECT:  # SWF1 legacy PlaceObject — no MOVE flag, no name
        if len(tag_body) >= 4:
            char_id = struct.unpack_from("<H", tag_body, 0)[0]
            depth = struct.unpack_from("<H", tag_body, 2)[0]
            display_list[depth] = _DisplayEntry(char_id, None)

    elif tag_type == _TAG_PLACE_OBJECT2:
        fields = _extract_place_object2_fields(tag_body)
        depth = fields["depth"]
        if fields["has_move"]:
            if depth in display_list:
                if fields["char_id"] is not None:
                    display_list[depth].char_id = fields["char_id"]
                if fields["name"] is not None:
                    display_list[depth].name = fields["name"]
        else:
            display_list[depth] = _DisplayEntry(fields["char_id"], fields["name"])

    elif tag_type == _TAG_PLACE_OBJECT3:
        fields = _extract_place_object3_fields(tag_body)
        depth = fields["depth"]
        if fields["has_move"]:
            if depth in display_list:
                if fields["char_id"] is not None:
                    display_list[depth].char_id = fields["char_id"]
                if fields["name"] is not None:
                    display_list[depth].name = fields["name"]
        else:
            display_list[depth] = _DisplayEntry(fields["char_id"], fields["name"])

    elif tag_type == _TAG_REMOVE_OBJECT:  # char_id(2) + depth(2)
        if len(tag_body) >= 4:
            depth = struct.unpack_from("<H", tag_body, 2)[0]
            display_list.pop(depth, None)

    elif tag_type == _TAG_REMOVE_OBJECT2:  # depth(2)
        if len(tag_body) >= 2:
            depth = struct.unpack_from("<H", tag_body, 0)[0]
            display_list.pop(depth, None)


def _simulate_display_list(
    events: list[_TagEvent],
    target_frame: int,
) -> dict[int, _DisplayEntry]:
    """Simulate the accumulated display list at target_frame (inclusive semantics).

    fn <= target_frame — matches the runtime FUN_140996b80 gotoFrame behavior
    confirmed in Direction 56/57: seeking to frame F commits all events labeled
    0 .. F.
    """
    display_list: dict[int, _DisplayEntry] = {}
    for event in events:
        if event.frame > target_frame:
            break
        _apply_event_to_display_list(event, display_list)
    return display_list


def _anchor_set_from_display_list(
    display_list: dict[int, _DisplayEntry],
) -> frozenset[str]:
    """Return the subset of ANCHOR_NAMES currently present in the display list."""
    return frozenset(
        entry.name
        for entry in display_list.values()
        if entry.name in ANCHOR_NAMES
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_cat_head_placements(swf_bytes: bytes) -> list[frozenset[str]]:
    """Return per-frame cumulative anchor sets for CatHeadPlacements.

    Result is indexed by 0-based frame number; element k is the set of
    anchor names present at frame k under inclusive cumulative semantics
    (matches the runtime FUN_140996b80 behavior, per Direction 56/57).

    Returns an empty list if the DefineSprite for CAT_HEAD_PLACEMENTS_CHAR_ID
    cannot be located in swf_bytes.
    """
    sprite_bounds = _find_sprite_body(swf_bytes, CAT_HEAD_PLACEMENTS_CHAR_ID)
    if sprite_bounds is None:
        return []

    body_start, body_end = sprite_bounds
    events = _parse_sprite_tag_stream(swf_bytes, body_start, body_end)
    if not events:
        return []

    max_frame = max(event.frame for event in events)
    per_frame: list[frozenset[str]] = []
    for frame_index in range(max_frame + 1):
        display_list = _simulate_display_list(events, frame_index)
        per_frame.append(_anchor_set_from_display_list(display_list))

    return per_frame


def missing_anchors_for_head_shape(
    per_frame: list[frozenset[str]],
    head_shape: int,
) -> frozenset[str]:
    """Return the set of anchor names absent at frame head_shape - 1.

    The game's runtime seeks to headShape - 1 in the CatHeadPlacements clip
    (confirmed by Direction 54/56/57 analysis).

    Returns an empty frozenset when per_frame is empty (e.g. no gpak loaded)
    or head_shape - 1 is out of range. The opposite choice (all anchors
    "missing") would falsely synthesize eye/eyebrow/ear/mouth defects for
    every cat when SWF data is unavailable, which is far worse than the
    miss — defect display already degrades to the T-array sentinel path
    when the SWF can't be consulted.
    """
    if not per_frame:
        return frozenset()
    target_frame = head_shape - 1
    if target_frame < 0 or target_frame >= len(per_frame):
        return frozenset()
    return ANCHOR_NAMES - per_frame[target_frame]
