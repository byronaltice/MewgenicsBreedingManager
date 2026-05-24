"""SWF sprite-timeline walker.

Adapted from defect-investigation/scripts/extract-symbols/extract_sprites.py
(dev-only paths and dev-only CLI removed). Pure helpers used by
``extract_abilities`` to render named MovieClip sprite frames to PNG.
"""

from __future__ import annotations

import struct

from .swf_parser import (
    _parse_header, _skip_rect, _read_swf_tags,
    _parse_export_assets, _parse_symbol_class,
    _parse_bits_lossless, _parse_bits_jpeg,
    TAG_DEFINE_BITS_LOSSLESS, TAG_DEFINE_BITS_LOSSLESS2,
    TAG_DEFINE_BITS_JPEG2, TAG_DEFINE_BITS_JPEG3, TAG_DEFINE_BITS_JPEG4,
    TAG_EXPORT_ASSETS, TAG_SYMBOL_CLASS,
)
from .swf_shape_renderer import (
    parse_shape, SHAPE_TAGS, TWIPS_PER_PIXEL,
)

# SWF tag types
TAG_END = 0
TAG_SHOW_FRAME = 1
TAG_PLACE_OBJECT2 = 26
TAG_REMOVE_OBJECT2 = 28
TAG_DEFINE_SPRITE = 39
TAG_FRAME_LABEL = 43
TAG_PLACE_OBJECT3 = 70

# PlaceObject2 flag bits
_PLACE2_FLAG_HAS_CHARACTER = 1 << 1
_PLACE_OBJECT2_MIN_LEN = 3
_PLACE_OBJECT2_WITH_CHARID_MIN_LEN = 5
_PLACE_OBJECT3_MIN_LEN = 4
_PLACE_OBJECT3_WITH_CHARID_MIN_LEN = 6
_REMOVE_OBJECT2_LEN = 2
_DEFINE_SPRITE_HEADER_LEN = 4  # char_id u16 + frame_count u16


def _read_tags_from(data_slice: bytes):
    """Yield (tag_type, tag_data) pairs from a flat tag stream."""
    pos = 0
    length = len(data_slice)
    while pos < length - 1:
        if pos + 2 > length:
            break
        record_header = struct.unpack_from("<H", data_slice, pos)[0]
        pos += 2
        tag_type = record_header >> 6
        tag_len = record_header & 0x3F
        if tag_len == 0x3F:
            if pos + 4 > length:
                break
            tag_len = struct.unpack_from("<i", data_slice, pos)[0]
            pos += 4
        tag_data = data_slice[pos: pos + tag_len]
        pos += tag_len
        yield tag_type, tag_data
        if tag_type == TAG_END:
            break


def parse_all_tags(swf_source) -> dict:
    """Parse a SWF and return structured data.

    ``swf_source`` may be either a filesystem path (``str`` / ``PathLike``)
    pointing at a ``.swf`` file, or an in-memory ``bytes`` blob containing
    the raw SWF.

    Returns dict with keys:
        names: {char_id: symbol_name}
        shapes: {char_id: (tag_type, tag_data)}
        sprites: {char_id: [(child_tag_type, child_tag_data), ...]}
        bitmaps: {char_id: info_dict}
    """
    if isinstance(swf_source, (bytes, bytearray, memoryview)):
        raw = bytes(swf_source)
    else:
        with open(swf_source, "rb") as f:
            raw = f.read()

    body, _version = _parse_header(raw)
    _SWF_RATE_PLUS_COUNT_BYTES = 4
    after_header = _skip_rect(body)[_SWF_RATE_PLUS_COUNT_BYTES:]

    names: dict[int, str] = {}
    shapes: dict[int, tuple[int, bytes]] = {}
    sprites: dict[int, list[tuple[int, bytes]]] = {}
    bitmaps: dict[int, dict] = {}

    for tag_type, tag_data in _read_swf_tags(after_header):
        if tag_type in SHAPE_TAGS:
            if len(tag_data) >= 2:
                char_id = struct.unpack_from("<H", tag_data, 0)[0]
                shapes[char_id] = (tag_type, tag_data)
        elif tag_type == TAG_DEFINE_SPRITE:
            if len(tag_data) >= _DEFINE_SPRITE_HEADER_LEN:
                char_id = struct.unpack_from("<H", tag_data, 0)[0]
                inner_data = tag_data[_DEFINE_SPRITE_HEADER_LEN:]
                sprites[char_id] = list(_read_tags_from(inner_data))
        elif tag_type in (TAG_DEFINE_BITS_LOSSLESS, TAG_DEFINE_BITS_LOSSLESS2):
            _parse_bits_lossless(tag_type, tag_data, bitmaps)
        elif tag_type in (TAG_DEFINE_BITS_JPEG2, TAG_DEFINE_BITS_JPEG3, TAG_DEFINE_BITS_JPEG4):
            _parse_bits_jpeg(tag_type, tag_data, bitmaps)
        elif tag_type == TAG_EXPORT_ASSETS:
            _parse_export_assets(tag_data, names)
        elif tag_type == TAG_SYMBOL_CLASS:
            _parse_symbol_class(tag_data, names)

    return {
        "names": names,
        "shapes": shapes,
        "sprites": sprites,
        "bitmaps": bitmaps,
    }


def collect_shapes_in_sprite(sprite_id: int, sprites: dict, shapes: dict,
                             visited: set | None = None) -> list[int]:
    """Recursively collect all shape char_ids referenced by a sprite."""
    if visited is None:
        visited = set()
    if sprite_id in visited:
        return []
    visited.add(sprite_id)

    placed_ids = _get_placed_shape_ids(sprites.get(sprite_id, []))

    result_shapes = []
    for placed_id in placed_ids:
        if placed_id in shapes:
            result_shapes.append(placed_id)
        elif placed_id in sprites:
            result_shapes.extend(collect_shapes_in_sprite(placed_id, sprites, shapes, visited))
    return result_shapes


def _get_placed_shape_ids(inner_tags) -> list[int]:
    placed: list[int] = []
    for tag_type, tag_data in inner_tags:
        if tag_type == TAG_PLACE_OBJECT2:
            if len(tag_data) < _PLACE_OBJECT2_MIN_LEN:
                continue
            flags = tag_data[0]
            if (flags & _PLACE2_FLAG_HAS_CHARACTER) and len(tag_data) >= _PLACE_OBJECT2_WITH_CHARID_MIN_LEN:
                placed.append(struct.unpack_from("<H", tag_data, 3)[0])
        elif tag_type == TAG_PLACE_OBJECT3:
            if len(tag_data) < _PLACE_OBJECT3_MIN_LEN:
                continue
            flags1 = tag_data[0]
            if (flags1 & _PLACE2_FLAG_HAS_CHARACTER) and len(tag_data) >= _PLACE_OBJECT3_WITH_CHARID_MIN_LEN:
                placed.append(struct.unpack_from("<H", tag_data, 4)[0])
    return placed


def get_combined_bounds(shape_ids: list[int], shapes: dict):
    """Compute the union bounding box of all shapes in twips."""
    all_bounds = []
    for cid in shape_ids:
        if cid not in shapes:
            continue
        tag_type, tag_data = shapes[cid]
        try:
            parsed = parse_shape(tag_data, tag_type)
            all_bounds.append(parsed["bounds"])
        except Exception:
            pass

    if not all_bounds:
        return None

    xmin = min(b[0] for b in all_bounds)
    xmax = max(b[1] for b in all_bounds)
    ymin = min(b[2] for b in all_bounds)
    ymax = max(b[3] for b in all_bounds)
    return xmin, xmax, ymin, ymax


# ── Render helpers shared with sprite-frame rendering ─────────────────────────

# Re-exported render-shapes-to-canvas helper. Implementation copied from
# defect-investigation/scripts/extract-symbols/extract_sprites.py.
def render_parsed_shape_to_canvas(canvas, shape_data, pix_scale, tx, ty):
    """Render a parsed shape's records onto a skia canvas."""
    import skia  # local import — keep skia dep out of module load

    fills = shape_data["fills"]
    lines = shape_data["lines"]
    records = shape_data["records"]

    def px(twip_x):
        return twip_x * pix_scale + tx

    def py(twip_y):
        return twip_y * pix_scale + ty

    paths_by_fill = {}
    paths_by_line = {}

    cur_fill0_idx = 0
    cur_fill1_idx = 0
    cur_line_idx = 0
    path_x = 0.0
    path_y = 0.0
    subpath_started = False
    have_position = False

    for rec in records:
        rtype = rec["type"]
        if rtype == "style":
            cur_fill0_idx = rec["fill0"]
            cur_fill1_idx = rec["fill1"]
            cur_line_idx = rec["line"]
            if have_position:
                for idx in (cur_fill0_idx, cur_fill1_idx):
                    if idx > 0:
                        paths_by_fill.setdefault(idx, skia.Path()).moveTo(px(path_x), py(path_y))
                if cur_line_idx > 0:
                    paths_by_line.setdefault(cur_line_idx, skia.Path()).moveTo(px(path_x), py(path_y))
                subpath_started = True
            else:
                subpath_started = False
        elif rtype == "move":
            path_x, path_y = rec["x"], rec["y"]
            have_position = True
            for idx in (cur_fill0_idx, cur_fill1_idx):
                if idx > 0:
                    paths_by_fill.setdefault(idx, skia.Path()).moveTo(px(path_x), py(path_y))
            if cur_line_idx > 0:
                paths_by_line.setdefault(cur_line_idx, skia.Path()).moveTo(px(path_x), py(path_y))
            subpath_started = True
        elif rtype == "line" and subpath_started:
            ex, ey = rec["x"], rec["y"]
            for idx in (cur_fill0_idx, cur_fill1_idx):
                if idx > 0:
                    p = paths_by_fill.setdefault(idx, skia.Path())
                    if p.isEmpty():
                        p.moveTo(px(path_x), py(path_y))
                    p.lineTo(px(ex), py(ey))
            if cur_line_idx > 0:
                p = paths_by_line.setdefault(cur_line_idx, skia.Path())
                if p.isEmpty():
                    p.moveTo(px(path_x), py(path_y))
                p.lineTo(px(ex), py(ey))
            path_x, path_y = ex, ey
        elif rtype == "curve" and subpath_started:
            cx, cy, ex, ey = rec["cx"], rec["cy"], rec["x"], rec["y"]
            for idx in (cur_fill0_idx, cur_fill1_idx):
                if idx > 0:
                    p = paths_by_fill.setdefault(idx, skia.Path())
                    if p.isEmpty():
                        p.moveTo(px(path_x), py(path_y))
                    p.quadTo(px(cx), py(cy), px(ex), py(ey))
            if cur_line_idx > 0:
                p = paths_by_line.setdefault(cur_line_idx, skia.Path())
                if p.isEmpty():
                    p.moveTo(px(path_x), py(path_y))
                p.quadTo(px(cx), py(cy), px(ex), py(ey))
            path_x, path_y = ex, ey

    _DEFAULT_GRAY = (180, 180, 180, 200)
    _DEFAULT_STROKE = (0, 0, 0, 255)
    _MIN_STROKE_PX = 1.0

    for fill_idx, path in paths_by_fill.items():
        if fill_idx < 1 or fill_idx > len(fills):
            continue
        fill_style = fills[fill_idx - 1]
        paint = skia.Paint()
        paint.setAntiAlias(True)
        paint.setStyle(skia.Paint.kFill_Style)
        if fill_style["color"]:
            r, g, b, a = fill_style["color"]
            paint.setColor(skia.Color(r, g, b, a))
        else:
            paint.setColor(skia.Color(*_DEFAULT_GRAY))
        path.close()
        canvas.drawPath(path, paint)

    for line_idx, path in paths_by_line.items():
        if line_idx < 1 or line_idx > len(lines):
            continue
        line_style = lines[line_idx - 1]
        paint = skia.Paint()
        paint.setAntiAlias(True)
        paint.setStyle(skia.Paint.kStroke_Style)
        paint.setStrokeWidth(max(_MIN_STROKE_PX, line_style["width"] * pix_scale))
        paint.setStrokeCap(skia.Paint.kRound_Cap)
        paint.setStrokeJoin(skia.Paint.kRound_Join)
        if line_style["color"]:
            r, g, b, a = line_style["color"]
            paint.setColor(skia.Color(r, g, b, a))
        else:
            paint.setColor(skia.Color(*_DEFAULT_STROKE))
        canvas.drawPath(path, paint)
