"""
Extract specific named sprites from SWF files and render them to PNG.

Target sprites from events.swf (stat icons):
  statstr_352, statdex_365, statcon_368, statint_371, statspd_374, statcha_377, statlck_380
  choiceSTR_274, choiceCON_275, choiceSPD_276, choiceINT_273, choiceDEX_277, choiceCHA_280, choiceLUK_281

Target sprites from house.swf (nametag/room stat icons):
  HouseNametag (418), RoomStatsUI (501)
"""

import os
import sys
import struct
import zlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from swf_parser import (
    _parse_header, _skip_rect, _read_swf_tags,
    _parse_export_assets, _parse_symbol_class,
    extract_all_bitmaps
)
from swf_shape_renderer import (
    parse_shape, render_shape_to_png, SHAPE_TAGS,
    TAG_DEFINE_SHAPE, TAG_DEFINE_SHAPE2, TAG_DEFINE_SHAPE3, TAG_DEFINE_SHAPE4
)

TAG_DEFINE_SPRITE = 39
TAG_PLACE_OBJECT2 = 26
TAG_PLACE_OBJECT3 = 70
TAG_FRAME_LABEL = 43
TAG_SHOW_FRAME = 1
TAG_REMOVE_OBJECT2 = 28
TAG_END = 0

DEFECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
SWF_DIR = os.path.join(DEFECT_DIR, "game-files", "resources", "gpak-video", "swfs")
OUTPUT_BASE = os.path.join(DEFECT_DIR, "audit", "direction", "symbol-candidates")


def parse_all_tags(swf_path):
    """
    Parse all tags in a SWF and return structured data:
    - shapes: {char_id: (tag_type, tag_data)}
    - sprites: {char_id: [(child_tag_type, child_tag_data), ...]}
    - names: {char_id: name}
    - bitmaps: {char_id: info_dict}
    """
    with open(swf_path, "rb") as f:
        raw = f.read()

    body, version = _parse_header(raw)
    after_header = _skip_rect(body)[4:]

    names = {}
    shapes = {}    # char_id -> (tag_type, tag_data)
    sprites = {}   # char_id -> [(tag_type, tag_data), ...]
    bitmaps = {}

    # We need to parse sprites recursively — sprites have their own tag stream inside
    # The SWF tag stream is flat; DefineSprite contains an internal tag count
    # but we read all nested tags as part of the sprite

    def read_tags_from(data_slice):
        """Yield (tag_type, tag_data) pairs from a byte slice."""
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

    from swf_parser import (
        _parse_bits_lossless, _parse_bits_jpeg,
        TAG_DEFINE_BITS_LOSSLESS, TAG_DEFINE_BITS_LOSSLESS2,
        TAG_DEFINE_BITS_JPEG2, TAG_DEFINE_BITS_JPEG3, TAG_DEFINE_BITS_JPEG4
    )

    for tag_type, tag_data in _read_swf_tags(after_header):
        if tag_type in SHAPE_TAGS:
            if len(tag_data) >= 2:
                char_id = struct.unpack_from("<H", tag_data, 0)[0]
                shapes[char_id] = (tag_type, tag_data)

        elif tag_type == TAG_DEFINE_SPRITE:
            if len(tag_data) >= 4:
                char_id = struct.unpack_from("<H", tag_data, 0)[0]
                # tag_data: [2 char_id] [2 frame_count] [inner tags...]
                inner_data = tag_data[4:]
                inner_tags = list(read_tags_from(inner_data))
                sprites[char_id] = inner_tags

        elif tag_type in (TAG_DEFINE_BITS_LOSSLESS, TAG_DEFINE_BITS_LOSSLESS2):
            _parse_bits_lossless(tag_type, tag_data, bitmaps)

        elif tag_type in (TAG_DEFINE_BITS_JPEG2, TAG_DEFINE_BITS_JPEG3, TAG_DEFINE_BITS_JPEG4):
            _parse_bits_jpeg(tag_type, tag_data, bitmaps)

        elif tag_type == 56:
            _parse_export_assets(tag_data, names)
        elif tag_type == 76:
            _parse_symbol_class(tag_data, names)

    return {
        "names": names,
        "shapes": shapes,
        "sprites": sprites,
        "bitmaps": bitmaps,
    }


def get_placed_shape_ids(sprite_inner_tags):
    """
    Extract all shape/sprite character IDs placed in a sprite's timeline.
    PlaceObject2: [flags:u8] [depth:u16] [char_id:u16 if hasCharacter] ...
    """
    placed = []
    for tag_type, tag_data in sprite_inner_tags:
        if tag_type == TAG_PLACE_OBJECT2:
            if len(tag_data) < 3:
                continue
            flags = tag_data[0]
            has_character = (flags >> 1) & 1
            if has_character and len(tag_data) >= 5:
                char_id = struct.unpack_from("<H", tag_data, 3)[0]
                placed.append(char_id)
        elif tag_type == TAG_PLACE_OBJECT3:
            if len(tag_data) < 4:
                continue
            flags1 = tag_data[0]
            flags2 = tag_data[1]
            has_character = (flags1 >> 1) & 1
            if has_character and len(tag_data) >= 6:
                char_id = struct.unpack_from("<H", tag_data, 4)[0]
                placed.append(char_id)
    return placed


def collect_shapes_in_sprite(sprite_id, sprites, shapes, visited=None):
    """Recursively collect all shape char_ids used by a sprite."""
    if visited is None:
        visited = set()
    if sprite_id in visited:
        return []
    visited.add(sprite_id)

    inner_tags = sprites.get(sprite_id, [])
    placed_ids = get_placed_shape_ids(inner_tags)

    result_shapes = []
    for placed_id in placed_ids:
        if placed_id in shapes:
            result_shapes.append(placed_id)
        elif placed_id in sprites:
            result_shapes.extend(collect_shapes_in_sprite(placed_id, sprites, shapes, visited))

    return result_shapes


def get_combined_bounds(shape_ids, shapes):
    """Compute the union bounding box of all shapes."""
    all_bounds = []
    for cid in shape_ids:
        if cid not in shapes:
            continue
        tag_type, tag_data = shapes[cid]
        try:
            parsed = parse_shape(tag_data, tag_type)
            xmin, xmax, ymin, ymax = parsed["bounds"]
            all_bounds.append((xmin, xmax, ymin, ymax))
        except Exception:
            pass

    if not all_bounds:
        return None

    xmin = min(b[0] for b in all_bounds)
    xmax = max(b[1] for b in all_bounds)
    ymin = min(b[2] for b in all_bounds)
    ymax = max(b[3] for b in all_bounds)
    return xmin, xmax, ymin, ymax


def render_sprite_to_png(sprite_id, swf_data, out_path, scale=4.0, padding=4):
    """
    Render a sprite (by char_id) to a PNG by collecting and rendering all its shapes.
    """
    import skia

    shapes = swf_data["shapes"]
    sprites = swf_data["sprites"]

    shape_ids = collect_shapes_in_sprite(sprite_id, sprites, shapes)
    if not shape_ids:
        print(f"    No shapes found in sprite {sprite_id}")
        return False

    bounds = get_combined_bounds(shape_ids, shapes)
    if not bounds:
        return False

    xmin, xmax, ymin, ymax = bounds

    from swf_shape_renderer import TWIPS_PER_PIXEL
    pix_scale = scale / TWIPS_PER_PIXEL
    width_twips = max(1, xmax - xmin)
    height_twips = max(1, ymax - ymin)
    px_w = max(1, int(width_twips * pix_scale) + 2 * padding)
    px_h = max(1, int(height_twips * pix_scale) + 2 * padding)
    px_w = min(px_w, 4096)
    px_h = min(px_h, 4096)

    tx = -xmin * pix_scale + padding
    ty = -ymin * pix_scale + padding

    surface = skia.Surface(px_w, px_h)

    with surface as canvas:
        canvas.clear(skia.ColorTRANSPARENT)

        for cid in shape_ids:
            tag_type, tag_data = shapes[cid]
            try:
                parsed = parse_shape(tag_data, tag_type)
                _render_parsed_shape_to_canvas(canvas, parsed, pix_scale, tx, ty)
            except Exception as e:
                pass  # skip problematic shapes

    img = surface.makeImageSnapshot()
    data = img.encodeToData()
    with open(out_path, "wb") as f:
        f.write(bytes(data))
    return True


def _render_parsed_shape_to_canvas(canvas, shape_data, pix_scale, tx, ty):
    """Render a parsed shape to an existing skia canvas with given transform."""
    import skia

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
        if rec["type"] == "style":
            cur_fill0_idx = rec["fill0"]
            cur_fill1_idx = rec["fill1"]
            cur_line_idx = rec["line"]
            # When style changes and a position exists, open subpaths at current position.
            if have_position:
                for idx in (cur_fill0_idx, cur_fill1_idx):
                    if idx > 0:
                        if idx not in paths_by_fill:
                            paths_by_fill[idx] = skia.Path()
                        paths_by_fill[idx].moveTo(px(path_x), py(path_y))
                if cur_line_idx > 0:
                    if cur_line_idx not in paths_by_line:
                        paths_by_line[cur_line_idx] = skia.Path()
                    paths_by_line[cur_line_idx].moveTo(px(path_x), py(path_y))
                subpath_started = True
            else:
                subpath_started = False

        elif rec["type"] == "move":
            path_x = rec["x"]
            path_y = rec["y"]
            have_position = True
            for idx in (cur_fill0_idx, cur_fill1_idx):
                if idx > 0:
                    if idx not in paths_by_fill:
                        paths_by_fill[idx] = skia.Path()
                    paths_by_fill[idx].moveTo(px(path_x), py(path_y))
            if cur_line_idx > 0:
                if cur_line_idx not in paths_by_line:
                    paths_by_line[cur_line_idx] = skia.Path()
                paths_by_line[cur_line_idx].moveTo(px(path_x), py(path_y))
            subpath_started = True

        elif rec["type"] == "line" and subpath_started:
            ex, ey = rec["x"], rec["y"]
            for idx in (cur_fill0_idx, cur_fill1_idx):
                if idx > 0:
                    if idx not in paths_by_fill:
                        paths_by_fill[idx] = skia.Path()
                        paths_by_fill[idx].moveTo(px(path_x), py(path_y))
                    paths_by_fill[idx].lineTo(px(ex), py(ey))
            if cur_line_idx > 0:
                if cur_line_idx not in paths_by_line:
                    paths_by_line[cur_line_idx] = skia.Path()
                    paths_by_line[cur_line_idx].moveTo(px(path_x), py(path_y))
                paths_by_line[cur_line_idx].lineTo(px(ex), py(ey))
            path_x, path_y = ex, ey

        elif rec["type"] == "curve" and subpath_started:
            cx, cy, ex, ey = rec["cx"], rec["cy"], rec["x"], rec["y"]
            for idx in (cur_fill0_idx, cur_fill1_idx):
                if idx > 0:
                    if idx not in paths_by_fill:
                        paths_by_fill[idx] = skia.Path()
                        paths_by_fill[idx].moveTo(px(path_x), py(path_y))
                    paths_by_fill[idx].quadTo(px(cx), py(cy), px(ex), py(ey))
            if cur_line_idx > 0:
                if cur_line_idx not in paths_by_line:
                    paths_by_line[cur_line_idx] = skia.Path()
                    paths_by_line[cur_line_idx].moveTo(px(path_x), py(path_y))
                paths_by_line[cur_line_idx].quadTo(px(cx), py(cy), px(ex), py(ey))
            path_x, path_y = ex, ey

    # Render fills
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
        elif fill_style["gradient"] and fill_style["gradient"]["stops"]:
            grad = fill_style["gradient"]
            colors = [skia.Color(*stop[1]) for stop in grad["stops"]]
            positions = [stop[0] / 255.0 for stop in grad["stops"]]
            shader = skia.GradientShader.MakeLinear(
                points=[skia.Point(0, 0), skia.Point(px_w if hasattr(canvas, '_w') else 100, 0)],
                colors=colors,
                positions=positions,
            )
            paint.setShader(shader)
        else:
            paint.setColor(skia.Color(180, 180, 180, 200))

        path.close()
        canvas.drawPath(path, paint)

    # Render lines
    for line_idx, path in paths_by_line.items():
        if line_idx < 1 or line_idx > len(lines):
            continue
        line_style = lines[line_idx - 1]
        paint = skia.Paint()
        paint.setAntiAlias(True)
        paint.setStyle(skia.Paint.kStroke_Style)
        stroke_width = max(1.0, line_style["width"] * pix_scale)
        paint.setStrokeWidth(stroke_width)
        paint.setStrokeCap(skia.Paint.kRound_Cap)
        paint.setStrokeJoin(skia.Paint.kRound_Join)
        if line_style["color"]:
            r, g, b, a = line_style["color"]
            paint.setColor(skia.Color(r, g, b, a))
        else:
            paint.setColor(skia.Color(0, 0, 0, 255))
        canvas.drawPath(path, paint)


def extract_named_sprites_from_swf(swf_name, target_name_substrings, output_dir, scale=4.0):
    """
    Extract sprites matching target_name_substrings from a SWF file.
    Returns list of (name_tag_key, char_id, name, out_path, w, h).
    """
    swf_path = os.path.join(SWF_DIR, swf_name)
    if not os.path.exists(swf_path):
        print(f"  [SKIP] {swf_name} not found")
        return []

    print(f"\nParsing {swf_name}...")
    swf_data = parse_all_tags(swf_path)
    names = swf_data["names"]
    sprites = swf_data["sprites"]
    shapes = swf_data["shapes"]

    results = []
    os.makedirs(output_dir, exist_ok=True)

    for char_id, sym_name in sorted(names.items()):
        matched_key = None
        for substring in target_name_substrings:
            if substring.lower() in sym_name.lower():
                matched_key = substring
                break
        if not matched_key:
            continue

        out_filename = f"{char_id:04d}_{sym_name.replace('/', '_')}.png"
        out_path = os.path.join(output_dir, out_filename)

        rendered = False
        width = height = 0

        # Try to render as sprite
        if char_id in sprites:
            try:
                rendered = render_sprite_to_png(char_id, swf_data, out_path, scale=scale)
                if rendered and os.path.exists(out_path):
                    from PIL import Image
                    img = Image.open(out_path)
                    width, height = img.size
                    img.close()
                    print(f"  Rendered sprite {char_id:4d} '{sym_name}' -> {width}x{height}px")
            except Exception as e:
                print(f"  Error rendering sprite {char_id}: {e}")

        # Try as a direct shape
        if not rendered and char_id in shapes:
            try:
                tag_type, tag_data = shapes[char_id]
                parsed = parse_shape(tag_data, tag_type)
                rendered = render_shape_to_png(parsed, out_path, scale=scale)
                if rendered and os.path.exists(out_path):
                    from PIL import Image
                    img = Image.open(out_path)
                    width, height = img.size
                    img.close()
                    print(f"  Rendered shape  {char_id:4d} '{sym_name}' -> {width}x{height}px")
            except Exception as e:
                print(f"  Error rendering shape {char_id}: {e}")

        if rendered:
            results.append({
                "matched_key": matched_key,
                "char_id": char_id,
                "name": sym_name,
                "path": out_path,
                "width": width,
                "height": height,
                "swf": swf_name,
            })

    return results


if __name__ == "__main__":
    # Test extraction of stat icons from events.swf
    swf_out_dir = os.path.join(OUTPUT_BASE, "events")
    os.makedirs(swf_out_dir, exist_ok=True)

    target_substrings = [
        "statstr", "statdex", "statcon", "statint", "statspd", "statcha", "statlck",
        "choiceSTR", "choiceDEX", "choiceCON", "choiceINT", "choiceSPD", "choiceCHA", "choiceLUK",
    ]

    results = extract_named_sprites_from_swf(
        "events.swf",
        target_substrings,
        swf_out_dir,
        scale=8.0
    )

    print(f"\nFound {len(results)} sprites:")
    for r in results:
        print(f"  {r['char_id']:4d} '{r['name']}' [{r['width']}x{r['height']}] -> {os.path.basename(r['path'])}")
