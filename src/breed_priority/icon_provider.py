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
import threading
from typing import Optional

from PySide6.QtCore import Qt, QCoreApplication, QEventLoop, QObject, QThread, Signal
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
from .icon_extraction.ffdec_tool import (
    find_ffdec,
    find_java,
    validate as validate_ffdec,
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
_PLACEHOLDER_FILENAME = "circle.png"  # Already-shipped neutral fallback symbol.
_PLACEHOLDER_DIR_REL = os.path.join("breed_priority", "assets", "symbols")
_CACHE_KEY_PREFIX = "bp_ability_icon::"
_MUTATION_CACHE_KEY_PREFIX = "bp_mutation_icon::"
_MUTATION_SUBDIR = "mutations"  # under .../assets/symbols/
_PNG_EXT = ".png"
# Repo-shipped icon assets — populated by a one-time bulk extraction and
# committed alongside the code so end users don't need FFDEC/Java to see
# ability icons. The %APPDATA% per-user dir (``app_settings.icons_dir()``)
# still wins when present so power users can override with a fresh extraction
# from a newer game version.
_SHIPPED_ICONS_SUBDIR = "icons"
_SHIPPED_ASSETS_SUBDIR = "assets"
_ABILITY_ICON_MAP_FILENAME = "ability_icon_map.json"
_QPIXMAP_CACHE_LIMIT_KB = 8 * 1024  # 8 MB — plenty for a few hundred small PNGs.
_PROGRESS_DIALOG_MIN_WIDTH = 420
_CONSOLE_PROGRESS_START_MSG = "[icon-extract] starting…"
_CONSOLE_PROGRESS_INTERVAL = 100  # print to console every N frames

# Common Mewgenics install paths to probe automatically before prompting the
# operator. Ordered by likelihood; first one that validates wins.
_DEFAULT_INSTALL_PATHS = (
    r"C:\Program Files (x86)\Steam\steamapps\common\Mewgenics",
)

# External-tool download landing pages we point operators at when FFDEC or
# Java can't be located on their machine.
_FFDEC_DOWNLOAD_URL = "https://github.com/jindrapetrik/jpexs-decompiler/releases"
_JAVA_DOWNLOAD_URL = "https://learn.microsoft.com/en-us/java/openjdk/download"


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


def _shipped_icons_dir() -> str:
    """Return the absolute path to the repo-shipped icons directory.

    Mirrors the structure of ``app_settings.icons_dir()`` (``<root>/abilities``
    plus ``ability_icon_map.json`` at the root) so the same path-resolution
    helpers work against either location.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, _SHIPPED_ASSETS_SUBDIR, _SHIPPED_ICONS_SUBDIR)


def _shipped_abilities_dir() -> str:
    return os.path.join(_shipped_icons_dir(), _ABILITIES_SUBDIR)


def _has_shipped_ability_icons() -> bool:
    """True when the repo-shipped abilities directory has any PNGs.

    Used to short-circuit ``ensure_assets_ready`` for the typical end-user
    install — once icons ship in the repo (or PyInstaller bundle), no
    FFDEC/Java prompt is ever needed.
    """
    shipped = _shipped_abilities_dir()
    if not os.path.isdir(shipped):
        return False
    try:
        for name in os.listdir(shipped):
            if name.lower().endswith(_PNG_EXT):
                return True
    except OSError:
        return False
    return False


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
    """Load the ability-name → icon-metadata map.

    Prefers the per-user ``%APPDATA%`` map (so a power-user re-extraction
    from a newer game version overrides the shipped data), falling back to
    the repo-shipped map when no user copy exists.
    """
    global _ability_icon_map
    if _ability_icon_map is None:
        user_map = load_ability_icon_map(app_settings.icons_dir())
        if user_map:
            _ability_icon_map = user_map
        else:
            _ability_icon_map = load_ability_icon_map(_shipped_icons_dir())
    return _ability_icon_map


def _reset_caches() -> None:
    global _ability_icon_map
    _ability_icon_map = None
    QPixmapCache.clear()


# ── Public API ────────────────────────────────────────────────────────────────

def ensure_assets_ready(parent: Optional[QWidget] = None) -> bool:
    """Return True if ability icons are available for display.

    With pre-extracted icons shipped in the repo (and bundled into the
    PyInstaller build), the typical end user never needs FFDEC or Java —
    this is a cheap no-op that returns True immediately. The %APPDATA%
    per-user extraction path is reserved for power users who explicitly
    invoke ``reextract_icons`` to override the shipped data with a fresh
    pull from a newer game version.
    """
    if _has_shipped_ability_icons():
        return True
    # No shipped icons (development checkout that hasn't been seeded, or
    # the assets dir was deleted) — fall back to the per-user manifest so
    # an earlier extraction still counts as "ready".
    return is_manifest_current(app_settings.icons_dir())


def _ensure_ffdec_ready(parent: Optional[QWidget]) -> bool:
    """Locate FFDEC + Java, prompting the operator if either is missing."""
    java_exe = find_java()
    ffdec_jar = find_ffdec()
    if java_exe and ffdec_jar:
        ok, _ = validate_ffdec(java_exe, ffdec_jar)
        if ok:
            return True

    # Tell the operator what's missing and where to get it.
    QMessageBox.information(
        parent,
        _tr("FFDEC + Java required"),
        _tr(
            "Icon extraction requires JPEXS Free Flash Decompiler (FFDEC) and a "
            "Java runtime.\n\n"
            "Download FFDEC: {ffdec}\n"
            "Download Java (Microsoft OpenJDK): {java}\n\n"
            "After installing them, you'll be asked to locate ffdec.jar."
        ).format(ffdec=_FFDEC_DOWNLOAD_URL, java=_JAVA_DOWNLOAD_URL),
    )
    chosen_jar, _ = QFileDialog.getOpenFileName(
        parent,
        _tr("Locate ffdec.jar"),
        "",
        _tr("FFDEC jar (ffdec.jar)"),
    )
    if not chosen_jar:
        return False
    app_settings.set_ffdec_jar_path(chosen_jar)

    # Java may already be discoverable now that the operator's installed it;
    # only prompt for it if discovery still fails.
    java_exe = find_java()
    if not java_exe:
        chosen_java, _ = QFileDialog.getOpenFileName(
            parent,
            _tr("Locate java.exe"),
            "",
            _tr("Java executable (java.exe)"),
        )
        if not chosen_java:
            return False
        app_settings.set_java_exe_path(chosen_java)
        java_exe = chosen_java

    ok, reason = validate_ffdec(java_exe, chosen_jar)
    if not ok:
        QMessageBox.warning(
            parent,
            _tr("FFDEC validation failed"),
            _tr("FFDEC could not be validated:") + "\n" + reason,
        )
        return False
    return True


def reextract_icons(parent: Optional[QWidget] = None) -> bool:
    """Power-user opt-in: re-extract ability icons into ``%APPDATA%``.

    The repo ships pre-extracted icons that work for the typical user with
    no external tooling. This entry point exists for operators who want to
    refresh from a newer game version — it requires a local Mewgenics
    install plus FFDEC + Java, and the freshly-extracted icons (written to
    ``app_settings.icons_dir()``) take precedence over the shipped copies
    on subsequent launches.
    """
    icons_dir = app_settings.icons_dir()
    delete_manifest(icons_dir)
    _reset_caches()

    install_path = _resolve_install_path(parent)
    if not install_path:
        return False
    if not _ensure_ffdec_ready(parent):
        return False
    return _run_extraction(parent, install_path, icons_dir)


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

    base_path = _resolve_base_icon_path(ability_name)
    pixmap = QPixmap()
    if base_path:
        pixmap.load(base_path)

    if pixmap.isNull():
        pixmap = _get_placeholder_pixmap()

    QPixmapCache.insert(cache_key, pixmap)
    return pixmap


def get_ability_icon_file_url(ability_name: str) -> Optional[str]:
    """Return a ``file:///...`` URL for use in HTML tooltips.

    Returns None when no extracted icon exists for the ability — callers
    can decide whether to emit a placeholder or skip the ``<img>`` tag.
    """
    base_path = _resolve_base_icon_path(ability_name)
    if not base_path:
        return None
    return _file_url(base_path)


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


def _resolve_base_icon_path(ability_name: str) -> Optional[str]:
    """Return the absolute path to the base icon PNG, or None.

    Tries each candidate frame label in priority order (map ``animation``,
    map ``ability_icon_override``, lookup-key variants, the bare ability
    name) and returns the first one whose PNG actually exists. Checks the
    per-user ``%APPDATA%`` directory first so a power-user re-extraction
    can override the shipped icons, then falls back to the repo-shipped
    copy that every install gets for free.
    """
    user_dir = os.path.join(app_settings.icons_dir(), _ABILITIES_SUBDIR)
    shipped_dir = _shipped_abilities_dir()
    seen: set[str] = set()
    for frame in _candidate_frame_labels(ability_name):
        if not frame or frame in seen:
            continue
        seen.add(frame)
        filename = frame + _PNG_EXT
        user_candidate = os.path.join(user_dir, filename)
        if os.path.exists(user_candidate):
            return user_candidate
        shipped_candidate = os.path.join(shipped_dir, filename)
        if os.path.exists(shipped_candidate):
            return shipped_candidate
    return None


def _resolve_frame_label(ability_name: str) -> Optional[str]:
    """Look up the best SWF frame label for an ability name.

    Returns the first candidate from :func:`_candidate_frame_labels` — the
    map-declared ``animation`` when present, else an override target, else
    the bare ability name. Note this does **not** verify the PNG exists;
    use :func:`_resolve_base_icon_path` for end-to-end resolution.
    """
    for frame in _candidate_frame_labels(ability_name):
        if frame:
            return frame
    return None


def _candidate_frame_labels(ability_name: str):
    """Yield frame-label candidates for an ability in priority order.

    Order is:
      1. Each ``_candidate_lookup_keys`` variant of the input name (most
         specific — many abilities ship a dedicated icon symbol named after
         the ability itself, e.g. ``Kamehameha.png``).
      2. ``animation`` from any matching map entry (the GON's
         ``graphics.animation`` field — refers to the in-combat animation
         and often doubles as a shared generic icon when an ability has no
         dedicated one, e.g. Kamehameha falls back to ``hadouken``).
      3. ``ability_icon_override`` target (one-hop redirect to another
         ability whose name resolves a frame).

    Callers walk the sequence and pick the first whose PNG exists, so a
    dedicated per-ability icon wins over the shared animation-name icon.
    """
    icon_map = _load_ability_map_if_needed()
    lookup_keys = list(_candidate_lookup_keys(ability_name))

    for key in lookup_keys:
        yield key

    if icon_map:
        for key in lookup_keys:
            entry = icon_map.get(key)
            if isinstance(entry, dict):
                anim = entry.get("animation")
                if isinstance(anim, str) and anim and anim.lower() != "none":
                    yield anim
        for key in lookup_keys:
            entry = icon_map.get(key)
            if isinstance(entry, dict):
                override = entry.get("ability_icon_override")
                if isinstance(override, str) and override:
                    yield override


def _candidate_lookup_keys(ability_name: str):
    """Yield map-lookup key variants for an ability name.

    Handles three sources of mismatch between caller and map:
      * Trailing tier digit (``BlowKiss2`` → ``BlowKiss``).
      * Display-name spaces (``Buy Catnip`` → ``BuyCatnip``) — UI code
        sometimes passes the human label rather than the internal key.
      * Combined: ``Blow Kiss 2`` → ``BlowKiss``.
    """
    yield ability_name
    stripped_digits = ability_name.rstrip("0123456789")
    if stripped_digits and stripped_digits != ability_name:
        yield stripped_digits
    if " " in ability_name:
        no_spaces = ability_name.replace(" ", "")
        if no_spaces and no_spaces != ability_name:
            yield no_spaces
        no_spaces_no_digits = no_spaces.rstrip("0123456789")
        if no_spaces_no_digits and no_spaces_no_digits not in (no_spaces, ability_name):
            yield no_spaces_no_digits


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
