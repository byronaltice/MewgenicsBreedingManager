"""
SWF DefineShape parser and Skia-based rasterizer.

Handles DefineShape (2), DefineShape2 (22), DefineShape3 (32), DefineShape4 (83).
Renders shapes to PNG using skia-python.

SWF coordinate system: twips (1 twip = 1/20 pixel). All coordinates are in twips.
"""

import struct
import math
import os
import sys

try:
    import skia
    _HAS_SKIA = True
except ImportError:
    _HAS_SKIA = False

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


# Tag type constants
TAG_DEFINE_SHAPE = 2
TAG_DEFINE_SHAPE2 = 22
TAG_DEFINE_SHAPE3 = 32
TAG_DEFINE_SHAPE4 = 83
SHAPE_TAGS = {TAG_DEFINE_SHAPE, TAG_DEFINE_SHAPE2, TAG_DEFINE_SHAPE3, TAG_DEFINE_SHAPE4}

# Fill type constants
FILL_SOLID = 0x00
FILL_LINEAR_GRADIENT = 0x10
FILL_RADIAL_GRADIENT = 0x12
FILL_FOCAL_GRADIENT = 0x13
FILL_REPEATING_BITMAP = 0x40
FILL_CLIPPED_BITMAP = 0x41
FILL_NON_SMOOTHED_REPEATING_BITMAP = 0x42
FILL_NON_SMOOTHED_CLIPPED_BITMAP = 0x43

TWIPS_PER_PIXEL = 20.0


class BitStream:
    """Bit-level reader for SWF binary data."""

    def __init__(self, data, byte_offset=0):
        self._data = data
        self._byte_pos = byte_offset
        self._bit_pos = 0  # bits consumed in current byte (0-7)

    @property
    def byte_offset(self):
        """Current aligned byte offset (clears any partial bit consumption)."""
        if self._bit_pos > 0:
            self._byte_pos += 1
            self._bit_pos = 0
        return self._byte_pos

    def align(self):
        """Align to next byte boundary."""
        if self._bit_pos > 0:
            self._byte_pos += 1
            self._bit_pos = 0

    def read_bits(self, n):
        """Read n bits, MSB first."""
        result = 0
        for _ in range(n):
            if self._byte_pos >= len(self._data):
                break
            bit = (self._data[self._byte_pos] >> (7 - self._bit_pos)) & 1
            result = (result << 1) | bit
            self._bit_pos += 1
            if self._bit_pos == 8:
                self._bit_pos = 0
                self._byte_pos += 1
        return result

    def read_signed_bits(self, n):
        """Read n-bit signed integer."""
        val = self.read_bits(n)
        if n > 0 and (val >> (n - 1)) & 1:
            val -= (1 << n)
        return val

    def read_u8(self):
        self.align()
        val = self._data[self._byte_pos]
        self._byte_pos += 1
        return val

    def read_u16(self):
        self.align()
        val = struct.unpack_from("<H", self._data, self._byte_pos)[0]
        self._byte_pos += 2
        return val

    def read_i16(self):
        self.align()
        val = struct.unpack_from("<h", self._data, self._byte_pos)[0]
        self._byte_pos += 2
        return val

    def read_u32(self):
        self.align()
        val = struct.unpack_from("<I", self._data, self._byte_pos)[0]
        self._byte_pos += 4
        return val

    def read_rgb(self):
        r, g, b = self.read_u8(), self.read_u8(), self.read_u8()
        return (r, g, b, 255)

    def read_rgba(self):
        r, g, b, a = self.read_u8(), self.read_u8(), self.read_u8(), self.read_u8()
        return (r, g, b, a)

    def read_argb(self):
        a, r, g, b = self.read_u8(), self.read_u8(), self.read_u8(), self.read_u8()
        return (r, g, b, a)

    def read_matrix(self):
        """Read SWF MATRIX structure. Returns (a, b, c, d, tx, ty) in twips."""
        self.align()
        has_scale = self.read_bits(1)
        sx, sy = 1.0, 1.0
        if has_scale:
            n = self.read_bits(5)
            sx = self.read_signed_bits(n) / 65536.0
            sy = self.read_signed_bits(n) / 65536.0

        has_rotate = self.read_bits(1)
        skewX, skewY = 0.0, 0.0
        if has_rotate:
            n = self.read_bits(5)
            skewX = self.read_signed_bits(n) / 65536.0
            skewY = self.read_signed_bits(n) / 65536.0

        n = self.read_bits(5)
        tx = self.read_signed_bits(n)
        ty = self.read_signed_bits(n)
        self.align()
        return (sx, skewX, skewY, sy, tx, ty)  # a, b, c, d, tx, ty

    def read_rect(self):
        """Read SWF RECT structure. Returns (xmin, xmax, ymin, ymax) in twips."""
        self.align()
        n = self.read_bits(5)
        xmin = self.read_signed_bits(n)
        xmax = self.read_signed_bits(n)
        ymin = self.read_signed_bits(n)
        ymax = self.read_signed_bits(n)
        self.align()
        return (xmin, xmax, ymin, ymax)

    def read_gradient(self, version, has_alpha):
        """Read GRADIENT structure."""
        matrix = self.read_matrix()
        self.align()
        spread = self.read_bits(2)
        interp = self.read_bits(2)
        count = self.read_bits(4)
        stops = []
        for _ in range(count):
            ratio = self.read_u8()
            if has_alpha:
                color = self.read_rgba()
            else:
                color = self.read_rgb()
            stops.append((ratio, color))
        return {"matrix": matrix, "spread": spread, "interp": interp, "stops": stops}


def _read_fill_style(bs, version, has_alpha):
    fill_type = bs.read_u8()
    color = None
    gradient = None
    bitmap_id = None
    bitmap_matrix = None

    if fill_type == FILL_SOLID:
        if has_alpha:
            color = bs.read_rgba()
        else:
            color = bs.read_rgb()
    elif fill_type in (FILL_LINEAR_GRADIENT, FILL_RADIAL_GRADIENT, FILL_FOCAL_GRADIENT):
        gradient = bs.read_gradient(version, has_alpha)
        if fill_type == FILL_FOCAL_GRADIENT:
            # focal point: FIXED8
            bs.read_i16()  # skip focal point
    elif fill_type in (FILL_REPEATING_BITMAP, FILL_CLIPPED_BITMAP,
                       FILL_NON_SMOOTHED_REPEATING_BITMAP, FILL_NON_SMOOTHED_CLIPPED_BITMAP):
        bitmap_id = bs.read_u16()
        bitmap_matrix = bs.read_matrix()

    return {
        "type": fill_type,
        "color": color,
        "gradient": gradient,
        "bitmap_id": bitmap_id,
        "bitmap_matrix": bitmap_matrix,
    }


def _read_line_style(bs, version, has_alpha):
    width = bs.read_u16()
    if version >= 4:  # DefineShape4
        bs.read_u16()  # start/end cap, join style bits
        has_fill = bs.read_bits(1)
        bs.read_bits(3)  # no_hscale, no_vscale, pixel_hinting, no_close
        if not has_fill:
            if has_alpha:
                color = bs.read_rgba()
            else:
                color = bs.read_rgb()
            return {"width": width, "color": color, "fill": None}
        else:
            fill = _read_fill_style(bs, version, has_alpha)
            return {"width": width, "color": None, "fill": fill}
    else:
        if has_alpha:
            color = bs.read_rgba()
        else:
            color = bs.read_rgb()
        return {"width": width, "color": color, "fill": None}


def _read_style_arrays(bs, version, has_alpha):
    fill_count = bs.read_u8()
    if fill_count == 0xFF and version >= 2:
        fill_count = bs.read_u16()
    fills = [_read_fill_style(bs, version, has_alpha) for _ in range(fill_count)]

    line_count = bs.read_u8()
    if line_count == 0xFF and version >= 2:
        line_count = bs.read_u16()
    lines = [_read_line_style(bs, version, has_alpha) for _ in range(line_count)]

    return fills, lines


def parse_shape(data, tag_type):
    """
    Parse a DefineShape* tag body.
    Returns a dict with shape bounds, fill/line styles, and path records.
    """
    version = {
        TAG_DEFINE_SHAPE: 1,
        TAG_DEFINE_SHAPE2: 2,
        TAG_DEFINE_SHAPE3: 3,
        TAG_DEFINE_SHAPE4: 4,
    }.get(tag_type, 1)

    has_alpha = (version >= 3)

    bs = BitStream(data)
    char_id = bs.read_u16()
    bounds = bs.read_rect()

    if version == 4:
        edge_bounds = bs.read_rect()
        _flags = bs.read_u8()  # uses fill winding, uses nonscaling strokes, etc.

    fills, lines = _read_style_arrays(bs, version, has_alpha)

    # Now read shape records
    n_fill_bits = bs.read_bits(4)
    n_line_bits = bs.read_bits(4)

    records = []
    cur_fill0 = 0
    cur_fill1 = 0
    cur_line = 0
    cur_x = 0
    cur_y = 0

    while True:
        type_flag = bs.read_bits(1)
        if type_flag == 0:
            # Non-edge record
            flags = bs.read_bits(5)
            if flags == 0:
                # End of shape
                break
            state_new_styles = (flags >> 4) & 1
            state_line = (flags >> 3) & 1
            state_fill1 = (flags >> 2) & 1
            state_fill0 = (flags >> 1) & 1
            state_move = flags & 1

            if state_move:
                move_bits = bs.read_bits(5)
                move_dx = bs.read_signed_bits(move_bits)
                move_dy = bs.read_signed_bits(move_bits)
                cur_x = move_dx
                cur_y = move_dy
                records.append({"type": "move", "x": cur_x, "y": cur_y})

            if state_fill0 and n_fill_bits > 0:
                cur_fill0 = bs.read_bits(n_fill_bits)
            if state_fill1 and n_fill_bits > 0:
                cur_fill1 = bs.read_bits(n_fill_bits)
            if state_line and n_line_bits > 0:
                cur_line = bs.read_bits(n_line_bits)

            if state_new_styles and version >= 2:
                new_fills, new_lines = _read_style_arrays(bs, version, has_alpha)
                fills = fills + new_fills
                lines = lines + new_lines
                n_fill_bits = bs.read_bits(4)
                n_line_bits = bs.read_bits(4)

            records.append({
                "type": "style",
                "fill0": cur_fill0,
                "fill1": cur_fill1,
                "line": cur_line,
            })
        else:
            # Edge record
            is_straight = bs.read_bits(1)
            if is_straight:
                num_bits = bs.read_bits(4) + 2
                is_general = bs.read_bits(1)
                if is_general:
                    dx = bs.read_signed_bits(num_bits)
                    dy = bs.read_signed_bits(num_bits)
                else:
                    is_vert = bs.read_bits(1)
                    if is_vert:
                        dx = 0
                        dy = bs.read_signed_bits(num_bits)
                    else:
                        dx = bs.read_signed_bits(num_bits)
                        dy = 0
                cur_x += dx
                cur_y += dy
                records.append({"type": "line", "x": cur_x, "y": cur_y})
            else:
                # Curved (quadratic Bezier)
                num_bits = bs.read_bits(4) + 2
                cdx = bs.read_signed_bits(num_bits)
                cdy = bs.read_signed_bits(num_bits)
                adx = bs.read_signed_bits(num_bits)
                ady = bs.read_signed_bits(num_bits)
                cx = cur_x + cdx
                cy = cur_y + cdy
                cur_x = cx + adx
                cur_y = cy + ady
                records.append({"type": "curve", "cx": cx, "cy": cy, "x": cur_x, "y": cur_y})

    return {
        "char_id": char_id,
        "bounds": bounds,
        "fills": fills,
        "lines": lines,
        "records": records,
        "version": version,
    }


def _color_to_skia(color):
    """Convert (r, g, b, a) tuple to skia color."""
    r, g, b, a = color
    return skia.Color(r, g, b, a)


def render_shape_to_png(shape_data, out_path, scale=2.0, padding=4):
    """
    Render a parsed shape dict to a PNG file using skia.
    scale: pixels per twip (normally 1/20, but upscaled for visibility)
    """
    if not _HAS_SKIA:
        raise RuntimeError("skia-python not available")

    xmin, xmax, ymin, ymax = shape_data["bounds"]
    fills = shape_data["fills"]
    lines = shape_data["lines"]
    records = shape_data["records"]

    # Canvas dimensions in pixels
    width_twips = max(1, xmax - xmin)
    height_twips = max(1, ymax - ymin)

    px_w = int(width_twips * scale / TWIPS_PER_PIXEL) + 2 * padding
    px_h = int(height_twips * scale / TWIPS_PER_PIXEL) + 2 * padding

    if px_w <= 0 or px_h <= 0:
        return False

    px_w = max(1, min(px_w, 4096))
    px_h = max(1, min(px_h, 4096))

    surface = skia.Surface(px_w, px_h)

    # Transform: twips -> pixels
    # offset by -xmin, -ymin, then scale by scale/TWIPS_PER_PIXEL, then add padding
    pix_scale = scale / TWIPS_PER_PIXEL
    tx = -xmin * pix_scale + padding
    ty = -ymin * pix_scale + padding

    with surface as canvas:
        canvas.clear(skia.ColorTRANSPARENT)

        # Build path segments grouped by fill/line style
        cur_fill1 = 0
        cur_line = 0
        cur_x = 0.0
        cur_y = 0.0
        path_started = False
        current_path = None

        def px(twip_x):
            return twip_x * pix_scale + tx

        def py(twip_y):
            return twip_y * pix_scale + ty

        # We'll collect subpaths and render them
        # Group records by fill/line style
        paths_by_fill = {}  # fill_index -> skia.Path
        paths_by_line = {}  # line_index -> skia.Path

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
                # When style changes and we already have a position, start subpaths
                # at the current position for the newly active styles.
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

                # Start new subpaths for active styles
                if cur_fill0_idx > 0:
                    if cur_fill0_idx not in paths_by_fill:
                        paths_by_fill[cur_fill0_idx] = skia.Path()
                    paths_by_fill[cur_fill0_idx].moveTo(px(path_x), py(path_y))

                if cur_fill1_idx > 0:
                    if cur_fill1_idx not in paths_by_fill:
                        paths_by_fill[cur_fill1_idx] = skia.Path()
                    paths_by_fill[cur_fill1_idx].moveTo(px(path_x), py(path_y))

                if cur_line_idx > 0:
                    if cur_line_idx not in paths_by_line:
                        paths_by_line[cur_line_idx] = skia.Path()
                    paths_by_line[cur_line_idx].moveTo(px(path_x), py(path_y))

                subpath_started = True

            elif rec["type"] == "line" and subpath_started:
                ex, ey = rec["x"], rec["y"]

                if cur_fill1_idx > 0:
                    if cur_fill1_idx not in paths_by_fill:
                        paths_by_fill[cur_fill1_idx] = skia.Path()
                        paths_by_fill[cur_fill1_idx].moveTo(px(path_x), py(path_y))
                    paths_by_fill[cur_fill1_idx].lineTo(px(ex), py(ey))

                if cur_fill0_idx > 0:
                    if cur_fill0_idx not in paths_by_fill:
                        paths_by_fill[cur_fill0_idx] = skia.Path()
                        paths_by_fill[cur_fill0_idx].moveTo(px(path_x), py(path_y))
                    # Reverse for fill0
                    paths_by_fill[cur_fill0_idx].lineTo(px(ex), py(ey))

                if cur_line_idx > 0:
                    if cur_line_idx not in paths_by_line:
                        paths_by_line[cur_line_idx] = skia.Path()
                        paths_by_line[cur_line_idx].moveTo(px(path_x), py(path_y))
                    paths_by_line[cur_line_idx].lineTo(px(ex), py(ey))

                path_x, path_y = ex, ey

            elif rec["type"] == "curve" and subpath_started:
                cx, cy, ex, ey = rec["cx"], rec["cy"], rec["x"], rec["y"]

                if cur_fill1_idx > 0:
                    if cur_fill1_idx not in paths_by_fill:
                        paths_by_fill[cur_fill1_idx] = skia.Path()
                        paths_by_fill[cur_fill1_idx].moveTo(px(path_x), py(path_y))
                    paths_by_fill[cur_fill1_idx].quadTo(px(cx), py(cy), px(ex), py(ey))

                if cur_fill0_idx > 0:
                    if cur_fill0_idx not in paths_by_fill:
                        paths_by_fill[cur_fill0_idx] = skia.Path()
                        paths_by_fill[cur_fill0_idx].moveTo(px(path_x), py(path_y))
                    paths_by_fill[cur_fill0_idx].quadTo(px(cx), py(cy), px(ex), py(ey))

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
            elif fill_style["gradient"]:
                grad = fill_style["gradient"]
                if grad["stops"]:
                    mat = grad["matrix"]
                    # Simple: use first and last stop colors
                    colors = [skia.Color(*stop[1]) for stop in grad["stops"]]
                    positions = [stop[0] / 255.0 for stop in grad["stops"]]
                    # Linear gradient
                    shader = skia.GradientShader.MakeLinear(
                        points=[skia.Point(-819.2 * pix_scale + tx, 0),
                                skia.Point(819.2 * pix_scale + tx, 0)],
                        colors=colors,
                        positions=positions,
                    )
                    paint.setShader(shader)
            else:
                paint.setColor(skia.Color(128, 128, 128, 200))

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

    img = surface.makeImageSnapshot()
    data = img.encodeToData()
    with open(out_path, "wb") as f:
        f.write(bytes(data))
    return True
