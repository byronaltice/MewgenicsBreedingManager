"""Profile Compare dialog — per-row editor builder helpers.

Each build_* function appends one or more rows to the shared QGridLayout and
returns a list of (slot_num, widget) pairs so the dialog can track editors
for change handling and "show only differences" filtering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLabel, QLineEdit, QCheckBox, QGridLayout, QWidget
from PySide6.QtCore import Qt

from .constants import (
    COL_LABEL_WIDTH, COL_SLOT_WIDTH,
    NUM_PROFILES, EMPTY_SLOT_PLACEHOLDER, INT_PARAM_RANGES,
)
from ..theme import CLR_TEXT_LABEL_GROUP, CLR_TEXT_CONTENT_SECONDARY, CLR_SURFACE_SEPARATOR
from ..delegates import _RatingCombo
from ..widgets import _WeightSpin, _IntParamSpin

if TYPE_CHECKING:
    pass


def _label_widget(text: str, indent: bool = False) -> QLabel:
    """Create a styled row-label widget."""
    lbl = QLabel(text)
    lbl.setFixedWidth(COL_LABEL_WIDTH)
    style = f"color:{CLR_TEXT_CONTENT_SECONDARY}; font-size:10px;"
    if indent:
        style += " padding-left:12px;"
    lbl.setStyleSheet(style)
    return lbl


def _section_header(text: str) -> QLabel:
    """Create a styled section-header label spanning all columns."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{CLR_TEXT_LABEL_GROUP}; font-size:10px; font-weight:bold;"
        f" letter-spacing:1px; border-bottom:1px solid {CLR_SURFACE_SEPARATOR};"
        " padding:4px 0 2px 0;"
    )
    return lbl


def _empty_label() -> QLabel:
    """Placeholder label for an empty profile slot column."""
    lbl = QLabel(EMPTY_SLOT_PLACEHOLDER)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedWidth(COL_SLOT_WIDTH)
    lbl.setStyleSheet(f"color:{CLR_SURFACE_SEPARATOR}; font-size:10px; font-style:italic;")
    return lbl


class RowTracker:
    """Tracks all rows added to the grid for visibility management."""

    def __init__(self):
        # List of (label_widget, {slot: editor_widget}) per data row
        self.data_rows: list[tuple[QLabel, dict[int, QWidget]]] = []
        # List of (header_label, grid_row_idx)
        self.header_rows: list[tuple[QLabel, int]] = []
        self._grid_row: int = 0

    def next_row(self) -> int:
        r = self._grid_row
        self._grid_row += 1
        return r

    def current_row(self) -> int:
        return self._grid_row


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


def add_name_row(
    grid: QGridLayout,
    tracker: RowTracker,
    staged: dict[int, dict],
    present_slots: set[int],
    on_changed,  # callable(slot, value)
) -> None:
    """Add the profile Name row."""
    r = tracker.next_row()
    lbl = _label_widget("Name")
    grid.addWidget(lbl, r, 0)

    editors: dict[int, QWidget] = {}
    for n in range(1, NUM_PROFILES + 1):
        if n not in present_slots:
            w = _empty_label()
        else:
            w = QLineEdit(staged[n].get("name", ""))
            w.setFixedWidth(COL_SLOT_WIDTH)
            w.setMaxLength(80)
            w.setStyleSheet(
                "QLineEdit { background:#0e1828; color:#aabbcc; border:1px solid #1a2a44;"
                " border-radius:3px; padding:1px 4px; font-size:10px; }"
                "QLineEdit:focus { border-color:#2244aa; }"
            )
            slot = n
            w.textChanged.connect(lambda val, s=slot: on_changed(s, "name", val))
        editors[n] = w
        grid.addWidget(w, r, n)

    tracker.data_rows.append((lbl, editors))


def add_weight_rows(
    grid: QGridLayout,
    tracker: RowTracker,
    weight_ui_rows: list,
    staged: dict[int, dict],
    present_slots: set[int],
    on_changed,  # callable(slot, key, value)
) -> None:
    """Add one row per entry in WEIGHT_UI_ROWS, plus trait_flat_scoring checkbox."""
    for key, label_spec in weight_ui_rows:
        if key is None:
            # Separator — skip for the compare grid (keep layout compact)
            continue

        # Determine label text
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
        for n in range(1, NUM_PROFILES + 1):
            if n not in present_slots:
                w = _empty_label()
            else:
                current_val = staged[n].get("weights", {}).get(key, 0.0)
                if key in INT_PARAM_RANGES:
                    mn, mx = INT_PARAM_RANGES[key]
                    w = _IntParamSpin(int(round(current_val)), min_val=mn, max_val=mx)
                else:
                    w = _WeightSpin(float(current_val))
                w.setFixedWidth(COL_SLOT_WIDTH)
                slot = n
                w.valueChanged.connect(lambda val, s=slot, k=key: on_changed(s, k, val))
            editors[n] = w
            grid.addWidget(w, r, n)

        tracker.data_rows.append((lbl, editors))

    # Flat trait scoring checkbox row
    r = tracker.next_row()
    lbl = _label_widget("Flat trait scoring")
    grid.addWidget(lbl, r, 0)

    editors = {}
    for n in range(1, NUM_PROFILES + 1):
        if n not in present_slots:
            w = _empty_label()
        else:
            is_flat = staged[n].get("weights", {}).get("trait_flat_scoring", 0.0) >= 0.5
            w = QCheckBox()
            w.setChecked(is_flat)
            w.setFixedWidth(COL_SLOT_WIDTH)
            w.setStyleSheet("QCheckBox { color:#aabbcc; font-size:10px; }")
            slot = n
            w.stateChanged.connect(
                lambda state, s=slot: on_changed(s, "trait_flat_scoring", 1.0 if state else 0.0)
            )
        editors[n] = w
        grid.addWidget(w, r, n)

    tracker.data_rows.append((lbl, editors))


def add_complex_weight_rows(
    grid: QGridLayout,
    tracker: RowTracker,
    complex_weights: list,
    staged: dict[int, dict],
    present_slots: set[int],
    on_changed,  # callable(slot, cw_id, enabled_bool)
) -> None:
    """Add one checkbox row per entry in the complex_weights catalog."""
    for cw in complex_weights:
        r = tracker.next_row()
        lbl = _label_widget(cw.name or cw.id)
        grid.addWidget(lbl, r, 0)

        editors: dict[int, QWidget] = {}
        for n in range(1, NUM_PROFILES + 1):
            if n not in present_slots:
                w = _empty_label()
            else:
                enabled_ids = set(staged[n].get("complex_weights_enabled_ids", []))
                w = QCheckBox()
                w.setChecked(cw.id in enabled_ids)
                w.setFixedWidth(COL_SLOT_WIDTH)
                w.setStyleSheet("QCheckBox { color:#aabbcc; font-size:10px; }")
                slot = n
                cw_id = cw.id
                w.stateChanged.connect(
                    lambda state, s=slot, cid=cw_id: on_changed(s, cid, bool(state))
                )
            editors[n] = w
            grid.addWidget(w, r, n)

        tracker.data_rows.append((lbl, editors))


def add_trait_rows(
    grid: QGridLayout,
    tracker: RowTracker,
    trait_names: list[str],
    staged: dict[int, dict],
    present_slots: set[int],
    on_changed,  # callable(slot, trait_name, rating_value)
) -> None:
    """Add one _RatingCombo row per trait name."""
    for trait in trait_names:
        r = tracker.next_row()
        lbl = _label_widget(trait)
        grid.addWidget(lbl, r, 0)

        editors: dict[int, QWidget] = {}
        for n in range(1, NUM_PROFILES + 1):
            if n not in present_slots:
                w = _empty_label()
            else:
                rating = staged[n].get("ma_ratings", {}).get(trait)
                # Map stored rating to combo index
                # Indices: 0=Top Priority(2), 1=Desirable(1), 2=Neutral(0), 3=Undecided(None), 4=Undesirable(-1)
                rating_to_index = {2: 0, 1: 1, 0: 2, None: 3, -1: 4}
                w = _RatingCombo()
                w.setFixedWidth(COL_SLOT_WIDTH)
                w.setCurrentIndex(rating_to_index.get(rating, 3))
                slot = n
                trait_name = trait
                w.currentIndexChanged.connect(
                    lambda idx, s=slot, t=trait_name: _on_rating_changed(staged, s, t, idx, on_changed)
                )
            editors[n] = w
            grid.addWidget(w, r, n)

        tracker.data_rows.append((lbl, editors))


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
