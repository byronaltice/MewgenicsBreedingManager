"""Breed Priority view and scoring logic.

Standalone module — no imports from mewgenics_manager to avoid circular deps.
Game-specific helpers (STAT_NAMES, ROOM_DISPLAY, mutation_display_name,
ability_tip) are injected via compute_breed_priority_score() parameters and
BreedPriorityView.__init__() arguments.
"""

import os
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QCheckBox, QComboBox, QPushButton, QDialog, QGridLayout,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush


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


# ── Scoring constants ─────────────────────────────────────────────────────────

BREED_PRIORITY_WEIGHTS = {
    "stat_7":          5.0,
    "unique_ma_max":   2.0,
    "low_aggression":  1.0,
    "unknown_gender":  1.0,
    "high_libido":     0.5,
    "high_aggression": -1.0,
    "low_libido":      -0.5,
    "no_children":     4.0,
    "many_children":   -3.0,
}

# (key, short label) pairs for the weight editor UI — in display order
WEIGHT_UI_ROWS = [
    ("stat_7",          "7-stat score"),
    ("unique_ma_max",   "Trait score"),
    ("low_aggression",  "Low aggression"),
    ("unknown_gender",  "Unknown gender"),
    ("high_libido",     "High libido"),
    ("high_aggression", "High aggression"),
    ("low_libido",      "Low libido"),
    ("no_children",     "Genetic Novelty"),
    ("many_children",   "4+ children"),
]

# (threshold, label, color) — first match wins; None threshold = catch-all
BREED_PRIORITY_TIERS = [
    (10,   "Keep",     "#f0c060"),
    ( 4,   "Good",     "#1ec8a0"),
    ( 0,   "Neutral",  "#777777"),
    (-5,   "Consider", "#e08030"),
    (None, "Cull",     "#e04040"),
]

# Index → (display label, stored value or None to remove from dict)
TRAIT_RATING_OPTIONS = [
    ("Desirable — sole owner +4, shared +2÷n",  1),
    ("Neutral — reviewed, not scored",            0),
    ("Undecided — not yet reviewed",              None),
    ("Undesirable — scored −2",                  -1),
]
TRAIT_RATING_LABELS = [label for label, _ in TRAIT_RATING_OPTIONS]
TRAIT_RATING_VALUES = [val   for _, val  in TRAIT_RATING_OPTIONS]
RATING_SHORT_LABELS = ["Desirable", "Neutral", "Undecided", "Undesirable"]
RATING_ITEM_COLORS  = ["#6aaa6a", "#b0a040", "#888899", "#aa6a6a"]

_PRIORITY_TABLE_STYLE = """
    QTableWidget {
        background:#0d0d1c; alternate-background-color:#131326;
        color:#ddd; border:none; font-size:12px;
    }
    QTableWidget::item { padding:3px 4px; }
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
    __slots__ = ("total", "tier", "tier_color", "breakdown")

    def __init__(self, total: float, tier: str, tier_color: str, breakdown: list):
        self.total = total
        self.tier = tier
        self.tier_color = tier_color
        self.breakdown = breakdown


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
                         mutation_display_name=None) -> ScoreResult:
    """Compute breed priority score for a cat.

    stat_names: ordered list of stat keys (e.g. ["STR","DEX",...]).
    mutation_display_name: callable(str) -> str for display labels in breakdown.
    ma_ratings: {trait_key: int} where 1=Desirable, 0=Neutral, -1=Undesirable.
      Ability keys are base ability names; mutation keys are display strings.
    """
    _w = weights if weights is not None else BREED_PRIORITY_WEIGHTS
    _display = mutation_display_name if mutation_display_name else (lambda n: n)
    breakdown: list = []
    scope_set = {id(c) for c in scope_cats}

    # ── Positive attributes ───────────────────────────────────────────────────
    if cat.gender == "?":
        breakdown.append(("Unknown gender (?)", _w["unknown_gender"]))

    if cat.aggression is not None and cat.aggression <= 0.3333:
        breakdown.append(("Low aggression", _w["low_aggression"]))

    if cat.libido is not None and cat.libido > 0.6667:
        breakdown.append(("High libido", _w["high_libido"]))

    for stat_name in stat_names:
        if cat.base_stats.get(stat_name) == 7:
            n = sum(1 for c in scope_cats if c.base_stats.get(stat_name) == 7)
            w = max(1, _w["stat_7"] - max(0, n - 7))
            penalty = n - 7
            label = (
                f"7 in {stat_name} ({n} in scope)"
                if penalty <= 0 else
                f"7 in {stat_name} ({n} in scope, −{penalty})"
            )
            breakdown.append((label, float(w)))

    # Combined trait set per scope cat (ability base names + mutation display strings)
    scope_base_traits = {
        id(c): (
            {ability_base(a) for a in list(c.abilities) + list(c.passive_abilities)}
            | set(c.mutations)
        )
        for c in scope_cats
    }
    _u = _w["unique_ma_max"]

    # Score abilities (active + passive), normalized to base names
    all_ability_bases = list({
        ability_base(m) for m in list(cat.abilities) + list(cat.passive_abilities)
        if not is_basic_trait(m)
    })
    for ma in all_ability_bases:
        rating = ma_ratings.get(ma)
        display = _display(ma)
        n = max(1, sum(1 for c in scope_cats if ma in scope_base_traits[id(c)]))
        if rating in (None, 0):
            pass
        elif n == 1:
            if rating == 1:
                breakdown.append((f"Sole owner (desirable): {display}", 2 * _u))
            else:
                breakdown.append((f"Sole owner (undesirable): {display}", -_u))
        elif rating == 1:
            breakdown.append((f"Desirable (÷{n}): {display}", round(_u / n, 3)))
        elif rating == -1:
            breakdown.append((f"Undesirable: {display}", -_u))

    # Score visual mutations (keyed by display string from cat.mutations)
    for ma in cat.mutations:
        if is_basic_trait(ma):
            continue
        rating = ma_ratings.get(ma)
        n = max(1, sum(1 for c in scope_cats if ma in scope_base_traits[id(c)]))
        if rating in (None, 0):
            pass
        elif n == 1:
            if rating == 1:
                breakdown.append((f"Sole owner (desirable): {ma}", 2 * _u))
            else:
                breakdown.append((f"Sole owner (undesirable): {ma}", -_u))
        elif rating == 1:
            breakdown.append((f"Desirable (÷{n}): {ma}", round(_u / n, 3)))
        elif rating == -1:
            breakdown.append((f"Undesirable: {ma}", -_u))

    # ── Negative attributes ───────────────────────────────────────────────────
    if cat.aggression is not None and cat.aggression > 0.6667:
        breakdown.append(("High aggression", _w["high_aggression"]))

    if cat.libido is not None and cat.libido <= 0.3333:
        breakdown.append(("Low libido", _w["low_libido"]))

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
    if len(children_in_scope) >= 4:
        breakdown.append((
            f"{len(children_in_scope)} children in scope (≥4)",
            _w["many_children"],
        ))

    total = sum(pts for _, pts in breakdown)
    tier, color = priority_tier(total)
    return ScoreResult(total=total, tier=tier, tier_color=color, breakdown=breakdown)


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


class _WeightSpin(QWidget):
    """Compact value editor with visible ▲/▼ buttons."""
    valueChanged = Signal(float)

    _BTN_STYLE = (
        "QPushButton { color:#ccc; background:#3a3a60; border:1px solid #4a4a80;"
        " font-size:8px; padding:0; }"
        "QPushButton:hover { background:#5050a0; }"
        "QPushButton:pressed { background:#6060c0; }"
    )
    _LBL_STYLE = (
        "color:#ccc; font-size:10px; background:#131326;"
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
        self._lbl.setStyleSheet(self._LBL_STYLE)

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

    def _set(self, val: float):
        val = round(max(self._min, min(self._max, val)) / self._step) * self._step
        if val != self._value:
            self._value = val
            self._lbl.setText(self._fmt(val))
            if not self.signalsBlocked():
                self.valueChanged.emit(val)

    def _inc(self): self._set(self._value + self._step)
    def _dec(self): self._set(self._value - self._step)

    def value(self) -> float:
        return self._value

    def setValue(self, val: float):
        self._value = float(val)
        self._lbl.setText(self._fmt(self._value))


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
        self._load_ratings()
        self._build_ui()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_ratings(self):
        if os.path.exists(self._ratings_path):
            try:
                with open(self._ratings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for section in ("abilities", "mutations"):
                    for trait, val in data.get(section, {}).items():
                        if val in (-1, 0, 1):
                            self._ma_ratings[trait] = val
                self._saved_scope = data.get("scope", {})
                for key in BREED_PRIORITY_WEIGHTS:
                    if key in data.get("weights", {}):
                        self._weights[key] = float(data["weights"][key])
            except Exception:
                pass

    def _save_ratings(self):
        ability_set = {
            ability_base(a)
            for c in self._cats
            for a in list(c.abilities) + list(c.passive_abilities)
            if not is_basic_trait(a)
        }
        mutation_set = {m for c in self._cats for m in c.mutations}
        data = {
            "abilities": {k: v for k, v in self._ma_ratings.items() if k in ability_set},
            "mutations": {k: v for k, v in self._ma_ratings.items() if k in mutation_set},
            "scope": self._saved_scope,
            "weights": self._weights,
        }
        try:
            with open(self._ratings_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

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
        return t

    def _build_ui(self):
        vb = QVBoxLayout(self)
        vb.setContentsMargins(0, 0, 0, 0)
        vb.setSpacing(0)

        top_bar = QWidget()
        top_bar.setStyleSheet("background:#16213e; border-bottom:1px solid #1e1e38;")
        top_bar.setFixedHeight(46)
        hb = QHBoxLayout(top_bar)
        hb.setContentsMargins(14, 0, 14, 0)
        title_lbl = QLabel("Breed Priority")
        title_lbl.setStyleSheet("color:#ddd; font-size:16px; font-weight:bold;")
        hb.addWidget(title_lbl)
        hb.addStretch()
        vb.addWidget(top_bar)

        hs = QSplitter(Qt.Horizontal)
        hs.setHandleWidth(6)
        hs.setStyleSheet(SPLITTER_H_STYLE)
        vb.addWidget(hs)

        # Left: scope + weights panel
        left = QWidget()
        left.setFixedWidth(180)
        left.setStyleSheet("background:#14142a;")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 12, 8, 8)
        lv.setSpacing(4)

        scope_lbl = QLabel("COMPARISON SCOPE")
        scope_lbl.setStyleSheet(
            "color:#555; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        lv.addWidget(scope_lbl)

        self._chk_all_cats = QCheckBox("All Cats")
        self._chk_all_cats.setStyleSheet("color:#aaa; font-size:11px;")
        self._chk_all_cats.setChecked(True)
        self._chk_all_cats.stateChanged.connect(self._on_scope_changed)
        lv.addWidget(self._chk_all_cats)

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
        for r, (key, label) in enumerate(WEIGHT_UI_ROWS):
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#888; font-size:10px;")
            spin = _WeightSpin(self._weights[key])
            spin.valueChanged.connect(lambda val, k=key: self._on_weight_changed(k, val))
            wg.addWidget(lbl,  r, 0)
            wg.addWidget(spin, r, 1)
            self._weight_spins[key] = spin

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

        btn_row = len(WEIGHT_UI_ROWS)
        wg.addWidget(reset_btn, btn_row, 0)
        wg.addWidget(info_btn,  btn_row, 1)
        lv.addWidget(weights_widget)
        lv.addStretch()
        hs.addWidget(left)

        # Right: score table (top) + trait editor (bottom)
        vs = QSplitter(Qt.Vertical)
        vs.setHandleWidth(6)
        vs.setStyleSheet(SPLITTER_V_STYLE)
        hs.addWidget(vs)
        hs.setStretchFactor(0, 0)
        hs.setStretchFactor(1, 1)

        self._score_table = QTableWidget()
        self._score_table.setColumnCount(5)
        self._score_table.setHorizontalHeaderLabels(["Name", "Room", "Score", "Tier", "Age"])
        self._score_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._score_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._score_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._score_table.verticalHeader().setVisible(False)
        self._score_table.setShowGrid(False)
        self._score_table.setAlternatingRowColors(True)
        self._score_table.setSortingEnabled(True)
        self._score_table.setStyleSheet(_PRIORITY_TABLE_STYLE)
        shh = self._score_table.horizontalHeader()
        shh.setSectionResizeMode(0, QHeaderView.Stretch)
        shh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        shh.setSectionResizeMode(2, QHeaderView.Fixed)
        self._score_table.setColumnWidth(2, 65)
        shh.setSectionResizeMode(3, QHeaderView.Fixed)
        self._score_table.setColumnWidth(3, 85)
        shh.setSectionResizeMode(4, QHeaderView.Fixed)
        self._score_table.setColumnWidth(4, 38)
        vs.addWidget(self._score_table)
        self._score_table.itemSelectionChanged.connect(self._on_cat_selected)

        ma_widget = QWidget()
        ma_widget.setStyleSheet("background:#0d0d1c;")
        ma_vb = QVBoxLayout(ma_widget)
        ma_vb.setContentsMargins(8, 6, 8, 6)
        ma_vb.setSpacing(4)
        ma_lbl = QLabel("TRAIT DESIRABILITY")
        ma_lbl.setStyleSheet(
            "color:#555; font-size:10px; font-weight:bold; letter-spacing:1px;"
        )
        ma_vb.addWidget(ma_lbl)
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
        ma_vb.addWidget(ma_hs)
        vs.addWidget(ma_widget)
        vs.setSizes([500, 220])
        vs.setStretchFactor(0, 1)
        vs.setStretchFactor(1, 0)

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
        self._refresh_trait_table_order()

    def _refresh_trait_table_order(self):
        cat = self._selected_cat
        if cat is None:
            self._populate_trait_table(self._abilities_table, self._all_abilities)
            self._populate_trait_table(self._mutations_table, self._all_mutations)
            return

        cat_ab = {
            ability_base(a)
            for a in list(cat.abilities) + list(cat.passive_abilities)
            if not is_basic_trait(a)
        }
        cat_mut = set(cat.mutations)

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

    # ── Scope helpers ─────────────────────────────────────────────────────────

    def _get_scope_cats(self) -> list:
        alive = [c for c in self._cats if c.status == "In House"]
        if self._chk_all_cats.isChecked():
            return alive
        selected = {r for r, chk in self._room_checks.items() if chk.isChecked()}
        return [c for c in alive if c.room in selected] if selected else alive

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

    def _on_scope_changed(self, *_):
        all_checked = self._chk_all_cats.isChecked()
        for chk in self._room_checks.values():
            chk.setEnabled(not all_checked)
        self._saved_scope = {
            "all_cats": all_checked,
            "rooms": {r: chk.isChecked() for r, chk in self._room_checks.items()},
        }
        self._save_ratings()
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
        for room in rooms:
            chk = QCheckBox(self._room_display.get(room, room))
            chk.setStyleSheet("color:#888; font-size:11px;")
            chk.setChecked(saved_rooms.get(room, False))
            chk.setEnabled(not self._chk_all_cats.isChecked())
            chk.stateChanged.connect(self._on_scope_changed)
            self._room_checks_vb.addWidget(chk)
            self._room_checks[room] = chk

        self._all_abilities = sorted({
            ability_base(a)
            for c in alive
            for a in list(c.abilities) + list(c.passive_abilities)
            if not is_basic_trait(a)
        })
        self._all_mutations = sorted({
            m for c in alive for m in c.mutations
            if not is_basic_trait(m)
        })
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
            tip = self._ability_tip(trait)
            if tip:
                name_item.setToolTip(f"{display}\n\n{tip}")
            table.setItem(row, 0, name_item)

            combo = _RatingCombo()
            for ci, clr in enumerate(RATING_ITEM_COLORS):
                combo.model().item(ci).setForeground(QColor(clr))
            if tip:
                combo.setToolTip(f"{display}\n\n{tip}")
            init_idx = {1: 0, 0: 1, None: 2, -1: 3}.get(current, 2)
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
                {ability_base(a) for a in list(c.abilities) + list(c.passive_abilities)
                 if not is_basic_trait(a)}
                | set(c.mutations)
            )
            for c in scope_cats
        }
        _u = self._weights["unique_ma_max"]

        passive_base = {
            ability_base(p) for p in cat.passive_abilities if not is_basic_trait(p)
        }
        seen: set = set()
        active_traits = [
            t for t in (
                ability_base(a) for a in cat.abilities
                if not is_basic_trait(a) and ability_base(a) not in passive_base
            )
            if not (t in seen or seen.add(t))
        ]
        passive_traits = sorted(passive_base)
        mutation_traits = [t for t in cat.mutations if not is_basic_trait(t)]

        def _trait_rows_for(traits: list) -> list:
            rows = []
            for trait in traits:
                display = self._display_name(trait)
                rating = self._ma_ratings.get(trait)
                n = max(1, sum(1 for c in scope_cats if trait in _scope_base[id(c)]))
                cats_str = f" ({n} cats)"
                if rating in (None, 0):
                    color = "#4a4a6a" if rating is None else "#7a7a9a"
                    label = f"{display}  ?" if rating is None else display
                    rows.append(row(color, label, "+0.00"))
                elif n == 1:
                    pts = 2 * _u if rating == 1 else -_u
                    star = "★★" if rating == 1 else "★"
                    clr  = "#1ec8a0" if rating == 1 else "#e04040"
                    rows.append(row(clr, f"{display}  {star}", f"{pts:+.2f}"))
                elif rating == 1:
                    pts = round(_u / n, 3)
                    rows.append(row("#1ec8a0", display, f"{pts:+.2f}{cats_str}"))
                elif rating == -1:
                    rows.append(row("#e04040", display, f"{-_u:+.2f}{cats_str}"))
                else:
                    rows.append(row("#7a7a9a", display, f"+0.00{cats_str}"))
            return rows

        active_rows   = _trait_rows_for(active_traits)
        passive_rows  = _trait_rows_for(passive_traits)
        mutation_rows = _trait_rows_for(mutation_traits)

        scope_set = {id(c) for c in scope_cats}
        children_in_scope = [c for c in cat.children if id(c) in scope_set]
        other_rows = []
        for desc, pts in result.breakdown:
            if desc.startswith(("Sole owner", "Desirable (÷", "Undesirable:")):
                continue
            color = "#1ec8a0" if pts > 0 else "#e04040"
            other_rows.append(row(color, desc, f"{pts:+.2f}"))
            if "children in scope" in desc and children_in_scope:
                for child in children_in_scope:
                    room = self._room_display.get(child.room, child.room or "?")
                    other_rows.append(row("#555577", f"&nbsp;&nbsp;↳ {child.name}  ({room})", ""))

        total_color = "#1ec8a0" if result.total > 0 else "#e04040" if result.total < 0 else "#888"
        html_parts = [
            '<html><body style="font-family:monospace;font-size:11px">',
            f'<b style="color:#eee;font-size:12px">{cat.name}</b>',
        ]
        if active_rows:
            html_parts.append('<br><span style="color:#999;font-size:10px">ACTIVE ABILITIES</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(active_rows) + '</table>')
        if passive_rows:
            html_parts.append('<br><span style="color:#999;font-size:10px">PASSIVE ABILITIES</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(passive_rows) + '</table>')
        if mutation_rows:
            html_parts.append('<br><span style="color:#999;font-size:10px">MUTATIONS</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(mutation_rows) + '</table>')
        if other_rows:
            html_parts.append('<br><span style="color:#999;font-size:10px">OTHER</span>')
            html_parts.append('<table cellspacing="0" cellpadding="1">' + "".join(other_rows) + '</table>')
        html_parts.append(
            f'<br><b style="color:{total_color}">Total: {result.total:+.2f} &nbsp; {result.tier}</b>'
        )
        html_parts.append('</body></html>')
        return "".join(html_parts)

    def recompute(self, *_):
        if self._populating:
            return
        _restore_name = self._selected_cat.name if self._selected_cat else None

        scope_cats = self._get_scope_cats()
        alive = [c for c in self._cats if c.status == "In House"]

        self._score_table.setSortingEnabled(False)
        self._score_table.setRowCount(len(alive))
        for row, cat in enumerate(alive):
            result = compute_breed_priority_score(
                cat, scope_cats, self._ma_ratings,
                stat_names=self._stat_names,
                weights=self._weights,
                mutation_display_name=self._display_name,
            )

            name_item = QTableWidgetItem(cat.name)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._score_table.setItem(row, 0, name_item)

            room_item = QTableWidgetItem(self._room_display.get(cat.room, cat.room or "?"))
            room_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._score_table.setItem(row, 1, room_item)

            score_item = _NumericSortItem(f"{result.total:+.1f}")
            score_item.setData(Qt.UserRole, result.total)
            score_item.setTextAlignment(Qt.AlignCenter)
            if result.total > 0:
                score_item.setForeground(QColor("#1ec8a0"))
            elif result.total < 0:
                score_item.setForeground(QColor("#e04040"))
            else:
                score_item.setForeground(QColor("#777777"))
            score_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._score_table.setItem(row, 2, score_item)

            tier_item = _NumericSortItem(result.tier)
            tier_item.setData(Qt.UserRole, result.total)
            tier_item.setForeground(QColor(result.tier_color))
            tier_item.setTextAlignment(Qt.AlignCenter)
            tier_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._score_table.setItem(row, 3, tier_item)

            age_text = str(int(cat.age)) if cat.age is not None else "—"
            age_item = _NumericSortItem(age_text)
            age_item.setData(Qt.UserRole, cat.age if cat.age is not None else -1.0)
            age_item.setTextAlignment(Qt.AlignCenter)
            age_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._score_table.setItem(row, 4, age_item)

            tooltip = self._build_cat_tooltip(cat, result, scope_cats)
            for col in range(5):
                item = self._score_table.item(row, col)
                if item:
                    item.setToolTip(tooltip)
            self._score_table.setRowHeight(row, 22)

        self._score_table.setSortingEnabled(True)
        self._score_table.sortItems(2, Qt.DescendingOrder)

        if _restore_name:
            for r in range(self._score_table.rowCount()):
                item = self._score_table.item(r, 0)
                if item and item.text() == _restore_name:
                    self._score_table.blockSignals(True)
                    self._score_table.selectRow(r)
                    self._score_table.blockSignals(False)
                    break

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

        title = QLabel("Breed Priority — Scoring Weights")
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
        rows_data = [
            ("7 in a stat (≤7 cats in scope have it)",         f"+{w['stat_7']:.0f}"),
            ("7 in a stat (8 cats)",                           f"+{max(1, w['stat_7']-1):.0f}"),
            ("7 in a stat (9 cats)",                           f"+{max(1, w['stat_7']-2):.0f}"),
            ("7 in a stat (10 cats)",                          f"+{max(1, w['stat_7']-3):.0f}"),
            ("7 in a stat (11+ cats)",                         f"+{max(1, w['stat_7']-4):.0f} (min +1)"),
            ("Trait — desirable sole owner",                   f"+{2*w['unique_ma_max']:.1f}"),
            ("Trait — desirable, shared with N cats",         f"+{w['unique_ma_max']:.1f} ÷ N"),
            ("Trait — neutral or undecided",                   "+0.00"),
            ("Trait — undesirable",                           f"-{w['unique_ma_max']:.1f}"),
            ("Low aggression (≤33%)",                          f"+{w['low_aggression']:.1f}"),
            ("Unknown gender (?)",                             f"+{w['unknown_gender']:.1f}"),
            ("High libido (>67%)",                             f"+{w['high_libido']:.1f}"),
            ("High aggression (>67%)",                         f"{w['high_aggression']:.1f}"),
            ("Low libido (≤33%)",                              f"{w['low_libido']:.1f}"),
            ("Genetic Novelty (no relatives in scope)",        f"+{w['no_children']:.1f}"),
            ("4+ children in scope",                           f"{w['many_children']:.1f}"),
        ]
        table.setRowCount(len(rows_data))
        for r, (attr, wt) in enumerate(rows_data):
            a_item = QTableWidgetItem(attr)
            a_item.setFlags(Qt.ItemIsEnabled)
            w_item = QTableWidgetItem(wt)
            w_item.setFlags(Qt.ItemIsEnabled)
            w_item.setTextAlignment(Qt.AlignCenter)
            if wt.startswith("+"):
                w_item.setForeground(QColor("#1ec8a0"))
            elif wt.startswith("-"):
                w_item.setForeground(QColor("#e04040"))
            table.setItem(r, 0, a_item)
            table.setItem(r, 1, w_item)
            table.setRowHeight(r, 24)
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
