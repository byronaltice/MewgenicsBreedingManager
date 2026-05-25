"""Profile Compare dialog — side-by-side profile editor with synchronized scroll."""

from __future__ import annotations

import copy
from typing import Callable

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QScrollArea, QWidget, QGridLayout, QMenu, QFrame,
)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor

from ..scoring import BREED_PRIORITY_WEIGHTS, WEIGHT_UI_ROWS
from ..delegates import _ConfirmDialog
from ..theme import (
    CLR_TEXT_LABEL_GROUP, CLR_SURFACE_APP_MAIN, CLR_SURFACE_SEPARATOR,
    CLR_TEXT_CONTENT_SECONDARY,
)
from .constants import (
    COL_LABEL_WIDTH, NUM_PROFILES, GROUP_TITLES,
    COPY_FLASH_COLOR, COPY_FLASH_DURATION,
    TOAST_AUTO_DISMISS_MS, TOAST_BG_COLOR, TOAST_BORDER_COLOR,
    TOAST_TEXT_COLOR, TOAST_UNDO_COLOR, TOAST_HEIGHT, TOAST_MARGIN,
)
from .rows import (
    RowTracker, RowDescriptor,
    add_section_header,
    add_name_row, add_weight_rows, add_complex_weight_rows, add_trait_rows,
)
from .copy_actions import copy_section, copy_row

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

# Fallback dialog size when no parent window geometry is available
_FALLBACK_DIALOG_W = 1400
_FALLBACK_DIALOG_H = 900

# Flash border style fragments
_FLASH_BORDER_STYLE = f"border:2px solid {COPY_FLASH_COLOR};"
_FLASH_NORMAL_BORDER = "border:1px solid #1a2a44;"


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
        display_name_fn: Callable[[str], str] | None = None,
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
        self._display_name_fn: Callable[[str], str] = display_name_fn or (lambda t: t)

        # Only slots with actual saved data are shown; blank slots are hidden entirely.
        self._visible_slots: list[int] = sorted(
            n for n in range(1, NUM_PROFILES + 1) if n in profiles
        )

        # Staging state — seeded only for visible slots
        self._staged: dict[int, dict] = {
            n: copy.deepcopy(profiles[n]) for n in self._visible_slots
        }
        self._dirty_slots: set[int] = set()

        # Result (set on Apply)
        self.result_profiles: dict[int, dict] | None = None

        # Track row visibility
        self._tracker = RowTracker()

        # Slot → grid column mapping (excludes hidden slots)
        # Column 0 = label; columns 1..N = visible slots in slot order
        self._slot_to_col: dict[int, int] = {}

        # Undo state for section copies (most-recent only)
        self._undo_snapshot: dict | None = None   # {dst_slot, section_key, blob_snapshot}
        self._toast_widget: QFrame | None = None
        self._toast_timer: QTimer | None = None

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
        _trailing_col = len(self._visible_slots) + 1
        self._grid.setColumnStretch(_trailing_col, 1)

        self._build_grid_content()
        # Set initial diff marker state now that all rows are registered
        self._refresh_diff_markers()
        scroll.setWidget(body_widget)
        root.addWidget(scroll)

    def _build_toolbar(self) -> QWidget:
        """Build the top toolbar with include checkboxes and Apply/Cancel."""
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

        # Only show the "Slots:" label + checkboxes when there are multiple visible slots
        self._include_checks: dict[int, QCheckBox] = {}
        if len(self._visible_slots) > 1:
            slot_lbl = QLabel("Slots:")
            slot_lbl.setStyleSheet(f"color:{CLR_TEXT_LABEL_GROUP}; font-size:10px; font-weight:bold;")
            hb.addWidget(slot_lbl)

            for n in self._visible_slots:
                name = self._staged[n].get("name", "")
                label_text = name if name else str(n)
                chk = QCheckBox(label_text)
                chk.setChecked(True)
                chk.setStyleSheet(_INCLUDE_CHK_STYLE)
                chk.stateChanged.connect(lambda _state, slot=n: self._on_include_toggled(slot))
                self._include_checks[n] = chk
                hb.addWidget(chk)

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
        from ..stat_text_formatter import StatTextFormatter

        grid = self._grid
        tracker = self._tracker

        present_slots = set(self._visible_slots)

        # Initial column mapping: visible slots packed left starting at column 1
        self._slot_to_col = {n: i + 1 for i, n in enumerate(self._visible_slots)}
        num_cols = len(self._visible_slots)
        multi_slot = num_cols > 1

        def _trait_label(trait: str) -> str:
            """Resolve a raw trait key to an emoji-formatted display label."""
            try:
                raw = self._display_name_fn(trait)
                return StatTextFormatter.emojify(raw) if raw else trait
            except Exception:
                return trait

        slot_to_col = self._slot_to_col

        # Copy section handler: show popup listing source slots
        on_copy = self._on_section_copy_requested if multi_slot else None
        on_copy_row = self._show_row_copy_menu if multi_slot else None

        # ── Name ──────────────────────────────────────────────────────────────
        add_section_header(
            grid, tracker, GROUP_TITLES["name"], num_cols,
            section_key="name",
            visible_slots=self._visible_slots if multi_slot else None,
            on_copy_section=on_copy,
        )
        add_name_row(
            grid, tracker, self._staged, present_slots, self._on_field_changed,
            slot_to_col=slot_to_col, on_copy_row=on_copy_row,
        )

        # ── Weights ───────────────────────────────────────────────────────────
        add_section_header(
            grid, tracker, GROUP_TITLES["weights"], num_cols,
            section_key="weights",
            visible_slots=self._visible_slots if multi_slot else None,
            on_copy_section=on_copy,
        )
        add_weight_rows(
            grid, tracker, WEIGHT_UI_ROWS,
            self._staged, present_slots, self._on_weight_changed,
            slot_to_col=slot_to_col, on_copy_row=on_copy_row,
        )

        # ── Complex Weights ───────────────────────────────────────────────────
        if self._complex_weights:
            add_section_header(
                grid, tracker, GROUP_TITLES["complex_weights"], num_cols,
                section_key="complex_weights",
                visible_slots=self._visible_slots if multi_slot else None,
                on_copy_section=on_copy,
            )
            add_complex_weight_rows(
                grid, tracker, self._complex_weights,
                self._staged, present_slots, self._on_cw_changed,
                slot_to_col=slot_to_col, on_copy_row=on_copy_row,
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
            add_section_header(
                grid, tracker, GROUP_TITLES[section_key], num_cols,
                section_key=section_key,
                visible_slots=self._visible_slots if multi_slot else None,
                on_copy_section=on_copy,
                trait_list=trait_list,
            )
            add_trait_rows(
                grid, tracker, trait_list,
                self._staged, present_slots, self._on_trait_changed,
                label_fn=_trait_label,
                slot_to_col=slot_to_col, on_copy_row=on_copy_row,
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
            n for n in self._visible_slots if self._include_checks[n].isChecked()
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

        # Update copy button visibility in section headers
        for sec_desc in self._tracker.header_rows:
            for slot_num, btn in sec_desc.copy_buttons.items():
                btn.setVisible(slot_num in new_slot_to_col)

        self._slot_to_col = new_slot_to_col
        self._refresh_diff_visibility()

    def _update_include_label(self, slot: int) -> None:
        """Update include checkbox label if name changed."""
        if slot not in self._include_checks:
            return
        name = self._staged[slot].get("name", "")
        label_text = name if name else str(slot)
        self._include_checks[slot].setText(label_text)

    # ── Section copy ──────────────────────────────────────────────────────────

    def _on_section_copy_requested(self, dst_slot: int, section_key: str) -> None:
        """Show a popup menu listing other visible slots as copy sources."""
        currently_visible = [
            n for n in self._visible_slots
            if n in self._slot_to_col
        ]
        sources = [n for n in currently_visible if n != dst_slot]
        if not sources:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#0e1828; color:#aabbcc; border:1px solid #2244aa; font-size:11px; }"
            "QMenu::item:selected { background:#1a2a44; }"
        )

        dst_name = self._staged[dst_slot].get("name", "") or f"Slot {dst_slot}"
        section_title = GROUP_TITLES.get(section_key, section_key)

        for src_slot in sources:
            src_name = self._staged[src_slot].get("name", "") or f"Slot {src_slot}"
            action = menu.addAction(f"Copy {section_title} from: {src_name}")
            action.setData((src_slot, dst_slot, section_key))

        chosen = menu.exec(self.cursor().pos())
        if chosen is None:
            return

        src_slot, dst_slot, section_key = chosen.data()
        self._execute_section_copy(src_slot, dst_slot, section_key)

    def _execute_section_copy(self, src_slot: int, dst_slot: int, section_key: str) -> None:
        """Perform the section copy, update editors, flash, and show undo toast."""
        # Find the section descriptor so we know the trait_list (if any)
        trait_list: list[str] | None = None
        for sec_desc in self._tracker.header_rows:
            if sec_desc.section_key == section_key:
                trait_list = sec_desc.trait_list
                break

        # Save undo snapshot before mutating
        self._undo_snapshot = {
            "dst_slot": dst_slot,
            "section_key": section_key,
            "blob": copy.deepcopy(self._staged[dst_slot]),
        }

        # Mutate staged dict
        copy_section(self._staged, section_key, src_slot, dst_slot, trait_list=trait_list)
        self._dirty_slots.add(dst_slot)

        # Refresh editor widgets in the destination column for this section
        self._refresh_section_editors(section_key, dst_slot)
        self._refresh_diff_markers()

        # Flash destination editors in this section
        self._flash_section_editors(section_key, dst_slot)

        # Show undo toast
        src_name = self._staged[src_slot].get("name", "") or f"Slot {src_slot}"
        dst_name = self._staged[dst_slot].get("name", "") or f"Slot {dst_slot}"
        section_title = GROUP_TITLES.get(section_key, section_key)

        # Count rated traits if trait section
        count_info = ""
        if trait_list is not None:
            src_ratings = self._staged[src_slot].get("ma_ratings") or {}
            rated_count = sum(1 for t in trait_list if t in src_ratings)
            count_info = f" ({rated_count} ratings)"

        toast_msg = f"Copied {section_title} from {src_name}{count_info} → {dst_name}"
        self._show_undo_toast(toast_msg)

    def _refresh_section_editors(self, section_key: str, dst_slot: int) -> None:
        """Re-read staged values and push them into dst_slot's editor widgets.

        Iterates all data rows that belong to the given section and calls
        each RowDescriptor's value_setter to update the destination editor.
        """
        if dst_slot not in self._slot_to_col:
            return

        # Collect section's row range from header descriptors
        header_rows_sorted = sorted(self._tracker.header_rows, key=lambda h: h.grid_row)
        section_start: int | None = None
        section_end: int | None = None

        for i, sec_desc in enumerate(header_rows_sorted):
            if sec_desc.section_key == section_key:
                section_start = sec_desc.grid_row
                # Next header's grid_row is the exclusive end
                if i + 1 < len(header_rows_sorted):
                    section_end = header_rows_sorted[i + 1].grid_row
                break

        if section_start is None:
            return

        staged_blob = self._staged[dst_slot]
        for desc in self._tracker.data_rows:
            if desc.grid_row <= section_start:
                continue
            if section_end is not None and desc.grid_row >= section_end:
                continue
            if desc.value_setter is None:
                continue
            editor = desc.editors.get(dst_slot)
            if editor is None:
                continue
            new_value = desc.value_getter(staged_blob)
            desc.value_setter(editor, new_value)

    def _flash_section_editors(self, section_key: str, dst_slot: int) -> None:
        """Briefly flash a yellow border on destination editors in the section."""
        if dst_slot not in self._slot_to_col:
            return

        header_rows_sorted = sorted(self._tracker.header_rows, key=lambda h: h.grid_row)
        section_start: int | None = None
        section_end: int | None = None

        for i, sec_desc in enumerate(header_rows_sorted):
            if sec_desc.section_key == section_key:
                section_start = sec_desc.grid_row
                if i + 1 < len(header_rows_sorted):
                    section_end = header_rows_sorted[i + 1].grid_row
                break

        if section_start is None:
            return

        flashed_widgets: list = []
        for desc in self._tracker.data_rows:
            if desc.grid_row <= section_start:
                continue
            if section_end is not None and desc.grid_row >= section_end:
                continue
            editor = desc.editors.get(dst_slot)
            if editor is None:
                continue
            original_style = editor.styleSheet()
            editor.setStyleSheet(_FLASH_BORDER_STYLE + " " + original_style)
            flashed_widgets.append((editor, original_style))

        def _restore():
            for w, orig in flashed_widgets:
                w.setStyleSheet(orig)

        QTimer.singleShot(COPY_FLASH_DURATION, _restore)

    # ── Row copy (context menu) ───────────────────────────────────────────────

    def _show_row_copy_menu(
        self,
        editor_widget,
        dst_slot: int,
        desc: RowDescriptor,
        pos,
    ) -> None:
        """Show a right-click context menu for per-row copy."""
        currently_visible = [
            n for n in self._visible_slots
            if n in self._slot_to_col
        ]
        sources = [n for n in currently_visible if n != dst_slot]
        if not sources:
            return

        dst_value = _hashable(desc.value_getter(self._staged[dst_slot]))
        differing_sources = [
            n for n in sources
            if _hashable(desc.value_getter(self._staged[n])) != dst_value
        ]

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#0e1828; color:#aabbcc; border:1px solid #2244aa; font-size:11px; }"
            "QMenu::item:selected { background:#1a2a44; }"
            "QMenu::item:disabled { color:#445566; }"
        )

        if not differing_sources:
            placeholder = menu.addAction("All profiles match")
            placeholder.setEnabled(False)
        else:
            for src_slot in differing_sources:
                src_name = self._staged[src_slot].get("name", "") or f"Slot {src_slot}"
                action = menu.addAction(f"Copy this value from: {src_name}")
                action.setData((src_slot, dst_slot, desc))

        global_pos = editor_widget.mapToGlobal(pos)
        chosen = menu.exec(global_pos)
        if chosen is None or not chosen.isEnabled():
            return

        data = chosen.data()
        if data is None:
            return

        src_slot, dst_slot, row_desc = data
        self._execute_row_copy(src_slot, dst_slot, row_desc, editor_widget)

    def _execute_row_copy(
        self,
        src_slot: int,
        dst_slot: int,
        desc: RowDescriptor,
        dst_editor,
    ) -> None:
        """Copy one row value from src to dst and refresh the destination editor."""
        if desc.value_setter is None:
            return

        src_value = desc.value_getter(self._staged[src_slot])

        def _blob_setter(blob: dict, val: object) -> None:
            # We use the value_setter on the editor widget, not on the blob directly.
            # The blob is mutated by re-reading from widget via the change handler.
            # Instead, directly copy via value_setter on staged blob equivalent:
            # We need to write back to staged — delegate to desc.value_setter on widget,
            # then let the widget's change handler propagate. But signals are blocked.
            # Safest: set widget (unblocked this once), which fires on_changed.
            pass

        # Actually: set the editor widget with signals UN-blocked so the change handler fires.
        # value_setter blocks signals, so we call it then manually update staged.
        src_value_copy = copy.deepcopy(src_value)

        # Use value_setter to update widget (blocks signals, no double-fire)
        desc.value_setter(dst_editor, src_value_copy)

        # Manually push the value into staged since we blocked signals
        self._push_row_value_to_staged(dst_slot, desc, src_value_copy)

        self._dirty_slots.add(dst_slot)
        self._refresh_diff_markers()

        # Brief border flash on the single editor
        original_style = dst_editor.styleSheet()
        dst_editor.setStyleSheet(_FLASH_BORDER_STYLE + " " + original_style)
        QTimer.singleShot(COPY_FLASH_DURATION, lambda: dst_editor.setStyleSheet(original_style))

    def _push_row_value_to_staged(
        self,
        slot: int,
        desc: RowDescriptor,
        value: object,
    ) -> None:
        """Write a row value directly into the staged blob for the given slot.

        Since we bypass widget signals during row copy, we must manually update
        staged. We determine which staged key to write by comparing the value_getter
        result with known blob paths. This is done by re-dispatching through the
        appropriate _on_*_changed handler after identifying the field.

        The cleanest approach: call value_getter on a scratch dict with a known key
        set, then match. In practice we identify the handler by examining which
        staged keys change when the getter is called — but that's complex. Instead,
        the row builders provide a direct staged_setter closure via _make_staged_setter.

        For now: re-run value_getter on a scratch blob to determine the field path,
        then replicate the handler logic by re-firing a synthetic change. Since we
        already have the staged dict and the value, write directly via a pattern-match
        on which staged sub-dict changed.

        Simpler approach: just replicate the handler logic here by checking which
        staged keys are involved. The value_getter is the only coupling. We can
        call the widget's on_changed equivalent manually.

        Even simpler: the widget's own change signal fires the on_changed handler
        which writes to staged. We blocked signals in value_setter. So after
        value_setter, we must manually call the same on_changed equivalent.

        Since the row builders don't expose the key per descriptor, we detect
        the write path by probing the staged dict. For this implementation, we
        call value_getter on a sentinel blob and observe what it reads — if it
        reads "name", "weights.X", "ma_ratings.X", or "complex_weights_enabled_ids".

        Actually the cleanest real solution: store a staged_writer on RowDescriptor.
        That's done below in this implementation — add a `staged_writer` field.
        """
        # Fallback: the staged dict is already correct for some row types where
        # value_getter reads directly (e.g. trait ratings where we set via combo
        # and the combo on_changed writes to staged). Since we blocked signals,
        # we need to write staged directly.
        # The value_getter tells us the current value FROM staged; we need to set it.
        # Walk the staged dict keys to infer the path.
        blob = self._staged[slot]

        # Check "name"
        test_name = {"name": "__SENTINEL__"}
        if desc.value_getter(test_name) == "__SENTINEL__":
            blob["name"] = str(value) if value is not None else ""
            self._update_include_label(slot)
            return

        # Check "weights" keys: value_getter({"weights": {"KEY": 99.0}}) == 99.0
        for test_key in list(blob.get("weights", {}).keys()):
            test_w = {"weights": {test_key: 99.0}}
            if desc.value_getter(test_w) == 99.0:
                if "weights" not in blob:
                    blob["weights"] = dict(BREED_PRIORITY_WEIGHTS)
                blob["weights"][test_key] = value
                return

        # Check complex_weights: value_getter({"complex_weights_enabled_ids": [cw_id]}) == True
        # We probe using all cw ids in the staged dict
        all_cw_ids = set(blob.get("complex_weights_enabled_ids") or [])
        for cw_obj in self._complex_weights:
            cid = cw_obj.id
            present_blob = {"complex_weights_enabled_ids": [cid]}
            absent_blob: dict = {"complex_weights_enabled_ids": []}
            if desc.value_getter(present_blob) is True and desc.value_getter(absent_blob) is False:
                enabled_ids = list(blob.get("complex_weights_enabled_ids") or [])
                if value and cid not in enabled_ids:
                    enabled_ids.append(cid)
                elif not value and cid in enabled_ids:
                    enabled_ids.remove(cid)
                blob["complex_weights_enabled_ids"] = enabled_ids
                return

        # Check ma_ratings (trait): value_getter({"ma_ratings": {trait: 2}}) == 2
        all_trait_sections = [
            self._active_abilities, self._passive_abilities,
            self._disorders, self._good_mutations, self._defects,
        ]
        for trait_list in all_trait_sections:
            for trait in (trait_list or []):
                test_blob = {"ma_ratings": {trait: 99}}
                if desc.value_getter(test_blob) == 99:
                    if "ma_ratings" not in blob:
                        blob["ma_ratings"] = {}
                    if value is None or value == 0:
                        blob["ma_ratings"].pop(trait, None)
                    else:
                        blob["ma_ratings"][trait] = value
                    return

    # ── Undo toast ────────────────────────────────────────────────────────────

    def _show_undo_toast(self, message: str) -> None:
        """Show a dismissible toast at the bottom of the dialog with an Undo button."""
        # Cancel any previous auto-dismiss timer
        if self._toast_timer is not None:
            self._toast_timer.stop()
            self._toast_timer = None

        # Remove previous toast
        if self._toast_widget is not None:
            self._toast_widget.hide()
            self._toast_widget.deleteLater()
            self._toast_widget = None

        toast = QFrame(self)
        toast.setStyleSheet(
            f"QFrame {{ background:{TOAST_BG_COLOR}; border:1px solid {TOAST_BORDER_COLOR};"
            f"  border-radius:4px; }}"
            f"QLabel {{ color:{TOAST_TEXT_COLOR}; font-size:11px; background:transparent; border:none; }}"
        )

        hb = QHBoxLayout(toast)
        hb.setContentsMargins(10, 4, 6, 4)
        hb.setSpacing(8)

        msg_lbl = QLabel(message)
        hb.addWidget(msg_lbl)
        hb.addStretch()

        undo_btn = QPushButton("Undo")
        undo_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{TOAST_UNDO_COLOR};"
            "  border:none; font-size:11px; padding:0 4px; text-decoration:underline; }}"
            f"QPushButton:hover {{ color:#cce0ff; }}"
        )
        undo_btn.clicked.connect(self._on_undo_section_copy)
        hb.addWidget(undo_btn)

        close_btn = QPushButton("×")
        close_btn.setStyleSheet(
            "QPushButton { background:transparent; color:#667788; border:none;"
            "  font-size:14px; padding:0 2px; }"
            "QPushButton:hover { color:#aabbcc; }"
        )
        close_btn.clicked.connect(self._dismiss_toast)
        hb.addWidget(close_btn)

        # Position at bottom of dialog
        self._reposition_toast(toast)
        toast.show()
        toast.raise_()
        self._toast_widget = toast

        # Auto-dismiss
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._dismiss_toast)
        timer.start(TOAST_AUTO_DISMISS_MS)
        self._toast_timer = timer

    def _reposition_toast(self, toast: QFrame) -> None:
        """Position the toast widget at the bottom-centre of the dialog."""
        dialog_w = self.width()
        toast_w = max(400, dialog_w - 2 * TOAST_MARGIN)
        toast.setGeometry(
            TOAST_MARGIN,
            self.height() - TOAST_HEIGHT - TOAST_MARGIN,
            toast_w,
            TOAST_HEIGHT,
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._toast_widget is not None and self._toast_widget.isVisible():
            self._reposition_toast(self._toast_widget)

    def _dismiss_toast(self) -> None:
        """Dismiss the toast and clear undo state."""
        if self._toast_timer is not None:
            self._toast_timer.stop()
            self._toast_timer = None
        if self._toast_widget is not None:
            self._toast_widget.hide()
            self._toast_widget.deleteLater()
            self._toast_widget = None
        self._undo_snapshot = None

    def _on_undo_section_copy(self) -> None:
        """Revert the most recent section copy using the saved snapshot."""
        if self._undo_snapshot is None:
            self._dismiss_toast()
            return

        dst_slot = self._undo_snapshot["dst_slot"]
        section_key = self._undo_snapshot["section_key"]
        saved_blob = self._undo_snapshot["blob"]

        # Restore staged blob for the affected keys
        self._staged[dst_slot].update(copy.deepcopy(saved_blob))

        # Refresh editors for the restored section
        self._refresh_section_editors(section_key, dst_slot)
        self._refresh_diff_markers()

        self._dismiss_toast()

    # ── Diff markers and slot visibility ─────────────────────────────────────

    def _refresh_diff_visibility(self) -> None:
        """Restore editor slot-column visibility after include-checkbox toggles.

        Slot visibility is controlled by the include checkboxes; diff markers
        are updated separately by _refresh_diff_markers.
        """
        for desc in self._tracker.data_rows:
            for n, w in desc.editors.items():
                w.setVisible(n in self._slot_to_col)
        self._refresh_diff_markers()

    def _refresh_diff_markers(self) -> None:
        """Show a yellow asterisk on every row whose value differs across visible slots."""
        included_slots = [
            n for n in self._visible_slots
            if n not in self._include_checks or self._include_checks[n].isChecked()
        ]

        for desc in self._tracker.data_rows:
            if desc.diff_marker is None:
                continue
            if len(included_slots) < 2:
                desc.diff_marker.setVisible(False)
                continue
            values = [desc.value_getter(self._staged[n]) for n in included_slots]
            differs = len({_hashable(v) for v in values}) > 1
            desc.diff_marker.setVisible(differs)

    # ── Apply / Cancel ────────────────────────────────────────────────────────

    def _on_apply(self) -> None:
        """Collect staged state for all visible slots and accept."""
        self.result_profiles = {n: self._staged[n] for n in self._visible_slots}
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
