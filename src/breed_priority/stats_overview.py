"""Breed Priority — Current Stats Overview popup.

Standalone QDialog showing per-cat effective (or base) stats with injury details.
Opens as a non-blocking window from the Breed Priority top bar.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QPushButton, QCheckBox, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .columns import INJURY_STAT_NAMES, _INJ_SHORT
from .styles import (
    ACTION_BUTTON_SECONDARY_LARGE_STYLE, checkbox_style, PRIORITY_TABLE_STYLE,
)
from .theme import (
    CLR_BG_SCORE_AREA, CLR_TEXT_PRIMARY, CLR_TEXT_MUTED,
    CLR_BG_HEADER, CLR_VALUE_NEG, CLR_DESIRABLE, CLR_NEUTRAL,
    CLR_SURFACE_SEPARATOR, CLR_VALUE_POS,
)


_STAT_NAMES = ["STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK"]

_STAT_MAX_BASE = 7   # highest achievable base value in-game

# Stat value → foreground color (base-stat range)
_STAT_COLOR = {
    7: CLR_DESIRABLE,
    6: CLR_NEUTRAL,
}

_COL_HEADERS = ["Name"] + _STAT_NAMES + ["Sum", "Injuries"]
_COL_NAME  = 0
_COL_SUM   = 8
_COL_INJ   = 9


def _injuries_for(cat, stat_names: list) -> list:
    """Return [(display_name, stat_key, delta), ...] for stats with a negative modifier."""
    total = getattr(cat, 'total_stats', None)
    base  = getattr(cat, 'base_stats', None)
    if total is None or base is None:
        return []
    result = []
    for sn in stat_names:
        b = base.get(sn, 0)
        t = total.get(sn, b)
        delta = t - b
        if delta < 0:
            result.append((INJURY_STAT_NAMES.get(sn, sn), sn, delta))
    return result


class StatsOverviewDialog(QDialog):
    """Non-blocking popup: all cats × current stats with optional injury toggle."""

    def __init__(self, cats: list, stat_names: list | None = None, parent=None):
        super().__init__(parent)
        self._cats = cats
        self._stat_names = stat_names or _STAT_NAMES
        self._include_injuries = True

        self.setWindowTitle("Current Stats Overview")
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setStyleSheet(f"background:{CLR_BG_SCORE_AREA}; color:{CLR_TEXT_PRIMARY};")
        self.resize(860, 560)

        vb = QVBoxLayout(self)
        vb.setContentsMargins(12, 12, 12, 12)
        vb.setSpacing(8)

        # ── Header bar ──────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet(
            f"background:{CLR_BG_HEADER}; border-radius:4px;"
            f" border-bottom:1px solid {CLR_SURFACE_SEPARATOR};"
        )
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(10, 6, 10, 6)
        hdr_l.setSpacing(10)

        title = QLabel("Current Stats Overview")
        title.setStyleSheet(
            f"color:{CLR_TEXT_PRIMARY}; font-size:14px; font-weight:bold;"
        )
        hdr_l.addWidget(title)
        hdr_l.addStretch()

        self._chk_injuries = QCheckBox("Include injuries")
        self._chk_injuries.setChecked(True)
        self._chk_injuries.setToolTip(
            "Checked: stats shown are base + injury modifiers (effective stat).\n"
            "Unchecked: stats shown are base values only — injuries excluded from sum."
        )
        self._chk_injuries.setStyleSheet(
            checkbox_style(font_size=11, emphasize_checked=True)
        )
        self._chk_injuries.stateChanged.connect(self._on_toggle)
        hdr_l.addWidget(self._chk_injuries)

        vb.addWidget(hdr)

        # ── Table ───────────────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(len(_COL_HEADERS))
        self._table.setHorizontalHeaderLabels(_COL_HEADERS)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.setStyleSheet(PRIORITY_TABLE_STYLE)
        self._table.verticalHeader().setVisible(False)

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(_COL_NAME, QHeaderView.Stretch)
        for c in range(1, 8):                          # stat columns
            hh.setSectionResizeMode(c, QHeaderView.Fixed)
            self._table.setColumnWidth(c, 38)
        hh.setSectionResizeMode(_COL_SUM, QHeaderView.Fixed)
        self._table.setColumnWidth(_COL_SUM, 44)
        hh.setSectionResizeMode(_COL_INJ, QHeaderView.ResizeToContents)

        vb.addWidget(self._table)

        # ── Footer ──────────────────────────────────────────────────────────────
        self._note = QLabel("")
        self._note.setStyleSheet(f"color:{CLR_TEXT_MUTED}; font-size:10px;")
        vb.addWidget(self._note)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(ACTION_BUTTON_SECONDARY_LARGE_STYLE)
        close_btn.clicked.connect(self.accept)
        vb.addWidget(close_btn, alignment=Qt.AlignRight)

        self._populate()

    # ── Internal ────────────────────────────────────────────────────────────────

    def _on_toggle(self):
        self._include_injuries = self._chk_injuries.isChecked()
        self._populate()

    def _populate(self):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._cats))

        injured_count = 0

        for row, cat in enumerate(self._cats):
            base  = getattr(cat, 'base_stats',  {}) or {}
            total = getattr(cat, 'total_stats', {}) or {}
            stats = total if self._include_injuries else base

            injuries = _injuries_for(cat, self._stat_names)
            if injuries:
                injured_count += 1

            # Name
            name_item = QTableWidgetItem(getattr(cat, 'name', '?'))
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._table.setItem(row, _COL_NAME, name_item)

            # Stat columns
            cat_sum = 0
            for ci, sn in enumerate(self._stat_names):
                val = stats.get(sn, 0)
                cat_sum += val

                item = QTableWidgetItem()
                item.setData(Qt.DisplayRole, val)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

                # Foreground: teal above base-max, green at 7, yellow at 6, muted below 5
                if val > _STAT_MAX_BASE:
                    item.setForeground(QColor(CLR_VALUE_POS))
                else:
                    fg = _STAT_COLOR.get(val)
                    if fg:
                        item.setForeground(QColor(fg))
                    elif val < 5:
                        item.setForeground(QColor(CLR_TEXT_MUTED))

                # Dark-red cell background when an injury is depressing this stat
                base_val = base.get(sn, 0)
                if self._include_injuries and val < base_val:
                    item.setBackground(QColor("#2a0505"))

                self._table.setItem(row, 1 + ci, item)

            # Sum
            sum_item = QTableWidgetItem()
            sum_item.setData(Qt.DisplayRole, cat_sum)
            sum_item.setTextAlignment(Qt.AlignCenter)
            sum_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._table.setItem(row, _COL_SUM, sum_item)

            # Injuries column — always shows actual injuries regardless of toggle
            if injuries:
                parts = [
                    f"{_INJ_SHORT.get(name, name)} ({sn} {delta:+d})"
                    for name, sn, delta in injuries
                ]
                inj_item = QTableWidgetItem(",  ".join(parts))
                inj_item.setForeground(QColor(CLR_VALUE_NEG))
            else:
                inj_item = QTableWidgetItem("—")
                inj_item.setForeground(QColor(CLR_TEXT_MUTED))
            inj_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self._table.setItem(row, _COL_INJ, inj_item)

        self._table.setSortingEnabled(True)
        self._table.sortByColumn(_COL_SUM, Qt.DescendingOrder)

        mode = "effective" if self._include_injuries else "base (injuries excluded from sum)"
        self._note.setText(
            f"{len(self._cats)} cats  ·  {injured_count} injured  ·  showing {mode} stats"
        )

    def refresh(self, cats: list):
        """Update cat list and repopulate (call when save reloads)."""
        self._cats = cats
        self._populate()


def show_stats_overview(parent, cats: list, stat_names: list | None = None) -> "StatsOverviewDialog":
    """Open (or raise) the current-stats overview window.

    Returns the dialog so the caller can hold a reference and call refresh()
    when new save data arrives.
    """
    dlg = StatsOverviewDialog(cats, stat_names, parent=parent)
    dlg.show()
    dlg.raise_()
    return dlg
