"""Profile Compare dialog — per-row editor builder helpers.

Each add_* function appends one or more rows to the shared QGridLayout and
registers a RowDescriptor so the dialog can track editors for change handling
and "show only differences" filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QLineEdit, QCheckBox, QGridLayout, QWidget
from PySide6.QtCore import Qt

from .constants import (
    COL_LABEL_WIDTH, COL_LABEL_MIN_WIDTH,
    INT_PARAM_RANGES,
    LABEL_FONT_SIZE_PX, ROW_BG_EVEN, ROW_BG_ODD,
    SECTION_HEADER_FONT_SIZE_PX, SECTION_HEADER_COLOR, SECTION_HEADER_BORDER_COLOR,
)
from ..theme import CLR_TEXT_CONTENT_SECONDARY
from ..delegates import _RatingCombo
from ..widgets import _WeightSpin, _IntParamSpin

if TYPE_CHECKING:
    pass

# Sentinel for empty-slot values
_EMPTY = object()


@dataclass
class RowDescriptor:
    """Describes one data row: its label, per-slot editor widgets, and a value getter."""
    label: QLabel
    editors: dict[int, QWidget]
    # value_getter(staged_blob) -> comparable value; receives the staged dict for one slot
    value_getter: Callable[[dict], object]
    grid_row: int = 0   # grid row index (set by append_data_row via RowTracker)
    parity: int = 0     # 0 = even, 1 = odd (set by RowTracker)


class RowTracker:
    """Tracks all rows added to the grid for visibility management."""

    def __init__(self):
        self.data_rows: list[RowDescriptor] = []
        # List of (header_label, grid_row_idx)
        self.header_rows: list[tuple[QLabel, int]] = []
        self._grid_row: int = 0
        self._data_parity: int = 0

    def next_row(self) -> int:
        r = self._grid_row
        self._grid_row += 1
        return r

    def current_row(self) -> int:
        return self._grid_row

    def _next_parity(self) -> int:
        p = self._data_parity
        self._data_parity ^= 1
        return p

    def append_data_row(self, desc: RowDescriptor) -> None:
        """Register a data row, recording its grid row and assigning stripe parity."""
        desc.grid_row = self._grid_row - 1  # row was already consumed by next_row()
        desc.parity = self._next_parity()
        self.data_rows.append(desc)


# ── Widget factories ──────────────────────────────────────────────────────────

def _label_widget(text: str, indent: bool = False) -> QLabel:
    """Create a styled row-label widget."""
    lbl = QLabel(text)
    lbl.setMinimumWidth(COL_LABEL_MIN_WIDTH)
    lbl.setFixedWidth(COL_LABEL_WIDTH)
    style = f"color:{CLR_TEXT_CONTENT_SECONDARY}; font-size:{LABEL_FONT_SIZE_PX}px;"
    if indent:
        style += " padding-left:12px;"
    lbl.setStyleSheet(style)
    return lbl


def _section_header(text: str) -> QLabel:
    """Create a styled section-header label spanning all columns.

    Headers use a larger, brighter style so they are visually dominant over
    the 11px row labels beneath them.
    """
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{SECTION_HEADER_COLOR}; font-size:{SECTION_HEADER_FONT_SIZE_PX}px; font-weight:bold;"
        f" letter-spacing:2px; border-bottom:1px solid {SECTION_HEADER_BORDER_COLOR};"
        " padding:10px 0 4px 0; margin-top:6px;"
    )
    return lbl


def _apply_row_stripe(widgets: list[QWidget], parity: int) -> None:
    """Apply alternating row background to a list of widgets."""
    bg = ROW_BG_EVEN if parity == 0 else ROW_BG_ODD
    for w in widgets:
        existing = w.styleSheet()
        # Inject background without clobbering the rest of the stylesheet
        w.setStyleSheet(f"background:{bg}; " + existing)


# ── Section header ────────────────────────────────────────────────────────────

def add_section_header(
    grid: QGridLayout,
    tracker: RowTracker,
    title: str,
    num_cols: int,
) -> int:
    """Add a section-header row spanning all columns. Returns the grid row index."""
    r = tracker.next_row()
    hdr = _section_header(title)
    grid.addWidget(hdr, r, 0, 1, num_cols + 1)
    tracker.header_rows.append((hdr, r))
    return r


# ── Row builders ──────────────────────────────────────────────────────────────

def add_name_row(
    grid: QGridLayout,
    tracker: RowTracker,
    staged: dict[int, dict],
    present_slots: set[int],
    on_changed,  # callable(slot, field, value)
    slot_to_col: dict[int, int] | None = None,
) -> None:
    """Add the profile Name row."""
    r = tracker.next_row()
    lbl = _label_widget("Name")
    grid.addWidget(lbl, r, 0)

    _col = slot_to_col if slot_to_col is not None else {n: n for n in present_slots}
    editors: dict[int, QWidget] = {}
    for n in sorted(present_slots):
        w = QLineEdit(staged[n].get("name", ""))
        w.setMaxLength(80)
        w.setStyleSheet(
            "QLineEdit { background:#0e1828; color:#aabbcc; border:1px solid #1a2a44;"
            " border-radius:3px; padding:1px 4px; font-size:10px; }"
            "QLineEdit:focus { border-color:#2244aa; }"
        )
        slot = n
        w.textChanged.connect(lambda val, s=slot: on_changed(s, "name", val))
        editors[n] = w
        grid.addWidget(w, r, _col[n], Qt.AlignLeft | Qt.AlignVCenter)

    def _name_getter(blob: dict) -> object:
        return blob.get("name", "")

    desc = RowDescriptor(label=lbl, editors=editors, value_getter=_name_getter)
    tracker.append_data_row(desc)
    _apply_row_stripe([lbl] + list(editors.values()), desc.parity)


def add_weight_rows(
    grid: QGridLayout,
    tracker: RowTracker,
    weight_ui_rows: list,
    staged: dict[int, dict],
    present_slots: set[int],
    on_changed,  # callable(slot, key, value)
    slot_to_col: dict[int, int] | None = None,
) -> None:
    """Add one row per entry in WEIGHT_UI_ROWS."""
    _col = slot_to_col if slot_to_col is not None else {n: n for n in present_slots}

    for key, label_spec in weight_ui_rows:
        if key is None:
            # Separator — skip for the compare grid (keep layout compact)
            continue

        if isinstance(label_spec, tuple):
            group_label, sub_label = label_spec
            label_text = f"{group_label} / {sub_label}".strip(" /")
        else:
            label_text = str(label_spec)

        indent = label_text.startswith("  └")
        display_label = label_text.lstrip("  └").strip() if indent else label_text

        r = tracker.next_row()
        lbl = _label_widget(display_label, indent=indent)
        grid.addWidget(lbl, r, 0)

        editors: dict[int, QWidget] = {}
        for n in sorted(present_slots):
            current_val = staged[n].get("weights", {}).get(key, 0.0)
            if key in INT_PARAM_RANGES:
                mn, mx = INT_PARAM_RANGES[key]
                w = _IntParamSpin(int(round(current_val)), min_val=mn, max_val=mx)
            else:
                w = _WeightSpin(float(current_val))
            slot = n
            w.valueChanged.connect(lambda val, s=slot, k=key: on_changed(s, k, val))
            editors[n] = w
            grid.addWidget(w, r, _col[n], Qt.AlignLeft | Qt.AlignVCenter)

        weight_key = key

        def _weight_getter(blob: dict, k=weight_key) -> object:
            return blob.get("weights", {}).get(k)

        desc = RowDescriptor(label=lbl, editors=editors, value_getter=_weight_getter)
        tracker.append_data_row(desc)
        _apply_row_stripe([lbl] + list(editors.values()), desc.parity)


def add_complex_weight_rows(
    grid: QGridLayout,
    tracker: RowTracker,
    complex_weights: list,
    staged: dict[int, dict],
    present_slots: set[int],
    on_changed,  # callable(slot, cw_id, enabled_bool)
    slot_to_col: dict[int, int] | None = None,
) -> None:
    """Add one checkbox row per entry in the complex_weights catalog."""
    _col = slot_to_col if slot_to_col is not None else {n: n for n in present_slots}

    for cw in complex_weights:
        r = tracker.next_row()
        lbl = _label_widget(cw.name or cw.id)
        grid.addWidget(lbl, r, 0)

        editors: dict[int, QWidget] = {}
        for n in sorted(present_slots):
            enabled_ids = set(staged[n].get("complex_weights_enabled_ids", []))
            w = QCheckBox()
            w.setChecked(cw.id in enabled_ids)
            w.setStyleSheet("QCheckBox { color:#aabbcc; font-size:10px; }")
            slot = n
            cw_id = cw.id
            w.stateChanged.connect(
                lambda state, s=slot, cid=cw_id: on_changed(s, cid, bool(state))
            )
            editors[n] = w
            grid.addWidget(w, r, _col[n], Qt.AlignLeft | Qt.AlignVCenter)

        cw_id_cap = cw.id

        def _cw_getter(blob: dict, cid=cw_id_cap) -> object:
            return cid in set(blob.get("complex_weights_enabled_ids") or [])

        desc = RowDescriptor(label=lbl, editors=editors, value_getter=_cw_getter)
        tracker.append_data_row(desc)
        _apply_row_stripe([lbl] + list(editors.values()), desc.parity)


def add_trait_rows(
    grid: QGridLayout,
    tracker: RowTracker,
    trait_names: list[str],
    staged: dict[int, dict],
    present_slots: set[int],
    on_changed,  # callable(slot, trait_name, rating_value)
    label_fn: Callable[[str], str] | None = None,
    slot_to_col: dict[int, int] | None = None,
) -> None:
    """Add one _RatingCombo row per trait name.

    Args:
        label_fn: Optional callable that converts a raw trait key to a display
            label string. If omitted, the raw trait key is used directly.
        slot_to_col: Maps slot numbers to grid column indices. Defaults to
            identity mapping if omitted.
    """
    _resolve_label = label_fn if label_fn is not None else (lambda t: t)
    _col = slot_to_col if slot_to_col is not None else {n: n for n in present_slots}

    for trait in trait_names:
        r = tracker.next_row()
        lbl = _label_widget(_resolve_label(trait))
        grid.addWidget(lbl, r, 0)

        editors: dict[int, QWidget] = {}
        for n in sorted(present_slots):
            rating = staged[n].get("ma_ratings", {}).get(trait)
            rating_to_index = {2: 0, 1: 1, 0: 2, None: 3, -1: 4}
            w = _RatingCombo()
            w.setCurrentIndex(rating_to_index.get(rating, 3))
            slot = n
            trait_name = trait
            w.currentIndexChanged.connect(
                lambda idx, s=slot, t=trait_name: _on_rating_changed(staged, s, t, idx, on_changed)
            )
            editors[n] = w
            grid.addWidget(w, r, _col[n], Qt.AlignLeft | Qt.AlignVCenter)

        trait_cap = trait

        def _trait_getter(blob: dict, t=trait_cap) -> object:
            return blob.get("ma_ratings", {}).get(t, 0)

        desc = RowDescriptor(label=lbl, editors=editors, value_getter=_trait_getter)
        tracker.append_data_row(desc)
        _apply_row_stripe([lbl] + list(editors.values()), desc.parity)


# ── Rating combo helpers ──────────────────────────────────────────────────────

# Rating combo index → stored value
_INDEX_TO_RATING = {0: 2, 1: 1, 2: 0, 3: None, 4: -1}


def _on_rating_changed(
    staged: dict[int, dict],
    slot: int,
    trait: str,
    index: int,
    on_changed,
) -> None:
    """Convert combo index to rating value and call on_changed."""
    rating = _INDEX_TO_RATING.get(index, None)
    on_changed(slot, trait, rating)
