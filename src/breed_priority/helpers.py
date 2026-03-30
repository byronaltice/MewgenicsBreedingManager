"""Breed Priority — helper functions, color math, and collapsible-splitter widgets.

Standalone module — no imports from mewgenics_manager to avoid circular deps.
Functions that were previously in breed_priority_constants.py live here so
that the constants module stays declarative.
"""

from PySide6.QtWidgets import QSplitter, QSplitterHandle
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QBrush, QPainter, QFont, QFontMetrics



# ── Color math (delegated to ColorUtils) ─────────────────────────────────────

from .color_utils import ColorUtils


# ── Room style lookup ────────────────────────────────────────────────────────

def _room_style(display_name: str):
    """Return color string for a room display name, or None."""
    from .constants import _ROOM_STYLE
    return _ROOM_STYLE.get(display_name)


# ── Color mapping functions ──────────────────────────────────────────────────

def _rarity_chip_colors(n: int, threshold: float = 7.0) -> tuple:
    """Return (bg, fg) chip colors for a stat-at-7 chip.

    n <= threshold        → full green  (within scoring range, full points)
    n >= threshold + 10   → full grey   (very common, no score contribution)
    Values in between fade linearly from green to grey.
    """
    from .constants import _CHIP_DESIRABLE, _CHIP_UNDECIDED
    t = min(1.0, max(0.0, (n - threshold) / 10.0))
    return (
        ColorUtils.lerp(_CHIP_DESIRABLE[0], _CHIP_UNDECIDED[0], t),
        ColorUtils.lerp(_CHIP_DESIRABLE[1], _CHIP_UNDECIDED[1], t),
    )


def _sevens_color(count_7: int, max_7: int, positive_weight: bool) -> str:
    """Return gradient color for a cat with count_7 stats at 7, relative to max_7.

    The cat with the most 7s across the visible list gets the best color.
    With positive_weight=True:  0→red, max_7→green, midpoint→yellow
    With positive_weight=False: reversed (0→green, max_7→red)
    """
    from .constants import (
        CLR_TEXT_GRAYEDOUT, CLR_DESIRABLE, _CLR_RED, _CLR_YELLOW,
    )
    if max_7 == 0:
        return CLR_TEXT_GRAYEDOUT
    lo, hi = (_CLR_RED, CLR_DESIRABLE) if positive_weight else (CLR_DESIRABLE, _CLR_RED)
    t = count_7 / max_7  # 0.0 → 1.0
    if t <= 0.5:
        return ColorUtils.lerp(lo, _CLR_YELLOW, t * 2)
    else:
        return ColorUtils.lerp(_CLR_YELLOW, hi, (t - 0.5) * 2)

def _rank_colors(score_map: dict) -> dict:
    """Map categorical labels to display colors by relative rank.

    score_map: {label: score_value}

    Rules:
      - 3 distinct values: highest=green, middle=grey, lowest=red
      - 2 distinct values: highest=green, lower=grey  (no red - tied pair)
      - 1 distinct value : all grey  (3-way tie)
    """
    from .constants import (
        CLR_DESIRABLE, CLR_UNDESIRABLE, CLR_VALUE_NEUTRAL,
    )
    unique = sorted(set(score_map.values()), reverse=True)
    result = {}
    for label, score in score_map.items():
        if len(unique) == 1:
            result[label] = CLR_VALUE_NEUTRAL
        elif len(unique) == 2:
            result[label] = CLR_DESIRABLE if score == unique[0] else CLR_VALUE_NEUTRAL
        else:
            if score == unique[0]:
                result[label] = CLR_DESIRABLE
            elif score == unique[-1]:
                result[label] = CLR_UNDESIRABLE
            else:
                result[label] = CLR_VALUE_NEUTRAL
    return result


def _paired_weight_colors(w_a: float, w_b: float) -> tuple:
    """Return (color_a, color_b) for two related weights shown side-by-side.

    Rules:
      Both positive, equal   -> both green
      Both positive, unequal -> greater=green, lesser=yellow
      Both negative, equal   -> both red
      Both negative, unequal -> greater (less negative)=yellow, lesser=red
      Mixed signs            -> positive=green, negative=red
      Zero                   -> grey (no preference expressed)
    """
    from .constants import (
        CLR_DESIRABLE, CLR_NEUTRAL, CLR_UNDESIRABLE, CLR_VALUE_NEUTRAL,
    )
    def _sign(v): return 1 if v > 0 else (-1 if v < 0 else 0)
    sa, sb = _sign(w_a), _sign(w_b)
    if sa == 0 and sb == 0:
        return CLR_VALUE_NEUTRAL, CLR_VALUE_NEUTRAL
    if sa > 0 and sb > 0:
        if w_a > w_b: return CLR_DESIRABLE, CLR_NEUTRAL
        if w_b > w_a: return CLR_NEUTRAL,   CLR_DESIRABLE
        return CLR_DESIRABLE, CLR_DESIRABLE
    if sa < 0 and sb < 0:
        if w_a > w_b: return CLR_NEUTRAL,     CLR_UNDESIRABLE  # a less negative
        if w_b > w_a: return CLR_UNDESIRABLE, CLR_NEUTRAL       # b less negative
        return CLR_UNDESIRABLE, CLR_UNDESIRABLE
    # mixed signs or one is zero
    clr_a = CLR_DESIRABLE if sa > 0 else (CLR_UNDESIRABLE if sa < 0 else CLR_VALUE_NEUTRAL)
    clr_b = CLR_DESIRABLE if sb > 0 else (CLR_UNDESIRABLE if sb < 0 else CLR_VALUE_NEUTRAL)
    return clr_a, clr_b


def _sex_indicator_to_chip(color: str) -> tuple:
    """Map an indicator color string (from _paired_weight_colors) to a (bg, fg) chip pair."""
    from .constants import (
        CLR_DESIRABLE, CLR_UNDESIRABLE, CLR_NEUTRAL,
        CLR_TEXT_GRAYEDOUT, CLR_TEXT_SECONDARY,
        _CHIP_DESIRABLE, _CHIP_UNDESIRABLE, _CHIP_NEUTRAL,
    )
    if color == CLR_DESIRABLE:
        return _CHIP_DESIRABLE
    if color == CLR_UNDESIRABLE:
        return _CHIP_UNDESIRABLE
    if color == CLR_NEUTRAL:
        return _CHIP_NEUTRAL
    return (CLR_TEXT_GRAYEDOUT, CLR_TEXT_SECONDARY)   # grey / no preference


def _score_to_chip(score_val: float) -> tuple:
    """Map a score value to a (bg, fg) chip pair based on sign."""
    from .constants import _CHIP_DESIRABLE, _CHIP_UNDESIRABLE, _CHIP_DIM
    if score_val > 0:
        return _CHIP_DESIRABLE
    if score_val < 0:
        return _CHIP_UNDESIRABLE
    return _CHIP_DIM


# ── Cat data helpers ─────────────────────────────────────────────────────────

def _cat_injuries(cat, stat_names: list) -> list:
    """Return list of (injury_name, stat_key, delta) for stats with a negative total-vs-base delta.

    A negative delta (total_stats[stat] - base_stats[stat]) reliably indicates
    an injury or penalty for that stat.  delta is always < 0 (e.g. -1, -2).
    Returns an empty list when no injuries are detected or the data is absent.
    """
    from .constants import INJURY_STAT_NAMES
    injuries = []
    total = getattr(cat, 'total_stats', None)
    base  = getattr(cat, 'base_stats', None)
    if total is None or base is None:
        return injuries
    for sn in stat_names:
        b = base.get(sn, 0)
        t = total.get(sn, b)
        delta = t - b
        if delta < 0:
            name = INJURY_STAT_NAMES.get(sn, sn)
            injuries.append((name, sn, delta))
    return injuries


# ── Chip layout ──────────────────────────────────────────────────────────────

def _fit_chips(chips: list, available_width: int, fm: QFontMetrics) -> tuple:
    """Return (visible_chips, hidden_count) given available pixel width.

    Reserves room for a '+N' indicator pill when chips would overflow.
    """
    from .constants import _CHIP_PAD_X, _CHIP_GAP
    IND_W = fm.horizontalAdvance("+99") + 2 * _CHIP_PAD_X
    x = 4
    for i, (name, bg, fg) in enumerate(chips):
        chip_w = fm.horizontalAdvance(name) + 2 * _CHIP_PAD_X
        hidden = len(chips) - i
        # Need indicator room if any chips remain after this one
        extra = (_CHIP_GAP + IND_W) if hidden > 1 else 0
        if x + chip_w + extra > available_width - 2:
            return chips[:i], hidden
        x += chip_w + _CHIP_GAP
    return chips, 0


# ── Heatmap painting ─────────────────────────────────────────────────────────

def _paint_heatmap_bar(painter, rect, heat: float):
    """Draw a heatmap background bar into *rect*.  *heat* is signed normalised intensity."""
    from .constants import _HEAT_POS, _HEAT_NEG
    intensity = abs(heat)
    if intensity < 0.001:
        return
    base = _HEAT_POS if heat > 0 else _HEAT_NEG
    # Faint full-width wash so scored cells are distinguishable from unscored
    wash = QColor(base.red(), base.green(), base.blue(), 18)
    painter.fillRect(rect, wash)
    # Proportional bar on top
    alpha = int(30 + 130 * min(1.0, intensity))
    bar_color = QColor(base.red(), base.green(), base.blue(), alpha)
    bar_w = max(2, int(rect.width() * min(1.0, intensity)))
    painter.fillRect(QRect(rect.x(), rect.y(), bar_w, rect.height()), bar_color)
    # Bright left-edge indicator so scored cells are unmistakable
    edge_color = QColor(base.red(), base.green(), base.blue(), 200)
    painter.fillRect(QRect(rect.x(), rect.y(), 1, rect.height()), edge_color)


# ── Collapsible left-panel splitter ──────────────────────────────────────────

_LEFT_PANEL_W = 180   # expanded width of the left scope/weights panel


class _CollapseHandle(QSplitterHandle):
    """Vertical splitter handle that collapses/expands the left pane on click.

    Draws a centred tab indicator (◀ / ▶) instead of offering drag-to-resize.
    """

    _TAB_H   = 44
    _BG      = QColor("#131326")
    _TAB_BG  = QColor("#22224a")
    _TAB_BDR = QColor("#3a3a70")
    _ARROW   = QColor("#8888cc")
    _ARROW_H = QColor("#aaaaee")

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setCursor(Qt.ArrowCursor)
        self._hovered = False

    def sizeHint(self):
        sh = super().sizeHint()
        sh.setWidth(14)
        return sh

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.rect()

        # Background stripe
        painter.fillRect(r, self._BG)

        # Subtle centre line
        cx = r.width() // 2
        painter.setPen(QColor("#1e1e3a"))
        painter.drawLine(cx, 0, cx, r.height())

        # Tab pill centred vertically
        tab_w   = r.width() - 4
        tab_h   = self._TAB_H
        tab_x   = (r.width() - tab_w) // 2
        tab_y   = (r.height() - tab_h) // 2

        tab_color = self._TAB_BDR if self._hovered else self._TAB_BG
        painter.setBrush(QBrush(tab_color))
        painter.setPen(self._TAB_BDR)
        painter.drawRoundedRect(tab_x, tab_y, tab_w, tab_h, 4, 4)

        # Arrow (◀ collapsed → ▶ expand, ◀ expanded → collapse)
        collapsed = self.splitter().sizes()[0] == 0
        arrow = "▶" if collapsed else "◀"
        arrow_color = self._ARROW_H if self._hovered else self._ARROW
        painter.setPen(arrow_color)
        font = QFont()
        font.setPointSize(7)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(tab_x, tab_y, tab_w, tab_h, Qt.AlignCenter, arrow)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            s = self.splitter()
            sizes = s.sizes()
            if sizes[0] == 0:
                s.setSizes([_LEFT_PANEL_W, max(0, sizes[1])])
            else:
                s.setSizes([0, sizes[0] + sizes[1]])
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    # Swallow drag events so the handle is click-only
    def mouseMoveEvent(self, event):   event.ignore()
    def mouseReleaseEvent(self, event): event.ignore()


class _CollapseSplitter(QSplitter):
    """QSplitter that installs _CollapseHandle for all handles."""
    def createHandle(self):
        return _CollapseHandle(self.orientation(), self)
