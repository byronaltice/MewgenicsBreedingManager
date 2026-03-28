"""Tag definitions, icons, and pixmaps."""
from typing import Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QBrush, QPainter, QPixmap, QIcon, QPen, QPainterPath

from mewgenics.utils.config import _load_app_config, _save_app_config


TAG_PRESET_COLORS = [
    "#e74c3c", "#e67e22", "#f1c40f", "#2ecc71",
    "#3498db", "#9b59b6", "#e91e8a", "#95a5a6",
]

_TAG_DEFS: list[dict] = []  # [{id, name, color}, ...]
_TAG_ICON_CACHE: dict[tuple, QIcon] = {}
_TAG_PIX_CACHE: dict[tuple, QPixmap] = {}
_PIN_ICON_CACHE: dict[tuple[bool, int], QIcon] = {}


def _load_tag_definitions():
    """Load tag definitions from app config into module global."""
    global _TAG_DEFS
    cfg = _load_app_config()
    _TAG_DEFS = cfg.get("tag_definitions", [])


def _save_tag_definitions():
    """Save current tag definitions to app config."""
    cfg = _load_app_config()
    cfg["tag_definitions"] = _TAG_DEFS
    _save_app_config(cfg)
    _TAG_ICON_CACHE.clear()
    _TAG_PIX_CACHE.clear()


def _tag_color(tag_id: str) -> str:
    """Look up hex color for a tag ID, default gray."""
    for td in _TAG_DEFS:
        if td["id"] == tag_id:
            return td["color"]
    return "#555555"


def _tag_name(tag_id: str) -> str:
    """Look up display name for a tag ID."""
    for td in _TAG_DEFS:
        if td["id"] == tag_id:
            return td["name"] or ""
    return ""


def _next_tag_id() -> str:
    """Generate the next sequential tag ID."""
    existing = {td["id"] for td in _TAG_DEFS}
    i = 1
    while f"tag_{i}" in existing:
        i += 1
    return f"tag_{i}"


def _cat_tags(cat) -> list[str]:
    """Safely get tags list from a Cat, handling missing attribute."""
    return getattr(cat, 'tags', None) or []


def _make_tag_icon(tag_ids: list[str], dot_size: int = 10, spacing: int = 3) -> QIcon:
    """Create a QIcon with colored dots for the given tag IDs, ordered by definition."""
    if not tag_ids:
        return QIcon()
    tag_set = set(tag_ids)
    valid = [td["id"] for td in _TAG_DEFS if td["id"] in tag_set]
    if not valid:
        return QIcon()
    cache_key = tuple(valid)
    if cache_key in _TAG_ICON_CACHE:
        return _TAG_ICON_CACHE[cache_key]
    width = len(valid) * (dot_size + spacing) - spacing + 2
    height = dot_size + 2
    pix = QPixmap(width, height)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    for i, tid in enumerate(valid):
        color = QColor(_tag_color(tid))
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        x = i * (dot_size + spacing) + 1
        painter.drawEllipse(x, 1, dot_size, dot_size)
    painter.end()
    icon = QIcon(pix)
    _TAG_ICON_CACHE[cache_key] = icon
    return icon


def _make_tag_pixmap(tag_ids: list[str], dot_size: int = 10, spacing: int = 3) -> Optional[QPixmap]:
    """Create a QPixmap with colored dots for the given tag IDs, ordered by definition."""
    if not tag_ids:
        return None
    tag_set = set(tag_ids)
    valid = [td["id"] for td in _TAG_DEFS if td["id"] in tag_set]
    if not valid:
        return None
    cache_key = tuple(valid)
    if cache_key in _TAG_PIX_CACHE:
        return _TAG_PIX_CACHE[cache_key]
    width = len(valid) * (dot_size + spacing) - spacing + 4
    height = dot_size + 4
    pix = QPixmap(width, height)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    for i, tid in enumerate(valid):
        color = QColor(_tag_color(tid))
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        x = i * (dot_size + spacing) + 2
        painter.drawEllipse(x, 2, dot_size, dot_size)
    painter.end()
    _TAG_PIX_CACHE[cache_key] = pix
    return pix


def _make_pin_icon(active: bool = True, size: int = 16) -> QIcon:
    """Create a compact pushpin icon for pin states."""
    cache_key = (bool(active), int(size))
    cached = _PIN_ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)

    if active:
        head = QColor(224, 86, 86)
        stem = QColor(165, 52, 52)
        outline = QColor(86, 24, 24)
    else:
        head = QColor(118, 123, 154)
        stem = QColor(70, 74, 99)
        outline = QColor(30, 32, 44)

    # Leave a little breathing room so the glyph doesn't feel cramped in the button.
    painter.translate(size * 0.5, size * 0.5)
    painter.scale(0.86, 0.86)
    painter.rotate(-20)

    painter.setPen(QPen(outline, 0.8))
    painter.setBrush(QBrush(head))
    painter.drawEllipse(QPointF(0, -size * 0.18), size * 0.42, size * 0.42)

    path = QPainterPath()
    path.moveTo(-size * 0.05, -size * 0.02)
    path.lineTo(size * 0.10, size * 0.32)
    path.lineTo(-size * 0.08, size * 0.32)
    path.closeSubpath()
    painter.setBrush(QBrush(stem))
    painter.drawPath(path)
    painter.end()

    icon = QIcon(pix)
    _PIN_ICON_CACHE[cache_key] = icon
    return icon
