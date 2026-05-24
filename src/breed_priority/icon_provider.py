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

import hashlib
import logging
import os
import threading
from typing import Optional

from PySide6.QtCore import Qt, QCoreApplication, QEventLoop, QObject, QThread, Signal
from PySide6.QtGui import QPainter, QPixmap, QPixmapCache
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
from .icon_extraction.mutation_slots import normalize_slot

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

_ABILITIES_SUBDIR = "abilities"
_BADGES_SUBDIR = "badges"
_SHELLS_SUBDIR = "shells"
_COMPOSED_SUBDIR = "composed"
_PLACEHOLDER_FILENAME = "circle.png"  # Already-shipped neutral fallback symbol.
_PLACEHOLDER_DIR_REL = os.path.join("breed_priority", "assets", "symbols")
_CACHE_KEY_PREFIX = "bp_ability_icon::"
_MUTATION_CACHE_KEY_PREFIX = "bp_mutation_icon::"
_MUTATION_SUBDIR = "mutations"  # under .../assets/symbols/
_PNG_EXT = ".png"
_QPIXMAP_CACHE_LIMIT_KB = 8 * 1024  # 8 MB — plenty for a few hundred small PNGs.
_PROGRESS_DIALOG_MIN_WIDTH = 420
_CONSOLE_PROGRESS_START_MSG = "[icon-extract] starting…"
_CONSOLE_PROGRESS_INTERVAL = 100  # print to console every N frames

# Composition layering — badges are rendered small in a corner; shells span
# the whole canvas. Sized relative to the base icon's bounding box.
_BADGE_SCALE = 0.45            # badge edge length as fraction of base icon edge
_COMPOSED_HASH_LEN = 16

# Common Mewgenics install paths to probe automatically before prompting the
# operator. Ordered by likelihood; first one that validates wins.
_DEFAULT_INSTALL_PATHS = (
    r"C:\Program Files (x86)\Steam\steamapps\common\Mewgenics",
)


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

    base_path, badge_path, shell_path = _resolve_layer_paths(ability_name)
    pixmap = QPixmap()
    if base_path:
        pixmap.load(base_path)
    if not pixmap.isNull() and (badge_path or shell_path):
        pixmap = _compose_layers(pixmap, badge_path, shell_path)

    if pixmap.isNull():
        pixmap = _get_placeholder_pixmap()

    QPixmapCache.insert(cache_key, pixmap)
    return pixmap


def get_ability_icon_file_url(ability_name: str) -> Optional[str]:
    """Return a ``file:///...`` URL for use in HTML tooltips.

    When an ability has a badge and/or shell layer, the layers are
    composited once to ``<icons_dir>/composed/<hash>.png`` and that URL is
    returned. Returns None when no extracted base icon exists for the
    ability — callers can decide whether to emit a placeholder or skip the
    ``<img>`` tag.
    """
    base_path, badge_path, shell_path = _resolve_layer_paths(ability_name)
    if not base_path:
        return None
    if not (badge_path or shell_path):
        return _file_url(base_path)
    composed = _ensure_composed_file(base_path, badge_path, shell_path)
    return _file_url(composed)


def _mutation_icon_path(slot: str) -> Optional[str]:
    """Resolve a shipped mutation placeholder PNG path, or None if unknown slot."""
    canonical = normalize_slot(slot)
    if canonical is None:
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "assets", "symbols", _MUTATION_SUBDIR, canonical + _PNG_EXT)
    return path if os.path.exists(path) else None


def get_mutation_icon(slot: str) -> QPixmap:
    """Return a QPixmap for the given mutation slot.

    ``slot`` matches the ``group_key`` on ``Cat.visual_mutation_entries``
    (e.g. ``"body"``, ``"eyebrows"``). Falls back to the generic circle
    placeholder when the slot is unknown or its PNG is missing.
    """
    _init_pixmap_cache()
    canonical = normalize_slot(slot) or ""
    cache_key = _MUTATION_CACHE_KEY_PREFIX + canonical
    cached = QPixmap()
    if canonical and QPixmapCache.find(cache_key, cached):
        return cached

    path = _mutation_icon_path(slot)
    pixmap = QPixmap()
    if path:
        pixmap.load(path)
    if pixmap.isNull():
        pixmap = _get_placeholder_pixmap()
    if canonical:
        QPixmapCache.insert(cache_key, pixmap)
    return pixmap


def get_mutation_icon_file_url(slot: str) -> Optional[str]:
    """Return a ``file:///...`` URL for embedding the slot icon in HTML tooltips."""
    path = _mutation_icon_path(slot)
    if not path:
        return None
    return "file:///" + path.replace(os.sep, "/")


# ── Internals ────────────────────────────────────────────────────────────────

def _file_url(path: str) -> str:
    return "file:///" + path.replace(os.sep, "/")


def _resolve_layer_paths(ability_name: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return ``(base_png, badge_png, shell_png)`` for an ability.

    Each element is an absolute path to an existing PNG, or None when the
    layer is unavailable. ``base_png`` is the only one required for the
    icon to render; the other two are optional overlays.
    """
    icons_dir = app_settings.icons_dir()
    frame = _resolve_frame_label(ability_name)
    base_path = None
    if frame:
        candidate = os.path.join(icons_dir, _ABILITIES_SUBDIR, frame + _PNG_EXT)
        if os.path.exists(candidate):
            base_path = candidate

    badge_name, shell_name = _resolve_badge_and_shell_names(ability_name)
    badge_path = _existing_layer_path(icons_dir, _BADGES_SUBDIR, badge_name)
    shell_path = _existing_layer_path(icons_dir, _SHELLS_SUBDIR, shell_name)
    return base_path, badge_path, shell_path


def _existing_layer_path(icons_dir: str, subdir: str, name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    path = os.path.join(icons_dir, subdir, name + _PNG_EXT)
    return path if os.path.exists(path) else None


def _resolve_badge_and_shell_names(ability_name: str) -> tuple[Optional[str], Optional[str]]:
    icon_map = _load_ability_map_if_needed()
    if not icon_map:
        return None, None
    for key in _candidate_lookup_keys(ability_name):
        entry = icon_map.get(key)
        if isinstance(entry, dict):
            badge = entry.get("type_icon")
            shell = entry.get("icon_shell_frame")
            return (
                badge if isinstance(badge, str) and badge else None,
                shell if isinstance(shell, str) and shell else None,
            )
    return None, None


def _compose_layers(
    base: QPixmap,
    badge_path: Optional[str],
    shell_path: Optional[str],
) -> QPixmap:
    """Layer shell (bottom) → base → badge (top-right) onto a copy of ``base``.

    The composed canvas inherits the base icon's dimensions; layers are
    scaled to fit. Returns the composed pixmap or the original on failure.
    """
    canvas = QPixmap(base.size())
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    try:
        if shell_path:
            shell = QPixmap(shell_path)
            if not shell.isNull():
                scaled = shell.scaled(
                    base.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                offset_x = (base.width() - scaled.width()) // 2
                offset_y = (base.height() - scaled.height()) // 2
                painter.drawPixmap(offset_x, offset_y, scaled)
        painter.drawPixmap(0, 0, base)
        if badge_path:
            badge = QPixmap(badge_path)
            if not badge.isNull():
                badge_edge = max(1, int(round(base.width() * _BADGE_SCALE)))
                scaled_badge = badge.scaled(
                    badge_edge, badge_edge,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                bx = base.width() - scaled_badge.width()
                by = base.height() - scaled_badge.height()
                painter.drawPixmap(bx, by, scaled_badge)
    finally:
        painter.end()
    return canvas


def _composed_filename(base_path: str, badge_path: Optional[str], shell_path: Optional[str]) -> str:
    key = "|".join([
        base_path,
        badge_path or "",
        shell_path or "",
    ])
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:_COMPOSED_HASH_LEN]
    base_stem = os.path.splitext(os.path.basename(base_path))[0]
    return f"{base_stem}_{digest}{_PNG_EXT}"


def _ensure_composed_file(
    base_path: str,
    badge_path: Optional[str],
    shell_path: Optional[str],
) -> str:
    """Write a composed PNG to ``<icons_dir>/composed/`` if missing; return path."""
    icons_dir = app_settings.icons_dir()
    composed_dir = os.path.join(icons_dir, _COMPOSED_SUBDIR)
    os.makedirs(composed_dir, exist_ok=True)
    out_path = os.path.join(composed_dir, _composed_filename(base_path, badge_path, shell_path))
    if os.path.exists(out_path):
        return out_path
    base = QPixmap(base_path)
    if base.isNull():
        return base_path
    composed = _compose_layers(base, badge_path, shell_path)
    if not composed.save(out_path, "PNG"):
        return base_path
    return out_path


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

    for candidate in _DEFAULT_INSTALL_PATHS:
        ok, _ = validate_install_path(candidate)
        if ok:
            app_settings.set_game_install_path(candidate)
            return candidate

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


class _ExtractionWorker(QObject):
    """Runs ability-icon extraction off the GUI thread.

    Owns a thread-safe cancel flag set by the GUI when the operator clicks
    the progress dialog's Cancel button. The extractor's existing
    ``progress_cb`` cancellation path is reused — we route the flag check
    through the callback's return value.
    """

    progress = Signal(int, int, str)   # done, total, label
    failed = Signal(str)               # error text for QMessageBox
    finished = Signal(object)          # summary dict, or None on failure

    def __init__(self, install_path: str, icons_dir: str) -> None:
        super().__init__()
        self._install_path = install_path
        self._icons_dir = icons_dir
        self._cancel_event = threading.Event()

    def request_cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        def on_progress(done: int, total: int, label: str) -> bool:
            self.progress.emit(done, total, label)
            return not self._cancel_event.is_set()

        try:
            build_ability_icon_map(self._install_path, self._icons_dir)
            summary = extract_ability_icons(
                self._install_path, self._icons_dir, progress_cb=on_progress,
            )
        except Exception as exc:
            logger.exception("Icon extraction failed")
            self.failed.emit(str(exc))
            self.finished.emit(None)
            return
        self.finished.emit(summary)


def _run_extraction(parent: Optional[QWidget], install_path: str, icons_dir: str) -> bool:
    """Run extraction on a worker thread with a cancellable progress dialog.

    Keeps a synchronous return-bool contract by spinning a local QEventLoop
    until the worker finishes. Returns True on successful extraction, False
    if cancelled or failed.
    """
    os.makedirs(icons_dir, exist_ok=True)

    progress = QProgressDialog(
        _tr("Extracting ability icons from your Mewgenics install..."),
        _tr("Cancel"),
        0, 0, parent,
    )
    progress.setWindowTitle(_tr("Extracting icons"))
    progress.setMinimumDuration(0)
    progress.setAutoClose(True)
    progress.setAutoReset(False)
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumWidth(_PROGRESS_DIALOG_MIN_WIDTH)
    # Force the dialog visible immediately — with minimumDuration=0 Qt still
    # waits for an event-loop tick, and on Windows that can swallow the
    # window if extraction finishes its first batch quickly.
    progress.setValue(0)
    progress.show()
    QCoreApplication.processEvents()
    print(_CONSOLE_PROGRESS_START_MSG, flush=True)

    thread = QThread()
    worker = _ExtractionWorker(install_path, icons_dir)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    # Mutable result holders — closed-over by the inner handlers below.
    summary_box: dict[str, object] = {"summary": None}
    error_box: dict[str, Optional[str]] = {"error": None}
    loop = QEventLoop()

    def on_progress(done: int, total: int, _label: str) -> None:
        if total > 0 and progress.maximum() != total:
            progress.setMaximum(total)
        progress.setValue(done)
        if total > 0 and (done % _CONSOLE_PROGRESS_INTERVAL == 0 or done == total):
            print(f"[icon-extract] {done}/{total}", flush=True)

    def on_failed(message: str) -> None:
        error_box["error"] = message

    def on_finished(summary) -> None:
        summary_box["summary"] = summary
        thread.quit()

    def on_cancel_clicked() -> None:
        worker.request_cancel()

    worker.progress.connect(on_progress)
    worker.failed.connect(on_failed)
    worker.finished.connect(on_finished)
    progress.canceled.connect(on_cancel_clicked)
    thread.finished.connect(loop.quit)

    thread.start()
    loop.exec()
    # Ensure the thread is fully torn down before we proceed.
    thread.wait()
    worker.deleteLater()
    thread.deleteLater()
    progress.close()

    if error_box["error"] is not None:
        QMessageBox.critical(
            parent,
            _tr("Extraction failed"),
            _tr("Icon extraction failed:") + f"\n\n{error_box['error']}",
        )
        return False

    summary = summary_box["summary"]
    if not isinstance(summary, dict):
        return False

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
    print(
        f"[icon-extract] done — {summary.get('written', 0)} written, "
        f"{summary.get('skipped', 0)} skipped",
        flush=True,
    )
    return True
