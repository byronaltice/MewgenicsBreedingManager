"""Column Visibility - modal dialog and apply helper for the score table.

Lets the user toggle visibility of any score-table column except Name,
Score, separators, and Complex Weight columns. Visibility is keyed by the
same stable column identity scheme used for column-order persistence
(``#<logical_idx>`` for static columns) and is purely visual - scoring,
sorting, and comparison continue to use every column regardless of
whether it is shown.

Columns are grouped into named sections, each with a tri-state header
checkbox that mirrors the union of its members.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QFrame,
    QPushButton, QCheckBox,
)
from PySide6.QtCore import Qt, Signal

from .columns import (
    COL_NAME, COL_LOC, COL_INJ, COL_RETIRED, COL_SCORE,
    COL_CW_SECTION_START, _SEP_COLS,
    _COL_STAT_START, _NUM_STAT_COLS,
    _STAT_COL_NAMES, _SCORE_COLS, _COL_SCORE_START,
)
from .scoring import SCORE_HEADER_7_COUNT
from .styles import ACTION_BUTTON_SECONDARY_STYLE
from .theme import (
    CLR_SURFACE_APP_MAIN, CLR_SURFACE_APP_ALT,
    CLR_SURFACE_HEADER, CLR_SURFACE_HEADER_BORDER,
    CLR_TEXT_CONTENT_PRIMARY, CLR_TEXT_LABEL_UI, CLR_TEXT_LABEL_GROUP,
)


_DIALOG_STYLE = (
    f"background:{CLR_SURFACE_APP_MAIN}; color:{CLR_TEXT_CONTENT_PRIMARY};"
)
_CHECKBOX_INDICATOR_STYLE = (
    f"QCheckBox::indicator {{ width:14px; height:14px;"
    f"  border:1px solid #8a8aa8; background:#1a1d2e; border-radius:2px; }}"
    f"QCheckBox::indicator:hover {{ border-color:#c0c0e0; }}"
    f"QCheckBox::indicator:checked {{ background:#5a8de0; border-color:#a8c8ff; }}"
    f"QCheckBox::indicator:indeterminate {{ background:#7a6840; border-color:#e0c878; }}"
)
_CHECKBOX_STYLE = (
    f"QCheckBox {{ color:{CLR_TEXT_CONTENT_PRIMARY}; font-size:12px;"
    f"  padding:2px 4px 2px 18px; spacing:8px; }}"
    f"QCheckBox:hover {{ background:{CLR_SURFACE_APP_ALT}; }}"
    + _CHECKBOX_INDICATOR_STYLE
)
_SECTION_HEADER_STYLE = (
    f"QCheckBox {{ background:{CLR_SURFACE_HEADER};"
    f"  color:#ffffff; font-size:13px; font-weight:bold;"
    f"  letter-spacing:1px; padding:8px 8px; spacing:10px;"
    f"  border-top:1px solid {CLR_SURFACE_HEADER_BORDER};"
    f"  border-bottom:1px solid {CLR_SURFACE_HEADER_BORDER}; }}"
    f"QCheckBox:hover {{ background:{CLR_SURFACE_APP_ALT}; }}"
    + _CHECKBOX_INDICATOR_STYLE
)
_DIALOG_MIN_WIDTH = 360
_DIALOG_MIN_HEIGHT = 560


# ── Column identities ─────────────────────────────────────────────────────────

def col_identity_for_static(logical_idx: int) -> str:
    """Stable identity string for a static (non-CW) column."""
    return f"#{logical_idx}"


def _score_col_logical(header_text: str) -> int:
    return _COL_SCORE_START + _SCORE_COLS.index(header_text)


def is_toggleable(logical_idx: int) -> bool:
    """True if the column is user-hideable.

    Name, Score, separators, and CW columns are excluded - Name and Score
    are always-visible anchors, separators are layout markers, and CWs
    are managed via the Complex Weights dialog.
    """
    if logical_idx == COL_NAME:
        return False
    if logical_idx == COL_SCORE:
        return False
    if logical_idx in _SEP_COLS:
        return False
    if logical_idx >= COL_CW_SECTION_START:
        return False
    return True


def apply_col_visibility(
    score_table,
    hidden_identities: set[str],
    width_for_static: Callable[[int], int],
):
    """Hide/show static columns based on the saved identity set.

    ``width_for_static(logical_idx) -> px`` provides the width to restore
    when un-hiding a column (Qt's internal pre-hide width can be wrong).
    Non-toggleable columns (Name, Score, separators, CWs) are forced
    visible so they can never be lost.
    """
    for logical_idx in range(COL_CW_SECTION_START):
        if not is_toggleable(logical_idx):
            score_table.showColumn(logical_idx)
            continue
        identity = col_identity_for_static(logical_idx)
        if identity in hidden_identities:
            score_table.hideColumn(logical_idx)
        else:
            score_table.showColumn(logical_idx)
            score_table.setColumnWidth(logical_idx, width_for_static(logical_idx))


# ── Section layout ────────────────────────────────────────────────────────────

# Display labels for individual columns. Where a header is ambiguous between
# sections (e.g. CHA appears as both a stat and a score column) the entry is
# resolved by section, not by header text - see _build_section_specs.
_COLUMN_LABELS = {
    "STR":   "STR - Strength",
    "DEX":   "DEX - Dexterity",
    "CON":   "CON - Constitution",
    "INT":   "INT - Intelligence",
    "SPD":   "SPD - Speed",
    "CHA":   "CHA - Charisma",
    "LCK":   "LCK - Luck",
    "Loc":   "Loc - Current Room",
    "Inj":   "Inj - Active Injuries",
    "Retired": "👑 - Retired Cat",
    "Age":   "Age",
    "Trait": "Trait - Trait Score",
    "Sum":   "Sum - Stat Sum",
    "7rare": "7rare - Rare 7s",
    "7sub":  "7sub - 7 Sub Attributes",
    SCORE_HEADER_7_COUNT: f"{SCORE_HEADER_7_COUNT} - Stat Count Above Threshold",
    "Sex":   "Sex - Sexuality",
    "Lib":   "Lib - Libido",
    "Gender": "Gender - Unknown Gender Weight",
    "Mate":  "Mate - Gender Disparity Weight",
    "💗":    "💗 - Lover in Scope/Room",
    "Gene":  "Gene - Genetic Risk",
    "Aggro": "Aggro - Aggression",
    "💥":    "💥 - Rival in Scope/Room",
}

# CHA appears both as a stat column and as a score column; the score-column
# entry needs a distinguishing label in the Eligibility section.
_CHA_SCORE_LABEL = "CHA - Low Charisma Weight"


_SECTION_STATS = "STATS"
_SECTION_OTHER = "OTHER NON-SCORED"
_SECTION_STAT_AWARE = "STAT AWARE"
_SECTION_ELIGIBILITY = "ELIGIBILITY AWARE"
_SECTION_SOCIAL = "SOCIAL AWARE"


def _build_section_specs() -> list[tuple[str, list[tuple[int, str]]]]:
    """Return ordered list of (section_label, [(logical_idx, label), ...]).

    Resolves the score-column-vs-stat-column CHA ambiguity by index.
    """
    stats_rows = [
        (_COL_STAT_START + i, _COLUMN_LABELS[_STAT_COL_NAMES[i]])
        for i in range(_NUM_STAT_COLS)
    ]
    other_rows = [
        (COL_RETIRED, _COLUMN_LABELS["Retired"]),
        (COL_LOC, _COLUMN_LABELS["Loc"]),
        (COL_INJ, _COLUMN_LABELS["Inj"]),
        (_score_col_logical("Age"),   _COLUMN_LABELS["Age"]),
        (_score_col_logical("Trait"), _COLUMN_LABELS["Trait"]),
    ]
    stat_aware_rows = [
        (_score_col_logical("Sum"),                  _COLUMN_LABELS["Sum"]),
        (_score_col_logical("7rare"),                _COLUMN_LABELS["7rare"]),
        (_score_col_logical(SCORE_HEADER_7_COUNT),   _COLUMN_LABELS[SCORE_HEADER_7_COUNT]),
        (_score_col_logical("7sub"),                 _COLUMN_LABELS["7sub"]),
    ]
    eligibility_rows = [
        (_score_col_logical("Sex"),     _COLUMN_LABELS["Sex"]),
        (_score_col_logical("Lib"),     _COLUMN_LABELS["Lib"]),
        (_score_col_logical("CHA"),     _CHA_SCORE_LABEL),
        (_score_col_logical("Gender"),  _COLUMN_LABELS["Gender"]),
        (_score_col_logical("Mate"),    _COLUMN_LABELS["Mate"]),
        (_score_col_logical("💗"),       _COLUMN_LABELS["💗"]),
    ]
    social_rows = [
        (_score_col_logical("Gene"),  _COLUMN_LABELS["Gene"]),
        (_score_col_logical("Aggro"), _COLUMN_LABELS["Aggro"]),
        (_score_col_logical("💥"),     _COLUMN_LABELS["💥"]),
    ]
    return [
        (_SECTION_STATS,        stats_rows),
        (_SECTION_OTHER,        other_rows),
        (_SECTION_STAT_AWARE,   stat_aware_rows),
        (_SECTION_ELIGIBILITY,  eligibility_rows),
        (_SECTION_SOCIAL,       social_rows),
    ]


# ── Dialog ────────────────────────────────────────────────────────────────────


class ColumnVisibilityDialog(QDialog):
    """Modal dialog letting the user toggle each column's visibility.

    Emits ``visibility_changed`` (with the new hidden-identity set) live
    on each toggle so the table updates immediately.
    """

    visibility_changed = Signal(object)  # set[str]

    def __init__(
        self,
        parent: QWidget,
        score_table,
        hidden_identities: set[str],
        header_descriptions: dict[str, str],
    ):
        super().__init__(parent)
        self.setWindowTitle("Column Visibility")
        self.setStyleSheet(_DIALOG_STYLE)
        self.setMinimumSize(_DIALOG_MIN_WIDTH, _DIALOG_MIN_HEIGHT)
        self._score_table = score_table
        self._hidden = set(hidden_identities)
        self._header_descriptions = header_descriptions
        # section_label -> (header_checkbox, [member_checkbox, ...])
        self._sections: dict[str, tuple[QCheckBox, list[QCheckBox]]] = {}
        self._suppress_section_signal = False
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        intro = QLabel(
            "Toggle which columns appear in the score table. Hiding a "
            "column is purely visual - scoring, sorting, and comparisons "
            "still use every column. Name, Score, and Complex Weight "
            "columns can't be hidden here."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{CLR_TEXT_LABEL_UI}; font-size:11px;")
        outer.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_inner = QWidget()
        scroll_layout = QVBoxLayout(scroll_inner)
        scroll_layout.setContentsMargins(0, 4, 0, 4)
        scroll_layout.setSpacing(0)

        for section_label, rows in _build_section_specs():
            self._add_section(scroll_layout, section_label, rows)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_inner)
        outer.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(ACTION_BUTTON_SECONDARY_STYLE)
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        outer.addLayout(button_row)

    def _add_section(self, parent_layout, section_label, rows):
        header_box = QCheckBox(section_label)
        header_box.setStyleSheet(_SECTION_HEADER_STYLE)
        header_box.setTristate(True)
        parent_layout.addWidget(header_box)

        member_boxes: list[QCheckBox] = []
        for logical_idx, label_text in rows:
            identity = col_identity_for_static(logical_idx)
            member = QCheckBox(label_text)
            member.setStyleSheet(_CHECKBOX_STYLE)
            item = self._score_table.horizontalHeaderItem(logical_idx)
            header_text = item.text() if item is not None else ""
            description = self._header_descriptions.get(header_text)
            if description:
                member.setToolTip(description)
            member.setChecked(identity not in self._hidden)
            member.toggled.connect(
                lambda visible, _id=identity, _section=section_label:
                    self._on_member_toggled(_section, _id, visible)
            )
            parent_layout.addWidget(member)
            member_boxes.append(member)

        self._sections[section_label] = (header_box, member_boxes)
        self._refresh_section_header(section_label)
        # Connect after initial refresh so the programmatic state set
        # doesn't trigger user-action handling.
        header_box.clicked.connect(
            lambda _checked, _section=section_label:
                self._on_section_clicked(_section)
        )

    def _refresh_section_header(self, section_label: str):
        header_box, members = self._sections[section_label]
        checked_count = sum(1 for m in members if m.isChecked())
        self._suppress_section_signal = True
        if checked_count == 0:
            header_box.setCheckState(Qt.Unchecked)
        elif checked_count == len(members):
            header_box.setCheckState(Qt.Checked)
        else:
            header_box.setCheckState(Qt.PartiallyChecked)
        self._suppress_section_signal = False

    def _on_member_toggled(self, section_label: str, identity: str, visible: bool):
        if visible:
            self._hidden.discard(identity)
        else:
            self._hidden.add(identity)
        self._refresh_section_header(section_label)
        self.visibility_changed.emit(set(self._hidden))

    def _on_section_clicked(self, section_label: str):
        if self._suppress_section_signal:
            return
        header_box, members = self._sections[section_label]
        # ``clicked`` fires after Qt updates the state, so the box's new
        # state already reflects the user's intent. Tristate boxes cycle
        # Unchecked -> PartiallyChecked -> Checked on click; collapse the
        # partial state to Checked so a click on a partial header turns
        # everything on, matching the user's mental model.
        target_visible = header_box.checkState() != Qt.Unchecked
        if header_box.checkState() == Qt.PartiallyChecked:
            target_visible = True
            self._suppress_section_signal = True
            header_box.setCheckState(Qt.Checked)
            self._suppress_section_signal = False
        for member in members:
            if member.isChecked() != target_visible:
                # Block the member's own signal - we'll emit one bulk
                # visibility_changed at the end so the table updates once.
                member.blockSignals(True)
                member.setChecked(target_visible)
                member.blockSignals(False)
                identity = self._identity_for_member(member, section_label)
                if target_visible:
                    self._hidden.discard(identity)
                else:
                    self._hidden.add(identity)
        self._refresh_section_header(section_label)
        self.visibility_changed.emit(set(self._hidden))

    def _identity_for_member(self, member: QCheckBox, section_label: str) -> str:
        """Recover the column identity tied to a member checkbox."""
        _header_box, members = self._sections[section_label]
        idx_in_section = members.index(member)
        for spec_label, rows in _build_section_specs():
            if spec_label == section_label:
                logical_idx, _ = rows[idx_in_section]
                return col_identity_for_static(logical_idx)
        raise KeyError(section_label)
