"""Extract ability icons (and badge / shell sprites) from a Mewgenics install.

Given an install path, walks the AbilityIcon and PassiveIcon MovieClip
timelines inside ``ability_icons.swf``, renders each labeled frame's shapes
to a cropped PNG, and writes the results under
``<icons_dir>/abilities/<frameLabel>.png``.

Also dumps any ``type_icon`` badges and ``icon_shell_frame`` shells we can
discover in ``ui.swf`` (best-effort — symbols not present are silently
skipped; missing icons are logged to ``extraction.log``).
"""

from __future__ import annotations

import os
import struct
from io import BytesIO
from typing import Callable, Iterable, Optional

import skia
from PIL import Image

from .swf_shape_renderer import parse_shape, TWIPS_PER_PIXEL
from .swf_sprite_walker import (
    parse_all_tags, collect_shapes_in_sprite, get_combined_bounds,
    render_parsed_shape_to_canvas,
    TAG_FRAME_LABEL, TAG_PLACE_OBJECT2, TAG_PLACE_OBJECT3,
    TAG_REMOVE_OBJECT2, TAG_SHOW_FRAME,
)

# ── Paths within a Mewgenics install ──────────────────────────────────────────

_SWF_RELDIR = os.path.join("resources", "gpak-video", "swfs")
_ABILITY_ICONS_SWF = "ability_icons.swf"
_UI_SWF = "ui.swf"

# ── Output directory layout ───────────────────────────────────────────────────

_ABILITIES_SUBDIR = "abilities"
_BADGES_SUBDIR = "badges"
_SHELLS_SUBDIR = "shells"
_LOG_FILENAME = "extraction.log"

# ── Render parameters ─────────────────────────────────────────────────────────

_RENDER_SCALE = 4.0           # pixels per twip * 20 → final PNG resolution factor
_RENDER_PADDING = 4           # px padding around bounding box
_MAX_CANVAS_DIM = 4096

# ── Sprite timeline tag flag bits ─────────────────────────────────────────────

_PLACE2_FLAG_HAS_CHARACTER = 1 << 1
_PLACE_OBJECT2_DEPTH_OFFSET = 1
_PLACE_OBJECT2_CHARID_OFFSET = 3
_PLACE_OBJECT3_DEPTH_OFFSET = 2
_PLACE_OBJECT3_CHARID_OFFSET = 4
_PLACE_OBJECT2_MIN_LEN = 3
_PLACE_OBJECT2_WITH_CHARID_LEN = 5
_PLACE_OBJECT3_MIN_LEN = 4
_PLACE_OBJECT3_WITH_CHARID_LEN = 6
_REMOVE_OBJECT2_LEN = 2

# Top-level MovieClip names inside ability_icons.swf.
_ABILITY_TIMELINE_SYMBOLS = ("AbilityIcon", "PassiveIcon")


def install_swfs_dir(install_path: str) -> str:
    return os.path.join(install_path, _SWF_RELDIR)


def validate_install_path(install_path: str) -> tuple[bool, str]:
    """Return (ok, reason). Checks resources.gpak + ability_icons.swf exist."""
    if not install_path or not os.path.isdir(install_path):
        return False, "Path is not a directory."
    if not os.path.isfile(os.path.join(install_path, "resources.gpak")):
        return False, "resources.gpak not found in selected folder."
    swf_path = os.path.join(install_swfs_dir(install_path), _ABILITY_ICONS_SWF)
    if not os.path.isfile(swf_path):
        return False, f"{_ABILITY_ICONS_SWF} not found under resources/gpak-video/swfs."
    return True, ""


# ── Timeline walk ─────────────────────────────────────────────────────────────

def _decode_frame_label(tag_data: bytes) -> str:
    end = tag_data.find(b"\x00")
    raw = tag_data[: end if end >= 0 else len(tag_data)]
    return raw.decode("utf-8", errors="replace")


def _walk_timeline_labels(inner_tags) -> Iterable[tuple[str, list[int]]]:
    """Yield (frame_label, [shape_or_sprite_ids]) for every labeled frame.

    Maintains a depth->char_id placement map across ``PlaceObject2``/
    ``PlaceObject3`` and ``RemoveObject2``, emitting the current placements
    at each ``ShowFrame`` that has a label.
    """
    placed: dict[int, int] = {}
    current_label: Optional[str] = None
    for tag_type, tag_data in inner_tags:
        if tag_type == TAG_FRAME_LABEL:
            current_label = _decode_frame_label(tag_data)
        elif tag_type == TAG_PLACE_OBJECT2:
            if len(tag_data) < _PLACE_OBJECT2_MIN_LEN:
                continue
            flags = tag_data[0]
            depth = struct.unpack_from("<H", tag_data, _PLACE_OBJECT2_DEPTH_OFFSET)[0]
            if (flags & _PLACE2_FLAG_HAS_CHARACTER) and len(tag_data) >= _PLACE_OBJECT2_WITH_CHARID_LEN:
                char_id = struct.unpack_from("<H", tag_data, _PLACE_OBJECT2_CHARID_OFFSET)[0]
                placed[depth] = char_id
        elif tag_type == TAG_PLACE_OBJECT3:
            if len(tag_data) < _PLACE_OBJECT3_MIN_LEN:
                continue
            flags1 = tag_data[0]
            depth = struct.unpack_from("<H", tag_data, _PLACE_OBJECT3_DEPTH_OFFSET)[0]
            if (flags1 & _PLACE2_FLAG_HAS_CHARACTER) and len(tag_data) >= _PLACE_OBJECT3_WITH_CHARID_LEN:
                char_id = struct.unpack_from("<H", tag_data, _PLACE_OBJECT3_CHARID_OFFSET)[0]
                placed[depth] = char_id
        elif tag_type == TAG_REMOVE_OBJECT2:
            if len(tag_data) < _REMOVE_OBJECT2_LEN:
                continue
            depth = struct.unpack_from("<H", tag_data, 0)[0]
            placed.pop(depth, None)
        elif tag_type == TAG_SHOW_FRAME:
            if current_label is not None:
                yield current_label, list(placed.values())
            current_label = None


# ── Rendering ────────────────────────────────────────────────────────────────

def _render_shapes_to_png(shape_ids: list[int], shapes: dict, out_path: str) -> Optional[tuple[int, int]]:
    """Render the union of the given shape ids to ``out_path``, cropping to
    the visible bounding box. Returns (width, height) or None on failure.
    """
    bounds = get_combined_bounds(shape_ids, shapes)
    if not bounds:
        return None
    xmin, xmax, ymin, ymax = bounds
    pix_scale = _RENDER_SCALE / TWIPS_PER_PIXEL
    width_twips = max(1, xmax - xmin)
    height_twips = max(1, ymax - ymin)
    px_w = max(1, int(width_twips * pix_scale) + 2 * _RENDER_PADDING)
    px_h = max(1, int(height_twips * pix_scale) + 2 * _RENDER_PADDING)
    px_w = min(px_w, _MAX_CANVAS_DIM)
    px_h = min(px_h, _MAX_CANVAS_DIM)

    tx = -xmin * pix_scale + _RENDER_PADDING
    ty = -ymin * pix_scale + _RENDER_PADDING

    surface = skia.Surface(px_w, px_h)
    with surface as canvas:
        canvas.clear(skia.ColorTRANSPARENT)
        for cid in shape_ids:
            if cid not in shapes:
                continue
            tag_type, tag_data = shapes[cid]
            try:
                parsed = parse_shape(tag_data, tag_type)
                render_parsed_shape_to_canvas(canvas, parsed, pix_scale, tx, ty)
            except Exception:
                # Best-effort: skip shapes that fail to parse.
                continue

    img_data = surface.makeImageSnapshot().encodeToData()
    pil_img = Image.open(BytesIO(bytes(img_data)))
    bbox = pil_img.getbbox()
    if bbox:
        pil_img = pil_img.crop(bbox)
    pil_img.save(out_path, "PNG")
    return pil_img.size


def _resolve_shape_ids(placed_ids: list[int], sprites: dict, shapes: dict) -> list[int]:
    """Expand sprite children into their constituent shape ids."""
    out: list[int] = []
    for cid in placed_ids:
        if cid in shapes:
            out.append(cid)
        elif cid in sprites:
            out.extend(collect_shapes_in_sprite(cid, sprites, shapes))
    return out


# ── Public entry point ───────────────────────────────────────────────────────

def extract_ability_icons(
    install_path: str,
    icons_dir: str,
    progress_cb: Optional[Callable[[int, int, str], bool]] = None,
) -> dict:
    """Render every labeled frame of AbilityIcon/PassiveIcon to PNGs.

    Args:
        install_path: Mewgenics install root (folder containing resources.gpak).
        icons_dir: Output directory (``<assets>/icons``).
        progress_cb: Optional ``(done, total, label) -> bool``. Return False
            to cancel.

    Returns a summary dict with counts and the list of missing labels.
    """
    ok, reason = validate_install_path(install_path)
    if not ok:
        raise FileNotFoundError(reason)

    abilities_swf = os.path.join(install_swfs_dir(install_path), _ABILITY_ICONS_SWF)
    out_dir = os.path.join(icons_dir, _ABILITIES_SUBDIR)
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(icons_dir, _LOG_FILENAME)

    swf_data = parse_all_tags(abilities_swf)
    names = swf_data["names"]
    sprites = swf_data["sprites"]
    shapes = swf_data["shapes"]

    name_to_id = {name: char_id for char_id, name in names.items()}

    # Pre-count total labeled frames for progress reporting.
    timeline_inner: list[tuple[str, list[tuple[int, bytes]]]] = []
    for sym_name in _ABILITY_TIMELINE_SYMBOLS:
        sym_id = name_to_id.get(sym_name)
        if sym_id is None:
            continue
        inner = sprites.get(sym_id)
        if inner is None:
            continue
        timeline_inner.append((sym_name, inner))

    total = sum(
        1
        for _sym, inner in timeline_inner
        for _label, _ids in _walk_timeline_labels(inner)
    )

    written = 0
    skipped = 0
    failures: list[str] = []
    cancelled = False
    done = 0

    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"# Icon extraction log\n# source: {install_path}\n\n")
        for sym_name, inner in timeline_inner:
            for label, placed_ids in _walk_timeline_labels(inner):
                done += 1
                if progress_cb is not None:
                    if not progress_cb(done, total, label):
                        cancelled = True
                        break
                safe = _sanitize_filename(label)
                out_path = os.path.join(out_dir, f"{safe}.png")
                shape_ids = _resolve_shape_ids(placed_ids, sprites, shapes)
                if not shape_ids:
                    log.write(f"[{sym_name}] {label}: no shapes\n")
                    skipped += 1
                    failures.append(label)
                    continue
                try:
                    result = _render_shapes_to_png(shape_ids, shapes, out_path)
                except Exception as exc:
                    log.write(f"[{sym_name}] {label}: render error {exc!r}\n")
                    failures.append(label)
                    continue
                if result is None:
                    log.write(f"[{sym_name}] {label}: empty bounds\n")
                    skipped += 1
                    failures.append(label)
                    continue
                written += 1
            if cancelled:
                break

        # Best-effort badges / shells from ui.swf.
        ui_swf_path = os.path.join(install_swfs_dir(install_path), _UI_SWF)
        if os.path.isfile(ui_swf_path):
            badges_written, shells_written = _extract_ui_badges_and_shells(
                ui_swf_path, icons_dir, log,
            )
        else:
            badges_written = shells_written = 0
            log.write(f"# {_UI_SWF} not present; badges/shells skipped\n")

    return {
        "written": written,
        "skipped": skipped,
        "total": total,
        "cancelled": cancelled,
        "failures": failures,
        "badges_written": badges_written,
        "shells_written": shells_written,
    }


# ── ui.swf — badges & shells (best effort) ────────────────────────────────────

_BADGE_SYMBOL_PREFIX = "type_icon"
_SHELL_SYMBOL_PREFIX = "icon_shell"


def _extract_ui_badges_and_shells(ui_swf_path: str, icons_dir: str, log) -> tuple[int, int]:
    swf_data = parse_all_tags(ui_swf_path)
    names = swf_data["names"]
    sprites = swf_data["sprites"]
    shapes = swf_data["shapes"]

    badges_dir = os.path.join(icons_dir, _BADGES_SUBDIR)
    shells_dir = os.path.join(icons_dir, _SHELLS_SUBDIR)
    os.makedirs(badges_dir, exist_ok=True)
    os.makedirs(shells_dir, exist_ok=True)

    badges_written = 0
    shells_written = 0

    for char_id, sym_name in names.items():
        target_dir: Optional[str] = None
        if sym_name.startswith(_BADGE_SYMBOL_PREFIX):
            target_dir = badges_dir
        elif sym_name.startswith(_SHELL_SYMBOL_PREFIX):
            target_dir = shells_dir
        if target_dir is None:
            continue

        if char_id in sprites:
            shape_ids = collect_shapes_in_sprite(char_id, sprites, shapes)
        elif char_id in shapes:
            shape_ids = [char_id]
        else:
            continue
        if not shape_ids:
            continue

        out_path = os.path.join(target_dir, f"{_sanitize_filename(sym_name)}.png")
        try:
            result = _render_shapes_to_png(shape_ids, shapes, out_path)
        except Exception as exc:
            log.write(f"[ui.swf] {sym_name}: render error {exc!r}\n")
            continue
        if result is None:
            continue
        if target_dir is badges_dir:
            badges_written += 1
        else:
            shells_written += 1

    return badges_written, shells_written


def _sanitize_filename(name: str) -> str:
    return (
        name.replace("/", "_").replace("\\", "_").replace(":", "_")
            .replace("*", "_").replace("?", "_").replace('"', "_")
            .replace("<", "_").replace(">", "_").replace("|", "_")
    )
