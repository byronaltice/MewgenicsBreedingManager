"""Profile Compare dialog — side-by-side profile editor with synchronized scroll."""

from __future__ import annotations

import copy

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QScrollArea, QWidget, QGridLayout,
)
from PySide6.QtCore import Qt

from ..scoring import BREED_PRIORITY_WEIGHTS, WEIGHT_UI_ROWS
from ..delegates import _ConfirmDialog
from ..theme import (
    CLR_TEXT_LABEL_GROUP, CLR_SURFACE_APP_MAIN, CLR_SURFACE_SEPARATOR,
    CLR_TEXT_CONTENT_SECONDARY,
)
from .constants import (
    COL_LABEL_WIDTH, NUM_PROFILES, GROUP_TITLES,
)
from .rows import (
    RowTracker, RowDescriptor,
    add_section_header,
    add_name_row, add_weight_rows, add_complex_weight_rows, add_trait_rows,
)

# ── Styling constants ─────────────────────────────────────────────────────────
_TOOLBAR_BTN_PRIMARY = (
    "QPushButton { background:#0e2030; color:#88aadd; border:1px solid #2244aa;"
    "  border-radius:4px; padding:4px 16px; font-size:11px; }"
    "QPushButton:hover { background:#122840; color:#aaccff; border-color:#3366cc; }"
)
_TOOLBAR_BTN_SECONDARY = (
    "QPushButton { background:#14142e; color:#8899bb; border:1px solid #2a2a55;"
    "  border-radius:4px; padding:4px 12px; font-size:11px; }"
    "QPushButton:hover { background:#1c1c3a; color:#ccd; border-color:#4444aa; }"
)
_INCLUDE_CHK_STYLE = (
    "QCheckBox { color:#aabbcc; font-size:11px; padding:2px 4px; }"
    "QCheckBox::indicator { width:14px; height:14px; }"
)
_DIFF_CHK_STYLE = (
    "QCheckBox { color:#88aacc; font-size:11px; padding:2px 6px; }"
    "QCheckBox::indicator { width:13px; height:13px; }"
)

# Sentinel for empty-slot value comparisons
_EMPTY = object()

# Fallback dialog size when no parent window geometry is available
_FALLBACK_DIALOG_W = 1400
_FALLBACK_DIALOG_H = 900


def _empty_blob() -> dict:
    """Return a default empty profile blob with default weights and no ratings."""
    return {
        "name": "",
        "weights": dict(BREED_PRIORITY_WEIGHTS),
        "ma_ratings": {},
        "complex_weights_enabled_ids": [],
    }


def _hashable(value) -> object:
    """Convert a value to something hashable for equality comparison."""
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_hashable(v) for v in value)
    return value


class ProfileCompareDialog(QDialog):
    """Sized modal dialog for side-by-side profile comparison and editing.

    Matches the main window's geometry on open. Does not maximize.

    Args:
        parent: Parent widget.
        profiles: Dict mapping slot numbers (1–5) to profile blobs.
        active_abilities: List of active ability trait names.
        passive_abilities: List of passive ability trait names.
        disorders: List of disorder trait names.
        good_mutations: List of good mutation trait names.
        defects: List of defect trait names.
        complex_weights: List of ComplexWeight objects (global catalog).
    """

    def __init__(
        self,
        parent,
        profiles: dict[int, dict],
        active_abilities: list[str],
        passive_abilities: list[str],
        disorders: list[str],
        good_mutations: list[str],
        defects: list[str],
        complex_weights: list,
    ):
        super().__init__(parent)
        self.setWindowTitle("Compare Profiles")
        self.setModal(True)

        # Dark background from frame one — must be set before any show()
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QDialog {{ background:{CLR_SURFACE_APP_MAIN}; }}"
            f"QWidget {{ background:{CLR_SURFACE_APP_MAIN}; }}"
            f"QScrollArea {{ background:{CLR_SURFACE_APP_MAIN}; border:none; }}"
            f"QLabel {{ color:{CLR_TEXT_CONTENT_SECONDARY}; background:transparent; border:none; }}"
        )

        # Match main-window geometry instead of maximizing
        mw = parent.window() if parent is not None else None
        if mw is not None:
            self.setGeometry(mw.geometry())
        else:
            self.resize(_FALLBACK_DIALOG_W, _FALLBACK_DIALOG_H)

        self._profiles_input = profiles
        self._active_abilities = active_abilities
        self._passive_abilities = passive_abilities
        self._disorders = disorders
        self._good_mutations = good_mutations
        self._defects = defects
        self._complex_weights = complex_weights

        # Staging state
        self._staged: dict[int, dict] = {
            n: copy.deepcopy(profiles[n]) if n in profiles else _empty_blob()
            for n in range(1, NUM_PROFILES + 1)
        }
        self._dirty_slots: set[int] = set()
        self._was_empty: set[int] = {n for n in range(1, NUM_PROFILES + 1) if n not in profiles}

        # Result (set on Apply)
        self.result_profiles: dict[int, dict] | None = None

        # Track row visibility
        self._tracker = RowTracker()

        # Slot → grid column mapping (excludes hidden slots)
        # Column 0 = label; columns 1..N = visible slots in slot order
        self._slot_to_col: dict[int, int] = {}

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the dialog layout: toolbar + scrollable grid body."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        body_widget = QWidget()
        body_widget.setStyleSheet(f"background:{CLR_SURFACE_APP_MAIN};")
        self._grid = QGridLayout(body_widget)
        self._grid.setContentsMargins(16, 12, 16, 16)
        self._grid.setHorizontalSpacing(6)
        self._grid.setVerticalSpacing(3)

        # Label column has fixed width; data columns size to content
        self._grid.setColumnMinimumWidth(0, COL_LABEL_WIDTH)
        # Trailing stretch column absorbs leftover horizontal space so data
        # columns hug left rather than distributing evenly.
        _trailing_col = NUM_PROFILES + 1
        self._grid.setColumnStretch(_trailing_col, 1)

        self._build_grid_content()
        scroll.setWidget(body_widget)
        root.addWidget(scroll)

    def _build_toolbar(self) -> QWidget:
        """Build the top toolbar with include checkboxes, diff toggle, and Apply/Cancel."""
        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"QWidget {{ background:#0a0f1a; border-bottom:1px solid {CLR_SURFACE_SEPARATOR}; }}"
            "QLabel { background:transparent; border:none; }"
            "QCheckBox { background:transparent; }"
        )
        toolbar.setFixedHeight(48)
        hb = QHBoxLayout(toolbar)
        hb.setContentsMargins(16, 0, 16, 0)
        hb.setSpacing(10)

        slot_lbl = QLabel("Slots:")
        slot_lbl.setStyleSheet(f"color:{CLR_TEXT_LABEL_GROUP}; font-size:10px; font-weight:bold;")
        hb.addWidget(slot_lbl)

        self._include_checks: dict[int, QCheckBox] = {}
        for n in range(1, NUM_PROFILES + 1):
            name = self._staged[n].get("name", "") if n not in self._was_empty else ""
            label_text = name if name else str(n)
            if n in self._was_empty:
                label_text = f"{label_text} (empty)"
            chk = QCheckBox(label_text)
            chk.setChecked(True)
            chk.setStyleSheet(_INCLUDE_CHK_STYLE)
            chk.stateChanged.connect(lambda _state, slot=n: self._on_include_toggled(slot))
            self._include_checks[n] = chk
            hb.addWidget(chk)

        hb.addSpacing(20)

        self._diff_chk = QCheckBox("Show only differences")
        self._diff_chk.setChecked(False)
        self._diff_chk.setStyleSheet(_DIFF_CHK_STYLE)
        self._diff_chk.stateChanged.connect(self._on_diff_toggled)
        hb.addWidget(self._diff_chk)

        hb.addStretch()

        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(_TOOLBAR_BTN_PRIMARY)
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self._on_apply)
        hb.addWidget(apply_btn)

        hb.addSpacing(6)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_TOOLBAR_BTN_SECONDARY)
        cancel_btn.clicked.connect(self._on_cancel)
        hb.addWidget(cancel_btn)

        return toolbar

    def _build_grid_content(self) -> None:
        """Populate the scrollable grid with all section groups and their rows."""
        grid = self._grid
        tracker = self._tracker

        # Only slots with real saved data get editor widgets; empty slots show placeholders
        present_slots = {n for n in range(1, NUM_PROFILES + 1) if n not in self._was_empty}

        # All slots start visible → initial column mapping is 1:1
        self._slot_to_col = {n: n for n in range(1, NUM_PROFILES + 1)}
        num_cols = NUM_PROFILES

        # ── Name ──────────────────────────────────────────────────────────────
        add_section_header(grid, tracker, GROUP_TITLES["name"], num_cols)
        add_name_row(grid, tracker, self._staged, present_slots, self._on_field_changed)

        # ── Weights ───────────────────────────────────────────────────────────
        add_section_header(grid, tracker, GROUP_TITLES["weights"], num_cols)
        add_weight_rows(
            grid, tracker, WEIGHT_UI_ROWS,
            self._staged, present_slots, self._on_weight_changed,
        )

        # ── Complex Weights ───────────────────────────────────────────────────
        if self._complex_weights:
            add_section_header(grid, tracker, GROUP_TITLES["complex_weights"], num_cols)
            add_complex_weight_rows(
                grid, tracker, self._complex_weights,
                self._staged, present_slots, self._on_cw_changed,
            )

        # ── Trait Desirability groups ─────────────────────────────────────────
        trait_sections = [
            ("active",         self._active_abilities),
            ("passive",        self._passive_abilities),
            ("disorders",      self._disorders),
            ("good_mutations", self._good_mutations),
            ("defects",        self._defects),
        ]
        for section_key, trait_list in trait_sections:
            if not trait_list:
                continue
            add_section_header(grid, tracker, GROUP_TITLES[section_key], num_cols)
            add_trait_rows(
                grid, tracker, trait_list,
                self._staged, present_slots, self._on_trait_changed,
            )

    # ── Change handlers ───────────────────────────────────────────────────────

    def _on_field_changed(self, slot: int, field: str, value) -> None:
        """Handle Name field change."""
        self._staged[slot][field] = value
        self._dirty_slots.add(slot)
        self._update_include_label(slot)
        self._refresh_diff_visibility()

    def _on_weight_changed(self, slot: int, key: str, value: float) -> None:
        """Handle a weight spin change."""
        if "weights" not in self._staged[slot]:
            self._staged[slot]["weights"] = dict(BREED_PRIORITY_WEIGHTS)
        self._staged[slot]["weights"][key] = value
        self._dirty_slots.add(slot)
        self._refresh_diff_visibility()

    def _on_cw_changed(self, slot: int, cw_id: str, enabled: bool) -> None:
        """Handle a complex weight checkbox toggle."""
        enabled_ids: list = list(self._staged[slot].get("complex_weights_enabled_ids", []))
        if enabled and cw_id not in enabled_ids:
            enabled_ids.append(cw_id)
        elif not enabled and cw_id in enabled_ids:
            enabled_ids.remove(cw_id)
        self._staged[slot]["complex_weights_enabled_ids"] = enabled_ids
        self._dirty_slots.add(slot)
        self._refresh_diff_visibility()

    def _on_trait_changed(self, slot: int, trait: str, rating) -> None:
        """Handle a trait rating combo change."""
        if "ma_ratings" not in self._staged[slot]:
            self._staged[slot]["ma_ratings"] = {}
        if rating is None or rating == 0:
            self._staged[slot]["ma_ratings"].pop(trait, None)
        else:
            self._staged[slot]["ma_ratings"][trait] = rating
        self._dirty_slots.add(slot)
        self._refresh_diff_visibility()

    def _on_include_toggled(self, slot: int) -> None:
        """Show or hide a slot's column when the include checkbox is toggled.

        Remaps all editor widgets to consecutive grid columns so no gap is left
        by a hidden slot.
        """
        # Recompute slot→column mapping based on currently checked slots
        visible_slots = [
            n for n in range(1, NUM_PROFILES + 1) if self._include_checks[n].isChecked()
        ]
        new_slot_to_col: dict[int, int] = {n: i + 1 for i, n in enumerate(visible_slots)}

        grid = self._grid

        for desc in self._tracker.data_rows:
            for n, w in desc.editors.items():
                slot_visible = n in new_slot_to_col
                w.setVisible(slot_visible)
                if slot_visible:
                    new_col = new_slot_to_col[n]
                    old_col = self._slot_to_col.get(n)
                    if old_col != new_col:
                        grid.removeWidget(w)
                        grid.addWidget(w, desc.grid_row, new_col,
                                       Qt.AlignLeft | Qt.AlignVCenter)

        self._slot_to_col = new_slot_to_col
        self._refresh_diff_visibility()

    def _on_diff_toggled(self, _state: int) -> None:
        """Recompute row dim state based on the diff-only toggle."""
        self._refresh_diff_visibility()

    def _update_include_label(self, slot: int) -> None:
        """Update include checkbox label if name changed."""
        name = self._staged[slot].get("name", "")
        label_text = name if name else str(slot)
        if slot in self._was_empty:
            label_text = f"{label_text} (empty)"
        self._include_checks[slot].setText(label_text)

    # ── Diff visibility ───────────────────────────────────────────────────────

    def _refresh_diff_visibility(self) -> None:
        """Grey out matching rows when diff mode is on; restore all when off.

        Rows are never hidden — matching rows are dimmed with setEnabled(False)
        so the user can still see them. Only differing rows are fully enabled.
        """
        diff_on = self._diff_chk.isChecked()
        included_slots = [n for n in range(1, NUM_PROFILES + 1) if self._include_checks[n].isChecked()]

        for desc in self._tracker.data_rows:
            if diff_on and len(included_slots) > 0:
                values = [
                    desc.value_getter(self._staged[n]) if n not in self._was_empty else _EMPTY
                    for n in included_slots
                ]
                same = len({_hashable(v) for v in values}) <= 1
            else:
                same = False  # diff off → treat all as differing (fully enabled)

            # Always show; grey when same under diff mode
            desc.label.setEnabled(not same)
            for n, w in desc.editors.items():
                w.setEnabled(not same)
                # Slot column visibility still controlled by include toggle
                w.setVisible(n in self._slot_to_col)

    # ── Apply / Cancel ────────────────────────────────────────────────────────

    def _on_apply(self) -> None:
        """Collect staged state, drop untouched empty slots, and accept."""
        result: dict[int, dict] = {}
        for n in range(1, NUM_PROFILES + 1):
            was_empty = n in self._was_empty
            touched = n in self._dirty_slots
            if was_empty and not touched:
                continue
            result[n] = self._staged[n]
        self.result_profiles = result
        self.accept()

    def _on_cancel(self) -> None:
        """Cancel the dialog, prompting if unsaved changes exist."""
        if self._dirty_slots:
            count = len(self._dirty_slots)
            noun = "profile" if count == 1 else "profiles"
            dlg = _ConfirmDialog(
                "Discard Changes",
                f"Discard changes to {count} {noun}?",
                "Discard",
                parent=self,
            )
            if dlg.exec() != QDialog.Accepted:
                return
        self.reject()
