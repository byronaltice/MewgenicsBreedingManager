"""
Extract the 18/19 cat symbol icons from ui.swf (FontIcon_* sprites).
Stages them in symbol-final/ named by name_tag.

All 18 target icons found in ui.swf as FontIcon_<name_tag> sprites:

Stat icons:
  FontIcon_str   (2704), FontIcon_spd   (2707), FontIcon_int   (2710)
  FontIcon_dex   (2713), FontIcon_con   (2716), FontIcon_cha   (2719)
  FontIcon_lck   (3897)

Room-stat icons:
  FontIcon_stimulation (2685), FontIcon_comfort (2687), FontIcon_appeal (2689)
  FontIcon_health (2665), FontIcon_evolution (2663)

Shape/object icons:
  FontIcon_star2  (2659), FontIcon_circle   (2681), FontIcon_triangle (2677)
  FontIcon_sword  (2673), FontIcon_shield2  (2661), FontIcon_poop     (2671)
"""

import os
import sys
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from extract_sprites import (
    parse_all_tags, collect_shapes_in_sprite, get_combined_bounds,
    render_sprite_to_png, _render_parsed_shape_to_canvas
)
from swf_shape_renderer import parse_shape, TWIPS_PER_PIXEL

import skia
from PIL import Image

DEFECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
SWF_DIR = os.path.join(DEFECT_DIR, "game-files", "resources", "gpak-video", "swfs")
CANDIDATES_DIR = os.path.join(DEFECT_DIR, "audit", "direction", "symbol-candidates", "ui")
FINAL_DIR = os.path.join(DEFECT_DIR, "audit", "direction", "symbol-final")

# Mapping: name_tag -> FontIcon symbol name suffix (in ui.swf)
NAME_TAG_MAP = {
    "str": "FontIcon_str",
    "dex": "FontIcon_dex",
    "con": "FontIcon_con",
    "int": "FontIcon_int",
    "spd": "FontIcon_spd",
    "cha": "FontIcon_cha",
    "lck": "FontIcon_lck",
    "stimulation": "FontIcon_stimulation",
    "comfort": "FontIcon_comfort",
    "appeal": "FontIcon_appeal",
    "health": "FontIcon_health",
    "evolution": "FontIcon_evolution",
    "star2": "FontIcon_star2",
    "circle": "FontIcon_circle",
    "triangle": "FontIcon_triangle",
    "sword": "FontIcon_sword",
    "shield2": "FontIcon_shield2",
    "poop": "FontIcon_poop",
}

# Target render size for icons (pixels)
ICON_RENDER_SCALE = 10.0  # pixels per pixel of twip * 20
ICON_PADDING = 8


def render_sprite_cropped(sprite_id, swf_data, out_path, scale=10.0, padding=8):
    """
    Render a sprite and crop to its visible bounding box.
    Returns (width, height) or None on failure.
    """
    shapes = swf_data["shapes"]
    sprites = swf_data["sprites"]

    shape_ids = collect_shapes_in_sprite(sprite_id, sprites, shapes)
    if not shape_ids:
        return None

    bounds = get_combined_bounds(shape_ids, shapes)
    if not bounds:
        return None

    xmin, xmax, ymin, ymax = bounds
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
            if cid not in shapes:
                continue
            tag_type, tag_data = shapes[cid]
            try:
                parsed = parse_shape(tag_data, tag_type)
                _render_parsed_shape_to_canvas(canvas, parsed, pix_scale, tx, ty)
            except Exception:
                pass

    img_data = surface.makeImageSnapshot()
    raw_bytes = bytes(img_data.encodeToData())

    # Load with PIL to crop
    from io import BytesIO
    pil_img = Image.open(BytesIO(raw_bytes))
    bbox = pil_img.getbbox()
    if bbox:
        pil_img = pil_img.crop(bbox)

    pil_img.save(out_path, "PNG")
    return pil_img.size


def main():
    os.makedirs(CANDIDATES_DIR, exist_ok=True)
    os.makedirs(FINAL_DIR, exist_ok=True)

    swf_path = os.path.join(SWF_DIR, "ui.swf")
    print(f"Parsing ui.swf...")
    swf_data = parse_all_tags(swf_path)
    names = swf_data["names"]

    # Build reverse name -> char_id map
    name_to_id = {v: k for k, v in names.items()}

    found = []
    not_found = []

    for name_tag, symbol_name in sorted(NAME_TAG_MAP.items()):
        char_id = name_to_id.get(symbol_name)
        if char_id is None:
            print(f"  [MISSING] {name_tag} -> {symbol_name} NOT FOUND in ui.swf")
            not_found.append(name_tag)
            continue

        # Render to candidates dir
        candidates_filename = f"{char_id:04d}_{symbol_name}.png"
        candidates_path = os.path.join(CANDIDATES_DIR, candidates_filename)

        result = render_sprite_cropped(char_id, swf_data, candidates_path,
                                       scale=ICON_RENDER_SCALE, padding=ICON_PADDING)
        if result is None:
            print(f"  [FAIL] {name_tag} -> {symbol_name} (ID={char_id}): rendering failed")
            not_found.append(name_tag)
            continue

        w, h = result
        print(f"  [OK] {name_tag:15s} -> {symbol_name} (ID={char_id}) [{w}x{h}px]")

        # Copy to final dir
        final_path = os.path.join(FINAL_DIR, f"{name_tag}.png")
        shutil.copy2(candidates_path, final_path)

        found.append({
            "name_tag": name_tag,
            "symbol": symbol_name,
            "char_id": char_id,
            "swf": "ui.swf",
            "width": w,
            "height": h,
            "candidates_path": candidates_path,
            "final_path": final_path,
        })

    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(found)}/18 icons extracted")
    if not_found:
        print(f"NOT FOUND: {not_found}")
    print(f"Staged in: {FINAL_DIR}")

    return found, not_found


if __name__ == "__main__":
    main()
