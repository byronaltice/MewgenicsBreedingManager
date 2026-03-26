"""Breed Priority view and scoring logic.

Standalone module - no imports from mewgenics_manager to avoid circular deps.
Game-specific helpers (STAT_NAMES, ROOM_DISPLAY, mutation_display_name,
ability_tip) are injected via compute_breed_priority_score() parameters and
BreedPriorityView.__init__() arguments.
"""

import os
import sys
import json

from breed_priority_filters import FilterState, FilterDialog, cat_passes_filter

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QSplitterHandle,
    QSizePolicy, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QListWidget, QListWidgetItem, QButtonGroup,
    QCheckBox, QComboBox, QLineEdit, QPushButton, QDialog, QGridLayout,
    QStyledItemDelegate, QApplication, QStyle,
)
from PySide6.QtCore import Qt, Signal, QTimer, QObject, QEvent, QRect, QSize
from PySide6.QtGui import QColor, QBrush, QPainter, QPen, QFont, QFontMetrics
from PySide6.QtWidgets import QToolTip


# ── Splitter handle styles ────────────────────────────────────────────────────

SPLITTER_V_STYLE = (
    "QSplitter::handle:vertical {"
    " min-height:6px;"
    " background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
    " stop:0 #131326, stop:0.25 #1a1a36, stop:0.45 #2e2e58,"
    " stop:0.5 #3c3c70, stop:0.55 #2e2e58, stop:0.75 #1a1a36, stop:1 #131326);"
    " }"
    "QSplitter::handle:vertical:hover {"
    " background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
    " stop:0 #16162e, stop:0.25 #22224a, stop:0.45 #44449a,"
    " stop:0.5 #5555c0, stop:0.55 #44449a, stop:0.75 #22224a, stop:1 #16162e);"
    " }"
)
SPLITTER_H_STYLE = (
    "QSplitter::handle:horizontal {"
    " min-width:6px;"
    " background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
    " stop:0 #131326, stop:0.25 #1a1a36, stop:0.45 #2e2e58,"
    " stop:0.5 #3c3c70, stop:0.55 #2e2e58, stop:0.75 #1a1a36, stop:1 #131326);"
    " }"
    "QSplitter::handle:horizontal:hover {"
    " background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
    " stop:0 #16162e, stop:0.25 #22224a, stop:0.45 #44449a,"
    " stop:0.5 #5555c0, stop:0.55 #44449a, stop:0.75 #22224a, stop:1 #16162e);"
    " }"
)


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


# ── Personality trait thresholds ─────────────────────────────────────────────
# Aggression/libido are stored as 0-1 floats; the game displays them as three
# levels.  These boundaries match in-game behaviour (verified against save data).

TRAIT_LOW_THRESHOLD  = 0.3   # < this  → "low"
TRAIT_HIGH_THRESHOLD = 0.7   # >= this → "high"

# ── Scoring constants ─────────────────────────────────────────────────────────

BREED_PRIORITY_WEIGHTS = {
    "stat_7":           5.0,
    "stat_7_threshold": 7.0,   # cats with 7 in a stat before score scales down
    "stat_7_count":     2.0,   # flat bonus per stat the cat personally has at 7 (additive)
    "unique_ma_max":    2.0,
    "low_aggression":  1.0,
    "unknown_gender":  1.0,
    "high_libido":     0.5,
    "high_aggression": -1.0,
    "low_libido":      -0.5,
    "gay_pref":        0.0,   # score applied to gay cats  (positive = favour, negative = penalise)
    "bi_pref":         0.0,   # score applied to bi cats
    "no_children":     4.0,
    "many_children":   -3.0,
    "stat_sum":        4.0,
    "age_penalty":    -2.0,   # score per year of age above threshold (negative = penalise older cats)
    "age_threshold":  10.0,   # cats at or below this age receive no age penalty
    "love_interest":      1.0,   # flat bonus when a love interest is in scope
    "rivalry":           -2.0,   # flat penalty when a rival is in scope
    "love_interest_room": 0.0,   # flat bonus when a love interest is in same room
    "rivalry_room":       0.0,   # flat penalty when a rival is in same room
    "seven_sub":           0.0,   # max score for cats whose 7-stat set is dominated by others in scope
    "seven_sub_threshold": 1.0,   # 7-sub count at which full score is applied (linear ramp from 0)
}

# (key, short label) - drives the weight editor on the left panel.
# (None, None) entries render as a thin separator line between groups.
# A string label renders left-aligned.
# A tuple label (group, sub) renders with group left-aligned and sub right-aligned,
#   letting two equal-rank options like High/Low appear visually equivalent.
# Labels starting with "  └" are styled as true sub-parameters (dimmed).
# Order mirrors SCORE_COLUMNS left-to-right so the panel is easy to scan.
WEIGHT_UI_ROWS = [
    ("stat_sum",         "Stat Sum"),                   # ── Sum ──
    (None, None),
    ("age_penalty",      "Age penalty"),               # ── Age ──
    ("age_threshold",    "  └ threshold"),
    (None, None),
    ("stat_7",           "7-rare"),                     # ── 7-rare / 7-cnt ──
    ("stat_7_threshold", "  └ threshold"),
    ("stat_7_count",     "7-count"),
    (None, None),
    ("seven_sub",          "7-Sub score"),               # ── 7-Sub ──
    ("seven_sub_threshold","  └ threshold"),
    (None, None),
    ("gay_pref",         ("Sexual", "Gay")),            # ── Sexual ──
    ("bi_pref",          ("",       "Bi")),
    (None, None),
    ("high_libido",      ("Libido", "High")),           # ── Libido ──
    ("low_libido",       ("",       "Low")),
    (None, None),
    ("unknown_gender",   "Unknown gender"),             # ── Gender? ──
    (None, None),
    ("no_children",      "Genetic Novelty"),            # ── Gene ──
    ("many_children",    "4+ children"),               # ── 4+Ch ──
    (None, None),
    ("high_aggression",  ("Aggro", "High")),            # ── Aggro ──
    ("low_aggression",   ("",      "Low")),
    (None, None),
    ("rivalry",            ("Hate", "In Scope")),        # ── Hate ──
    ("rivalry_room",       ("",     "In Room")),
    (None, None),
    ("love_interest",      ("Love", "In Scope")),        # ── Love ──
    ("love_interest_room", ("",     "In Room")),
    (None, None),
    ("unique_ma_max",    "Trait"),                      # ── Trait ──
]

# Score table columns - some weight keys are merged into one column.
# (column header, list of weight keys whose subtotals are summed for this column)
SCORE_COLUMNS = [
    ("Sum",        ["stat_sum"]),
    ("Age",        ["age_penalty"]),
    ("7-rare",     ["stat_7"]),
    ("7-cnt",      ["stat_7_count"]),
    ("7-Sub",      ["seven_sub"]),
    ("Sexual",     ["gay_pref", "bi_pref"]),
    ("Libido",     ["high_libido", "low_libido"]),
    ("Gender?",    ["unknown_gender"]),
    ("Gene",       ["no_children"]),
    ("4+Ch",       ["many_children"]),
    ("Aggro",      ["low_aggression", "high_aggression"]),
    ("Hate-Scope", ["rivalry"]),
    ("Hate-Room",  ["rivalry_room"]),
    ("Love-Scope", ["love_interest"]),
    ("Love-Room",  ["love_interest_room"]),
    ("Trait",      ["unique_ma_max"]),
]

_NUM_PROFILES = 5   # number of profile slots

# Column indices for the score table
# Name | Gender | Loc | Inj | STR DEX CON INT SPD CHA LCK | Sum Age 7-rare 7-cnt 7-Sub Sexual Libido Gender? Gene 4+Ch Aggro Hate-Scope Hate-Room Love-Scope Love-Room Trait | Score
COL_NAME        = 0
COL_GENDER      = 1
COL_LOC         = 2
COL_INJ         = 3
_STAT_COL_NAMES = ["STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK"]
_COL_STAT_START = 4
_NUM_STAT_COLS  = len(_STAT_COL_NAMES)
_SCORE_COLS     = [h for h, _ in SCORE_COLUMNS]
_COL_SCORE_START = _COL_STAT_START + _NUM_STAT_COLS   # = 11
COL_SCORE       = _COL_SCORE_START + len(SCORE_COLUMNS)
_ALL_HEADERS    = (
    ["Name", "Gender", "Loc", "Inj"]
    + _STAT_COL_NAMES
    + _SCORE_COLS
    + ["Score"]
)

# Room display name → (emoji, text color)
# Keys use the short form; _room_style() normalizes before lookup so locale
# variants like "Ground Floor Left" match the same entry as "Ground Left".
_ROOM_STYLE = {
    "Attic":        ("🏠", "#a0703a"),
    "Ground Left":  ("🍴", "#2aaa99"),
    "Ground Right": ("📺", "#c0a020"),
    "Second Left":  ("🛏️", "#aa66cc"),
    "Second Right": ("🚽", "#44aa66"),
}

def _room_style(display_name: str):
    """Return (emoji, color) for a room display name, normalizing away
    locale-injected words like 'Floor' so upstream locale changes don't
    break the lookup (e.g. 'Ground Floor Left' -> 'Ground Left')."""
    normalized = display_name.replace(" Floor", "")
    return _ROOM_STYLE.get(normalized) or _ROOM_STYLE.get(display_name)

# (threshold, label, color) - first match wins; None threshold = catch-all
BREED_PRIORITY_TIERS = [
    (10,   "Keep",     "#f0c060"),
    ( 4,   "Good",     "#1ec8a0"),
    ( 0,   "Neutral",  "#777777"),
    (-5,   "Consider", "#e08030"),
    (None, "Cull",     "#e04040"),
]

# Index → (display label, stored value or None to remove from dict)
TRAIT_RATING_OPTIONS = [
    ("Top Priority - sole owner +20, shared +10÷n", 2),
    ("Desirable - sole owner +4, shared +2÷n",     1),
    ("Neutral - reviewed, not scored",              0),
    ("Undecided - not yet reviewed",                None),
    ("Undesirable - scored −2",                    -1),
]
TRAIT_RATING_LABELS = [label for label, _ in TRAIT_RATING_OPTIONS]
TRAIT_RATING_VALUES = [val   for _, val  in TRAIT_RATING_OPTIONS]
RATING_SHORT_LABELS = ["Top Priority", "Desirable", "Neutral", "Undecided", "Undesirable"]
# Shared palette: Top Priority, Desirable, Neutral, Undecided, Undesirable
CLR_TOP_PRIORITY = "#40d0c0"
CLR_DESIRABLE  = "#6aaa6a"
CLR_NEUTRAL    = "#b0a040"
CLR_UNDECIDED  = "#888899"
CLR_UNDESIRABLE = "#aa6a6a"

# Sexuality display glyphs — swap these if a platform lacks glyph support.
# No single standard emoji exists for the bi pride flag, so we approximate with
# the three pride colours.
_SEX_EMOJI_GAY = "🏳️‍🌈"    # rainbow pride flag
_SEX_EMOJI_BI  = "BI"        # text label for bisexual
CLR_HIGHLIGHT  = "#eee"       # cat names and shared-cat name lists
RATING_ITEM_COLORS  = [CLR_TOP_PRIORITY, CLR_DESIRABLE, CLR_NEUTRAL, CLR_UNDECIDED, CLR_UNDESIRABLE]

# ── Injury display ────────────────────────────────────────────────────────────
# Maps stat name → confirmed in-game injury name.
# Stats not in this dict fall back to the stat key itself (e.g. "STR").
INJURY_STAT_NAMES = {
    "INT": "Concussion",
    "LCK": "Jinxed",
    "CHA": "Disfigured",
}
# Abbreviated display labels for the narrow Inj column
_INJ_SHORT = {
    "Concussion": "Conc",
    "Jinxed":     "Jinx",
    "Disfigured": "Disfig",
}

def _lerp_color(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two hex colors (#rrggbb). t clamped to [0,1]."""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )

def _lerp_step(c1: str, c2: str, total_steps: int, step: int) -> str:
    """Return interpolated color at *step* within a [1..total_steps] range.

    step=1 returns c1, step=total_steps returns c2.  Intermediate steps are
    evenly spread.  Mirrors the behaviour described by the user:
        _lerp_step(red, yellow, 5, 2)  →  25 % of the way from red to yellow
        _lerp_step(yellow, green, 3, 2) →  50 % of the way from yellow to green
    """
    if total_steps <= 1:
        return c2
    t = (step - 1) / (total_steps - 1)
    return _lerp_color(c1, c2, t)

# Color constants used for gradient coloring
_CLR_RED    = "#cc3333"
_CLR_YELLOW = "#b0a040"

def _rarity_chip_colors(n: int, threshold: float = 7.0) -> tuple:
    """Return (bg, fg) chip colors for a stat-at-7 chip.

    n <= threshold        → full green  (within scoring range, full points)
    n >= threshold + 10   → full grey   (very common, no score contribution)
    Values in between fade linearly from green to grey.
    """
    t = min(1.0, max(0.0, (n - threshold) / 10.0))
    return (
        _lerp_color(_CHIP_DESIRABLE[0], _CHIP_UNDECIDED[0], t),
        _lerp_color(_CHIP_DESIRABLE[1], _CHIP_UNDECIDED[1], t),
    )


def _sevens_color(count_7: int, max_7: int, positive_weight: bool) -> str:
    """Return gradient color for a cat with count_7 stats at 7, relative to max_7.

    The cat with the most 7s across the visible list gets the best color.
    With positive_weight=True:  0→red, max_7→green, midpoint→yellow
    With positive_weight=False: reversed (0→green, max_7→red)
    """
    if max_7 == 0:
        return "#555555"
    lo, hi = (_CLR_RED, CLR_DESIRABLE) if positive_weight else (CLR_DESIRABLE, _CLR_RED)
    t = count_7 / max_7  # 0.0 → 1.0
    if t <= 0.5:
        return _lerp_color(lo, _CLR_YELLOW, t * 2)
    else:
        return _lerp_color(_CLR_YELLOW, hi, (t - 0.5) * 2)

def _rank_colors(score_map: dict) -> dict:
    """Map categorical labels to display colors by relative rank.

    score_map: {label: score_value}

    Rules:
      - 3 distinct values: highest=green, middle=grey, lowest=red
      - 2 distinct values: highest=green, lower=grey  (no red - tied pair)
      - 1 distinct value : all grey  (3-way tie)
    """
    unique = sorted(set(score_map.values()), reverse=True)
    result = {}
    for label, score in score_map.items():
        if len(unique) == 1:
            result[label] = "#888888"
        elif len(unique) == 2:
            result[label] = CLR_DESIRABLE if score == unique[0] else "#888888"
        else:
            if score == unique[0]:
                result[label] = CLR_DESIRABLE
            elif score == unique[-1]:
                result[label] = CLR_UNDESIRABLE
            else:
                result[label] = "#888888"
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
    def _sign(v): return 1 if v > 0 else (-1 if v < 0 else 0)
    sa, sb = _sign(w_a), _sign(w_b)
    if sa == 0 and sb == 0:
        return "#888888", "#888888"
    if sa > 0 and sb > 0:
        if w_a > w_b: return CLR_DESIRABLE, CLR_NEUTRAL
        if w_b > w_a: return CLR_NEUTRAL,   CLR_DESIRABLE
        return CLR_DESIRABLE, CLR_DESIRABLE
    if sa < 0 and sb < 0:
        if w_a > w_b: return CLR_NEUTRAL,     CLR_UNDESIRABLE  # a less negative
        if w_b > w_a: return CLR_UNDESIRABLE, CLR_NEUTRAL       # b less negative
        return CLR_UNDESIRABLE, CLR_UNDESIRABLE
    # mixed signs or one is zero
    clr_a = CLR_DESIRABLE if sa > 0 else (CLR_UNDESIRABLE if sa < 0 else "#888888")
    clr_b = CLR_DESIRABLE if sb > 0 else (CLR_UNDESIRABLE if sb < 0 else "#888888")
    return clr_a, clr_b


def _sex_indicator_to_chip(color: str) -> tuple:
    """Map an indicator color string (from _paired_weight_colors) to a (bg, fg) chip pair."""
    if color == CLR_DESIRABLE:
        return _CHIP_DESIRABLE
    if color == CLR_UNDESIRABLE:
        return _CHIP_UNDESIRABLE
    if color == CLR_NEUTRAL:
        return _CHIP_NEUTRAL
    return ("#555555", "#cccccc")   # grey / no preference


def _cat_injuries(cat, stat_names: list) -> list:
    """Return list of (injury_name, stat_key, delta) for stats with a negative total-vs-base delta.

    A negative delta (total_stats[stat] - base_stats[stat]) reliably indicates
    an injury or penalty for that stat.  delta is always < 0 (e.g. -1, -2).
    Returns an empty list when no injuries are detected or the data is absent.
    """
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


_PRIORITY_TABLE_STYLE = """
    QTableWidget {
        background:#0d0d1c; alternate-background-color:#131326;
        color:#ddd; border:none; font-size:12px;
    }
    QTableWidget::item {
        padding:3px 4px;
        border-right:1px solid #16213e;
    }
    QTableWidget::item:selected { background:#1e3060; color:#fff; }
    QHeaderView::section {
        background:#16213e; color:#888; padding:5px 4px;
        border:none; border-bottom:1px solid #1e1e38;
        border-right:1px solid #16213e;
        font-size:11px; font-weight:bold;
    }
    QScrollBar:vertical { background:#0d0d1c; width:10px; }
    QScrollBar::handle:vertical {
        background:#252545; border-radius:5px; min-height:20px;
    }
"""

_PRIORITY_COMBO_STYLE = (
    "QComboBox { background:#131326; color:#ccc; border:1px solid #252545;"
    " padding:1px 4px; font-size:11px; }"
    "QComboBox:hover { border-color:#3a3a7a; }"
    "QComboBox::drop-down { border:none; }"
    "QComboBox QAbstractItemView { background:#131326; color:#ccc;"
    " selection-background-color:#1e3060; border:1px solid #252545; }"
)


# ── Scoring helpers ───────────────────────────────────────────────────────────

class ScoreResult:
    __slots__ = ("total", "tier", "tier_color", "breakdown", "subtotals",
                 "scope_relatives_count")

    def __init__(self, total: float, tier: str, tier_color: str, breakdown: list,
                 subtotals: dict | None = None, scope_relatives_count: int = 0):
        self.total = total
        self.tier = tier
        self.tier_color = tier_color
        self.breakdown = breakdown
        self.subtotals = subtotals or {}
        self.scope_relatives_count = scope_relatives_count


def priority_tier(score: float) -> tuple:
    for threshold, label, color in BREED_PRIORITY_TIERS:
        if threshold is None or score >= threshold:
            return label, color
    return "Cull", "#e04040"


def is_basic_trait(name: str) -> bool:
    """Return True for generic starter traits that should be ignored."""
    return name.lower().startswith("basic")


def ability_base(name: str) -> str:
    """Strip trailing '2' if present (e.g. 'Vurp2' → 'Vurp'). When Breeding, we only care about the base ability."""
    if len(name) > 1 and name[-1] == "2":
        return name[:-1]
    return name


def compute_breed_priority_score(cat, scope_cats: list, ma_ratings: dict,
                         stat_names: list, weights: dict = None,
                         mutation_display_name=None,
                         scope_stat_sums: list = None,
                         hated_by: list = None) -> ScoreResult:
    """Compute breed priority score for a cat.

    stat_names: ordered list of stat keys (e.g. ["STR","DEX",...]).
    mutation_display_name: callable(str) -> str for display labels in breakdown.
    ma_ratings: {trait_key: int} where 1=Desirable, 0=Neutral, -1=Undesirable.
      Ability keys are base ability names; mutation keys are display strings.
    scope_stat_sums: sorted list of total base-stat sums for all scope cats,
      used to compute percentile rank for stat_sum scoring.
    hated_by: list of cats (in scope/room) that have *this* cat as their rival.
    """
    _w = weights if weights is not None else BREED_PRIORITY_WEIGHTS
    _display = mutation_display_name if mutation_display_name else (lambda n: n)
    breakdown: list = []
    subtotals: dict = {
        "stat_7": 0.0, "stat_7_count": 0.0, "unique_ma_max": 0.0,
        "low_aggression": 0.0, "high_aggression": 0.0,
        "unknown_gender": 0.0,
        "high_libido": 0.0, "low_libido": 0.0,
        "no_children": 0.0, "many_children": 0.0,
        "stat_sum": 0.0, "age_penalty": 0.0,
        "love_interest": 0.0, "rivalry": 0.0,
    }
    scope_set = {id(c) for c in scope_cats}
    _cat_in_scope = id(cat) in scope_set

    # ── Positive attributes ───────────────────────────────────────────────────
    if cat.gender == "?":
        breakdown.append(("Unknown gender (?)", _w["unknown_gender"]))
        subtotals["unknown_gender"] = _w["unknown_gender"]

    if cat.aggression is not None and cat.aggression < TRAIT_LOW_THRESHOLD:
        breakdown.append(("Low aggression", _w["low_aggression"]))
        subtotals["low_aggression"] = _w["low_aggression"]

    if cat.libido is not None and cat.libido >= TRAIT_HIGH_THRESHOLD:
        breakdown.append(("High libido", _w["high_libido"]))
        subtotals["high_libido"] = _w["high_libido"]

    _sex = getattr(cat, 'sexuality', 'straight') or 'straight'
    if _sex == 'gay' and _w.get("gay_pref", 0.0) != 0.0:
        breakdown.append(("Gay", _w["gay_pref"]))
        subtotals["gay_pref"] = _w["gay_pref"]
    elif _sex == 'bi' and _w.get("bi_pref", 0.0) != 0.0:
        breakdown.append(("Bi", _w["bi_pref"]))
        subtotals["bi_pref"] = _w["bi_pref"]

    _TARGET_N = int(round(_w.get("stat_7_threshold", 7.0)))  # cats with a 7 before score scales down
    _STAT7_BASE = _w["stat_7"]
    for stat_name in stat_names:
        if cat.base_stats.get(stat_name) == 7:
            n_scope = sum(1 for c in scope_cats if c.base_stats.get(stat_name) == 7)
            n = n_scope if _cat_in_scope else n_scope + 1
            # Sole owner of a 7 in this stat - extra bonus
            if n == 1:
                w = _w["stat_7"] * 2
                label = f"7 in {stat_name} (sole ★★)"
            # Full user weight up to target; beyond target, overflow portion
            # uses the default base weight so user increases favour the first 7
            elif n <= _TARGET_N:
                w = _w["stat_7"]
                label = f"7 in {stat_name} ({n} in scope)"
            else:
                w = round(_STAT7_BASE * _TARGET_N / n, 3)
                label = f"7 in {stat_name} ({n} in scope, ÷{n / _TARGET_N:.1f})"
            breakdown.append((label, float(w)))
            subtotals["stat_7"] += float(w)

    # ── 7-count bonus: scaled by how many 7's this cat personally owns ────────
    _w_7ct = _w.get("stat_7_count", 0.0)
    if _w_7ct != 0.0:
        _n_sevens = sum(1 for sn in stat_names if cat.base_stats.get(sn) == 7)
        if _n_sevens > 0:
            _7ct_pts = round(_w_7ct * _n_sevens, 3)
            _s = "s" if _n_sevens != 1 else ""
            breakdown.append((f"{_n_sevens} stat{_s} at 7", _7ct_pts))
            subtotals["stat_7_count"] = _7ct_pts

    # Combined trait set per scope cat (ability base names + mutation display strings)
    scope_base_traits = {
        id(c): (
            {ability_base(a) for a in list(c.abilities) + list(c.passive_abilities) + list(getattr(c, 'disorders', []))}
            | set(c.mutations)
            | set(getattr(c, 'defects', []))
        )
        for c in scope_cats
    }
    _u = _w["unique_ma_max"]

    # Score abilities (active + passive), normalized to base names
    all_ability_bases = list({
        ability_base(m) for m in list(cat.abilities) + list(cat.passive_abilities) + list(getattr(cat, 'disorders', []))
        if not is_basic_trait(m)
    })
    def _score_trait(label: str, rating, n: int):
        if rating in (None, 0):
            return
        if n == 1:
            if rating == 2:
                pts = 10 * _u
                tag = "Sole owner (top priority)"
            elif rating == 1:
                pts = 2 * _u
                tag = "Sole owner (desirable)"
            else:
                pts = -_u
                tag = "Sole owner (undesirable)"
        elif rating == 2:
            pts = round(5 * _u / n, 3)
            tag = f"Top Priority (÷{n})"
        elif rating == 1:
            pts = round(_u / n, 3)
            tag = f"Desirable (÷{n})"
        elif rating == -1:
            pts = -_u
            tag = "Undesirable"
        else:
            return
        breakdown.append((f"{tag}: {label}", pts))
        subtotals["unique_ma_max"] += pts

    for ma in all_ability_bases:
        rating = ma_ratings.get(ma)
        n_scope = sum(1 for c in scope_cats if ma in scope_base_traits[id(c)])
        n = max(1, n_scope if _cat_in_scope else n_scope + 1)
        _score_trait(_display(ma), rating, n)

    # Score visual mutations (keyed by display string from cat.mutations)
    for ma in cat.mutations:
        if is_basic_trait(ma):
            continue
        rating = ma_ratings.get(ma)
        n_scope = sum(1 for c in scope_cats if ma in scope_base_traits[id(c)])
        n = max(1, n_scope if _cat_in_scope else n_scope + 1)
        _score_trait(ma, rating, n)

    # Score birth defects (visual mutation IDs 700-706)
    for ma in getattr(cat, 'defects', []):
        if is_basic_trait(ma):
            continue
        rating = ma_ratings.get(ma)
        n_scope = sum(1 for c in scope_cats if ma in scope_base_traits[id(c)])
        n = max(1, n_scope if _cat_in_scope else n_scope + 1)
        _score_trait(ma, rating, n)

    # ── Negative attributes ───────────────────────────────────────────────────
    if cat.aggression is not None and cat.aggression >= TRAIT_HIGH_THRESHOLD:
        breakdown.append(("High aggression", _w["high_aggression"]))
        subtotals["high_aggression"] = _w["high_aggression"]

    if cat.libido is not None and cat.libido < TRAIT_LOW_THRESHOLD:
        breakdown.append(("Low libido", _w["low_libido"]))
        subtotals["low_libido"] = _w["low_libido"]

    # Genetic Novelty: no relatives in comparison scope
    relatives_in_scope: list = []
    frontier = [cat]
    visited = {id(cat)}
    while frontier:
        node = frontier.pop()
        for rel in [node.parent_a, node.parent_b] + list(node.children):
            if rel is None or id(rel) in visited:
                continue
            visited.add(id(rel))
            if id(rel) in scope_set and id(rel) != id(cat):
                relatives_in_scope.append(rel)
                frontier.append(rel)
    children_in_scope = [c for c in cat.children if id(c) in scope_set]

    if not relatives_in_scope:
        breakdown.append(("Genetic Novelty", _w["no_children"]))
        subtotals["no_children"] = _w["no_children"]
    if len(children_in_scope) >= 4:
        breakdown.append((
            f"{len(children_in_scope)} children in scope (≥4)",
            _w["many_children"],
        ))
        subtotals["many_children"] = _w["many_children"]

    # ── Stat sum percentile scoring ───────────────────────────────────────────
    w_sum = _w.get("stat_sum", 0.0)
    if w_sum != 0 and scope_stat_sums:
        cat_sum = sum(cat.base_stats.values())
        n = len(scope_stat_sums)
        rank = sum(1 for v in scope_stat_sums if v <= cat_sum)
        pct = rank / n * 100
        if pct >= 90:
            pts = w_sum
        elif pct >= 75:
            pts = max(0.0, w_sum - 1)
        elif pct >= 50:
            pts = max(0.0, w_sum - 2)
        else:
            pts = 0.0
        if pts:
            breakdown.append((f"Stat sum {cat_sum} ({pct:.0f}th percentile)", pts))
            subtotals["stat_sum"] = pts

    # ── Age penalty ───────────────────────────────────────────────────────────
    w_age = _w.get("age_penalty", 0.0)
    if w_age != 0.0:
        age = getattr(cat, 'age', None)
        if age is not None:
            _age_thr = int(round(_w.get("age_threshold", 10.0)))
            if age > _age_thr:
                _over = age - _age_thr
                _mult = 1 + (_over - 1) // 3
                pts = round(_mult * w_age, 2)
                breakdown.append((f"Age {age} (+{_over} over threshold, {_mult}×)", pts))
                subtotals["age_penalty"] = pts

    # ── Love interest bonus ────────────────────────────────────────────────────
    w_love = _w.get("love_interest", 0.0)
    if w_love != 0.0:
        for lover in getattr(cat, 'lovers', []):
            if id(lover) in scope_set:
                pts = round(w_love, 2)
                breakdown.append((f"Loves {lover.name} (in scope)", pts))
                subtotals["love_interest"] = pts
                break  # flat bonus - only once

    # ── Rivalry penalty ────────────────────────────────────────────────────────
    w_rival = _w.get("rivalry", 0.0)
    if w_rival != 0.0:
        _rival_total = 0.0
        # Cat's own rivals in scope
        for hater in getattr(cat, 'haters', []):
            if id(hater) in scope_set:
                pts = round(w_rival, 2)
                breakdown.append((f"Hates {hater.name} (in scope)", pts))
                _rival_total += pts
        # Cats in scope that hate this cat (reverse)
        for hater in (hated_by or []):
            if id(hater) in scope_set and hater not in getattr(cat, 'haters', []):
                pts = round(w_rival, 2)
                breakdown.append((f"Hated by {hater.name} (in scope)", pts))
                _rival_total += pts
        if _rival_total:
            subtotals["rivalry"] = _rival_total

    # ── Love interest (room) bonus ─────────────────────────────────────────────
    w_love_room = _w.get("love_interest_room", 0.0)
    if w_love_room != 0.0:
        _cat_room = getattr(cat, 'room', None)
        if _cat_room:
            for lover in getattr(cat, 'lovers', []):
                if getattr(lover, 'room', None) == _cat_room:
                    pts = round(w_love_room, 2)
                    breakdown.append((f"Loves {lover.name} (in room)", pts))
                    subtotals["love_interest_room"] = pts
                    break

    # ── Rivalry (room) penalty ─────────────────────────────────────────────────
    w_rival_room = _w.get("rivalry_room", 0.0)
    if w_rival_room != 0.0:
        _cat_room = getattr(cat, 'room', None)
        if _cat_room:
            _rr_total = 0.0
            for hater in getattr(cat, 'haters', []):
                if getattr(hater, 'room', None) == _cat_room:
                    pts = round(w_rival_room, 2)
                    breakdown.append((f"Hates {hater.name} (in room)", pts))
                    _rr_total += pts
            for hater in (hated_by or []):
                if hater not in getattr(cat, 'haters', []) and getattr(hater, 'room', None) == _cat_room:
                    pts = round(w_rival_room, 2)
                    breakdown.append((f"Hated by {hater.name} (in room)", pts))
                    _rr_total += pts
            if _rr_total:
                subtotals["rivalry_room"] = _rr_total

    total = sum(pts for _, pts in breakdown)
    tier, color = priority_tier(total)
    return ScoreResult(total=total, tier=tier, tier_color=color,
                       breakdown=breakdown, subtotals=subtotals,
                       scope_relatives_count=len(relatives_in_scope))


# Custom data role for chip data stored on Trait column items
_CHIP_ROLE             = Qt.UserRole + 2
_SCORE_SECONDARY_ROLE  = Qt.UserRole + 3   # score string shown below value in "both" mode
_HEATMAP_ROLE          = Qt.UserRole + 4   # float 0..1 intensity for heatmap mode (sign from score)

# Chip appearance constants
_CHIP_H       = 15   # chip height px
_CHIP_PAD_X   = 5    # horizontal text padding inside chip
_CHIP_GAP     = 4    # gap between chips
_CHIP_RADIUS  = 5    # corner radius

# Chip color pairs (bg, fg) by rating
_CHIP_TOP_PRIORITY = ("#004040", "#60e8d8")   # dark teal bg,  bright teal text
_CHIP_DESIRABLE   = ("#1d4a1d", "#a0e8a0")   # dark green bg, light green text
_CHIP_UNDESIRABLE = ("#4a1d1d", "#e8a0a0")   # dark red bg,   light red text
_CHIP_NEUTRAL     = ("#3a3a10", "#d8d870")   # dark yellow bg, yellow text
_CHIP_UNDECIDED   = ("#252535", "#888888")   # dark grey bg,   grey text


def _fit_chips(chips: list, available_width: int, fm: QFontMetrics) -> tuple:
    """Return (visible_chips, hidden_count) given available pixel width.

    Reserves room for a '+N' indicator pill when chips would overflow.
    """
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


class _ChipOverflowPopup(QFrame):
    """Frameless popup that shows all chips in a multi-row layout.
    Uses Qt.Popup so it auto-dismisses when focus is lost.
    """
    _PAD   = 8
    _ROW_H = _CHIP_H + 6
    _MAX_W = 340

    def __init__(self, chips: list, global_pos):
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._chips = chips
        self._rows  = self._layout()
        n = len(self._rows)
        h = self._PAD * 2 + n * self._ROW_H + max(0, n - 1) * 2
        self.setFixedSize(self._MAX_W, h)
        # Position below click, clamped to screen
        screen = QApplication.primaryScreen().availableGeometry()
        px = min(global_pos.x(), screen.right()  - self._MAX_W)
        py = min(global_pos.y() + 6, screen.bottom() - h)
        self.move(px, py)

    def _layout(self):
        fm = QFontMetrics(QApplication.font())
        rows, row, x = [], [], self._PAD
        for chip in self._chips:
            w = fm.horizontalAdvance(chip[0]) + 2 * _CHIP_PAD_X
            if row and x + w > self._MAX_W - self._PAD:
                rows.append(row)
                row, x = [], self._PAD
            row.append(chip)
            x += w + _CHIP_GAP
        if row:
            rows.append(row)
        return rows

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#12122a"))
        painter.drawRoundedRect(self.rect(), 6, 6)
        painter.setPen(QColor("#334466"))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)

        fm = QFontMetrics(painter.font())
        y = self._PAD
        for row in self._rows:
            x = self._PAD
            chip_y = y + (self._ROW_H - _CHIP_H) // 2
            for name, bg, fg in row:
                w = fm.horizontalAdvance(name) + 2 * _CHIP_PAD_X
                r = QRect(x, chip_y, w, _CHIP_H)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(bg))
                painter.drawRoundedRect(r, _CHIP_RADIUS, _CHIP_RADIUS)
                painter.setPen(QColor(fg))
                painter.drawText(r, Qt.AlignCenter, name)
                x += w + _CHIP_GAP
            y += self._ROW_H + 2
        painter.end()


class _TraitChipDelegate(QStyledItemDelegate):
    """Renders trait name chips with individual per-trait colored pill backgrounds.
    Shows a '+N' overflow indicator when the column is too narrow, and opens
    a floating popup with all chips on click.
    """

    def paint(self, painter, option, index):
        chips = index.data(_CHIP_ROLE)
        if not chips:
            super().paint(painter, option, index)
            return

        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, option.widget)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        fm         = QFontMetrics(painter.font())
        chip_top   = option.rect.y() + (option.rect.height() - _CHIP_H) // 2
        x          = option.rect.x() + 4
        avail      = option.rect.width()
        visible, hidden_count = _fit_chips(chips, avail, fm)

        for name, bg_color, text_color in visible:
            chip_w  = fm.horizontalAdvance(name) + 2 * _CHIP_PAD_X
            chip_rect = QRect(x, chip_top, chip_w, _CHIP_H)
            painter.setBrush(QColor(bg_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(chip_rect, _CHIP_RADIUS, _CHIP_RADIUS)
            painter.setPen(QColor(text_color))
            painter.drawText(chip_rect, Qt.AlignCenter, name)
            x += chip_w + _CHIP_GAP

        if hidden_count:
            ind_text = f"+{hidden_count}"
            ind_w    = fm.horizontalAdvance(ind_text) + 2 * _CHIP_PAD_X
            ind_rect = QRect(x, chip_top, ind_w, _CHIP_H)
            painter.setBrush(QColor("#2a2a3a"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(ind_rect, _CHIP_RADIUS, _CHIP_RADIUS)
            painter.setPen(QColor("#8888bb"))
            painter.drawText(ind_rect, Qt.AlignCenter, ind_text)

        _score_sub = index.data(_SCORE_SECONDARY_ROLE)
        if _score_sub:
            _sf = QFont(painter.font())
            _sf.setPointSizeF(max(6.0, _sf.pointSizeF() * 0.72))
            painter.setFont(_sf)
            painter.setPen(QColor(CLR_DESIRABLE if _score_sub.startswith("+") else CLR_UNDESIRABLE if _score_sub.startswith("-") else "#666677"))
            _sub_rect = QRect(option.rect.x(), option.rect.bottom() - QFontMetrics(_sf).height() - 1,
                              option.rect.width(), QFontMetrics(_sf).height() + 2)
            painter.drawText(_sub_rect, Qt.AlignCenter, _score_sub)

        painter.restore()

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        return QSize(sh.width(), max(sh.height(), _CHIP_H + 8))


class _SexChipDelegate(QStyledItemDelegate):
    """Renders the Sexual column as a single pill chip with a ~30 % larger font."""

    def paint(self, painter, option, index):
        chips = index.data(_CHIP_ROLE)
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, option.widget)

        if not chips:
            # Score mode: draw plain centred text with the item's foreground colour
            text = index.data(Qt.DisplayRole) or ""
            if text:
                fg = index.data(Qt.ForegroundRole)
                painter.save()
                if fg:
                    painter.setPen(fg.color() if hasattr(fg, "color") else QColor(str(fg)))
                painter.drawText(option.rect, Qt.AlignCenter, text)
                painter.restore()
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        font = painter.font()
        if font.pointSizeF() > 0:
            font.setPointSizeF(font.pointSizeF() * 1.3)
        else:
            # Font uses pixel size — scale that instead
            px = font.pixelSize()
            if px > 0:
                font.setPixelSize(int(px * 1.3))
        painter.setFont(font)
        fm = QFontMetrics(font)

        chip_h   = fm.height() + 4
        chip_top = option.rect.y() + (option.rect.height() - chip_h) // 2
        name, bg_color, text_color = chips[0]
        chip_w   = fm.horizontalAdvance(name) + 2 * _CHIP_PAD_X
        x        = option.rect.x() + max(4, (option.rect.width() - chip_w) // 2)
        chip_rect = QRect(x, chip_top, chip_w, chip_h)

        painter.setBrush(QColor(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(chip_rect, _CHIP_RADIUS, _CHIP_RADIUS)
        painter.setPen(QColor(text_color))
        painter.drawText(chip_rect, Qt.AlignCenter, name)

        _score_sub = index.data(_SCORE_SECONDARY_ROLE)
        if _score_sub:
            _sf = QFont(painter.font())
            _sf.setPointSizeF(max(6.0, _sf.pointSizeF() * 0.72))
            painter.setFont(_sf)
            painter.setPen(QColor(CLR_DESIRABLE if _score_sub.startswith("+") else CLR_UNDESIRABLE if _score_sub.startswith("-") else "#666677"))
            _sub_rect = QRect(option.rect.x(), option.rect.bottom() - QFontMetrics(_sf).height() - 1,
                              option.rect.width(), QFontMetrics(_sf).height() + 2)
            painter.drawText(_sub_rect, Qt.AlignCenter, _score_sub)

        painter.restore()

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        return QSize(sh.width(), max(sh.height(), _CHIP_H + 8))


# ── Both-mode delegate ────────────────────────────────────────────────────────

class _BothModeDelegate(QStyledItemDelegate):
    """For 'Both' display mode: renders value text (top) + score subscript (bottom, dim, smaller)."""

    def paint(self, painter, option, index):
        score_sub = index.data(_SCORE_SECONDARY_ROLE)
        if not score_sub:
            super().paint(painter, option, index)
            return

        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, option.widget)

        painter.save()
        r = option.rect
        # Primary text – upper ~60% of cell
        val_rect = QRect(r.x(), r.y(), r.width(), int(r.height() * 0.62))
        fg = index.data(Qt.ForegroundRole)
        if fg:
            painter.setPen(fg.color() if hasattr(fg, "color") else QColor(str(fg)))
        text = index.data(Qt.DisplayRole) or ""
        painter.drawText(val_rect, Qt.AlignCenter, text)
        # Score sub – lower ~38% of cell, smaller dim font
        _sf = QFont(painter.font())
        _sf.setPointSizeF(max(6.0, _sf.pointSizeF() * 0.72))
        painter.setFont(_sf)
        painter.setPen(QColor(CLR_DESIRABLE if score_sub.startswith("+") else CLR_UNDESIRABLE if score_sub.startswith("-") else "#666677"))
        sub_rect = QRect(r.x(), r.y() + int(r.height() * 0.60), r.width(), r.height() - int(r.height() * 0.60))
        painter.drawText(sub_rect, Qt.AlignCenter, score_sub)
        painter.restore()


class _HeatmapDelegate(QStyledItemDelegate):
    """'Heatmap' display mode: shows value text with a colored background bar
    whose intensity reflects the score magnitude.  Green = positive, red = negative.
    The bar fills the cell width proportionally to the normalised intensity stored
    in ``_HEATMAP_ROLE`` (0.0–1.0).  Falls through to ``_BothModeDelegate`` /
    default for chip columns.
    """

    _POS_COLOR = QColor(106, 170, 106, 55)   # CLR_DESIRABLE at low alpha
    _NEG_COLOR = QColor(170, 106, 106, 55)   # CLR_UNDESIRABLE at low alpha

    def paint(self, painter, option, index):
        heat = index.data(_HEATMAP_ROLE)
        if heat is None:
            super().paint(painter, option, index)
            return

        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, option.widget)

        painter.save()
        r = option.rect

        # Draw heat bar — fill from left, width proportional to intensity
        intensity = abs(heat)
        if intensity > 0.001:
            base = self._POS_COLOR if heat > 0 else self._NEG_COLOR
            # Scale alpha: min 30, max 160
            alpha = int(30 + 130 * min(1.0, intensity))
            bar_color = QColor(base.red(), base.green(), base.blue(), alpha)
            bar_w = max(2, int(r.width() * min(1.0, intensity)))
            painter.fillRect(QRect(r.x(), r.y(), bar_w, r.height()), bar_color)

        # Draw value text on top
        fg = index.data(Qt.ForegroundRole)
        if fg:
            painter.setPen(fg.color() if hasattr(fg, "color") else QColor(str(fg)))
        text = index.data(Qt.DisplayRole) or ""
        painter.drawText(r, Qt.AlignCenter, text)

        painter.restore()


# ── Hate-row overlay ──────────────────────────────────────────────────────────

class _HateRowOverlay(QWidget):
    """Transparent overlay on the score-table viewport that draws a red outline
    around any row whose cat is hated by the currently selected cat.

    Sits above all items (transparent to mouse), redraws on scroll/resize.
    """

    _PEN_COLOR = "#bb2222"
    _PEN_WIDTH = 2

    def __init__(self, table):
        super().__init__(table.viewport())
        self._table = table
        self._hate_cat_ids: set[int] = set()
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Geometry is synced lazily in paintEvent; also connect scroll so we repaint
        table.verticalScrollBar().valueChanged.connect(self._sync_and_update)
        table.horizontalScrollBar().valueChanged.connect(self._sync_and_update)
        table.viewport().installEventFilter(self)

    def _sync_and_update(self):
        """Keep overlay covering the full viewport, then repaint."""
        vp = self._table.viewport()
        r = vp.rect()
        if self.geometry() != r:
            self.setGeometry(r)
        self.raise_()
        self.update()

    def set_hate_ids(self, cat_ids: set[int]):
        self._hate_cat_ids = cat_ids
        self._sync_and_update()

    def eventFilter(self, obj, event):
        if obj is self._table.viewport() and event.type() in (QEvent.Resize, QEvent.Show):
            self._sync_and_update()
        return False

    def paintEvent(self, _event):
        # Sync geometry at paint time so it's always correct
        vp_rect = self._table.viewport().rect()
        if self.geometry() != vp_rect:
            self.setGeometry(vp_rect)
            self.raise_()
        if not self._hate_cat_ids:
            return
        table = self._table
        painter = QPainter(self)
        pen = QPen(QColor(self._PEN_COLOR))
        pen.setWidth(self._PEN_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        p = self._PEN_WIDTH // 2
        vw = self.width()
        for r in range(table.rowCount()):
            if table.isRowHidden(r):
                continue
            name_item = table.item(r, COL_NAME)
            if name_item is None:
                continue
            if name_item.data(Qt.UserRole + 1) not in self._hate_cat_ids:
                continue
            # visualRect gives the item's rectangle in viewport coordinates — reliable
            # regardless of sort order, scroll position, or header height.
            vis = table.visualRect(table.indexFromItem(name_item))
            if not vis.isValid() or vis.bottom() < 0 or vis.top() > self.height():
                continue
            painter.drawRect(QRect(p, vis.y() + p, vw - self._PEN_WIDTH,
                                   vis.height() - self._PEN_WIDTH))
        painter.end()


# ── UI helpers ────────────────────────────────────────────────────────────────

class _NumericSortItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically via Qt.UserRole."""

    def __lt__(self, other: "QTableWidgetItem") -> bool:
        try:
            return float(self.data(Qt.UserRole)) < float(other.data(Qt.UserRole))
        except (TypeError, ValueError):
            return super().__lt__(other)


class _RatingCombo(QComboBox):
    """Rating combo that shows short labels collapsed, long labels in dropdown."""

    def __init__(self):
        super().__init__()
        self.wheelEvent = lambda e: e.ignore()
        self.addItems(RATING_SHORT_LABELS)

    def showPopup(self):
        for i, long in enumerate(TRAIT_RATING_LABELS):
            self.setItemText(i, long)
        super().showPopup()

    def hidePopup(self):
        super().hidePopup()
        for i, short in enumerate(RATING_SHORT_LABELS):
            self.setItemText(i, short)


class _SortHighlightHeader(QHeaderView):
    """Horizontal header that paints the sorted column with a visible highlight.

    All other sections are delegated to the normal QHeaderView paint path.
    The sorted section gets a brighter background, bolder label colour, and
    the sort-direction arrow drawn explicitly - no separate sort-label needed.
    """

    _NORMAL_BG   = QColor("#16213e")
    _SORTED_BG   = QColor("#1a3060")
    _NORMAL_FG   = QColor("#888888")
    _SORTED_FG   = QColor("#ccd8f0")
    _BORDER_R    = QColor("#16213e")
    _BORDER_B    = QColor("#1e1e38")

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self._sort_col   = -1
        self._sort_order = Qt.DescendingOrder

    def set_sort(self, col: int, order):
        self._sort_col   = col
        self._sort_order = order
        self.viewport().update()

    def mousePressEvent(self, event):
        # Qt toggles sort direction when the indicator is already on the
        # clicked column.  By silently pre-seeding the indicator to Ascending
        # on a *new* column (signals blocked so no sort fires), Qt's normal
        # click handler will toggle it to Descending - one sort, correct order.
        col = self.logicalIndexAt(event.pos())
        if col != self._sort_col and col >= 0:
            self.blockSignals(True)
            self.setSortIndicator(col, Qt.AscendingOrder)
            self.blockSignals(False)
        super().mousePressEvent(event)

    def paintSection(self, painter, rect, logical_idx):
        if logical_idx != self._sort_col:
            super().paintSection(painter, rect, logical_idx)
            return

        painter.save()
        painter.setClipRect(rect)

        # Highlighted background
        painter.fillRect(rect, self._SORTED_BG)

        # Right + bottom borders to match other sections
        painter.setPen(self._BORDER_R)
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
        painter.setPen(self._BORDER_B)
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        # Label + arrow
        label = self.model().headerData(logical_idx, Qt.Horizontal, Qt.DisplayRole) or ""
        arrow = " ▼" if self._sort_order == Qt.DescendingOrder else " ▲"
        font = painter.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() - 1)   # match the 11px style
        painter.setFont(font)
        painter.setPen(self._SORTED_FG)
        painter.drawText(
            rect.adjusted(4, 0, -4, 0),
            Qt.AlignCenter,
            str(label) + arrow,
        )

        painter.restore()


class _HeaderTooltipFilter(QObject):
    """Event filter that shows per-column tooltips on QHeaderView hover."""

    def __init__(self, header, tips: dict):
        super().__init__(header)
        self._header = header
        self._tips = tips   # {col_idx: str}
        header.viewport().setMouseTracking(True)
        header.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        t = event.type()
        if t in (QEvent.MouseMove, QEvent.Type.ToolTip):
            col = self._header.logicalIndexAt(event.pos())
            tip = self._tips.get(col, "")
            gpos = obj.mapToGlobal(event.pos())
            if tip:
                QToolTip.showText(gpos, tip, obj)
            else:
                QToolTip.hideText()
            return t == QEvent.Type.ToolTip   # suppress native ToolTip; pass MouseMove
        return False


class _FastTooltipFilter(QObject):
    """Event filter that shows QTableWidget item tooltips with a short custom delay,
    and handles chip-overflow popup on click.

    Intercepts MouseMove on the table viewport to start a short timer, then calls
    QToolTip.showText() directly - bypassing the platform's ~700ms default delay.
    Also suppresses the system QEvent.ToolTip so it can't re-trigger late.
    On MouseButtonRelease, checks whether the clicked cell has chip overflow and
    shows the _ChipOverflowPopup if so.
    """

    DELAY_MS = 60    # ~1/12th of the typical 700ms system tooltip delay

    def __init__(self, table: QTableWidget):
        super().__init__(table)
        self._table  = table
        self._tip    = ""
        self._gpos   = None
        self._timer  = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.DELAY_MS)
        self._timer.timeout.connect(self._show)
        self._chip_popup       = None   # keep reference to prevent GC
        self._pending_popup    = None   # (chips, gpos) deferred until event loop clears
        table.viewport().setMouseTracking(True)
        table.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.MouseMove:
            lpos  = event.position().toPoint()
            item  = self._table.itemAt(lpos)
            tip   = item.toolTip() if item else ""
            gpos  = self._table.viewport().mapToGlobal(lpos)
            self._gpos = gpos
            if tip != self._tip:
                self._tip = tip
                self._timer.stop()
                QToolTip.hideText()
                if tip:
                    self._timer.start()
        elif t == QEvent.MouseButtonRelease:
            lpos  = event.position().toPoint()
            item  = self._table.itemAt(lpos)
            if item is not None:
                chips = item.data(_CHIP_ROLE)
                if chips:
                    fm = QFontMetrics(QApplication.font())
                    col  = self._table.column(item)
                    col_w = self._table.columnWidth(col)
                    _, hidden = _fit_chips(chips, col_w, fm)
                    if hidden:
                        gpos = self._table.viewport().mapToGlobal(lpos)
                        # Defer until event loop is clear so Qt.Popup grab
                        # doesn't fight with in-flight mouse events
                        self._pending_popup = (chips, gpos)
                        QTimer.singleShot(0, self._show_chip_popup)
        elif t == QEvent.Leave:
            self._timer.stop()
            QToolTip.hideText()
            self._tip = ""
        elif t == QEvent.Type.ToolTip:
            # Suppress the platform-delayed tooltip; we handle it ourselves
            return True
        return False

    def _show(self):
        if self._tip and self._gpos:
            QToolTip.showText(self._gpos, self._tip)

    def _show_chip_popup(self):
        if self._pending_popup:
            chips, gpos = self._pending_popup
            self._pending_popup = None
            self._chip_popup = _ChipOverflowPopup(chips, gpos)
            self._chip_popup.show()


class _ListTooltipFilter(QObject):
    """Fast tooltip filter for QListWidget — shows item tooltips with a short delay."""

    DELAY_MS = 60

    def __init__(self, lst: QListWidget):
        super().__init__(lst)
        self._list  = lst
        self._tip   = ""
        self._gpos  = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.DELAY_MS)
        self._timer.timeout.connect(self._show)
        lst.viewport().setMouseTracking(True)
        lst.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.MouseMove:
            lpos = event.position().toPoint()
            item = self._list.itemAt(lpos)
            tip  = item.toolTip() if item else ""
            gpos = self._list.viewport().mapToGlobal(lpos)
            self._gpos = gpos
            if tip != self._tip:
                self._tip = tip
                self._timer.stop()
                QToolTip.hideText()
                if tip:
                    self._timer.start()
        elif t == QEvent.Leave:
            self._timer.stop()
            QToolTip.hideText()
            self._tip = ""
        elif t == QEvent.Type.ToolTip:
            return True
        return False

    def _show(self):
        if self._tip and self._gpos:
            QToolTip.showText(self._gpos, self._tip)


class _WeightSpin(QWidget):
    """Compact value editor with visible ▲/▼ buttons."""
    valueChanged = Signal(float)

    _BTN_STYLE = (
        "QPushButton { color:#ccc; background:#3a3a60; border:1px solid #4a4a80;"
        " font-size:8px; padding:0; }"
        "QPushButton:hover { background:#5050a0; }"
        "QPushButton:pressed { background:#6060c0; }"
    )
    _LBL_BASE = (
        "background:#131326;"
        " border:1px solid #252545; border-right:none;"
    )

    def __init__(self, value: float, min_val=-20.0, max_val=20.0, step=0.5):
        super().__init__()
        self._value = float(value)
        self._min   = min_val
        self._max   = max_val
        self._step  = step

        hb = QHBoxLayout(self)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(0)

        self._lbl = QLabel(self._fmt(self._value))
        self._lbl.setFixedWidth(36)
        self._lbl.setAlignment(Qt.AlignCenter)
        _f = self._lbl.font()
        _f.setPointSize(8)
        self._lbl.setFont(_f)
        self._update_color()

        btn_col = QWidget()
        bv = QVBoxLayout(btn_col)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(0)

        up = QPushButton("▲")
        up.setFixedSize(18, 11)
        up.setStyleSheet(self._BTN_STYLE)
        up.clicked.connect(self._inc)

        dn = QPushButton("▼")
        dn.setFixedSize(18, 11)
        dn.setStyleSheet(self._BTN_STYLE)
        dn.clicked.connect(self._dec)

        bv.addWidget(up)
        bv.addWidget(dn)
        hb.addWidget(self._lbl)
        hb.addWidget(btn_col)

    @staticmethod
    def _fmt(v: float) -> str:
        return f"{v:+.1f}"

    def _update_color(self):
        if self._value > 0:
            clr = CLR_DESIRABLE
        elif self._value < 0:
            clr = CLR_UNDESIRABLE
        else:
            clr = "#555566"
        self._lbl.setStyleSheet(f"color:{clr}; {self._LBL_BASE}")

    def _set(self, val: float):
        val = round(max(self._min, min(self._max, val)) / self._step) * self._step
        if val != self._value:
            self._value = val
            self._lbl.setText(self._fmt(val))
            self._update_color()
            if not self.signalsBlocked():
                self.valueChanged.emit(val)

    def _inc(self): self._set(self._value + self._step)
    def _dec(self): self._set(self._value - self._step)

    def value(self) -> float:
        return self._value

    def setValue(self, val: float):
        self._value = float(val)
        self._lbl.setText(self._fmt(self._value))
        self._update_color()


class _IntParamSpin(_WeightSpin):
    """Integer-only variant of _WeightSpin - shows plain integers, no +/- sign.

    Used for parameters like stat_7_threshold that are natural counts (1–20).
    """

    def _update_color(self):
        # Threshold / count parameters: always plain; no sign-based colouring
        self._lbl.setStyleSheet(f"color:#aaa; {self._LBL_BASE}")

    def __init__(self, value: int, min_val=1, max_val=20, step=1):
        super().__init__(float(value), float(min_val), float(max_val), float(step))
        self._lbl.setText(self._fmt(self._value))

    @staticmethod
    def _fmt(v: float) -> str:
        return str(int(round(v)))

    def _set(self, val: float):
        val = float(max(self._min, min(self._max, round(val))))
        if val != self._value:
            self._value = val
            self._lbl.setText(self._fmt(val))
            if not self.signalsBlocked():
                self.valueChanged.emit(val)

    def setValue(self, val: float):
        self._value = float(round(val))
        self._lbl.setText(self._fmt(self._value))


class _ProfileNameEdit(QLineEdit):
    """QLineEdit that accepts focus via single-click without selecting all text."""
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if not self.hasSelectedText():
            self.deselect()


class _ConfirmDialog(QDialog):
    """Simple dark-themed confirmation dialog with a message and Ok/Cancel buttons."""

    def __init__(self, title: str, message: str, ok_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setStyleSheet(
            "QDialog { background:#0f0f22; }"
            "QLabel  { color:#ccccdd; font-size:12px; background:transparent; border:none; }"
            "QPushButton { background:#14142e; color:#8899bb; border:1px solid #2a2a55;"
            "  border-radius:4px; padding:5px 18px; font-size:12px; }"
            "QPushButton:hover { background:#1c1c3a; color:#ccd; border-color:#4444aa; }"
            "QPushButton#ok { background:#0e2030; color:#88aadd; border-color:#2244aa; }"
            "QPushButton#ok:hover { background:#122840; color:#aaccff; border-color:#3366cc; }"
        )
        vb = QVBoxLayout(self)
        vb.setContentsMargins(24, 20, 24, 16)
        vb.setSpacing(16)
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        vb.addWidget(msg_lbl)
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton(ok_label)
        ok.setObjectName("ok")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addSpacing(8)
        btns.addWidget(ok)
        vb.addLayout(btns)
        self.setMinimumWidth(340)


# ── Main view ─────────────────────────────────────────────────────────────────

class BreedPriorityView(QWidget):
    """Shows breed priority (keep vs cull) scores for all alive cats.

    Args:
        ratings_path: Path to the JSON file used to persist ratings/weights.
        stat_names: Ordered list of stat keys (e.g. ["STR","DEX",...]).
        room_display: Dict mapping room keys to display strings.
        mutation_display_name: Callable(str) -> str; converts trait IDs to labels.
        ability_tip: Callable(str) -> str; returns tooltip text for a trait.
    """

    def __init__(self, ratings_path: str, stat_names: list, room_display: dict,
                 mutation_display_name, ability_tip):
        super().__init__()
        self._cats: list = []
        self._ratings_path = ratings_path
        self._stat_names = stat_names
        self._room_display = room_display
        self._display_name = mutation_display_name
        self._ability_tip  = ability_tip
        self._ma_ratings: dict = {}
        self._room_checks: dict = {}
        self._saved_scope: dict = {}
        self._weights: dict = dict(BREED_PRIORITY_WEIGHTS)
        self._weight_spins: dict = {}
        self._populating = False
        self._all_abilities: list = []
        self._all_mutations: list = []
        self._selected_cat = None
        self._hated_by_map: dict[int, list] = {}
        self._hide_kittens = False
        self._hide_out_of_scope = False
        self._display_mode = "score"   # "score" | "values" | "both"
        self._show_stats = False
        self._sort_col: int = COL_SCORE
        self._sort_order = Qt.DescendingOrder
        self._filters = FilterState()
        self._col_widths: dict = {}
        self._active_profile: int = 1   # currently selected profile slot
        self._loaded_profile: int = 1   # which profile's data is in memory
        self._profiles: dict = {}       # {int: dict} explicitly saved profile blobs
        self._profile_snapshot: dict = {} # serialized state when last profile was loaded
        self._profile_name_text: str = ""  # display name for the currently-loaded profile
        self._profile_traits_only: bool = False  # only save/load trait desirability ratings
        self._load_ratings()
        self._build_ui()
        self._col_save_timer = QTimer(self)
        self._col_save_timer.setSingleShot(True)
        self._col_save_timer.setInterval(600)
        self._col_save_timer.timeout.connect(self._save_ratings)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_ratings(self):
        if os.path.exists(self._ratings_path):
            try:
                with open(self._ratings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for section in ("abilities", "mutations"):
                    for trait, val in data.get(section, {}).items():
                        if val in (-1, 0, 1, 2):
                            self._ma_ratings[trait] = val
                self._saved_scope = data.get("scope", {})
                for key in BREED_PRIORITY_WEIGHTS:
                    if key in data.get("weights", {}):
                        self._weights[key] = float(data["weights"][key])
                self._hide_kittens = bool(data.get("hide_kittens", False))
                self._hide_out_of_scope = bool(data.get("hide_out_of_scope", False))
                _sv = data.get("display_mode", "values" if data.get("show_values", False) else "score")
                self._display_mode = _sv if _sv in ("score", "values", "both", "heatmap") else "score"
                self._show_stats = bool(data.get("show_stats", False))
                self._sort_col = int(data.get("sort_col", COL_SCORE))
                self._sort_order = (
                    Qt.DescendingOrder if data.get("sort_desc", True)
                    else Qt.AscendingOrder
                )
                if "filters" in data:
                    self._filters = FilterState.from_dict(data["filters"])
                self._col_widths = {
                    int(k): int(v) for k, v in data.get("col_widths", {}).items()
                }
                # Profile slots
                self._active_profile = int(data.get("active_profile", 1))
                self._loaded_profile = int(data.get("loaded_profile", 1))
                self._profiles = {
                    int(k): v for k, v in data.get("profiles", {}).items()
                }
                self._profile_snapshot = self._profiles.get(self._loaded_profile, {})
                self._profile_name_text = self._profile_snapshot.get("name", "")
                self._profile_traits_only = bool(data.get("profile_traits_only", False))
            except Exception:
                pass

    def _save_ratings(self):
        ability_set = {
            ability_base(a)
            for c in self._cats
            for a in list(c.abilities) + list(c.passive_abilities) + list(getattr(c, 'disorders', []))
            if not is_basic_trait(a)
        }
        mutation_set = {m for c in self._cats for m in list(c.mutations) + list(getattr(c, 'defects', []))}
        data = {
            "abilities": {k: v for k, v in self._ma_ratings.items() if k in ability_set},
            "mutations": {k: v for k, v in self._ma_ratings.items() if k in mutation_set},
            "scope": self._saved_scope,
            "weights": self._weights,
            "hide_kittens": self._hide_kittens,
            "hide_out_of_scope": self._hide_out_of_scope,
            "display_mode": self._display_mode,
            "show_stats": self._show_stats,
            "sort_col": self._sort_col,
            "sort_desc": self._sort_order == Qt.DescendingOrder,
            "filters": self._filters.to_dict(),
            "col_widths": {str(k): v for k, v in self._col_widths.items()},
            # Profile slots (separate from working state)
            "active_profile": self._active_profile,
            "loaded_profile": self._loaded_profile,
            "profiles": {str(k): v for k, v in self._profiles.items()},
            "profile_traits_only": self._profile_traits_only,
        }
        try:
            os.makedirs(os.path.dirname(self._ratings_path), exist_ok=True)
            with open(self._ratings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
        self._update_profile_bar()

    # ── Profile management ─────────────────────────────────────────────────────

    def _serialize_current(self) -> dict:
        """Snapshot of all current settings in profile-blob format."""
        return {
            "name": self._profile_name_text,
            "ma_ratings": dict(self._ma_ratings),
            "scope": self._saved_scope,
            "weights": dict(self._weights),
            "hide_kittens": self._hide_kittens,
            "hide_out_of_scope": self._hide_out_of_scope,
            "display_mode": self._display_mode,
            "show_stats": self._show_stats,
            "sort_col": self._sort_col,
            "sort_desc": self._sort_order == Qt.DescendingOrder,
            "filters": self._filters.to_dict(),
        }

    def _is_dirty(self) -> bool:
        """True if current settings differ from the last-loaded profile snapshot."""
        if not self._profile_snapshot:
            return False
        if self._profile_traits_only:
            return self._ma_ratings != self._profile_snapshot.get("ma_ratings", {})
        return self._serialize_current() != self._profile_snapshot

    def _apply_profile_data(self, data: dict):
        """Apply a profile blob to all instance vars and refresh every UI widget."""
        # Weights
        new_w = data.get("weights", {})
        for key in BREED_PRIORITY_WEIGHTS:
            self._weights[key] = float(new_w.get(key, BREED_PRIORITY_WEIGHTS[key]))
        if self._weight_spins:
            self._populating = True
            for key, spin in self._weight_spins.items():
                spin.blockSignals(True)
                spin.setValue(self._weights.get(key, BREED_PRIORITY_WEIGHTS[key]))
                spin.blockSignals(False)
            self._populating = False

        # Trait ratings
        self._ma_ratings = {k: v for k, v in data.get("ma_ratings", {}).items()
                            if v in (-1, 0, 1, 2)}

        # Scope
        self._saved_scope = data.get("scope", {})

        # Options
        self._hide_kittens      = bool(data.get("hide_kittens", False))
        self._hide_out_of_scope = bool(data.get("hide_out_of_scope", False))
        _sv = data.get("display_mode", "values" if data.get("show_values", False) else "score")
        self._display_mode      = _sv if _sv in ("score", "values", "both", "heatmap") else "score"
        self._show_stats        = bool(data.get("show_stats", False))
        self._sort_col          = int(data.get("sort_col", COL_SCORE))
        self._sort_order        = (Qt.DescendingOrder if data.get("sort_desc", True)
                                   else Qt.AscendingOrder)
        if "filters" in data:
            self._filters = FilterState.from_dict(data["filters"])

        # Profile name
        self._profile_name_text = data.get("name", "")
        if hasattr(self, "_profile_name_edit"):
            self._profile_name_edit.blockSignals(True)
            self._profile_name_edit.setText(self._profile_name_text)
            self._profile_name_edit.blockSignals(False)

        # Stop here if UI hasn't been built yet
        if not hasattr(self, "_chk_hide_kittens"):
            return

        # Option checkboxes
        for chk, val in [
            (self._chk_hide_kittens,      self._hide_kittens),
            (self._chk_hide_out_of_scope, self._hide_out_of_scope),
            (self._chk_show_stats,        self._show_stats),
        ]:
            chk.blockSignals(True)
            chk.setChecked(val)
            chk.blockSignals(False)

        # Segmented display-mode control
        if hasattr(self, "_btn_mode_score"):
            _mode_map = {"score": self._btn_mode_score,
                         "values": self._btn_mode_values,
                         "both": self._btn_mode_both,
                         "heatmap": self._btn_mode_heatmap}
            for _b in _mode_map.values():
                _b.blockSignals(True)
            _mode_map.get(self._display_mode, self._btn_mode_score).setChecked(True)
            for _b in _mode_map.values():
                _b.blockSignals(False)
            self._score_table.setItemDelegate(
                self._heatmap_delegate if self._display_mode == "heatmap" else self._both_delegate)
        self._apply_stat_column_visibility()

        # Scope UI
        all_cats_on  = self._saved_scope.get("all_cats", True)
        saved_rooms  = self._saved_scope.get("rooms", {})
        self._chk_all_cats.blockSignals(True)
        self._chk_all_cats.setChecked(all_cats_on)
        self._chk_all_cats.blockSignals(False)
        for room, chk in self._room_checks.items():
            chk.blockSignals(True)
            chk.setChecked(all_cats_on or saved_rooms.get(room, False))
            chk.blockSignals(False)

        # Sort indicator
        _hdr = self._score_table.horizontalHeader()
        _hdr.blockSignals(True)
        _hdr.setSortIndicator(self._sort_col, self._sort_order)
        _hdr._sort_col = self._sort_col
        _hdr.blockSignals(False)

        # Trait tables + recompute
        if self._cats:
            for defect in getattr(self, "_defect_names", set()):
                if defect not in self._ma_ratings:
                    self._ma_ratings[defect] = -1
            self._selected_cat = None
            self._populate_trait_table(self._abilities_table, self._all_abilities)
            self._populate_trait_table(self._mutations_table, self._all_mutations)
        self.recompute()
        self._update_filter_btn()

    def _update_profile_bar(self):
        """Refresh profile button styles, name widgets, and status indicators."""
        if not hasattr(self, "_profile_btns"):
            return
        dirty  = self._is_dirty()
        active = self._active_profile
        loaded = self._loaded_profile
        for n, btn in self._profile_btns.items():
            sel   = (n == active)
            ld    = (n == loaded)
            has   = (n in self._profiles)
            if sel and ld:
                style = "background:#0a1e18; color:#aaddcc; border:2px solid #1ec8a0;"
            elif sel and has:
                style = "background:#0e1828; color:#88aadd; border:2px solid #3355aa;"
            elif sel:
                # selected but empty — dim blue dashed
                style = "background:#090916; color:#445577; border:2px dashed #1e2d55;"
            elif ld:
                style = "background:#0a1a16; color:#5a9a88; border:2px solid #1a4a44;"
            elif has:
                # filled, not selected/loaded — slightly brighter than empty
                style = "background:#0e0e26; color:#404070; border:1px solid #22224a;"
            else:
                # empty, unselected — very dim
                style = "background:#080818; color:#22223a; border:1px dashed #141428;"
            btn.setStyleSheet(
                f"QPushButton {{ {style} border-radius:6px; font-size:22px; font-weight:bold; }}"
                f"QPushButton:hover {{ color:#aaaaee; border-color:#4444aa; }}"
            )
        # Name row: show selected profile's name as a preview when it differs from loaded
        if hasattr(self, "_profile_name_edit"):
            if active != loaded:
                sel_name = self._profiles.get(active, {}).get("name", "") or ""
                self._profile_sel_name_lbl.setText(sel_name or f"Profile {active}")
                self._profile_sel_name_lbl.setVisible(True)
                self._profile_sel_arrow_lbl.setVisible(True)
            else:
                self._profile_sel_name_lbl.setVisible(False)
                self._profile_sel_arrow_lbl.setVisible(False)
        if active != loaded:
            self._profile_loaded_lbl.setText(f"Loaded: {loaded}  -  Load or Save to sync")
            self._profile_loaded_lbl.setVisible(True)
        else:
            self._profile_loaded_lbl.setVisible(False)
        self._profile_dirty_lbl.setVisible(dirty)

    def _build_profile_bar(self) -> QWidget:
        """Build the centered profile selector bar above the score table."""
        bar = QWidget()
        bar.setStyleSheet("background:#07071a; border-bottom:1px solid #111130;")
        vb = QVBoxLayout(bar)
        vb.setContentsMargins(0, 4, 0, 4)
        vb.setSpacing(4)

        # ── Name row ──────────────────────────────────────────────────────────
        name_row = QWidget()
        name_row.setStyleSheet("background:transparent;")
        nh = QHBoxLayout(name_row)
        nh.setContentsMargins(0, 0, 0, 0)
        nh.setSpacing(6)
        nh.addStretch()

        # Editable name for the currently-loaded profile (green tint)
        self._profile_name_edit = _ProfileNameEdit()
        self._profile_name_edit.setFixedWidth(200)
        self._profile_name_edit.setFixedHeight(24)
        self._profile_name_edit.setPlaceholderText("Profile name…")
        self._profile_name_edit.setText(self._profile_name_text)
        self._profile_name_edit.setStyleSheet(
            "QLineEdit {"
            "  background:#071812; color:#aaddcc;"
            "  border:1px solid #1a5040; border-radius:4px;"
            "  padding:0 6px; font-size:11px;"
            "}"
            "QLineEdit:focus { border-color:#1ec8a0; }"
        )
        self._profile_name_edit.textChanged.connect(self._on_profile_name_changed)
        nh.addWidget(self._profile_name_edit)

        # Arrow + selected profile name preview (blue tint) — shown when active != loaded
        self._profile_sel_arrow_lbl = QLabel("➜")
        self._profile_sel_arrow_lbl.setStyleSheet("color:#334466; font-size:18px;")
        self._profile_sel_arrow_lbl.setVisible(False)
        nh.addWidget(self._profile_sel_arrow_lbl)

        self._profile_sel_name_lbl = QLabel()
        self._profile_sel_name_lbl.setFixedWidth(160)
        self._profile_sel_name_lbl.setStyleSheet(
            "color:#88aadd; background:#080e1a; border:1px solid #223366;"
            " border-radius:4px; padding:0 6px; font-size:11px;"
        )
        self._profile_sel_name_lbl.setVisible(False)
        nh.addWidget(self._profile_sel_name_lbl)

        nh.addSpacing(16)

        # "Traits only" checkbox — affects Save/Load behaviour
        self._chk_traits_only = QCheckBox("Only Trait Desirability")
        self._chk_traits_only.setChecked(self._profile_traits_only)
        self._chk_traits_only.setToolTip(
            "When checked, Save only stores Trait Desirability ratings into the profile\n"
            "and Load only restores those ratings — weights and other settings are untouched."
        )
        self._chk_traits_only.setStyleSheet("color:#667788; font-size:10px;")
        self._chk_traits_only.stateChanged.connect(self._on_traits_only_changed)
        nh.addWidget(self._chk_traits_only)

        nh.addStretch()
        vb.addWidget(name_row)

        # ── Button row ────────────────────────────────────────────────────────
        btn_row = QWidget()
        btn_row.setStyleSheet("background:transparent;")
        hb = QHBoxLayout(btn_row)
        hb.setContentsMargins(16, 0, 16, 0)
        hb.setSpacing(0)
        hb.addStretch()

        lbl = QLabel("PROFILES")
        lbl.setStyleSheet(
            "color:#282850; font-size:10px; font-weight:bold; letter-spacing:2px;"
        )
        hb.addWidget(lbl)
        hb.addSpacing(12)

        self._profile_btns = {}
        for n in range(1, _NUM_PROFILES + 1):
            btn = QPushButton(str(n))
            btn.setFixedSize(44, 36)
            btn.clicked.connect(lambda _=False, n=n: self._on_profile_btn_clicked(n))
            self._profile_btns[n] = btn
            hb.addWidget(btn)
            if n < _NUM_PROFILES:
                hb.addSpacing(4)

        hb.addSpacing(20)

        _act_style = (
            "QPushButton { background:#0e1a2e; color:#7799bb; border:1px solid #1a2a44;"
            "  border-radius:4px; padding:2px 12px; font-size:11px; }"
            "QPushButton:hover { background:#122236; color:#99bbdd; border-color:#2a4a6a; }"
        )
        self._profile_load_btn = QPushButton("Load")
        self._profile_load_btn.setFixedHeight(28)
        self._profile_load_btn.setStyleSheet(_act_style)
        self._profile_load_btn.clicked.connect(self._on_profile_load)
        hb.addWidget(self._profile_load_btn)
        hb.addSpacing(6)

        self._profile_save_btn = QPushButton("Save")
        self._profile_save_btn.setFixedHeight(28)
        self._profile_save_btn.setStyleSheet(_act_style)
        self._profile_save_btn.clicked.connect(self._on_profile_save)
        hb.addWidget(self._profile_save_btn)
        hb.addSpacing(6)

        _del_style = (
            "QPushButton { background:#1a0e0e; color:#885555; border:1px solid #3a1a1a;"
            "  border-radius:4px; padding:2px 10px; font-size:11px; }"
            "QPushButton:hover { background:#2a1212; color:#cc7777; border-color:#662222; }"
        )
        self._profile_delete_btn = QPushButton("Delete")
        self._profile_delete_btn.setFixedHeight(28)
        self._profile_delete_btn.setStyleSheet(_del_style)
        self._profile_delete_btn.setToolTip("Delete the selected profile slot, restoring it to empty")
        self._profile_delete_btn.clicked.connect(self._on_profile_delete)
        hb.addWidget(self._profile_delete_btn)
        hb.addSpacing(16)

        self._profile_loaded_lbl = QLabel()
        self._profile_loaded_lbl.setStyleSheet("color:#445566; font-size:11px;")
        self._profile_loaded_lbl.setVisible(False)
        hb.addWidget(self._profile_loaded_lbl)
        hb.addSpacing(8)

        self._profile_dirty_lbl = QLabel("● Modified")
        self._profile_dirty_lbl.setStyleSheet("color:#bb8822; font-size:11px;")
        self._profile_dirty_lbl.setVisible(False)
        hb.addWidget(self._profile_dirty_lbl)

        hb.addStretch()
        vb.addWidget(btn_row)

        self._update_profile_bar()
        return bar

    def _on_profile_name_changed(self, text: str):
        """User edited the profile name — update state and mark dirty."""
        self._profile_name_text = text
        self._save_ratings()

    def _on_traits_only_changed(self, state: int):
        self._profile_traits_only = bool(state)
        self._save_ratings()

    def _on_profile_btn_clicked(self, n: int):
        self._active_profile = n
        self._update_profile_bar()

    def _on_profile_load(self):
        n = self._active_profile
        profile_data = self._profiles.get(n)
        if profile_data is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Empty Profile",
                f"Profile {n} has no saved settings yet.\n\nUse Save to store current settings here.",
                QMessageBox.Ok,
            )
            return
        _TD = "<span style='color:#d8c050; font-weight:bold;'>Trait Desirability</span>"
        if self._profile_traits_only:
            msg = (f"Load Profile {n}?<br><br>"
                   f"Only {_TD} ratings will be loaded.<br>"
                   f"Weights and other settings will not change.")
            if self._is_dirty():
                msg += "<br><br>Unsaved changes to the current profile will be lost."
        else:
            msg = f"Load Profile {n}?\n\nYour current settings will be replaced with those saved in Profile {n}."
            if self._is_dirty():
                msg += "\n\nUnsaved changes to the current profile will be lost."
        dlg = _ConfirmDialog("Load Profile", msg, f"Load Profile {n}", parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        if self._profile_traits_only:
            # Only restore trait ratings and profile name
            self._ma_ratings = {k: v for k, v in profile_data.get("ma_ratings", {}).items()
                                 if v in (-1, 0, 1, 2)}
            self._profile_name_text = profile_data.get("name", "")
            if hasattr(self, "_profile_name_edit"):
                self._profile_name_edit.blockSignals(True)
                self._profile_name_edit.setText(self._profile_name_text)
                self._profile_name_edit.blockSignals(False)
            if self._cats:
                for defect in getattr(self, "_defect_names", set()):
                    if defect not in self._ma_ratings:
                        self._ma_ratings[defect] = -1
                self._selected_cat = None
                self._populate_trait_table(self._abilities_table, self._all_abilities)
                self._populate_trait_table(self._mutations_table, self._all_mutations)
            self.recompute()
        else:
            self._apply_profile_data(profile_data)
        self._loaded_profile = n
        self._active_profile = n
        self._profile_snapshot = dict(profile_data)
        self._save_ratings()

    def _on_profile_save(self):
        n = self._active_profile
        has_data = n in self._profiles
        if self._profile_traits_only and not has_data:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Profile Empty",
                f"Profile {n} has no saved settings yet.\n\n"
                f"\"Only Trait Desirability\" mode can only update an existing profile.\n\n"
                f"To proceed: uncheck \"Only Trait Desirability\", save a full profile to "
                f"slot {n}, then re-enable the option for future trait-only saves.",
                QMessageBox.Ok,
            )
            return
        _TD = "<span style='color:#d8c050; font-weight:bold;'>Trait Desirability</span>"
        if self._profile_traits_only:
            msg = (f"Save to Profile {n}?<br><br>"
                   f"Only {_TD} ratings will be updated.<br>"
                   f"Weights and other settings will not be changed.")
        elif has_data:
            msg = f"Save to Profile {n}?\n\nThis will overwrite Profile {n} with your current settings."
        else:
            msg = f"Save to Profile {n}?\n\nProfile {n} is currently empty. Your settings will be saved here."
        dlg = _ConfirmDialog("Save Profile", msg, f"Save to Profile {n}", parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        if self._profile_traits_only:
            # Preserve any existing full profile data; only update the traits portion
            existing = dict(self._profiles.get(n, {}))
            existing["name"] = self._profile_name_text
            existing["ma_ratings"] = dict(self._ma_ratings)
            snapshot = existing
        else:
            snapshot = self._serialize_current()
        self._profiles[n] = snapshot
        self._loaded_profile = n
        self._active_profile = n
        self._profile_snapshot = snapshot
        self._save_ratings()

    def _on_profile_delete(self):
        n = self._active_profile
        if n not in self._profiles:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Nothing to Delete",
                f"Profile {n} is already empty — there is nothing to delete.",
                QMessageBox.Ok,
            )
            return
        if len(self._profiles) <= 1:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Cannot Delete",
                "You cannot delete the only remaining saved profile.\n\n"
                "Save your settings to another slot first, then delete this one.",
                QMessageBox.Ok,
            )
            return
        pname = self._profiles[n].get("name", "") or f"Profile {n}"
        dlg = _ConfirmDialog(
            "Delete Profile",
            f"Delete Profile {n} (\"{pname}\")?\n\n"
            f"This will erase all settings saved in slot {n} and cannot be undone.",
            f"Delete Profile {n}",
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        del self._profiles[n]
        # Load the lowest-numbered remaining profile
        next_n = min(self._profiles.keys())
        self._apply_profile_data(self._profiles[next_n])
        self._loaded_profile = next_n
        self._active_profile = next_n
        self._profile_snapshot = dict(self._profiles[next_n])
        self._save_ratings()

    # ── UI build ──────────────────────────────────────────────────────────────

    def _make_trait_table(self) -> QTableWidget:
        t = QTableWidget()
        t.setColumnCount(2)
        t.setHorizontalHeaderLabels(["Trait", "Rating"])
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setSelectionMode(QAbstractItemView.NoSelection)
        t.verticalHeader().setVisible(False)
        t.setShowGrid(False)
        t.setAlternatingRowColors(True)
        t.setStyleSheet(_PRIORITY_TABLE_STYLE)
        hh = t.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        t.setColumnWidth(1, 115)
        _FastTooltipFilter(t)   # fast tooltip on the trait name column
        return t

    @staticmethod
    def _make_banner(icon: str, text: str, color: str, bg: str, border: str) -> QWidget:
        """Two-column banner: fixed-width centered icon label + text label.

        Using a real layout instead of padded spaces ensures the icon and text
        are independently aligned regardless of glyph width differences.
        """
        w = QWidget()
        w.setStyleSheet(
            f"QWidget {{ background:{bg}; border-bottom:1px solid {border}; }}"
            f"QLabel  {{ background:transparent; border:none; }}"
        )
        hb = QHBoxLayout(w)
        hb.setContentsMargins(14, 0, 14, 0)
        hb.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(20)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(f"color:{color}; font-size:14px;")

        text_lbl = QLabel(text)
        text_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        text_lbl.setStyleSheet(f"color:{color}; font-size:12px; font-weight:bold;")

        hb.addWidget(icon_lbl)
        hb.addWidget(text_lbl)
        hb.addStretch()
        w.setFixedHeight(38)
        return w

    def _build_ui(self):
        vb = QVBoxLayout(self)
        vb.setContentsMargins(0, 0, 0, 0)
        vb.setSpacing(0)

        # TEMP: green stripe at top for visual version distinction (-t flag)
        if "-t" in sys.argv:
            _top_stripe = QWidget()
            _top_stripe.setFixedHeight(4)
            _top_stripe.setStyleSheet("background:#00cc44;")
            vb.addWidget(_top_stripe)

        top_bar = QWidget()
        top_bar.setStyleSheet("background:#16213e; border-bottom:1px solid #1e1e38;")
        top_bar.setFixedHeight(46)
        hb = QHBoxLayout(top_bar)
        hb.setContentsMargins(14, 0, 14, 0)
        hb.setSpacing(12)
        title_lbl = QLabel("Breed Priority")
        title_lbl.setStyleSheet("color:#ddd; font-size:16px; font-weight:bold;")
        hb.addWidget(title_lbl)
        hb.addStretch()

        _chk_style = "color:#aaa; font-size:11px;"
        # Segmented Score / Values / Both control
        _seg_btn_style = """
            QPushButton {
                color: #777; background: #1a1a26; border: 1px solid #333;
                padding: 1px 7px; font-size: 10px; border-radius: 0px;
            }
            QPushButton:checked { color: #ddd; background: #2c2c3e; border-color: #555; }
            QPushButton:hover:!checked { color: #aaa; background: #222230; }
        """
        self._btn_mode_score   = QPushButton("Score")
        self._btn_mode_values  = QPushButton("Values")
        self._btn_mode_both    = QPushButton("Both")
        self._btn_mode_heatmap = QPushButton("Heatmap")
        for _b in (self._btn_mode_score, self._btn_mode_values, self._btn_mode_both, self._btn_mode_heatmap):
            _b.setCheckable(True)
            _b.setStyleSheet(_seg_btn_style)
            _b.setFixedHeight(20)
        _mode_init = {"score": self._btn_mode_score, "values": self._btn_mode_values,
                      "both": self._btn_mode_both, "heatmap": self._btn_mode_heatmap}
        _mode_init.get(self._display_mode, self._btn_mode_score).setChecked(True)
        self._display_mode_group = QButtonGroup(self)
        self._display_mode_group.setExclusive(True)
        self._display_mode_group.addButton(self._btn_mode_score,   0)
        self._display_mode_group.addButton(self._btn_mode_values,  1)
        self._display_mode_group.addButton(self._btn_mode_both,    2)
        self._display_mode_group.addButton(self._btn_mode_heatmap, 3)
        self._display_mode_group.idToggled.connect(self._on_display_mode_changed)
        _seg_w = QWidget()
        _seg_l = QHBoxLayout(_seg_w)
        _seg_l.setSpacing(0)
        _seg_l.setContentsMargins(0, 0, 0, 0)
        for _b in (self._btn_mode_score, self._btn_mode_values, self._btn_mode_both, self._btn_mode_heatmap):
            _seg_l.addWidget(_b)
        hb.addWidget(_seg_w)

        self._chk_show_stats = QCheckBox("Show Stats")
        self._chk_show_stats.setStyleSheet(_chk_style)
        self._chk_show_stats.setToolTip(
            "Show individual STR/DEX/CON/INT/SPD/CHA/LCK stat columns."
        )
        self._chk_show_stats.setChecked(self._show_stats)
        self._chk_show_stats.stateChanged.connect(self._on_show_stats_changed)
        hb.addWidget(self._chk_show_stats)

        vb.addWidget(top_bar)

        hs = _CollapseSplitter(Qt.Horizontal)
        hs.setHandleWidth(14)
        vb.addWidget(hs)

        # Left: scope + weights panel
        left = QWidget()
        left.setMinimumWidth(0)
        left.setStyleSheet("background:#14142a;")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 12, 8, 8)
        lv.setSpacing(4)

        scope_lbl = QLabel("COMPARISON SCOPE")
        scope_lbl.setStyleSheet(
            "color:#555; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        lv.addWidget(scope_lbl)

        _ac_row = QWidget()
        _ac_row.setStyleSheet("background:transparent;")
        _ac_h = QHBoxLayout(_ac_row)
        _ac_h.setContentsMargins(0, 0, 0, 0)
        _ac_h.setSpacing(3)
        self._chk_all_cats = QCheckBox("All Cats")
        self._chk_all_cats.setStyleSheet("color:#aaa; font-size:11px;")
        self._chk_all_cats.setChecked(True)
        self._chk_all_cats.stateChanged.connect(self._on_all_cats_changed)
        _ac_h.addWidget(self._chk_all_cats)
        _ac_h.addStretch()
        for _leg_txt, _leg_clr in (("M", "#2aaa99"), ("F", "#bb88dd"), ("?", "#ccaa44")):
            _leg = QLabel(_leg_txt)
            _leg.setFixedWidth(32)
            _leg.setStyleSheet(f"color:{_leg_clr}; font-size:10px; font-weight:bold;")
            _leg.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            _ac_h.addWidget(_leg)
        lv.addWidget(_ac_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#252545; margin:2px 0;")
        lv.addWidget(sep)

        self._room_checks_widget = QWidget()
        self._room_checks_vb = QVBoxLayout(self._room_checks_widget)
        self._room_checks_vb.setContentsMargins(6, 0, 0, 0)
        self._room_checks_vb.setSpacing(2)
        lv.addWidget(self._room_checks_widget)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color:#252545; margin:6px 0 2px 0;")
        lv.addWidget(sep2)

        weights_lbl = QLabel("WEIGHTS")
        weights_lbl.setStyleSheet(
            "color:#555; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        lv.addWidget(weights_lbl)

        weights_widget = QWidget()
        weights_widget.setStyleSheet("background:#14142a;")
        wg = QGridLayout(weights_widget)
        wg.setContentsMargins(0, 0, 0, 0)
        wg.setHorizontalSpacing(4)
        wg.setVerticalSpacing(3)
        r = 0   # grid row index (separators consume a row too)
        for key, label in WEIGHT_UI_ROWS:
            if key is None:
                # Thin separator line spanning both columns
                _sep = QFrame()
                _sep.setFrameShape(QFrame.HLine)
                _sep.setStyleSheet("color:#252545; margin:1px 0;")
                wg.addWidget(_sep, r, 0, 1, 2)
                r += 1
                continue
            if isinstance(label, tuple):
                # Paired option: group name left, sub-label right (e.g. "Aggro | High")
                group_text, sub_text = label
                lbl = QWidget()
                lbl.setStyleSheet("background:transparent;")
                _lh = QHBoxLayout(lbl)
                _lh.setContentsMargins(0, 0, 0, 0)
                _lh.setSpacing(2)
                _grp = QLabel(group_text)
                _grp.setStyleSheet("color:#666; font-size:10px;")
                _lh.addWidget(_grp)
                _lh.addStretch()
                _sub = QLabel(sub_text)
                _sub.setStyleSheet("color:#888; font-size:10px;")
                _lh.addWidget(_sub)
            else:
                is_subitem = label.startswith("  └")
                lbl = QLabel(label)
                lbl.setStyleSheet(
                    "color:#555; font-size:10px;" if is_subitem else "color:#888; font-size:10px;"
                )
            if key in ("stat_7_threshold", "age_threshold", "seven_sub_threshold"):
                spin = _IntParamSpin(int(round(self._weights[key])))
            else:
                spin = _WeightSpin(self._weights[key])
            spin.valueChanged.connect(lambda val, k=key: self._on_weight_changed(k, val))
            wg.addWidget(lbl,  r, 0)
            wg.addWidget(spin, r, 1)
            self._weight_spins[key] = spin
            r += 1

        _small_btn_style = (
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:3px 4px; font-size:10px; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        reset_btn = QPushButton("Reset")
        reset_btn.setStyleSheet(_small_btn_style)
        reset_btn.setToolTip("Reset all weights to defaults")
        reset_btn.clicked.connect(self._reset_weights)

        info_btn = QPushButton("?")
        info_btn.setFixedWidth(22)
        info_btn.setStyleSheet(_small_btn_style)
        info_btn.setToolTip("Show scoring weights reference")
        info_btn.clicked.connect(self._show_weights_popup)

        btn_row = r
        wg.addWidget(reset_btn, btn_row, 0)
        wg.addWidget(info_btn,  btn_row, 1)
        lv.addWidget(weights_widget)

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet("color:#252545; margin:6px 0 2px 0;")
        lv.addWidget(sep3)

        opts_lbl = QLabel("OPTIONS")
        opts_lbl.setStyleSheet(
            "color:#555; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        lv.addWidget(opts_lbl)

        self._chk_hide_kittens = QCheckBox("Hide Kittens")
        self._chk_hide_kittens.setStyleSheet("color:#aaa; font-size:11px;")
        self._chk_hide_kittens.setToolTip(
            "Exclude kittens (age 1) from the list and from scoring comparisons."
        )
        self._chk_hide_kittens.setChecked(self._hide_kittens)
        self._chk_hide_kittens.stateChanged.connect(self._on_hide_kittens_changed)
        lv.addWidget(self._chk_hide_kittens)

        self._chk_hide_out_of_scope = QCheckBox("Hide Out-of-Scope")
        self._chk_hide_out_of_scope.setStyleSheet("color:#aaa; font-size:11px;")
        self._chk_hide_out_of_scope.setToolTip(
            "Only show cats that are within the current comparison scope."
        )
        self._chk_hide_out_of_scope.setChecked(self._hide_out_of_scope)
        self._chk_hide_out_of_scope.stateChanged.connect(self._on_hide_out_of_scope_changed)
        lv.addWidget(self._chk_hide_out_of_scope)

        sep_f = QFrame()
        sep_f.setFrameShape(QFrame.HLine)
        sep_f.setStyleSheet("color:#252545; margin:4px 0 2px 0;")
        lv.addWidget(sep_f)

        self._filter_btn = QPushButton("Filters…")
        self._filter_btn.setStyleSheet(_small_btn_style)
        self._filter_btn.setToolTip("Open filter settings to hide cats that don't match criteria.")
        self._filter_btn.clicked.connect(self._open_filters)
        lv.addWidget(self._filter_btn)
        self._update_filter_btn()

        lv.addStretch()
        hs.addWidget(left)

        # Right: score table (top) + trait editor (bottom)
        vs = QSplitter(Qt.Vertical)
        vs.setHandleWidth(6)
        vs.setStyleSheet(SPLITTER_V_STYLE)
        hs.addWidget(vs)
        hs.setCollapsible(0, True)
        hs.setCollapsible(1, False)
        hs.setStretchFactor(0, 0)
        hs.setStretchFactor(1, 1)
        hs.setSizes([_LEFT_PANEL_W, 10000])

        self._score_table = QTableWidget()
        self._score_table.setColumnCount(len(_ALL_HEADERS))
        shh = _SortHighlightHeader(self._score_table)
        shh.setSectionsClickable(True)   # must be explicit; not inherited from QTableWidget's default header
        self._score_table.setHorizontalHeader(shh)
        self._score_table.setHorizontalHeaderLabels(_ALL_HEADERS)
        # Column header tooltips - use event filter since QHeaderView item tooltips
        # are unreliable without explicit mouse tracking on the header viewport.
        _HEADER_TIPS_TEXT = {
            "Name":    "Cat name",
            "Age":     "Age in days",
            "Gender":  "M / F / Unknown",
            "Loc":     "Current room",
            "Inj":     "Active injuries",
            "STR":     "Strength",
            "DEX":     "Dexterity",
            "CON":     "Constitution",
            "INT":     "Intelligence",
            "SPD":     "Speed",
            "CHA":     "Charisma",
            "LCK":     "Luck",
            "Sum":     "Stat sum score. Percentile vs scope: full weight if top 10%, −1 per quartile drop, 0 below median.",
            "7-rare":  "Rare 7s. Per stat at 7: full weight up to threshold owners; scaled down beyond; 2× if sole owner.",
            "7-cnt":   "7-Count — flat weight × number of stats at 7.",
            "Trait":   "Trait score. Desirable sole owner = 2× weight; shared = weight ÷ N owners. Undesirable = −weight always.",
            "Aggro":   "Aggression — flat weight if High or Low.",
            "Gender?": "Unknown gender — flat weight if gender is ?.",
            "Libido":  "Libido — flat weight if High or Low.",
            "Sexual":  "Sexuality — flat Gay or Bi weight (straight = no score).",
            "Gene":    "Genetic Novelty — flat weight if no blood relatives in scope.",
            "4+Ch":    "4+ Children — flat weight if ≥4 children in scope.",
            "Age":     "Age penalty. No penalty at/below threshold. Each 3 years over = +1× multiplier (1 over=1×, 4 over=2×, 7 over=3×…).",
            "Love-Scope": "Love interest (scope) — flat weight if love interest is in scope. Pink = in scope, grey = out.",
            "Hate-Scope": "Rivalry (scope) — weight per rival in scope (both directions: hates + hated by).",
            "Love-Room":  "Love interest (room) — flat weight if love interest shares this cat's room.",
            "Hate-Room":  "Rivalry (room) — weight per rival in same room (both directions: hates + hated by).",
            "Score":   "Total weighted score — sum of all column scores.",
            "7-Sub":   "7-Subset: cats in scope whose stat-7 set strictly contains this cat's (▲N = dominated by N cats). Score = (count above threshold) × weight.",
        }
        _col_tips = {ci: _HEADER_TIPS_TEXT[hdr]
                     for ci, hdr in enumerate(_ALL_HEADERS) if hdr in _HEADER_TIPS_TEXT}
        _HeaderTooltipFilter(shh, _col_tips)
        self._score_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._score_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._score_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._score_table.verticalHeader().setVisible(False)
        self._score_table.setShowGrid(False)
        self._score_table.setAlternatingRowColors(True)
        self._score_table.setSortingEnabled(True)
        self._score_table.setStyleSheet(_PRIORITY_TABLE_STYLE)
        shh.setSectionResizeMode(QHeaderView.Interactive)
        shh.setMinimumSectionSize(28)
        self._score_table.setColumnWidth(COL_NAME, 120)
        self._score_table.setColumnWidth(COL_GENDER, 58)
        self._score_table.setColumnWidth(COL_LOC, 112)
        self._score_table.setColumnWidth(COL_INJ, 100)
        for ci in range(_COL_STAT_START, _COL_STAT_START + _NUM_STAT_COLS):
            self._score_table.setColumnWidth(ci, 36)
        for ci in range(_COL_SCORE_START, _COL_SCORE_START + len(_SCORE_COLS)):
            self._score_table.setColumnWidth(ci, 52)
        _sex_col = _COL_SCORE_START + _SCORE_COLS.index("Sexual")
        self._score_table.setColumnWidth(_sex_col, 72)   # wider for emoji glyph
        _age_col = _COL_SCORE_START + _SCORE_COLS.index("Age")
        self._score_table.setColumnWidth(_age_col, 46)
        _loves_col = _COL_SCORE_START + _SCORE_COLS.index("Love-Scope")
        self._score_table.setColumnWidth(_loves_col, 90)
        _hates_col = _COL_SCORE_START + _SCORE_COLS.index("Hate-Scope")
        self._score_table.setColumnWidth(_hates_col, 90)
        _lroom_col = _COL_SCORE_START + _SCORE_COLS.index("Love-Room")
        self._score_table.setColumnWidth(_lroom_col, 90)
        _hroom_col = _COL_SCORE_START + _SCORE_COLS.index("Hate-Room")
        self._score_table.setColumnWidth(_hroom_col, 90)
        _7sub_col = _COL_SCORE_START + _SCORE_COLS.index("7-Sub")
        self._score_table.setColumnWidth(_7sub_col, 52)
        self._score_table.setColumnWidth(COL_SCORE, 55)
        # Trait and 7-rare columns use chip delegates for colored pill rendering
        _chip_delegate = _TraitChipDelegate(self._score_table)
        _trait_col   = _COL_SCORE_START + _SCORE_COLS.index("Trait")
        _rare7_col   = _COL_SCORE_START + _SCORE_COLS.index("7-rare")
        _genderq_col = _COL_SCORE_START + _SCORE_COLS.index("Gender?")
        self._score_table.setItemDelegateForColumn(_trait_col,    _chip_delegate)
        self._score_table.setItemDelegateForColumn(_rare7_col,    _chip_delegate)
        self._score_table.setItemDelegateForColumn(COL_GENDER,    _chip_delegate)
        self._score_table.setItemDelegateForColumn(_genderq_col,  _chip_delegate)
        # Sexual column uses a larger-font chip delegate for the flag emoji
        _sex_delegate = _SexChipDelegate(self._score_table)
        _sexual_col   = _COL_SCORE_START + _SCORE_COLS.index("Sexual")
        self._score_table.setItemDelegateForColumn(_sexual_col, _sex_delegate)
        # Default delegate for "both" mode (non-chip score columns)
        self._both_delegate    = _BothModeDelegate(self._score_table)
        self._heatmap_delegate = _HeatmapDelegate(self._score_table)
        self._score_table.setItemDelegate(
            self._heatmap_delegate if self._display_mode == "heatmap" else self._both_delegate)
        # Apply any user-saved column widths (overrides defaults above)
        for ci, w in self._col_widths.items():
            self._score_table.setColumnWidth(ci, w)
        # Hide stat columns by default
        self._apply_stat_column_visibility()
        shh.sortIndicatorChanged.connect(self._on_sort_indicator_changed)
        shh.sectionResized.connect(self._on_col_resized)
        score_container = QWidget()
        score_container.setStyleSheet("background:#0a0a18;")
        sc_vb = QVBoxLayout(score_container)
        sc_vb.setContentsMargins(0, 0, 0, 0)
        sc_vb.setSpacing(0)

        sc_vb.addWidget(self._build_profile_bar())

        self._filters_active_lbl = self._make_banner(
            icon="⬤", text="Filters Active",
            color="#1ec8a0", bg="#143030", border="#1a5040",
        )
        self._filters_active_lbl.setVisible(False)
        sc_vb.addWidget(self._filters_active_lbl)

        self._no_scope_banner = self._make_banner(
            icon="⚠", text="No comparison scope selected - scores are unavailable",
            color="#e0a020", bg="#201400", border="#604000",
        )
        self._no_scope_banner.setVisible(False)
        sc_vb.addWidget(self._no_scope_banner)
        sc_vb.addWidget(self._score_table)
        vs.addWidget(score_container)
        self._score_table.itemSelectionChanged.connect(self._on_cat_selected)
        _FastTooltipFilter(self._score_table)
        self._hate_overlay = _HateRowOverlay(self._score_table)
        self._update_sort_label()

        ma_widget = QWidget()
        ma_widget.setStyleSheet("background:#0d0d1c;")
        ma_vb = QVBoxLayout(ma_widget)
        ma_vb.setContentsMargins(8, 6, 8, 6)
        ma_vb.setSpacing(4)
        ma_lbl = QLabel("TRAIT DESIRABILITY")
        ma_lbl.setStyleSheet(
            "color:#555; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        ma_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        ma_vb.addWidget(ma_lbl)
        ma_vb.setStretchFactor(ma_lbl, 0)
        ma_hs = QSplitter(Qt.Horizontal)
        ma_hs.setHandleWidth(6)
        ma_hs.setStyleSheet(SPLITTER_H_STYLE)
        for attr, label in (("_abilities_table", "Abilities"), ("_mutations_table", "Mutations")):
            w = QWidget()
            w.setStyleSheet("background:#0d0d1c;")
            wv = QVBoxLayout(w)
            wv.setContentsMargins(0, 0, 0, 0)
            wv.setSpacing(2)
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#555; font-size:10px; font-weight:bold;")
            wv.addWidget(lbl)
            tbl = self._make_trait_table()
            setattr(self, attr, tbl)
            wv.addWidget(tbl)
            ma_hs.addWidget(w)
        ma_vb.addWidget(ma_hs, stretch=1)

        # Bottom row: Trait Desirability (left ~2/3) + Cat Details panel (right ~1/3)
        bottom_hs = QSplitter(Qt.Horizontal)
        bottom_hs.setHandleWidth(6)
        bottom_hs.setStyleSheet(SPLITTER_H_STYLE)
        bottom_hs.addWidget(ma_widget)
        bottom_hs.addWidget(self._make_children_panel())
        bottom_hs.setSizes([440, 220])
        bottom_hs.setStretchFactor(0, 2)
        bottom_hs.setStretchFactor(1, 1)
        vs.addWidget(bottom_hs)
        vs.setSizes([500, 220])
        vs.setStretchFactor(0, 1)
        vs.setStretchFactor(1, 0)

        # TEMP: green stripe at bottom for visual version distinction (-t flag)
        if "-t" in sys.argv:
            _bot_stripe = QWidget()
            _bot_stripe.setFixedHeight(4)
            _bot_stripe.setStyleSheet("background:#00cc44;")
            vb.addWidget(_bot_stripe)

        # Final pass: sync banner/button state now that all widgets exist
        self._update_filter_btn()

    # ── Cat selection ─────────────────────────────────────────────────────────

    def _on_cat_selected(self):
        row = self._score_table.currentRow()
        if row < 0:
            self._selected_cat = None
        else:
            name_item = self._score_table.item(row, 0)
            cat_name = name_item.text() if name_item else None
            alive = [c for c in self._cats if c.status == "In House"]
            self._selected_cat = next((c for c in alive if c.name == cat_name), None)
        # Update hate-row overlay: highlight rivals in both directions
        hate_ids = set()
        if self._selected_cat:
            # Cats that the selected cat hates
            hate_ids |= {id(c) for c in getattr(self._selected_cat, 'haters', [])}
            # Cats that hate the selected cat (reverse)
            hate_ids |= {id(c) for c in self._hated_by_map.get(id(self._selected_cat), [])}
        self._hate_overlay.set_hate_ids(hate_ids)
        self._refresh_trait_table_order()
        self._refresh_children_panel()

    def _refresh_trait_table_order(self):
        cat = self._selected_cat
        if cat is None:
            self._populate_trait_table(self._abilities_table, self._all_abilities)
            self._populate_trait_table(self._mutations_table, self._all_mutations)
            return

        cat_ab = {
            ability_base(a)
            for a in list(cat.abilities) + list(cat.passive_abilities) + list(getattr(cat, 'disorders', []))
            if not is_basic_trait(a)
        }
        cat_mut = set(cat.mutations) | set(getattr(cat, 'defects', []))

        ab_ordered = (
            [t for t in self._all_abilities if t in cat_ab]
            + [t for t in self._all_abilities if t not in cat_ab]
        )
        mut_ordered = (
            [t for t in self._all_mutations if t in cat_mut]
            + [t for t in self._all_mutations if t not in cat_mut]
        )
        self._populate_trait_table(self._abilities_table, ab_ordered, highlight=cat_ab)
        self._populate_trait_table(self._mutations_table, mut_ordered, highlight=cat_mut)

    # ── Children panel ────────────────────────────────────────────────────────

    def _make_children_panel(self) -> QWidget:
        self._children_filter = "all"   # "all" | "scope" | "room"
        w = QWidget()
        w.setStyleSheet("background:#0d0d1c;")
        vb = QVBoxLayout(w)
        vb.setContentsMargins(8, 6, 8, 6)
        vb.setSpacing(4)

        # Header row: label + count
        hdr = QHBoxLayout()
        self._children_hdr_lbl = QLabel("CHILDREN")
        self._children_hdr_lbl.setStyleSheet(
            "color:#555; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        self._children_hdr_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        hdr.addWidget(self._children_hdr_lbl)
        hdr.addStretch()
        self._children_count_lbl = QLabel("")
        self._children_count_lbl.setStyleSheet("color:#444; font-size:10px;")
        self._children_count_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        hdr.addWidget(self._children_count_lbl)
        vb.addLayout(hdr)

        # Filter toggle: All | In Scope | Same Room
        _seg_base = (
            "QPushButton { background:#161628; color:#666; border:1px solid #252545;"
            " padding:2px 7px; font-size:10px; }"
            "QPushButton:hover { background:#1e1e3c; color:#aaa; }"
            "QPushButton:checked { background:#1e2050; color:#99aaff;"
            " border-color:#3a3a88; }"
        )
        _seg_l = _seg_base + (
            "QPushButton { border-top-left-radius:3px; border-bottom-left-radius:3px;"
            " border-right:none; }"
        )
        _seg_m = _seg_base + "QPushButton { border-radius:0; border-right:none; }"
        _seg_r = _seg_base + (
            "QPushButton { border-top-right-radius:3px;"
            " border-bottom-right-radius:3px; }"
        )
        btn_all   = QPushButton("All")
        btn_scope = QPushButton("In Scope")
        btn_room  = QPushButton("Same Room")
        btn_all.setStyleSheet(_seg_l)
        btn_scope.setStyleSheet(_seg_m)
        btn_room.setStyleSheet(_seg_r)
        for btn in (btn_all, btn_scope, btn_room):
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        btn_all.setChecked(True)
        grp = QButtonGroup(w)
        grp.setExclusive(True)
        grp.addButton(btn_all,   0)
        grp.addButton(btn_scope, 1)
        grp.addButton(btn_room,  2)
        _fmap = {0: "all", 1: "scope", 2: "room"}

        def _on_toggle(bid: int, checked: bool):
            if checked:
                self._children_filter = _fmap[bid]
                self._refresh_children_panel()

        grp.idToggled.connect(_on_toggle)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(0)
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.addWidget(btn_all)
        toggle_row.addWidget(btn_scope)
        toggle_row.addWidget(btn_room)
        toggle_row.addStretch()
        vb.addLayout(toggle_row)

        self._children_list = QListWidget()
        self._children_list.setStyleSheet(
            "QListWidget { background:#080818; border:1px solid #1e1e38;"
            " color:#ccc; font-size:11px; outline:none; }"
            "QListWidget::item { padding:2px 6px; }"
            "QListWidget::item:hover { background:#181830; }"
            "QListWidget::item:selected { background:#252550; }"
        )
        self._children_list.setSelectionMode(QAbstractItemView.NoSelection)
        _ListTooltipFilter(self._children_list)
        vb.addWidget(self._children_list, stretch=1)
        return w

    def _refresh_children_panel(self):
        """Populate the children list for the currently selected cat."""
        self._children_list.clear()
        cat = self._selected_cat
        if not cat:
            self._children_hdr_lbl.setText("CHILDREN")
            self._children_count_lbl.setText("")
            return
        _possessive = cat.name + ("'" if cat.name.endswith("s") else "'s")
        self._children_hdr_lbl.setText(f"{_possessive} CHILDREN".upper())
        all_children = sorted(getattr(cat, 'children', []), key=lambda c: c.name)
        filt = getattr(self, '_children_filter', 'all')
        if filt == "scope":
            scope_ids = {id(c) for c in self._get_scope_cats()}
            children = [c for c in all_children if id(c) in scope_ids]
        elif filt == "room":
            children = [c for c in all_children if c.room == cat.room]
        else:
            children = all_children
        total = len(all_children)
        shown = len(children)
        if total == 0:
            self._children_count_lbl.setText("")
        elif filt == "all":
            self._children_count_lbl.setText(f"({total})")
        else:
            self._children_count_lbl.setText(f"({shown}/{total})")
        for child in children:
            room = self._room_display.get(child.room, child.room or "?")
            item = QListWidgetItem(f"{child.name}  ({room})")
            item.setToolTip(self._build_child_tooltip(child))
            self._children_list.addItem(item)

    def _build_child_tooltip(self, cat) -> str:
        """Build a rich HTML tooltip with full cat info for the children panel."""
        html_parts = [
            '<html><body style="font-family:monospace;font-size:11px;background:#0d0d1c">',
            f'<b style="color:{CLR_HIGHLIGHT};font-size:12px">{cat.name}</b>'
            f' <span style="color:#88aacc;font-size:11px">{cat.gender_display}</span>'
            f' <span style="color:#999;font-size:10px">age {getattr(cat, "age", "?")}</span>',
        ]
        # Stats row
        stats_str = "  ".join(
            f'{sn}:<b style="color:#ddddee">{cat.base_stats.get(sn, "?")}</b>'
            for sn in _STAT_COL_NAMES
        )
        html_parts.append(
            f'<br><span style="color:#888;font-size:10px">{stats_str}</span>'
        )
        # Trait sections
        active_abs  = [self._display_name(ability_base(a))
                       for a in cat.abilities if not is_basic_trait(a)]
        passive_abs = [self._display_name(ability_base(a))
                       for a in cat.passive_abilities if not is_basic_trait(a)]
        disorders   = [self._display_name(ability_base(d))
                       for d in getattr(cat, 'disorders', []) if not is_basic_trait(d)]
        mutations   = [m for m in cat.mutations if not is_basic_trait(m)]
        defects     = [d for d in getattr(cat, 'defects', []) if not is_basic_trait(d)]

        for title, items, color in (
            ("ACTIVE ABILITIES",  active_abs,  CLR_DESIRABLE),
            ("PASSIVE ABILITIES", passive_abs, "#88aacc"),
            ("DISORDERS",         disorders,   CLR_UNDESIRABLE),
            ("MUTATIONS",         mutations,   "#cc88ff"),
            ("BIRTH DEFECTS",     defects,     "#cc4444"),
        ):
            if items:
                rows = "".join(
                    f'<tr><td style="color:{color};padding:0 8px 0 0">{it}</td></tr>'
                    for it in items
                )
                html_parts.append(
                    f'<br><span style="color:#999;font-size:10px">{title}</span>'
                    f'<table cellspacing="0" cellpadding="1">{rows}</table>'
                )
        html_parts.append('</body></html>')
        return "".join(html_parts)

    # ── Scope helpers ─────────────────────────────────────────────────────────

    def _is_kitten(self, cat) -> bool:
        age = getattr(cat, 'age', None)
        return age is not None and age <= 1

    def _get_scope_cats(self) -> list:
        alive = [c for c in self._cats if c.status == "In House"]
        if self._hide_kittens:
            alive = [c for c in alive if not self._is_kitten(c)]
        if self._chk_all_cats.isChecked():
            return alive
        selected = {r for r, chk in self._room_checks.items() if chk.isChecked()}
        if not selected:
            return []   # empty scope - no rooms selected
        return [c for c in alive if c.room in selected]

    def _on_weight_changed(self, key: str, val: float):
        self._weights[key] = val
        self._save_ratings()
        self.recompute()

    def _reset_weights(self):
        for key, val in BREED_PRIORITY_WEIGHTS.items():
            self._weights[key] = val
            if key in self._weight_spins:
                self._weight_spins[key].blockSignals(True)
                self._weight_spins[key].setValue(val)
                self._weight_spins[key].blockSignals(False)
        self._save_ratings()
        self.recompute()

    def _on_all_cats_changed(self, *_):
        """Checking All Cats → check every room; unchecking → uncheck every room."""
        checked = self._chk_all_cats.isChecked()
        for chk in self._room_checks.values():
            chk.blockSignals(True)
            chk.setChecked(checked)
            chk.blockSignals(False)
        self._scope_commit()

    def _on_room_changed(self, *_):
        """Any individual room toggle → uncheck All Cats, then recompute."""
        self._chk_all_cats.blockSignals(True)
        self._chk_all_cats.setChecked(False)
        self._chk_all_cats.blockSignals(False)
        self._scope_commit()

    def _scope_commit(self):
        self._saved_scope = {
            "all_cats": self._chk_all_cats.isChecked(),
            "rooms": {r: chk.isChecked() for r, chk in self._room_checks.items()},
        }
        self._save_ratings()
        self.recompute()

    def _on_hide_kittens_changed(self, *_):
        self._hide_kittens = self._chk_hide_kittens.isChecked()
        self._save_ratings()
        self.recompute()

    def _on_hide_out_of_scope_changed(self, *_):
        self._hide_out_of_scope = self._chk_hide_out_of_scope.isChecked()
        self._save_ratings()
        self.recompute()

    def _on_display_mode_changed(self, btn_id: int, checked: bool):
        if not checked:
            return
        self._display_mode = ("score", "values", "both", "heatmap")[btn_id]
        self._score_table.setItemDelegate(
            self._heatmap_delegate if self._display_mode == "heatmap" else self._both_delegate)
        self._save_ratings()
        self.recompute()

    def _on_show_stats_changed(self, *_):
        self._show_stats = self._chk_show_stats.isChecked()
        self._save_ratings()
        self._apply_stat_column_visibility()

    def _apply_stat_column_visibility(self):
        _STAT_DEFAULT_W = 36
        for ci in range(_COL_STAT_START, _COL_STAT_START + _NUM_STAT_COLS):
            if self._show_stats:
                self._score_table.showColumn(ci)
                # showColumn() may restore Qt's internal pre-hide width which
                # can be wrong; explicitly apply the saved or default width.
                self._score_table.setColumnWidth(
                    ci, self._col_widths.get(ci, _STAT_DEFAULT_W)
                )
            else:
                self._score_table.hideColumn(ci)

    def _on_col_resized(self, logical_idx: int, _old: int, new_size: int):
        if new_size == 0:
            return  # hideColumn() fires sectionResized(0) - don't save that
        self._col_widths[logical_idx] = new_size
        self._col_save_timer.start()  # debounced - saves 600ms after last drag

    def _on_sort_indicator_changed(self, col_idx: int, order):
        self._sort_col = col_idx
        self._sort_order = order
        self._update_sort_label()
        self._save_ratings()

    def _update_sort_label(self):
        """Drive the header highlight - the label is gone, the column speaks for itself."""
        hh = self._score_table.horizontalHeader()
        if isinstance(hh, _SortHighlightHeader):
            hh.set_sort(self._sort_col, self._sort_order)

    _FILTER_BTN_ACTIVE = (
        "QPushButton { background:#143030; color:#1ec8a0; border:1px solid #1ec8a0;"
        " border-radius:4px; padding:3px 4px; font-size:10px; font-weight:bold; }"
        "QPushButton:hover { background:#1a4040; color:#3ae8b8; }"
    )
    _FILTER_BTN_INACTIVE = (
        "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a;"
        " border-radius:4px; padding:3px 4px; font-size:10px; }"
        "QPushButton:hover { background:#252545; color:#ddd; }"
    )

    def _update_filter_btn(self):
        active = self._filters.is_any_active()
        self._filter_btn.setText("Filters ●" if active else "Filters…")
        self._filter_btn.setStyleSheet(
            self._FILTER_BTN_ACTIVE if active else self._FILTER_BTN_INACTIVE
        )
        if hasattr(self, '_filters_active_lbl'):
            self._filters_active_lbl.setVisible(active)

    def _open_filters(self):
        _avail_rooms = sorted({
            self._room_display.get(c.room, c.room or "")
            for c in self._cats
            if c.room
        })
        dlg = FilterDialog(self, self._filters, _avail_rooms)
        if dlg.exec():
            new_state = dlg.applied_state()
            if new_state is not None:
                self._filters = new_state
                self._save_ratings()
                self._update_filter_btn()
                self.recompute()

    # ── Data ─────────────────────────────────────────────────────────────────

    def set_cats(self, cats: list):
        self._cats = cats
        alive = [c for c in cats if c.status == "In House"]

        saved_rooms = self._saved_scope.get("rooms", {})
        self._chk_all_cats.blockSignals(True)
        self._chk_all_cats.setChecked(self._saved_scope.get("all_cats", True))
        self._chk_all_cats.blockSignals(False)
        while self._room_checks_vb.count():
            item = self._room_checks_vb.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._room_checks.clear()

        _ROOM_ORDER = {
            "Attic": 0,
            "Floor2_Large": 1, "Floor2_Small": 2,
            "Floor1_Large": 3, "Floor1_Small": 4,
        }
        rooms = sorted(
            {c.room for c in alive if c.room},
            key=lambda r: _ROOM_ORDER.get(r, 99),
        )
        _all_cats_on = self._chk_all_cats.isChecked()
        # Gender colors matching the table's Gender column chips
        _GC_M = "#2aaa99"   # male   teal
        _GC_F = "#bb88dd"   # female purple
        _GC_U = "#ccaa44"   # unknown gold (matches Gender chip)
        for room in rooms:
            room_cats = [c for c in alive if c.room == room]
            _n = len(room_cats)
            _nm = sum(1 for c in room_cats if getattr(c, 'gender_display', '?') in ('M', 'Male'))
            _nf = sum(1 for c in room_cats if getattr(c, 'gender_display', '?') in ('F', 'Female'))
            _nu = _n - _nm - _nf

            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(3)

            chk = QCheckBox(self._room_display.get(room, room))
            chk.setStyleSheet("color:#888; font-size:11px;")
            # If All Cats is on, all room boxes start checked; otherwise restore saved state
            chk.setChecked(_all_cats_on or saved_rooms.get(room, False))
            chk.stateChanged.connect(self._on_room_changed)
            row_h.addWidget(chk)
            row_h.addStretch()

            if _n > 0:
                for _cnt, _gc in ((_nm, _GC_M), (_nf, _GC_F), (_nu, _GC_U)):
                    _pct = round(_cnt / _n * 100)
                    _glbl = QLabel(f"{_pct}%")
                    _glbl.setFixedWidth(32)   # fixed width keeps columns vertically aligned
                    _glbl.setStyleSheet(
                        f"color:{'#444' if _pct == 0 else _gc}; font-size:10px;"
                    )
                    _glbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    row_h.addWidget(_glbl)

            self._room_checks_vb.addWidget(row_w)
            self._room_checks[room] = chk

        self._all_abilities = sorted({
            ability_base(a)
            for c in alive
            for a in list(c.abilities) + list(c.passive_abilities) + list(getattr(c, 'disorders', []))
            if not is_basic_trait(a)
        })
        self._all_mutations = sorted({
            m for c in alive
            for m in list(c.mutations) + list(getattr(c, 'defects', []))
            if not is_basic_trait(m)
        })
        # Track which mutation names are birth defects (for auto-defaulting to undesirable)
        self._defect_names: set[str] = {
            d for c in alive for d in getattr(c, 'defects', [])
        }
        self._mutation_tips: dict[str, str] = {}
        for c in alive:
            for text, tip in getattr(c, "mutation_chip_items", []):
                if tip and text not in self._mutation_tips:
                    self._mutation_tips[text] = tip
            for text, tip in getattr(c, "defect_chip_items", []):
                if tip and text not in self._mutation_tips:
                    self._mutation_tips[text] = tip
        # Auto-default defects to undesirable
        for defect in self._defect_names:
            if defect not in self._ma_ratings:
                self._ma_ratings[defect] = -1
        self._selected_cat = None
        self._populate_trait_table(self._abilities_table, self._all_abilities)
        self._populate_trait_table(self._mutations_table, self._all_mutations)
        self.recompute()

    def _populate_trait_table(self, table: QTableWidget, traits: list,
                              highlight: set | None = None):
        visible = [t for t in traits if not is_basic_trait(t)]
        self._populating = True
        table.setSortingEnabled(False)
        table.setRowCount(len(visible))
        _HL_BG    = QColor("#1a2a40")
        _UNSET_BG = QColor("#111128")
        _RATED_BG = QBrush()

        for row, trait in enumerate(visible):
            display = self._display_name(trait)
            name_item = QTableWidgetItem(display)
            name_item.setData(Qt.UserRole, trait)
            name_item.setFlags(Qt.ItemIsEnabled)
            current = self._ma_ratings.get(trait)
            if highlight and trait in highlight:
                name_item.setBackground(_HL_BG)
            elif current is None:
                name_item.setBackground(_UNSET_BG)
            tip = self._ability_tip(trait) or self._mutation_tips.get(trait, "")
            if tip:
                name_item.setToolTip(f"{display}\n\n{tip}")
            table.setItem(row, 0, name_item)

            combo = _RatingCombo()
            for ci, clr in enumerate(RATING_ITEM_COLORS):
                combo.model().item(ci).setForeground(QColor(clr))
            # Tooltip is on the name item (col 0) and shown via _FastTooltipFilter
            init_idx = {v: i for i, v in enumerate(TRAIT_RATING_VALUES)}.get(current, TRAIT_RATING_VALUES.index(None))
            combo.setCurrentIndex(init_idx)

            def _apply_combo_color(idx: int, cb: QComboBox, ni: QTableWidgetItem,
                                   is_highlighted: bool):
                clr = RATING_ITEM_COLORS[idx] if 0 <= idx < len(RATING_ITEM_COLORS) else "#ccc"
                cb.setStyleSheet(
                    _PRIORITY_COMBO_STYLE + f"QComboBox {{ color:{clr}; }}"
                )
                if is_highlighted:
                    pass
                elif idx == 2:
                    ni.setBackground(_UNSET_BG)
                else:
                    ni.setBackground(_RATED_BG)

            is_hl = bool(highlight and trait in highlight)
            _apply_combo_color(init_idx, combo, name_item, is_hl)
            combo.currentIndexChanged.connect(
                lambda idx, t=trait, cb=combo, ni=name_item, hl=is_hl: [
                    self._on_rating_changed(t, idx),
                    _apply_combo_color(idx, cb, ni, hl),
                ]
            )
            table.setCellWidget(row, 1, combo)
            table.setRowHeight(row, 24)
        self._populating = False

    def _on_rating_changed(self, trait: str, combo_idx: int):
        if self._populating:
            return
        val = TRAIT_RATING_VALUES[combo_idx]
        if val is None:
            self._ma_ratings.pop(trait, None)
        else:
            self._ma_ratings[trait] = val
        self._save_ratings()
        self.recompute()

    # ── Score computation ─────────────────────────────────────────────────────

    def _build_cat_tooltip(self, cat, result: ScoreResult, scope_cats: list) -> str:
        def row(color: str, label: str, score: str) -> str:
            return (
                f'<tr>'
                f'<td style="color:{color};padding:0 8px 0 0">{label}</td>'
                f'<td style="color:{color};text-align:right">{score}</td>'
                f'</tr>'
            )

        _scope_base = {
            id(c): (
                {ability_base(a) for a in list(c.abilities) + list(c.passive_abilities) + list(getattr(c, 'disorders', []))
                 if not is_basic_trait(a)}
                | set(c.mutations)
                | set(getattr(c, 'defects', []))
            )
            for c in scope_cats
        }
        _u = self._weights["unique_ma_max"]

        passive_base = {
            ability_base(p) for p in cat.passive_abilities if not is_basic_trait(p)
        }
        disorder_base = {
            ability_base(d) for d in getattr(cat, 'disorders', []) if not is_basic_trait(d)
        }
        seen: set = set()
        active_traits = [
            t for t in (
                ability_base(a) for a in cat.abilities
                if not is_basic_trait(a) and ability_base(a) not in passive_base
                and ability_base(a) not in disorder_base
            )
            if not (t in seen or seen.add(t))
        ]
        passive_traits = sorted(passive_base)
        disorder_traits = sorted(disorder_base)
        mutation_traits = [t for t in cat.mutations if not is_basic_trait(t)]
        defect_traits = [t for t in getattr(cat, 'defects', []) if not is_basic_trait(t)]

        def _trait_rows_for(traits: list) -> list:
            rows = []
            for trait in traits:
                display = self._display_name(trait)
                rating = self._ma_ratings.get(trait)
                sharing = [c for c in scope_cats
                           if c is not cat and trait in _scope_base[id(c)]]
                n = len(sharing) + 1  # +1 for the cat itself
                cats_str = f" ({n} cats)"
                if rating in (None, 0):
                    color = CLR_UNDECIDED if rating is None else CLR_NEUTRAL
                    label = f"{display}  ?" if rating is None else display
                    rows.append(row(color, label, "+0.00"))
                elif n == 1:
                    if rating == 2:
                        pts = 10 * _u
                        clr, star = CLR_TOP_PRIORITY, "★★★"
                    elif rating == 1:
                        pts = 2 * _u
                        clr, star = CLR_DESIRABLE, "★★"
                    else:
                        pts = -_u
                        clr, star = CLR_UNDESIRABLE, "★"
                    rows.append(row(clr, f"{display}  {star}", f"{pts:+.2f}"))
                elif rating == 2:
                    pts = round(5 * _u / n, 3)
                    rows.append(row(CLR_TOP_PRIORITY, display, f"{pts:+.2f}{cats_str}"))
                elif rating == 1:
                    pts = round(_u / n, 3)
                    rows.append(row(CLR_DESIRABLE, display, f"{pts:+.2f}{cats_str}"))
                elif rating == -1:
                    rows.append(row(CLR_UNDESIRABLE, display, f"{-_u:+.2f}{cats_str}"))
                else:
                    rows.append(row(CLR_NEUTRAL, display, f"+0.00{cats_str}"))
                if sharing:
                    names = [c.name for c in sharing[:5]]
                    extra = len(sharing) - 5
                    names_text = ", ".join(names)
                    if extra > 0:
                        names_text += f", +{extra} more"
                    rows.append(row(CLR_HIGHLIGHT, f"&nbsp;&nbsp;↳ {names_text}", ""))
            return rows

        active_rows   = _trait_rows_for(active_traits)
        passive_rows  = _trait_rows_for(passive_traits)
        disorder_rows = _trait_rows_for(disorder_traits)
        mutation_rows = _trait_rows_for(mutation_traits)
        defect_rows   = _trait_rows_for(defect_traits)

        # Build injury rows
        _injuries = _cat_injuries(cat, self._stat_names)
        injury_rows = []
        for _iname, _isn, _idelta in _injuries:
            injury_rows.append(row("#cc4444", _isn, f"{_idelta:+d}"))

        scope_set = {id(c) for c in scope_cats}
        children_in_scope = [c for c in cat.children if id(c) in scope_set]
        other_rows = []
        for desc, pts in result.breakdown:
            if desc.startswith(("Sole owner", "Top Priority (÷", "Desirable (÷", "Undesirable:")):
                continue
            color = CLR_DESIRABLE if pts > 0 else CLR_UNDESIRABLE
            other_rows.append(row(color, desc, f"{pts:+.2f}"))
            if "children in scope" in desc and children_in_scope:
                for child in children_in_scope:
                    room = self._room_display.get(child.room, child.room or "?")
                    other_rows.append(row(CLR_HIGHLIGHT, f"&nbsp;&nbsp;↳ {child.name}  ({room})", ""))

        total_color = CLR_DESIRABLE if result.total > 0 else CLR_UNDESIRABLE if result.total < 0 else "#888"
        _sex = getattr(cat, 'sexuality', 'straight') or 'straight'
        _sex_glyph = (
            f' <span style="font-size:14px">{_SEX_EMOJI_GAY}</span>' if _sex == 'gay' else
            f' <span style="font-size:14px">{_SEX_EMOJI_BI}</span>'  if _sex == 'bi'  else
            ''
        )
        html_parts = [
            '<html><body style="font-family:monospace;font-size:11px;background:#0d0d1c">',
            f'<b style="color:{CLR_HIGHLIGHT};font-size:12px">{cat.name}</b>'
            f'{_sex_glyph}'
            f' <span style="color:#88aacc;font-size:11px">{cat.gender_display}</span>'
            f' <span style="color:#999;font-size:10px">age {getattr(cat, "age", "?")}</span>',
        ]
        if injury_rows:
            html_parts.append('<br><span style="color:#cc4444;font-size:10px">INJURIES</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(injury_rows) + '</table>')
        if active_rows:
            html_parts.append('<br><span style="color:#999;font-size:10px">ACTIVE ABILITIES</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(active_rows) + '</table>')
        if passive_rows:
            html_parts.append('<br><span style="color:#999;font-size:10px">PASSIVE ABILITIES</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(passive_rows) + '</table>')
        if disorder_rows:
            html_parts.append('<br><span style="color:#999;font-size:10px">DISORDERS</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(disorder_rows) + '</table>')
        if mutation_rows:
            html_parts.append('<br><span style="color:#999;font-size:10px">MUTATIONS</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(mutation_rows) + '</table>')
        if defect_rows:
            html_parts.append('<br><span style="color:#999;font-size:10px">BIRTH DEFECTS</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(defect_rows) + '</table>')
        if other_rows:
            html_parts.append('<br><span style="color:#999;font-size:10px">OTHER</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(other_rows) + '</table>')
        html_parts.append(
            f'<br><b style="color:{total_color}">Total: {result.total:+.2f}</b>'
        )
        html_parts.append('</body></html>')
        return "".join(html_parts)

    def _raw_col_value(self, cat, col_idx: int,
                       scope_relatives_count: int,
                       all_scope_relatives_counts: list) -> tuple:
        """Return (text, sort_val, color) for a column in value mode."""
        hdr = _ALL_HEADERS[col_idx]

        if hdr == "Age":
            age = getattr(cat, 'age', None)
            if age is None:
                return ("-", -1.0, "#666")
            _age_thr = int(round(self._weights.get("age_threshold", 10.0)))
            _over = age - _age_thr
            t = 0.0 if _over <= 0 else min(1.0, _over / 20.0)
            color = _lerp_color("#888888", "#cc3333", t)
            text = f"⏳{age}" if _over > 0 else str(age)
            return (text, float(age), color)

        if hdr == "Gender":
            g = getattr(cat, 'gender_display', '?')
            if g in ('M', 'Male'):
                return (g, 0, "#2aaa99")
            elif g in ('F', 'Female'):
                return (g, 1, "#bb88dd")
            return (g, 2, "#888888")

        if hdr == "Loc":
            loc = self._room_display.get(cat.room, cat.room or "")
            _rs = _room_style(loc)
            if _rs:
                return (f"{_rs[0]} {loc}", 0, _rs[1])
            return (loc, 0, "#888888")

        if hdr in _STAT_COL_NAMES:
            val = cat.base_stats.get(hdr, 0)
            color = "#ffcc44" if val == 7 else "#aaaaaa"
            return (str(val), float(val), color)

        if hdr == "Sum":
            s = sum(cat.base_stats.values())
            # gradient: low=brown, mid=teal, high=purple
            # use percentile of all scope cats
            return (str(s), float(s), "#aaaaaa")

        if hdr == "777":
            count_7 = sum(1 for v in cat.base_stats.values() if v == 7)
            if count_7 == 0:
                color = "#555555"
            else:
                # grey→gold
                t = min(1.0, count_7 / 7.0)
                color = _lerp_color("#888888", "#ffcc00", t)
            return (str(count_7) if count_7 else "", float(count_7), color)

        if hdr == "Trait":
            val = sum(result_subtotals.get(k, 0.0)
                      for k in ["unique_ma_max"]
                      for result_subtotals in [{}])  # placeholder
            return ("", 0.0, "#888888")

        if hdr == "Aggro":
            a = cat.aggression
            if a is None:
                return ("?", 0.0, "#666")
            _high_ag_w = self._weights.get("high_aggression", 0.0)
            _low_ag_w  = self._weights.get("low_aggression",  0.0)
            _high_clr, _low_clr = _paired_weight_colors(_high_ag_w, _low_ag_w)
            if a >= TRAIT_HIGH_THRESHOLD:
                return ("▲Hi", a, _high_clr)
            elif a < TRAIT_LOW_THRESHOLD:
                return ("▼Lo", a, _low_clr)
            else:
                return ("—",   a, "#555555")

        if hdr == "Gender?":
            gd = getattr(cat, 'gender_display', '?')
            is_unknown = gd == '?'
            if is_unknown:
                return ("⚥", 1.0, "#ccaa44")
            return ("", 0.0, "#444444")

        if hdr == "Libido":
            lb = cat.libido
            if lb is None:
                return ("?", 0.0, "#666")
            _high_lb_w = self._weights.get("high_libido", 0.0)
            _low_lb_w  = self._weights.get("low_libido",  0.0)
            _high_clr, _low_clr = _paired_weight_colors(_high_lb_w, _low_lb_w)
            if lb >= TRAIT_HIGH_THRESHOLD:
                return ("❤️", lb, _high_clr)
            elif lb < TRAIT_LOW_THRESHOLD:
                return ("💙", lb, _low_clr)
            else:
                return ("—", lb, "#555555")

        if hdr == "Sexual":
            sex = getattr(cat, 'sexuality', 'straight') or 'straight'
            if sex == 'straight':
                return ("", 0.0, "#444444")
            gay_w = self._weights.get("gay_pref", 0.0)
            bi_w  = self._weights.get("bi_pref",  0.0)
            gay_clr, bi_clr = _paired_weight_colors(gay_w, bi_w)
            if sex == 'gay':
                return (f"{_SEX_EMOJI_GAY}", gay_w, gay_clr)
            else:  # bi
                return (f"{_SEX_EMOJI_BI}", bi_w, bi_clr)

        if hdr == "Gene":
            n = scope_relatives_count
            total = len(all_scope_relatives_counts)
            if total > 0:
                rank = sum(1 for v in all_scope_relatives_counts if v <= n)
                pct = rank / total * 100
                # fewer relatives = better (greener)
                if n == 0:
                    color = CLR_DESIRABLE
                elif pct >= 75:
                    color = CLR_UNDESIRABLE
                elif pct >= 50:
                    color = "#e08030"
                else:
                    color = "#b0a040"
            else:
                color = "#888888"
            text = "✦" if n == 0 else ""
            return (text, float(n), color)

        if hdr == "4+Ch":
            # This is called with scope_relatives_count but we need children_in_scope
            # which is passed separately. We return a placeholder here; the actual
            # value is set in the main loop where ch_in_scope is available.
            return ("", 0.0, "#888888")

        return ("", 0.0, "#888888")

    def recompute(self, *_):
        if self._populating:
            return
        _restore_name = self._selected_cat.name if self._selected_cat else None

        scope_cats = self._get_scope_cats()
        _no_scope = len(scope_cats) == 0
        self._no_scope_banner.setVisible(_no_scope)

        alive = [c for c in self._cats if c.status == "In House"]
        if self._hide_kittens:
            alive = [c for c in alive if not self._is_kitten(c)]
        if self._hide_out_of_scope and not _no_scope:
            scope_set = {id(c) for c in scope_cats}
            alive = [c for c in alive if id(c) in scope_set]

        scope_set = {id(c) for c in scope_cats}

        # Pre-compute sorted stat sums for scope cats (percentile ranking)
        _scope_stat_sums = sorted(sum(c.base_stats.values()) for c in scope_cats)

        # Pre-compute 7-sets for 7-Sub column (strict-subset dominance detection)
        # Maps id(cat) → frozenset of stat names where base value == 7
        _seven_sets: dict[int, frozenset] = {
            id(c): frozenset(sn for sn in _STAT_COL_NAMES if c.base_stats.get(sn) == 7)
            for c in alive
        }
        # Only scope cats can act as dominators
        _scope_7_sets: dict[int, frozenset] = {
            cid: s for cid, s in _seven_sets.items()
            if cid in scope_set
        }

        # Pre-compute reverse-hated-by map: id(cat) → list of cats that hate it
        _hated_by_map: dict[int, list] = {}
        for c in alive:
            for h in getattr(c, 'haters', []):
                _hated_by_map.setdefault(id(h), []).append(c)
        self._hated_by_map = _hated_by_map

        # ── Pass 1: compute all ScoreResults + 7-sub contributions ──
        results: dict[int, ScoreResult] = {}
        _cat_sub_counts: dict[int, int] = {}  # id(cat) → 7-sub count
        for cat in alive:
            results[id(cat)] = compute_breed_priority_score(
                cat, scope_cats, self._ma_ratings,
                stat_names=self._stat_names,
                weights=self._weights,
                mutation_display_name=self._display_name,
                scope_stat_sums=_scope_stat_sums,
                hated_by=_hated_by_map.get(id(cat), []),
            )
            _my_sevens = _seven_sets.get(id(cat), frozenset())
            _sub_cnt = sum(
                1 for _oc, _os in _scope_7_sets.items()
                if _oc != id(cat) and _my_sevens < _os
            ) if _my_sevens else 0
            _cat_sub_counts[id(cat)] = _sub_cnt
            _sub_w   = self._weights.get("seven_sub", 0.0)
            _sub_thr = max(1, int(round(self._weights.get("seven_sub_threshold", 1.0))))
            _sub_pts = _sub_w * min(_sub_cnt / _sub_thr, 1.0) if _sub_cnt > 0 else 0.0
            results[id(cat)].subtotals["seven_sub"] = _sub_pts
            results[id(cat)].total += _sub_pts
            if _sub_pts != 0:
                results[id(cat)].breakdown.append(("7-Sub", _sub_pts))

        # Sorted score list for Score column quartile coloring (includes 7-sub)
        _all_scores_sorted = sorted(results[id(c)].total for c in alive)

        # Build sorted relatives-in-scope list (for Gene percentile coloring)
        # Only from scope cats
        _all_scope_rel_counts = sorted(
            results[id(c)].scope_relatives_count
            for c in scope_cats if id(c) in results
        )

        # Also compute children-in-scope counts for 4+Ch display
        def _children_in_scope(cat):
            return sum(1 for ch in cat.children if id(ch) in scope_set)

        _all_scope_children = sorted(_children_in_scope(c) for c in scope_cats)

        # Max 7-count across all visible cats - used for relative gradient coloring
        _max_7_count = max(
            (sum(1 for v in c.base_stats.values() if v == 7) for c in alive),
            default=0,
        )

        # Capture the current visible row order (by cat id) so we can restore
        # it as the insertion order.  This makes toggling Show Values a pure
        # cosmetic change - sortItems() will produce the exact same result
        # because the tiebreaker (insertion order) is identical to before.
        _cat_id_map = {id(c): c for c in alive}
        _prev_order: dict[int, int] = {}  # cat_id → previous display position
        for _r in range(self._score_table.rowCount()):
            _ni = self._score_table.item(_r, COL_NAME)
            if _ni is not None:
                _cid = _ni.data(Qt.UserRole + 1)
                if _cid in _cat_id_map:
                    _prev_order[_cid] = _r
        if _prev_order:
            alive.sort(key=lambda c: _prev_order.get(id(c), 999999))

        # Pre-compute per-column max absolute score for heatmap normalisation
        _col_max_abs: dict[int, float] = {}
        if self._display_mode == "heatmap":
            for ci, (_, keys) in enumerate(SCORE_COLUMNS):
                _mx = max((abs(sum(results[id(c)].subtotals.get(k, 0.0) for k in keys))
                           for c in alive), default=0.0)
                _col_max_abs[ci] = _mx if _mx > 0 else 1.0

        self._score_table.setSortingEnabled(False)
        self._score_table.setRowCount(len(alive))

        for row, cat in enumerate(alive):
            result = results[id(cat)]
            scope_rel_count = result.scope_relatives_count
            ch_in_scope = _children_in_scope(cat)
            _sub_count = _cat_sub_counts.get(id(cat), 0)

            # ── Name ──
            name_item = QTableWidgetItem(cat.name)
            name_item.setData(Qt.UserRole + 1, id(cat))  # used to restore row order on recompute
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._score_table.setItem(row, COL_NAME, name_item)

            # ── Gender ──
            gd = getattr(cat, 'gender_display', '?')
            if gd in ('M', 'Male'):
                _g_chip = [("M", "#0e3030", "#2aaa99")]
                _g_sort = 0
            elif gd in ('F', 'Female'):
                _g_chip = [("F", "#2a1540", "#bb88dd")]
                _g_sort = 1
            else:
                _g_chip = [("?", "#302010", "#ccaa44")]
                _g_sort = 2
            gender_item = _NumericSortItem("")
            gender_item.setData(Qt.UserRole, float(_g_sort))
            gender_item.setData(_CHIP_ROLE, _g_chip)
            gender_item.setTextAlignment(Qt.AlignCenter)
            gender_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._score_table.setItem(row, COL_GENDER, gender_item)

            # ── Location ──
            loc_text = self._room_display.get(cat.room, cat.room or "")
            _rs = _room_style(loc_text)
            if _rs:
                _loc_emoji, _loc_color = _rs
                loc_item = QTableWidgetItem(f"{_loc_emoji} {loc_text}")
                loc_item.setForeground(QColor(_loc_color))
            else:
                loc_item = QTableWidgetItem(loc_text)
                loc_item.setForeground(QColor("#888888"))
            loc_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if id(cat) in scope_set:
                _lf = loc_item.font()
                _lf.setBold(True)
                loc_item.setFont(_lf)
            self._score_table.setItem(row, COL_LOC, loc_item)

            # ── Injuries ──
            _injuries = _cat_injuries(cat, self._stat_names)
            if _injuries:
                _inj_parts = []
                for _iname, _isn, _idelta in _injuries:
                    _inj_parts.append(f"{_isn} {_idelta:+d}")
                inj_item = QTableWidgetItem(", ".join(_inj_parts))
                inj_item.setForeground(QColor("#cc4444"))
                inj_item.setData(Qt.UserRole, float(len(_injuries)))
            else:
                inj_item = QTableWidgetItem("-")
                inj_item.setForeground(QColor("#333355"))
                inj_item.setData(Qt.UserRole, 0.0)
            inj_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._score_table.setItem(row, COL_INJ, inj_item)

            # ── Stat columns ──
            for si, stat in enumerate(_STAT_COL_NAMES):
                val = cat.base_stats.get(stat, 0)
                stat_item = _NumericSortItem(str(val))
                stat_item.setData(Qt.UserRole, float(val))
                stat_item.setTextAlignment(Qt.AlignCenter)
                stat_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if val == 7:
                    stat_item.setForeground(QColor(CLR_DESIRABLE))
                elif val == 6:
                    stat_item.setForeground(QColor("#b0a040"))
                elif val == 5:
                    stat_item.setForeground(QColor("#e08030"))
                elif val >= 4:
                    stat_item.setForeground(QColor("#cc3333"))
                else:
                    stat_item.setForeground(QColor("#555555"))
                self._score_table.setItem(row, _COL_STAT_START + si, stat_item)

            # ── Score/value columns ──
            # sort_val is ALWAYS the score regardless of display mode so that
            # switching modes never changes the sort order.
            _cw = self._weights
            for ci, (hdr, keys) in enumerate(SCORE_COLUMNS):
                col_idx = _COL_SCORE_START + ci
                # Compute score (sort value) for this column - always used.
                score_val = sum(result.subtotals.get(k, 0.0) for k in keys)

                # Helper: score → display color
                def _score_color(v, pos=CLR_DESIRABLE, neg=CLR_UNDESIRABLE):
                    return pos if v > 0 else neg if v < 0 else "#444444"

                # ── Love-Scope / Hate-Scope / Love-Room / Hate-Room: show cat name ──
                if hdr in ("Love-Scope", "Hate-Scope", "Love-Room", "Hate-Room"):
                    _is_love = hdr in ("Love-Scope", "Love-Room")
                    _is_hate = not _is_love
                    _is_room = hdr in ("Love-Room", "Hate-Room")
                    _rel_list = getattr(cat, 'lovers' if _is_love else 'haters', [])
                    if _is_room:
                        _cat_room = getattr(cat, 'room', None)
                        _in_match = [c for c in _rel_list
                                     if _cat_room and getattr(c, 'room', None) == _cat_room]
                    else:
                        _in_match = [c for c in _rel_list if id(c) in scope_set]

                    # For hate columns, also include cats that hate this cat (reverse)
                    _hated_by_match = []
                    if _is_hate:
                        _hb = _hated_by_map.get(id(cat), [])
                        _own_haters_set = set(id(h) for h in getattr(cat, 'haters', []))
                        if _is_room:
                            _cat_room_h = getattr(cat, 'room', None)
                            _hated_by_match = [c for c in _hb
                                               if id(c) not in _own_haters_set
                                               and _cat_room_h and getattr(c, 'room', None) == _cat_room_h]
                        else:
                            _hated_by_match = [c for c in _hb
                                               if id(c) not in _own_haters_set
                                               and id(c) in scope_set]

                    _all_rivals = _in_match + _hated_by_match
                    _any = _all_rivals or _rel_list
                    _do_vals = self._display_mode in ("values", "both", "heatmap")
                    if _any:
                        if _do_vals:
                            if _all_rivals:
                                _first = _all_rivals[0]
                                _extra = len(_all_rivals) - 1
                                _prefix = "🏠" if _is_room else ""
                                _name = _prefix + _first.name + (f" +{_extra}" if _extra else "")
                            else:
                                _prefix = "🏠" if _is_room else ""
                                _name = _prefix + _rel_list[0].name
                            if _all_rivals:
                                if _is_room:
                                    _color = "#ddaa88" if _is_love else "#dd8844"
                                else:
                                    _color = "#ee88aa" if _is_love else "#cc4444"
                            else:
                                _color = "#555555"
                        else:
                            _name  = f"{score_val:+.1f}" if score_val != 0 else ""
                            _color = _score_color(score_val)
                    else:
                        _name  = ""
                        _color = "#444444"
                    # sort always by score
                    _rel_item = _NumericSortItem(_name)
                    _rel_item.setData(Qt.UserRole, score_val)
                    _rel_item.setTextAlignment(Qt.AlignCenter)
                    _rel_item.setForeground(QColor(_color))
                    _rel_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    if self._display_mode == "both" and _any and score_val != 0:
                        _rel_item.setData(_SCORE_SECONDARY_ROLE, f"{score_val:+.1f}")
                    # Tooltip listing all rivals for hate columns
                    if _is_hate and _all_rivals:
                        _tip_lines = []
                        for _rc in _in_match:
                            _tip_lines.append(f"Hates {_rc.name}")
                        for _rc in _hated_by_match:
                            _tip_lines.append(f"Hated by {_rc.name}")
                        _rel_item.setToolTip("\n".join(_tip_lines))
                    if self._display_mode == "heatmap" and ci in _col_max_abs:
                        _rel_item.setData(_HEATMAP_ROLE,
                                          score_val / _col_max_abs[ci] if score_val != 0 else 0.0)
                    self._score_table.setItem(row, col_idx, _rel_item)
                    continue

                # ── Sexual column in value mode: show flag chip ──
                if hdr == "Sexual" and self._display_mode in ("values", "both", "heatmap"):
                    _sex = getattr(cat, 'sexuality', 'straight') or 'straight'
                    _sx_item = _NumericSortItem("")
                    _sx_item.setData(Qt.UserRole, score_val)
                    _sx_item.setTextAlignment(Qt.AlignCenter)
                    _sx_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    if _sex != 'straight':
                        _gay_w = _cw.get("gay_pref", 0.0)
                        _bi_w  = _cw.get("bi_pref",  0.0)
                        _gay_clr, _bi_clr = _paired_weight_colors(_gay_w, _bi_w)
                        _sx_ind_clr = _gay_clr if _sex == 'gay' else _bi_clr
                        _sx_bg, _sx_fg = _sex_indicator_to_chip(_sx_ind_clr)
                        _sx_emoji = _SEX_EMOJI_GAY if _sex == 'gay' else _SEX_EMOJI_BI
                        # "BI" label: teal text; slightly darker bg when grey
                        if _sex == 'bi':
                            _sx_fg = "#4ecdc4"
                            if _sx_bg == "#555555":
                                _sx_bg = "#383838"
                        _sx_item.setData(_CHIP_ROLE, [(_sx_emoji, _sx_bg, _sx_fg)])
                    if self._display_mode == "both" and score_val != 0:
                        _sx_item.setData(_SCORE_SECONDARY_ROLE, f"{score_val:+.1f}")
                    if self._display_mode == "heatmap" and ci in _col_max_abs:
                        _sx_item.setData(_HEATMAP_ROLE,
                                         score_val / _col_max_abs[ci] if score_val != 0 else 0.0)
                    self._score_table.setItem(row, col_idx, _sx_item)
                    continue

                _chips = []   # populated for Trait column in value mode
                _score_for_sub = score_val   # preserved for "both" secondary text
                if self._display_mode in ("values", "both", "heatmap"):
                    # ── Value / Both display mode ──
                    if hdr == "Sum":
                        s = sum(cat.base_stats.values())
                        score_val = float(s)   # sort by raw sum, not score
                        total = len(_scope_stat_sums)
                        if total > 0:
                            rank = sum(1 for v in _scope_stat_sums if v <= s)
                            pct = rank / total * 100
                            if pct >= 75:
                                color = CLR_DESIRABLE
                            elif pct >= 50:
                                color = "#b0a040"
                            elif pct >= 25:
                                color = "#e08030"
                            else:
                                color = "#cc3333"
                        else:
                            color = "#888888"
                        text = str(s)
                    elif hdr == "7-rare":
                        # Chips: one per stat at 7, colored by rarity vs threshold
                        _cat_in_scope = id(cat) in scope_set
                        _thr = _cw.get("stat_7_threshold", 7.0)
                        for _sn in _STAT_COL_NAMES:
                            if cat.base_stats.get(_sn) == 7:
                                _n_sc = sum(1 for _sc in scope_cats if _sc.base_stats.get(_sn) == 7)
                                _n = _n_sc if _cat_in_scope else _n_sc + 1
                                _bg, _fg = _rarity_chip_colors(_n, _thr)
                                _chips.append((_sn, _bg, _fg))
                        text = ""   # rendered by delegate
                        color = _score_color(score_val)
                    elif hdr == "7-cnt":
                        count_7 = sum(1 for v in cat.base_stats.values() if v == 7)
                        w_7 = _cw.get(keys[0], 0.0)
                        color = _sevens_color(count_7, _max_7_count, w_7 >= 0)
                        text = f"{count_7}x7s"
                    elif hdr == "Trait":
                        # Value mode: individual colored chips per rated trait
                        # Hide entirely when the trait weight is 0 (no scoring context)
                        _chips = []
                        if _cw.get("unique_ma_max", 0.0) != 0.0:
                            for _desc, _pts in result.breakdown:
                                if _desc.startswith(("Sole owner", "Top Priority (÷", "Desirable (÷", "Undesirable:")):
                                    _tname = _desc.split(": ", 1)[1]
                                    if _desc.startswith(("Sole owner (top priority)", "Top Priority (÷")):
                                        _bg, _fg = _CHIP_TOP_PRIORITY
                                    elif _pts > 0:
                                        _bg, _fg = _CHIP_DESIRABLE
                                    else:
                                        _bg, _fg = _CHIP_UNDESIRABLE
                                    _chips.append((_tname, _bg, _fg))
                        text = ""   # rendered by delegate
                        color = _score_color(score_val)
                    elif hdr == "Aggro":
                        _high_ag_w = _cw.get("high_aggression", 0.0)
                        _low_ag_w  = _cw.get("low_aggression",  0.0)
                        _high_ag_clr, _low_ag_clr = _paired_weight_colors(_high_ag_w, _low_ag_w)
                        a = cat.aggression
                        if a is None:
                            text, color = "?", "#666"
                        elif a >= TRAIT_HIGH_THRESHOLD:
                            text, color = "▲Hi", _high_ag_clr
                        elif a < TRAIT_LOW_THRESHOLD:
                            text, color = "▼Lo", _low_ag_clr
                        else:
                            text, color = "—", "#555555"
                    elif hdr == "4+Ch":
                        if ch_in_scope >= 4:
                            text = f"👶×{ch_in_scope}"
                            color = _score_color(score_val) if score_val != 0 else CLR_UNDESIRABLE
                        else:
                            text = ""
                            color = "#555555"
                    elif hdr == "Gene":
                        text = "✦" if scope_rel_count == 0 else ""
                        if scope_rel_count == 0:
                            color = CLR_DESIRABLE
                        else:
                            _total = len(_all_scope_rel_counts) if _all_scope_rel_counts else 1
                            _pct = sum(1 for v in _all_scope_rel_counts if v <= scope_rel_count) / _total * 100
                            if _pct >= 75: color = CLR_UNDESIRABLE
                            elif _pct >= 50: color = "#e08030"
                            else: color = "#b0a040"
                    elif hdr == "Gender?":
                        gd = getattr(cat, 'gender_display', '?')
                        if gd == '?':
                            _chips = [("⚥", "#302010", "#ccaa44")]
                            text, color = "", "#ccaa44"
                        else:
                            text, color = "", "#444444"
                    elif hdr == "Libido":
                        _high_lb_w = _cw.get("high_libido", 0.0)
                        _low_lb_w  = _cw.get("low_libido",  0.0)
                        _high_lb_clr, _low_lb_clr = _paired_weight_colors(_high_lb_w, _low_lb_w)
                        lb = cat.libido
                        if lb is None:
                            text, color = "?", "#666"
                        elif lb >= TRAIT_HIGH_THRESHOLD:
                            text, color = "❤️", _high_lb_clr
                        elif lb < TRAIT_LOW_THRESHOLD:
                            text, color = "💙", _low_lb_clr
                        else:
                            text, color = "—", "#555555"
                    elif hdr == "Age":
                        age = getattr(cat, 'age', None)
                        if age is None:
                            text, color = "-", "#666"
                        else:
                            _age_thr = int(round(_cw.get("age_threshold", 10.0)))
                            _over = age - _age_thr
                            _t = 0.0 if _over <= 0 else min(1.0, _over / 20.0)
                            color = _lerp_color("#888888", "#cc3333", _t)
                            if _over > 0:
                                text = f"⏳{age}"
                            else:
                                text = str(age)
                        score_val = float(age) if age is not None else 0.0
                    elif hdr == "7-Sub":
                        text  = f"▲{_sub_count}" if _sub_count else ""
                        color = "#cc8844" if _sub_count else "#333333"
                    else:
                        text = f"{score_val:+.1f}" if score_val != 0 else ""
                        color = "#888888"
                    sub_item = _NumericSortItem(text)
                    sub_item.setData(Qt.UserRole, score_val)
                    if hdr in ("Trait", "7-rare", "Gender?") and _chips:
                        sub_item.setData(_CHIP_ROLE, _chips)
                    sub_item.setTextAlignment(Qt.AlignCenter)
                    sub_item.setForeground(QColor(color))
                    if self._display_mode == "both" and _score_for_sub != 0:
                        sub_item.setData(_SCORE_SECONDARY_ROLE, f"{_score_for_sub:+.1f}")
                    if self._display_mode == "heatmap" and ci in _col_max_abs:
                        sub_item.setData(_HEATMAP_ROLE,
                                         _score_for_sub / _col_max_abs[ci] if _score_for_sub != 0 else 0.0)
                else:
                    # ── Score display mode: always show numeric score ──
                    if hdr == "7-cnt":
                        count_7 = sum(1 for v in cat.base_stats.values() if v == 7)
                        w_7 = _cw.get(keys[0], 0.0)
                        color = _sevens_color(count_7, _max_7_count, w_7 >= 0)
                    elif hdr == "Aggro":
                        _hi, _lo = _paired_weight_colors(
                            _cw.get("high_aggression", 0.0), _cw.get("low_aggression", 0.0))
                        a = cat.aggression
                        if a is None:       color = "#666"
                        elif a >= TRAIT_HIGH_THRESHOLD: color = _hi
                        elif a < TRAIT_LOW_THRESHOLD:   color = _lo
                        else:               color = "#888888"
                    elif hdr == "Libido":
                        _hi, _lo = _paired_weight_colors(
                            _cw.get("high_libido", 0.0), _cw.get("low_libido", 0.0))
                        lb = cat.libido
                        if lb is None:      color = "#666"
                        elif lb >= TRAIT_HIGH_THRESHOLD: color = _hi
                        elif lb < TRAIT_LOW_THRESHOLD:   color = _lo
                        else:               color = "#888888"
                    elif hdr == "Sexual":
                        _gay_clr, _bi_clr = _paired_weight_colors(
                            _cw.get("gay_pref", 0.0), _cw.get("bi_pref", 0.0))
                        _sex = getattr(cat, 'sexuality', 'straight') or 'straight'
                        if _sex == 'gay':   color = _gay_clr
                        elif _sex == 'bi':  color = _bi_clr
                        else:               color = "#444444"
                    else:
                        color = _score_color(score_val)
                    text = f"{score_val:+.1f}" if score_val != 0 else ""
                    sub_item = _NumericSortItem(text)
                    sub_item.setData(Qt.UserRole, score_val)
                    sub_item.setTextAlignment(Qt.AlignCenter)
                    sub_item.setForeground(QColor(color))
                sub_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._score_table.setItem(row, col_idx, sub_item)

            # ── Total score ──
            score_item = _NumericSortItem(f"{result.total:+.1f}")
            score_item.setData(Qt.UserRole, result.total)
            score_item.setTextAlignment(Qt.AlignCenter)
            _sc_total = len(_all_scores_sorted)
            if _sc_total > 0:
                _sc_rank = sum(1 for v in _all_scores_sorted if v <= result.total)
                _sc_pct = _sc_rank / _sc_total * 100
                if _sc_pct >= 75:
                    _sc_color = CLR_DESIRABLE
                elif _sc_pct >= 50:
                    _sc_color = "#b0a040"
                elif _sc_pct >= 25:
                    _sc_color = "#e08030"
                else:
                    _sc_color = "#cc3333"
            else:
                _sc_color = "#888888"
            score_item.setForeground(QColor(_sc_color))
            score_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._score_table.setItem(row, COL_SCORE, score_item)

            # ── No-scope override: replace all score columns with N/A ──
            if _no_scope:
                for _ci in range(len(SCORE_COLUMNS)):
                    _it = _NumericSortItem("N/A")
                    _it.setData(Qt.UserRole, -999.0)
                    _it.setTextAlignment(Qt.AlignCenter)
                    _it.setForeground(QColor("#444444"))
                    _it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self._score_table.setItem(row, _COL_SCORE_START + _ci, _it)
                _sc_it = _NumericSortItem("N/A")
                _sc_it.setData(Qt.UserRole, -999.0)
                _sc_it.setTextAlignment(Qt.AlignCenter)
                _sc_it.setForeground(QColor("#444444"))
                _sc_it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self._score_table.setItem(row, COL_SCORE, _sc_it)

            # ── Tooltip ──
            tooltip = self._build_cat_tooltip(cat, result, scope_cats)
            for col in range(len(_ALL_HEADERS)):
                item = self._score_table.item(row, col)
                if item:
                    item.setToolTip(tooltip)
            self._score_table.setRowHeight(row, 36 if self._display_mode == "both" else 22)

        self._score_table.setSortingEnabled(True)
        shh = self._score_table.horizontalHeader()
        shh.blockSignals(True)
        self._score_table.sortItems(self._sort_col, self._sort_order)
        shh.blockSignals(False)

        # Apply row filters (hide cats that don't match active filters)
        _alive_by_name = {c.name: c for c in alive}
        _passes = {
            id(cat): cat_passes_filter(
                cat, results[id(cat)], _children_in_scope(cat),
                self._filters, TRAIT_LOW_THRESHOLD, TRAIT_HIGH_THRESHOLD,
                self._room_display,
            )
            for cat in alive
        }
        for _r in range(self._score_table.rowCount()):
            _ni = self._score_table.item(_r, COL_NAME)
            if _ni:
                _cat = _alive_by_name.get(_ni.text())
                self._score_table.setRowHidden(_r, not (_cat and _passes.get(id(_cat), True)))

        if _restore_name:
            for r in range(self._score_table.rowCount()):
                item = self._score_table.item(r, 0)
                if item and item.text() == _restore_name:
                    self._score_table.blockSignals(True)
                    self._score_table.selectRow(r)
                    self._score_table.blockSignals(False)
                    break

        # Keep hate overlay in sync after the table is rebuilt
        self._hate_overlay.update()
        # Keep children panel in sync (scope filter may have changed)
        self._refresh_children_panel()

    # ── Weights popup ─────────────────────────────────────────────────────────

    def _show_weights_popup(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Scoring Weights")
        dlg.setModal(True)
        dlg.setStyleSheet("background:#0a0a18; color:#ddd;")
        dlg.resize(440, 380)

        vb = QVBoxLayout(dlg)
        vb.setContentsMargins(16, 16, 16, 16)
        vb.setSpacing(8)

        title = QLabel("Breed Priority - Scoring Weights")
        title.setStyleSheet("color:#ddd; font-size:13px; font-weight:bold;")
        vb.addWidget(title)

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Attribute", "Weight"])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(_PRIORITY_TABLE_STYLE)
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        table.setColumnWidth(1, 90)

        w = self._weights
        _thr = int(round(w.get("stat_7_threshold", 7.0)))
        _n_stats = 7
        rows_data = [
            ("── 7-rare: bonus per stat where few scope cats share that 7 ──", ""),
            (f"  7 in a stat (≤{_thr} cats in scope have it)",  f"+{w['stat_7']:.0f}"),
            (f"  7 in a stat ({_thr+1} cats in scope)",         f"+{max(0.1, round(w['stat_7']*_thr/(_thr+1),1)):.1f}"),
            (f"  7 in a stat ({_thr+3} cats in scope)",         f"+{max(0.1, round(w['stat_7']*_thr/(_thr+3),1)):.1f}"),
            (f"  7 in a stat ({_thr+6} cats in scope)",         f"+{max(0.1, round(w['stat_7']*_thr/(_thr+6),1)):.1f}"),
            (f"  7 in a stat (sole owner, none in scope)",      f"+{w['stat_7']*2:.0f} (★★ bonus)"),
            ("── 7-cnt: bonus for total 7's this cat personally owns ──", ""),
            (f"  1 stat at 7",   f"+{w['stat_7_count']*1:.2f}"),
            (f"  3 stats at 7",  f"+{w['stat_7_count']*3:.2f}"),
            (f"  5 stats at 7",  f"+{w['stat_7_count']*5:.2f}"),
            (f"  7 stats at 7",  f"+{w['stat_7_count']*7:.2f} (max)"),
            ("Trait - desirable sole owner",                   f"+{2*w['unique_ma_max']:.1f}"),
            ("Trait - desirable, shared with N cats",         f"+{w['unique_ma_max']:.1f} ÷ N"),
            ("Trait - neutral or undecided",                   "+0.00"),
            ("Trait - undesirable",                           f"-{w['unique_ma_max']:.1f}"),
            (f"Low aggression (<{TRAIT_LOW_THRESHOLD*100:.0f}%)",   f"+{w['low_aggression']:.1f}"),
            ("Unknown gender (?)",                                    f"+{w['unknown_gender']:.1f}"),
            (f"High libido (≥{TRAIT_HIGH_THRESHOLD*100:.0f}%)",      f"+{w['high_libido']:.1f}"),
            (f"High aggression (≥{TRAIT_HIGH_THRESHOLD*100:.0f}%)",  f"{w['high_aggression']:.1f}"),
            (f"Low libido (<{TRAIT_LOW_THRESHOLD*100:.0f}%)",        f"{w['low_libido']:.1f}"),
            ("Genetic Novelty (no relatives in scope)",        f"+{w['no_children']:.1f}"),
            ("4+ children in scope",                           f"{w['many_children']:.1f}"),
            ("Love interest in scope",                         f"+{w['love_interest']:.1f}"),
            ("Rival in scope",                                 f"{w['rivalry']:.1f}"),
            ("── age penalty: multiplies per 3 years above threshold ──", ""),
            (f"  Age ≤ {int(round(w.get('age_threshold',10)))} (at or below threshold)",  "+0"),
            (f"  Age {int(round(w.get('age_threshold',10)))+1} (+1 over, 1×)",  f"{w['age_penalty']:.1f}"),
            (f"  Age {int(round(w.get('age_threshold',10)))+4} (+4 over, 2×)",  f"{2*w['age_penalty']:.1f}"),
            (f"  Age {int(round(w.get('age_threshold',10)))+7} (+7 over, 3×)",  f"{3*w['age_penalty']:.1f}"),
        ]
        table.setRowCount(len(rows_data))
        for r, (attr, wt) in enumerate(rows_data):
            is_header = wt == ""
            a_item = QTableWidgetItem(attr)
            a_item.setFlags(Qt.ItemIsEnabled)
            if is_header:
                a_item.setForeground(QColor("#7070c0"))
                f = a_item.font()
                f.setItalic(True)
                a_item.setFont(f)
            w_item = QTableWidgetItem(wt)
            w_item.setFlags(Qt.ItemIsEnabled)
            w_item.setTextAlignment(Qt.AlignCenter)
            if wt.startswith("+"):
                w_item.setForeground(QColor("#1ec8a0"))
            elif wt.startswith("-"):
                w_item.setForeground(QColor("#e04040"))
            table.setItem(r, 0, a_item)
            table.setItem(r, 1, w_item)
            table.setRowHeight(r, 22 if is_header else 24)
        vb.addWidget(table)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            "QPushButton { color:#ccc; background:#1a1a32; border:1px solid #2a2a4a;"
            " padding:6px 20px; border-radius:4px; font-size:12px; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        close_btn.clicked.connect(dlg.accept)
        vb.addWidget(close_btn, alignment=Qt.AlignRight)
        dlg.exec()
