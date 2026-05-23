# POC: Temporary proof-of-concept comparing icon load speed from two sources.
# POC: Delete this entire file (and the wiring in __init__.py marked with # POC:) to remove.
"""PoC icon loader benchmark.

Two sources:
  A) `defect-investigation/game-files/resources/resources.gpak` — large packed
     archive. The gpak format is not documented in this repo, so as a load-time
     proxy we scan the raw file bytes for PNG signatures and decode the first
     50 PNGs we encounter. Each PNG length is taken from its IHDR/IEND chunks
     by walking the PNG chunk structure starting from the `\\x89PNG` signature.
  B) `defect-investigation/game-files/resources/gpak-image/**/*.png` — already
     extracted PNG files on disk.

Both load 50 QPixmaps; elapsed perf_counter time is shown in a QDialog grid.
"""

from __future__ import annotations

import os
import struct
import time
from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

# POC: constants
_POC_ICON_COUNT = 50
_POC_GRID_COLS = 10
_POC_ICON_SIZE = 48
_POC_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_POC_GPAK_REL = "defect-investigation/game-files/resources/resources.gpak"
_POC_EXTRACTED_REL = "defect-investigation/game-files/resources/gpak-image"
# Cap how many bytes of the (very large) gpak we scan to find 50 PNGs.
_POC_GPAK_SCAN_LIMIT = 256 * 1024 * 1024  # 256 MiB
_POC_GPAK_CHUNK = 8 * 1024 * 1024  # 8 MiB read window
_POC_GPAK_OVERLAP = 1024 * 1024    # 1 MiB overlap to avoid splitting PNGs


def _poc_project_root() -> Path:
    # src/breed_priority/_poc_icon_loader.py -> project root is parents[2]
    return Path(__file__).resolve().parents[2]


def _poc_extract_pngs_from_gpak(path: Path, count: int) -> List[bytes]:
    """Scan the gpak file for PNG signatures and return the first `count` PNG byte blobs.

    Walks PNG chunks (length:4 BE | type:4 | data | crc:4) from each signature
    until IEND. Stops scanning after _POC_GPAK_SCAN_LIMIT bytes.
    """
    blobs: List[bytes] = []
    scanned = 0
    carry = b""
    base_offset = 0
    with open(path, "rb") as fh:
        while scanned < _POC_GPAK_SCAN_LIMIT and len(blobs) < count:
            chunk = fh.read(_POC_GPAK_CHUNK)
            if not chunk:
                break
            buffer = carry + chunk
            scanned += len(chunk)
            search_pos = 0
            while len(blobs) < count:
                sig_idx = buffer.find(_POC_PNG_SIG, search_pos)
                if sig_idx < 0:
                    break
                png_bytes = _poc_read_one_png(buffer, sig_idx)
                if png_bytes is None:
                    # Incomplete PNG at buffer tail; stop and carry remainder.
                    break
                blobs.append(png_bytes)
                search_pos = sig_idx + len(png_bytes)
            # Carry the tail so a PNG straddling the read boundary isn't lost.
            keep = min(_POC_GPAK_OVERLAP, len(buffer) - search_pos)
            carry = buffer[len(buffer) - keep:]
            base_offset += len(buffer) - keep
    return blobs


def _poc_read_one_png(buffer: bytes, start: int) -> bytes | None:
    """Parse a PNG by walking chunks; return full PNG bytes or None if truncated."""
    pos = start + len(_POC_PNG_SIG)
    buf_len = len(buffer)
    while pos + 8 <= buf_len:
        chunk_len = struct.unpack(">I", buffer[pos:pos + 4])[0]
        chunk_type = buffer[pos + 4:pos + 8]
        chunk_end = pos + 8 + chunk_len + 4  # +4 CRC
        if chunk_end > buf_len:
            return None
        if chunk_type == b"IEND":
            return buffer[start:chunk_end]
        pos = chunk_end
    return None


def _poc_load_from_gpak() -> Tuple[List[QPixmap], float]:
    gpak_path = _poc_project_root() / _POC_GPAK_REL
    started = time.perf_counter()
    pixmaps: List[QPixmap] = []
    if gpak_path.exists():
        png_blobs = _poc_extract_pngs_from_gpak(gpak_path, _POC_ICON_COUNT)
        for blob in png_blobs:
            pm = QPixmap()
            pm.loadFromData(blob, "PNG")
            pixmaps.append(pm)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return pixmaps, elapsed_ms


def _poc_load_from_extracted() -> Tuple[List[QPixmap], float]:
    root = _poc_project_root() / _POC_EXTRACTED_REL
    started = time.perf_counter()
    pixmaps: List[QPixmap] = []
    if root.exists():
        png_paths: List[str] = []
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if name.lower().endswith(".png"):
                    png_paths.append(os.path.join(dirpath, name))
                    if len(png_paths) >= _POC_ICON_COUNT:
                        break
            if len(png_paths) >= _POC_ICON_COUNT:
                break
        for fp in png_paths[:_POC_ICON_COUNT]:
            pm = QPixmap(fp)
            pixmaps.append(pm)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return pixmaps, elapsed_ms


def _poc_show_results_dialog(parent: QWidget, source_label: str,
                             pixmaps: List[QPixmap], elapsed_ms: float) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"PoC: from {source_label} — {elapsed_ms:.1f} ms ({len(pixmaps)} icons)")
    outer = QVBoxLayout(dlg)
    header = QLabel(
        f"Source: {source_label}    Loaded: {len(pixmaps)} icons    "
        f"Elapsed: {elapsed_ms:.2f} ms"
    )
    header.setStyleSheet("font-weight:bold; padding:6px;")
    outer.addWidget(header)

    scroll = QScrollArea(dlg)
    scroll.setWidgetResizable(True)
    inner = QWidget()
    grid = QGridLayout(inner)
    grid.setSpacing(4)
    for idx, pm in enumerate(pixmaps):
        lbl = QLabel()
        if not pm.isNull():
            lbl.setPixmap(pm.scaled(
                _POC_ICON_SIZE, _POC_ICON_SIZE,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            ))
        else:
            lbl.setText("(null)")
        lbl.setFixedSize(_POC_ICON_SIZE, _POC_ICON_SIZE)
        lbl.setAlignment(Qt.AlignCenter)
        grid.addWidget(lbl, idx // _POC_GRID_COLS, idx % _POC_GRID_COLS)
    scroll.setWidget(inner)
    outer.addWidget(scroll)
    dlg.resize(_POC_GRID_COLS * (_POC_ICON_SIZE + 8) + 40, 520)
    dlg.show()


def poc_on_click_load_gpak(parent: QWidget) -> None:
    """POC: button handler — load 50 icons from resources.gpak (Source A)."""
    pixmaps, elapsed_ms = _poc_load_from_gpak()
    _poc_show_results_dialog(parent, "gpak", pixmaps, elapsed_ms)


def poc_on_click_load_extracted(parent: QWidget) -> None:
    """POC: button handler — load 50 icons from extracted PNGs (Source B)."""
    pixmaps, elapsed_ms = _poc_load_from_extracted()
    _poc_show_results_dialog(parent, "extracted", pixmaps, elapsed_ms)


def add_poc_buttons(toolbar_layout, parent: QWidget) -> None:
    """POC: attach the two PoC benchmark buttons to a horizontal toolbar layout."""
    btn_gpak = QPushButton("PoC: Load 50 from gpak")
    btn_gpak.setFixedHeight(22)
    btn_gpak.setToolTip("PoC: scan resources.gpak for PNG signatures and load 50 as QPixmap.")
    btn_gpak.clicked.connect(lambda: poc_on_click_load_gpak(parent))
    toolbar_layout.addWidget(btn_gpak)

    btn_ext = QPushButton("PoC: Load 50 from extracted")
    btn_ext.setFixedHeight(22)
    btn_ext.setToolTip("PoC: load 50 PNG files from defect-investigation/.../gpak-image.")
    btn_ext.clicked.connect(lambda: poc_on_click_load_extracted(parent))
    toolbar_layout.addWidget(btn_ext)
