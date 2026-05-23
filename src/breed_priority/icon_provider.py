"""Runtime icon lookup for ability names.

Handles two responsibilities:

1. ``ensure_assets_ready(parent)`` — called once at startup. If the per-user
   icon assets are missing/outdated, prompts the operator for their game
   install path and runs extraction with a progress dialog.
2. ``get_ability_icon(name)`` — cached pixmap lookup by ability name. Maps
   ability name → animation frame label via ``ability_icon_map.json``, then
   loads ``<icons_dir>/abilities/<frame>.png``.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QPixmap, QPixmapCache
from PySide6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QWidget

from . import app_settings
from .icon_extraction import (
    is_manifest_current,
    write_manifest,
)
from .icon_extraction.extract_abilities import (
    extract_ability_icons,
    validate_install_path,
)
from .icon_extraction.gon_ability_map import (
    build_ability_icon_map,
    load_ability_icon_map,
)
from .icon_extraction.manifest import delete_manifest

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

_ABILITIES_SUBDIR = "abilities"
_PLACEHOLDER_FILENAME = "circle.png"  # Already-shipped neutral fallback symbol.
_PLACEHOLDER_DIR_REL = os.path.join("breed_priority", "assets", "symbols")
_CACHE_KEY_PREFIX = "bp_ability_icon::"
_QPIXMAP_CACHE_LIMIT_KB = 8 * 1024  # 8 MB — plenty for a few hundred small PNGs.


def _tr(text: str) -> str:
    """Local translation helper — keeps user-facing strings discoverable.

    The breed_priority module is intentionally standalone, so it uses Qt's
    translate function directly rather than importing the main-module helper.
    """
    return QCoreApplication.translate("BreedPriority", text)


# ── Module-level cached state ─────────────────────────────────────────────────

_ability_icon_map: dict[str, dict] | None = None
_placeholder_pixmap: QPixmap | None = None
_cache_initialized = False


def _init_pixmap_cache() -> None:
    global _cache_initialized
    if _cache_initialized:
        return
    QPixmapCache.setCacheLimit(_QPIXMAP_CACHE_LIMIT_KB)
    _cache_initialized = True


def _placeholder_path() -> Optional[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(here, "assets", "symbols", _PLACEHOLDER_FILENAME)
    return candidate if os.path.exists(candidate) else None


def _get_placeholder_pixmap() -> QPixmap:
    global _placeholder_pixmap
    if _placeholder_pixmap is None or _placeholder_pixmap.isNull():
        path = _placeholder_path()
        if path:
            _placeholder_pixmap = QPixmap(path)
        else:
            _placeholder_pixmap = QPixmap()
    return _placeholder_pixmap


def _load_ability_map_if_needed() -> dict[str, dict]:
    global _ability_icon_map
    if _ability_icon_map is None:
        _ability_icon_map = load_ability_icon_map(app_settings.icons_dir())
    return _ability_icon_map


def _reset_caches() -> None:
    global _ability_icon_map
    _ability_icon_map = None
    QPixmapCache.clear()


# ── Public API ────────────────────────────────────────────────────────────────

def ensure_assets_ready(parent: Optional[QWidget] = None) -> bool:
    """Verify the per-user icon assets exist; extract them if not.

    Returns True if assets are ready (already-present or freshly extracted)
    or False if the operator cancelled the install-path prompt or extraction.
    """
    icons_dir = app_settings.icons_dir()
    if is_manifest_current(icons_dir):
        return True

    install_path = _resolve_install_path(parent)
    if not install_path:
        return False
    return _run_extraction(parent, install_path, icons_dir)


def reextract_icons(parent: Optional[QWidget] = None) -> bool:
    """Force a fresh extraction. Wipes the existing manifest first."""
    icons_dir = app_settings.icons_dir()
    delete_manifest(icons_dir)
    _reset_caches()
    return ensure_assets_ready(parent)


def get_ability_icon(ability_name: str) -> QPixmap:
    """Return a QPixmap for the given ability name.

    Falls back to a small neutral placeholder when the icon is missing or
    extraction hasn't been run yet. Never returns a null pixmap unless the
    placeholder itself is missing.
    """
    _init_pixmap_cache()
    if not ability_name:
        return _get_placeholder_pixmap()

    cache_key = _CACHE_KEY_PREFIX + ability_name
    cached = QPixmap()
    if QPixmapCache.find(cache_key, cached):
        return cached

    frame = _resolve_frame_label(ability_name)
    pixmap = QPixmap()
    if frame:
        path = os.path.join(app_settings.icons_dir(), _ABILITIES_SUBDIR, frame + ".png")
        if os.path.exists(path):
            pixmap.load(path)

    if pixmap.isNull():
        pixmap = _get_placeholder_pixmap()

    QPixmapCache.insert(cache_key, pixmap)
    return pixmap


def get_ability_icon_file_url(ability_name: str) -> Optional[str]:
    """Return a ``file:///...`` URL for use in HTML tooltips.

    Returns None when no extracted icon exists for the ability — callers
    can decide whether to emit a placeholder or skip the ``<img>`` tag.
    """
    frame = _resolve_frame_label(ability_name)
    if not frame:
        return None
    path = os.path.join(app_settings.icons_dir(), _ABILITIES_SUBDIR, frame + ".png")
    if not os.path.exists(path):
        return None
    return "file:///" + path.replace(os.sep, "/")


# ── Internals ────────────────────────────────────────────────────────────────

def _resolve_frame_label(ability_name: str) -> Optional[str]:
    """Look up the SWF frame label for an ability name.

    Tries exact, lowercased, and ability-base (no trailing digits) keys to
    handle e.g. ``BlowKiss2`` falling back to ``BlowKiss``'s animation.
    """
    icon_map = _load_ability_map_if_needed()
    if not icon_map:
        return None

    for key in _candidate_lookup_keys(ability_name):
        entry = icon_map.get(key)
        if isinstance(entry, dict):
            anim = entry.get("animation")
            if isinstance(anim, str) and anim and anim.lower() != "none":
                return anim
            # Many abilities have no explicit ``graphics.animation`` but have
            # an ``ability_icon`` override pointing to another ability; that
            # target name is itself a valid frame label in AbilityIcon.
            override = entry.get("ability_icon_override")
            if isinstance(override, str) and override:
                return override
    # Last-resort: the ability name itself may be the frame label (matches
    # the convention used by AbilityIcon for abilities whose icon symbol is
    # simply named after the ability).
    return ability_name


def _candidate_lookup_keys(ability_name: str):
    yield ability_name
    stripped = ability_name.rstrip("0123456789")
    if stripped and stripped != ability_name:
        yield stripped


def _resolve_install_path(parent: Optional[QWidget]) -> Optional[str]:
    saved = app_settings.get_game_install_path()
    if saved:
        ok, _ = validate_install_path(saved)
        if ok:
            return saved

    QMessageBox.information(
        parent,
        _tr("Locate Mewgenics"),
        _tr(
            "Ability icons need to be extracted from your Mewgenics install.\n\n"
            "Select your Mewgenics install folder (the folder containing "
            "'resources.gpak')."
        ),
    )
    while True:
        chosen = QFileDialog.getExistingDirectory(
            parent,
            _tr("Select Mewgenics install folder"),
        )
        if not chosen:
            return None
        ok, reason = validate_install_path(chosen)
        if ok:
            app_settings.set_game_install_path(chosen)
            return chosen
        QMessageBox.warning(
            parent,
            _tr("Invalid folder"),
            _tr("That folder doesn't look like a Mewgenics install:") + "\n" + reason,
        )


def _run_extraction(parent: Optional[QWidget], install_path: str, icons_dir: str) -> bool:
    """Run extraction with a cancellable progress dialog."""
    os.makedirs(icons_dir, exist_ok=True)
    progress = QProgressDialog(
        _tr("Extracting ability icons..."),
        _tr("Cancel"),
        0, 100, parent,
    )
    progress.setWindowTitle(_tr("Mewgenics Breeding Manager"))
    progress.setMinimumDuration(0)
    progress.setAutoClose(True)
    progress.setWindowModality(Qt.WindowModal)
    progress.setValue(0)

    def on_progress(done: int, total: int, _label: str) -> bool:
        if total > 0:
            progress.setMaximum(total)
            progress.setValue(done)
        QCoreApplication.processEvents()
        return not progress.wasCanceled()

    try:
        build_ability_icon_map(install_path, icons_dir)
        summary = extract_ability_icons(
            install_path, icons_dir, progress_cb=on_progress,
        )
    except Exception as exc:
        logger.exception("Icon extraction failed")
        progress.close()
        QMessageBox.critical(
            parent,
            _tr("Extraction failed"),
            _tr("Icon extraction failed:") + f"\n\n{exc}",
        )
        return False

    progress.close()

    if summary.get("cancelled"):
        QMessageBox.information(
            parent,
            _tr("Extraction cancelled"),
            _tr("Icon extraction was cancelled. You can re-run it later from the menu."),
        )
        return False

    write_manifest(icons_dir, install_path)
    _reset_caches()
    logger.info(
        "Icon extraction complete: %d written, %d skipped, %d badges, %d shells",
        summary.get("written", 0), summary.get("skipped", 0),
        summary.get("badges_written", 0), summary.get("shells_written", 0),
    )
    return True
