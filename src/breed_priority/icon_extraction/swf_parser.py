"""
Lightweight pure-Python SWF parser for extracting embedded bitmaps.

Supports:
  - CWS (zlib-compressed) and FWS (uncompressed) SWF files
  - DefineBitsLossless (tag 20) — zlib-compressed 8-bit paletted or 24-bit RGB
  - DefineBitsLossless2 (tag 36) — zlib-compressed 8-bit RGBA or 32-bit ARGB
  - DefineBitsJPEG2 (tag 21), DefineBitsJPEG3 (tag 35), DefineBitsJPEG4 (tag 90)
  - SymbolClass (tag 76) and ExportAssets (tag 56) — name->id mapping
"""

import struct
import zlib
import io
import os

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


# SWF tag type constants
TAG_DEFINE_BITS_LOSSLESS = 20
TAG_DEFINE_BITS_JPEG2 = 21
TAG_DEFINE_BITS_LOSSLESS2 = 36
TAG_DEFINE_BITS_JPEG3 = 35
TAG_DEFINE_BITS_JPEG4 = 90
TAG_EXPORT_ASSETS = 56
TAG_SYMBOL_CLASS = 76
TAG_PLACE_OBJECT2 = 26
TAG_PLACE_OBJECT3 = 70
TAG_END = 0

# DefineBitsLossless format codes
BMP_FMT_8BIT_COLORMAPPED = 3
BMP_FMT_15BIT_RGB = 4
BMP_FMT_24BIT_RGB = 5


def _read_rect(data, offset):
    """Parse SWF RECT structure, return (xmin, xmax, ymin, ymax, bytes_consumed)."""
    nbits = (data[offset] >> 3) & 0x1F
    total_bits = 5 + 4 * nbits
    total_bytes = (total_bits + 7) // 8
    return total_bytes


def _read_swf_tags(data):
    """
    Parse a flat SWF body (after the header) and yield (tag_type, tag_data) tuples.
    """
    pos = 0
    length = len(data)

    while pos < length - 1:
        if pos + 2 > length:
            break
        record_header = struct.unpack_from("<H", data, pos)[0]
        pos += 2

        tag_type = record_header >> 6
        tag_len = record_header & 0x3F

        if tag_len == 0x3F:
            if pos + 4 > length:
                break
            tag_len = struct.unpack_from("<i", data, pos)[0]
            pos += 4

        tag_data = data[pos: pos + tag_len]
        pos += tag_len

        yield tag_type, tag_data

        if tag_type == TAG_END:
            break


def _parse_header(raw):
    """
    Read SWF header, decompress if needed.
    Returns (body_bytes, version) where body_bytes starts right after the file-length field.
    """
    sig = raw[:3]
    if sig == b"CWS":
        # zlib compressed after byte 8
        version = raw[3]
        body = zlib.decompress(raw[8:])
        return body, version
    elif sig == b"FWS":
        version = raw[3]
        return raw[8:], version
    elif sig == b"ZWS":
        # LZMA compressed - need to handle differently
        raise ValueError("LZMA-compressed SWF (ZWS) not supported in this parser")
    else:
        raise ValueError(f"Not a valid SWF file (signature: {sig!r})")


def _skip_rect(body):
    """Skip the RECT structure at the start of SWF body, return remaining bytes."""
    nbits = (body[0] >> 3) & 0x1F
    total_bits = 5 + 4 * nbits
    total_bytes = (total_bits + 7) // 8
    return body[total_bytes:]


def parse_swf(path):
    """
    Parse a SWF file and return a dict with:
      'version': int
      'bitmaps': {char_id: {'format': str, 'data': bytes}}
      'names': {char_id: name_str}   (from SymbolClass / ExportAssets)
    """
    with open(path, "rb") as f:
        raw = f.read()

    body, version = _parse_header(raw)

    # Skip RECT (frame size), then frame rate (2 bytes), frame count (2 bytes)
    rect_bytes = _skip_rect(body)
    after_header = rect_bytes[4:]  # skip frame rate + frame count

    bitmaps = {}
    names = {}  # char_id -> symbol name

    for tag_type, tag_data in _read_swf_tags(after_header):
        if tag_type in (TAG_DEFINE_BITS_LOSSLESS, TAG_DEFINE_BITS_LOSSLESS2):
            _parse_bits_lossless(tag_type, tag_data, bitmaps)

        elif tag_type in (TAG_DEFINE_BITS_JPEG2, TAG_DEFINE_BITS_JPEG3, TAG_DEFINE_BITS_JPEG4):
            _parse_bits_jpeg(tag_type, tag_data, bitmaps)

        elif tag_type == TAG_EXPORT_ASSETS:
            _parse_export_assets(tag_data, names)

        elif tag_type == TAG_SYMBOL_CLASS:
            _parse_symbol_class(tag_data, names)

    return {
        "version": version,
        "bitmaps": bitmaps,
        "names": names,
    }


def _parse_bits_lossless(tag_type, data, bitmaps):
    """Parse DefineBitsLossless (20) and DefineBitsLossless2 (36)."""
    if len(data) < 7:
        return
    char_id = struct.unpack_from("<H", data, 0)[0]
    fmt = data[2]
    width = struct.unpack_from("<H", data, 3)[0]
    height = struct.unpack_from("<H", data, 5)[0]

    has_alpha = (tag_type == TAG_DEFINE_BITS_LOSSLESS2)
    pixel_fmt = "RGBA" if has_alpha else "RGB"

    offset = 7
    color_table_size = 0
    if fmt == BMP_FMT_8BIT_COLORMAPPED:
        color_table_size = data[7] + 1
        offset = 8

    compressed = data[offset:]
    try:
        raw_pixels = zlib.decompress(compressed)
    except zlib.error:
        return

    bitmaps[char_id] = {
        "format": "lossless2" if has_alpha else "lossless",
        "raw": raw_pixels,
        "width": width,
        "height": height,
        "bmp_fmt": fmt,
        "color_table_size": color_table_size,
        "has_alpha": has_alpha,
        "tag_type": tag_type,
    }


def _parse_bits_jpeg(tag_type, data, bitmaps):
    """Parse DefineBitsJPEG2/3/4 tags."""
    if len(data) < 2:
        return
    char_id = struct.unpack_from("<H", data, 0)[0]

    if tag_type == TAG_DEFINE_BITS_JPEG2:
        jpeg_data = data[2:]
    elif tag_type in (TAG_DEFINE_BITS_JPEG3, TAG_DEFINE_BITS_JPEG4):
        if len(data) < 6:
            return
        alpha_offset = struct.unpack_from("<I", data, 2)[0]
        jpeg_data = data[6: 6 + alpha_offset]
    else:
        jpeg_data = data[2:]

    # Strip SWF JPEG table prefix if present (erroneous JFIF markers)
    if jpeg_data[:4] == b"\xff\xd9\xff\xd8":
        jpeg_data = jpeg_data[4:]

    bitmaps[char_id] = {
        "format": "jpeg",
        "jpeg_data": jpeg_data,
        "tag_type": tag_type,
    }


def _parse_export_assets(data, names):
    """Parse ExportAssets tag (56)."""
    if len(data) < 2:
        return
    count = struct.unpack_from("<H", data, 0)[0]
    pos = 2
    for _ in range(count):
        if pos + 2 > len(data):
            break
        char_id = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        end = data.index(b"\x00", pos)
        name = data[pos:end].decode("utf-8", errors="replace")
        names[char_id] = name
        pos = end + 1


def _parse_symbol_class(data, names):
    """Parse SymbolClass tag (76)."""
    if len(data) < 2:
        return
    count = struct.unpack_from("<H", data, 0)[0]
    pos = 2
    for _ in range(count):
        if pos + 2 > len(data):
            break
        char_id = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        end = data.index(b"\x00", pos)
        name = data[pos:end].decode("utf-8", errors="replace")
        names[char_id] = name
        pos = end + 1


def _bitmap_to_pil(info):
    """Convert a parsed bitmap dict to a PIL Image."""
    if not _HAS_PIL:
        raise RuntimeError("Pillow not installed")

    fmt = info["format"]

    if fmt == "jpeg":
        try:
            return Image.open(io.BytesIO(info["jpeg_data"]))
        except Exception as e:
            raise RuntimeError(f"JPEG decode error: {e}")

    # Lossless
    raw = info["raw"]
    width = info["width"]
    height = info["height"]
    bmp_fmt = info["bmp_fmt"]
    has_alpha = info["has_alpha"]

    if bmp_fmt == BMP_FMT_8BIT_COLORMAPPED:
        ct_size = info["color_table_size"]
        # Color table: each entry is 3 bytes (RGB) for lossless, 4 bytes (RGBA) for lossless2
        entry_size = 4 if has_alpha else 3
        ct_bytes = raw[: ct_size * entry_size]
        pixel_data = raw[ct_size * entry_size:]

        # Build palette
        if has_alpha:
            palette_rgba = list(ct_bytes)
            img = Image.new("RGBA", (width, height))
            pixels = []
            # Row-padded to 4-byte boundary
            row_bytes = (width + 3) & ~3
            for row in range(height):
                row_start = row * row_bytes
                for col in range(width):
                    idx = pixel_data[row_start + col]
                    base = idx * 4
                    r, g, b, a = palette_rgba[base], palette_rgba[base+1], palette_rgba[base+2], palette_rgba[base+3]
                    pixels.append((r, g, b, a))
            img.putdata(pixels)
            return img
        else:
            palette_rgb = list(ct_bytes)
            img = Image.new("RGB", (width, height))
            pixels = []
            row_bytes = (width + 3) & ~3
            for row in range(height):
                row_start = row * row_bytes
                for col in range(width):
                    idx = pixel_data[row_start + col]
                    base = idx * 3
                    r, g, b = palette_rgb[base], palette_rgb[base+1], palette_rgb[base+2]
                    pixels.append((r, g, b))
            img.putdata(pixels)
            return img

    elif bmp_fmt == BMP_FMT_24BIT_RGB:
        # SWF stores 24-bit as 32-bit (4 bytes per pixel, first byte unused/0)
        if has_alpha:
            # ARGB order
            img = Image.frombytes("RGBA", (width, height), raw, "raw", "ARGB")
        else:
            # 0RGB order - 4 bytes, first is padding
            arr = bytearray(width * height * 3)
            for i in range(width * height):
                src = i * 4
                arr[i*3] = raw[src+1]    # R
                arr[i*3+1] = raw[src+2]  # G
                arr[i*3+2] = raw[src+3]  # B
            img = Image.frombytes("RGB", (width, height), bytes(arr))
        return img

    elif bmp_fmt == BMP_FMT_15BIT_RGB:
        # 15-bit RGB555 - 2 bytes per pixel, row-padded to 4 bytes
        row_bytes = ((width * 2) + 3) & ~3
        pixels = []
        for row in range(height):
            row_start = row * row_bytes
            for col in range(width):
                pos = row_start + col * 2
                val = struct.unpack_from("<H", raw, pos)[0]
                r = ((val >> 10) & 0x1F) << 3
                g = ((val >> 5) & 0x1F) << 3
                b = (val & 0x1F) << 3
                pixels.append((r, g, b))
        img = Image.new("RGB", (width, height))
        img.putdata(pixels)
        return img

    raise RuntimeError(f"Unsupported bitmap format: {bmp_fmt}")


def extract_all_bitmaps(swf_path, output_dir):
    """
    Extract all bitmaps from a SWF file to output_dir.
    Returns list of (char_id, name, path, width, height) tuples.
    """
    os.makedirs(output_dir, exist_ok=True)
    result = parse_swf(swf_path)
    bitmaps = result["bitmaps"]
    names = result["names"]

    extracted = []
    for char_id, info in sorted(bitmaps.items()):
        name = names.get(char_id, "")
        safe_name = name.replace("/", "_").replace("\\", "_").replace(":", "_")
        filename = f"{char_id:04d}_{safe_name}.png" if safe_name else f"{char_id:04d}.png"
        out_path = os.path.join(output_dir, filename)

        try:
            img = _bitmap_to_pil(info)
            img.save(out_path, "PNG")
            w, h = img.size
            extracted.append((char_id, name, out_path, w, h))
        except Exception as e:
            print(f"  Warning: Could not convert char_id={char_id} name={name!r}: {e}")

    return extracted


def list_all_symbols(swf_path):
    """List all named symbols and bitmaps without extracting."""
    result = parse_swf(swf_path)
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python swf_parser.py <swf_file>")
        sys.exit(1)

    path = sys.argv[1]
    result = list_all_symbols(path)
    print(f"Version: {result['version']}")
    print(f"Bitmaps: {len(result['bitmaps'])}")
    print(f"Named symbols: {len(result['names'])}")
    print("\nNamed symbols:")
    for cid, name in sorted(result["names"].items()):
        bmp_info = result["bitmaps"].get(cid)
        bmp_str = ""
        if bmp_info:
            bmp_str = f" [{bmp_info['width']}x{bmp_info['height']}]"
        print(f"  {cid:4d} -> {name}{bmp_str}")

    unnamed_bitmaps = [cid for cid in result["bitmaps"] if cid not in result["names"]]
    if unnamed_bitmaps:
        print(f"\nUnnamed bitmaps ({len(unnamed_bitmaps)}): {unnamed_bitmaps[:20]}{'...' if len(unnamed_bitmaps) > 20 else ''}")
