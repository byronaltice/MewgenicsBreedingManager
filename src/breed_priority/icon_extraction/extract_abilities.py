"""Extract ability icons from a Mewgenics install using JPEXS FFDEC.

We shell out to ``java -jar ffdec.jar -format shape:png -export shape ...``
to rasterize every DefineShape character in ``ability_icons.swf``. Shape
export produces one PNG per character — clean icons with no stage cruft
from other timeline layers (the older ``-export sprite`` mode dumped the
whole sprite stage per frame, which bled persistent layers into every PNG).

After FFDEC finishes we walk each labeled frame in ``AbilityIcon`` and
``PassiveIcon``, pick the topmost (highest-depth) shape placed in that
frame, and copy ``<dump>/<char_id>.png`` to
``<icons_dir>/abilities/<frame_label>.png``.

The FFDEC dump (1000+ PNGs we don't keep) is deleted after copying.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Callable, Optional

from .ffdec_tool import find_ffdec, find_java, validate as validate_ffdec
from .gon_ability_map import load_ability_icon_map
from .gpak_reader import GpakReader, find_gpak_in
from .swf_sprite_walker import build_frame_to_character_index, parse_all_tags


# ── Internal paths inside resources.gpak ──────────────────────────────────────

_GPAK_FILENAME = "resources.gpak"
_ABILITY_ICONS_INTERNAL = "swfs/ability_icons.swf"

# ── Output directory layout ───────────────────────────────────────────────────

_ABILITIES_SUBDIR = "abilities"
_LOG_FILENAME = "extraction.log"

# ── FFDEC invocation ──────────────────────────────────────────────────────────

# Shape export emits ``<char_id>.png`` flat into the output directory.
_FFDEC_FORMAT_ARG = "shape:png"
_FFDEC_EXPORT_TYPE = "shape"
_FFDEC_TIMEOUT_SECS = 180
_SHAPE_PNG_EXT = ".png"

# Symbol class names of the two ability-icon timelines we care about.
_ABILITY_SPRITE_CLASS = "AbilityIcon"
_PASSIVE_SPRITE_CLASS = "PassiveIcon"

# Lookup priority — frame labels in AbilityIcon win over PassiveIcon when
# both define the same label. Empirically the active-ability timeline is
# the more common case.
_SPRITE_CLASS_PRIORITY = (_ABILITY_SPRITE_CLASS, _PASSIVE_SPRITE_CLASS)


# ── Public helpers ────────────────────────────────────────────────────────────

def gpak_path_for(install_path: str) -> Optional[str]:
    """Return the absolute path to ``resources.gpak`` for an install dir."""
    return find_gpak_in(install_path)


def validate_install_path(install_path: str) -> tuple[bool, str]:
    """Return (ok, reason). Checks gpak exists and contains the icons SWF."""
    if not install_path or not os.path.isdir(install_path):
        return False, "Path is not a directory."
    gpak = gpak_path_for(install_path)
    if not gpak:
        return False, f"{_GPAK_FILENAME} not found in selected folder."
    try:
        with GpakReader(gpak) as reader:
            if not reader.has(_ABILITY_ICONS_INTERNAL):
                return False, (
                    f"{_GPAK_FILENAME} does not contain {_ABILITY_ICONS_INTERNAL}."
                )
    except Exception as exc:
        return False, f"Could not read {_GPAK_FILENAME}: {exc}"
    return True, ""


# ── Frame-label → character-id index ──────────────────────────────────────────

def _build_label_to_char_indices(swf_bytes: bytes) -> dict[str, dict[str, int]]:
    """Per-class ``{frame_label: char_id}`` map parsed from the raw SWF."""
    swf_data = parse_all_tags(swf_bytes)
    names = swf_data["names"]
    sprites = swf_data["sprites"]
    name_to_id = {name: cid for cid, name in names.items()}

    out: dict[str, dict[str, int]] = {}
    for class_name in _SPRITE_CLASS_PRIORITY:
        sym_id = name_to_id.get(class_name)
        if sym_id is None:
            continue
        inner = sprites.get(sym_id)
        if inner is None:
            continue
        out[class_name] = build_frame_to_character_index(inner)
    return out


# ── Public entry point ───────────────────────────────────────────────────────

def extract_ability_icons(
    install_path: str,
    icons_dir: str,
    progress_cb: Optional[Callable[[int, int, str], bool]] = None,
) -> dict:
    """Run FFDEC shape-export against ``ability_icons.swf`` and copy PNGs out.

    Args:
        install_path: Mewgenics install root (folder containing resources.gpak).
        icons_dir: Output directory (``<assets>/icons``).
        progress_cb: Optional ``(done, total, label) -> bool``. Return False
            to cancel.

    Returns a summary dict with counts. Raises ``FileNotFoundError`` if the
    install path or FFDEC/Java are missing.
    """
    ok, reason = validate_install_path(install_path)
    if not ok:
        raise FileNotFoundError(reason)

    java_exe = find_java()
    ffdec_jar = find_ffdec()
    if not java_exe or not ffdec_jar:
        raise FileNotFoundError(
            "Java and FFDEC are required for icon extraction. "
            f"Java found: {bool(java_exe)}, FFDEC found: {bool(ffdec_jar)}."
        )
    valid, why = validate_ffdec(java_exe, ffdec_jar)
    if not valid:
        raise FileNotFoundError(f"FFDEC validation failed: {why}")

    out_dir = os.path.join(icons_dir, _ABILITIES_SUBDIR)
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(icons_dir, _LOG_FILENAME)

    # Pull the SWF out of the gpak into a temp file so FFDEC can read it.
    gpak = gpak_path_for(install_path)
    with GpakReader(gpak) as reader:
        swf_bytes = reader.read(_ABILITY_ICONS_INTERNAL)

    label_to_char = _build_label_to_char_indices(swf_bytes)

    # Walk the ability_icon_map (already built by the caller) to know which
    # frame labels we actually need; union with every labeled frame in both
    # ability sprites so passive/disorder icons (whose names don't appear as
    # ability keys in the GON map) also get extracted for runtime fallback
    # resolution by bare name.
    icon_map = load_ability_icon_map(icons_dir)
    needed_labels = _collect_needed_labels(icon_map, label_to_char)
    total = len(needed_labels)

    written = 0
    skipped_no_label = 0
    missing_char_png = 0
    failures: list[str] = []
    cancelled = False

    with tempfile.TemporaryDirectory(prefix="mbm_ffdec_") as tmp_root:
        swf_path = os.path.join(tmp_root, "ability_icons.swf")
        with open(swf_path, "wb") as fh:
            fh.write(swf_bytes)
        dump_dir = os.path.join(tmp_root, "shapes")
        os.makedirs(dump_dir, exist_ok=True)

        if progress_cb is not None and not progress_cb(0, total, "ffdec dump"):
            return _summary(written, skipped_no_label + missing_char_png,
                            total, True, failures)

        try:
            subprocess.run(
                [java_exe, "-jar", ffdec_jar,
                 "-format", _FFDEC_FORMAT_ARG,
                 "-export", _FFDEC_EXPORT_TYPE,
                 dump_dir, swf_path],
                check=True,
                capture_output=True,
                timeout=_FFDEC_TIMEOUT_SECS,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"FFDEC exited with code {exc.returncode}: "
                f"{(exc.stderr or b'').decode('utf-8', 'replace')[:500]}"
            ) from exc

        with open(log_path, "w", encoding="utf-8") as log:
            log.write(f"# Icon extraction log (FFDEC shape mode)\n"
                      f"# source: {install_path}\n\n")
            done = 0
            for label in needed_labels:
                done += 1
                if progress_cb is not None and not progress_cb(done, total, label):
                    cancelled = True
                    break
                char_id = _lookup_label_char(label, label_to_char)
                if char_id is None:
                    log.write(f"missing-frame-label: {label}\n")
                    failures.append(label)
                    skipped_no_label += 1
                    continue
                src_png = os.path.join(dump_dir, f"{char_id}{_SHAPE_PNG_EXT}")
                if not os.path.isfile(src_png):
                    log.write(
                        f"missing-char-png: {label} -> cid {char_id} "
                        f"(shape not dumped — likely a sprite, not a shape)\n"
                    )
                    failures.append(label)
                    missing_char_png += 1
                    continue
                dst = os.path.join(out_dir, _sanitize_filename(label) + _SHAPE_PNG_EXT)
                try:
                    shutil.copyfile(src_png, dst)
                    written += 1
                except OSError as exc:
                    log.write(f"copy-failed: {label}: {exc!r}\n")
                    failures.append(label)
                    missing_char_png += 1

    return _summary(written, skipped_no_label + missing_char_png,
                    total, cancelled, failures)


def _collect_needed_labels(
    icon_map: dict[str, dict],
    label_to_char: dict[str, dict[str, int]] | None = None,
) -> list[str]:
    """Collect the unique frame labels referenced by the ability map.

    Falls back to the ability name itself when ``animation`` is missing —
    matches the lookup convention in ``icon_provider._resolve_frame_label``.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for name, entry in sorted(icon_map.items()):
        candidates = []
        if isinstance(entry, dict):
            anim = entry.get("animation")
            override = entry.get("ability_icon_override")
            if isinstance(anim, str) and anim and anim.lower() != "none":
                candidates.append(anim)
            elif isinstance(override, str) and override:
                candidates.append(override)
        if not candidates:
            candidates.append(name)
        # Always include the bare ability name too so dedicated per-ability
        # shapes (e.g. ``Kamehameha`` itself, not just the shared
        # ``hadouken`` animation) get extracted when available.
        if name not in candidates:
            candidates.append(name)
        for label in candidates:
            if label not in seen:
                seen.add(label)
                ordered.append(label)

    # Union with every labeled frame present in either ability sprite —
    # ensures passive/disorder icons (not represented as ability keys in
    # the GON) ship too, so runtime bare-name lookups find them.
    if label_to_char:
        for class_name in _SPRITE_CLASS_PRIORITY:
            sprite_labels = label_to_char.get(class_name) or {}
            for label in sprite_labels:
                if label not in seen:
                    seen.add(label)
                    ordered.append(label)

    return ordered


def _lookup_label_char(
    label: str,
    label_to_char: dict[str, dict[str, int]],
) -> Optional[int]:
    """Resolve ``label`` to a character ID, preferring AbilityIcon."""
    for class_name in _SPRITE_CLASS_PRIORITY:
        labels = label_to_char.get(class_name)
        if not labels:
            continue
        char_id = labels.get(label)
        if char_id is not None:
            return char_id
    return None


def _summary(written: int, skipped: int, total: int, cancelled: bool,
             failures: list[str]) -> dict:
    return {
        "written": written,
        "skipped": skipped,
        "total": total,
        "cancelled": cancelled,
        "failures": failures,
        # Retained for API compatibility with the old extractor — FFDEC path
        # doesn't produce badges/shells, so these are always zero.
        "badges_written": 0,
        "shells_written": 0,
    }


def _sanitize_filename(name: str) -> str:
    return (
        name.replace("/", "_").replace("\\", "_").replace(":", "_")
            .replace("*", "_").replace("?", "_").replace('"', "_")
            .replace("<", "_").replace(">", "_").replace("|", "_")
    )
