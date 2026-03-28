from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QStyledItemDelegate,
    QStyle, QStyleOptionViewItem, QAbstractItemView, QHeaderView,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QBrush, QPalette

from save_parser import (
    Cat, can_breed, risk_percent, shared_ancestor_counts, _ancestor_depths,
)
from mewgenics.models.breeding_cache import BreedingCache
from mewgenics.utils.localization import _tr
from mewgenics.utils.tags import _cat_tags, _make_tag_icon
from mewgenics.utils.styling import _enforce_min_font_in_widget_tree


class SafeBreedingView(QWidget):
    """Dedicated view for ranking alive breeding candidates."""
    class _ColumnPaddingDelegate(QStyledItemDelegate):
        def __init__(self, extra_width: int, left_padding: int = 0, parent=None):
            super().__init__(parent)
            self._extra_width = extra_width
            self._left_padding = left_padding

        def sizeHint(self, option, index):
            s = super().sizeHint(option, index)
            return QSize(s.width() + self._extra_width, s.height())

        def paint(self, painter, option, index):
            if self._left_padding <= 0:
                return super().paint(painter, option, index)

            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            style = opt.widget.style() if opt.widget is not None else QApplication.style()

            text = opt.text
            opt.text = ""
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

            text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, opt, opt.widget).adjusted(
                self._left_padding, 0, 0, 0
            )
            if opt.textElideMode != Qt.ElideNone:
                text = opt.fontMetrics.elidedText(text, opt.textElideMode, text_rect.width())

            painter.save()
            if opt.state & QStyle.State_Selected:
                painter.setPen(opt.palette.color(QPalette.HighlightedText))
            else:
                painter.setPen(opt.palette.color(QPalette.Text))
            painter.setFont(opt.font)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)
            painter.restore()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QListWidget { background:#0d0d1c; color:#ddd; border:1px solid #1e1e38; }"
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; }"
            "QHeaderView::section { background:#151532; color:#7d8bb0; border:none; padding:4px; font-weight:bold; }"
        )
        self._cats: list[Cat] = []
        self._alive: list[Cat] = []
        self._by_key: dict[int, Cat] = {}
        self._table_row_cat_keys: list[int] = []
        self._cache: Optional[BreedingCache] = None

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        left = QWidget()
        left.setFixedWidth(320)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)
        self._list_title = QLabel(styleSheet="color:#666; font-size:10px; font-weight:bold;")
        lv.addWidget(self._list_title)
        self._search = QLineEdit()
        lv.addWidget(self._search)
        self._list = QListWidget()
        self._list.setIconSize(QSize(60, 20))
        lv.addWidget(self._list, 1)
        root.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)
        self._title = QLabel()
        self._title.setStyleSheet("color:#ddd; font-size:16px; font-weight:bold;")
        self._summary = QLabel("")
        self._summary.setStyleSheet("color:#666; font-size:11px;")
        self._table = QTableWidget(0, 4)
        self._table.setIconSize(QSize(60, 20))
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(22)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setItemDelegateForColumn(0, SafeBreedingView._ColumnPaddingDelegate(24, 8, self._table))
        self._table.setColumnWidth(0, 180)
        self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(2, 110)
        self._table.setItemDelegateForColumn(3, SafeBreedingView._ColumnPaddingDelegate(24, 0, self._table))
        self._table.horizontalHeader().setSortIndicatorShown(False)

        rv.addWidget(self._title)
        rv.addWidget(self._summary)
        rv.addWidget(self._table, 1)
        root.addWidget(right, 1)

        self._search.textChanged.connect(self._refresh_list)
        self._list.currentItemChanged.connect(self._on_current_item_changed)
        self._table.cellClicked.connect(self._on_table_row_clicked)
        self.retranslate_ui()
        _enforce_min_font_in_widget_tree(self)

    def retranslate_ui(self):
        self._list_title.setText(_tr("safe_breeding.list_title"))
        self._search.setPlaceholderText(_tr("safe_breeding.search_placeholder"))
        self._table.setHorizontalHeaderLabels([
            _tr("safe_breeding.table.cat"),
            _tr("safe_breeding.table.risk"),
            _tr("safe_breeding.table.shared_ancestors"),
            _tr("safe_breeding.table.child_outcome"),
        ])
        self._refresh_list()

    def set_cats(self, cats: list[Cat]):
        selected_key = None
        cur = self._list.currentItem()
        if cur is not None:
            selected_key = int(cur.data(Qt.UserRole))
        self._cats = cats
        self._alive = sorted([c for c in cats if c.status != "Gone"], key=lambda c: (c.name or "").lower())
        self._by_key = {c.db_key: c for c in self._alive}
        self._refresh_list()
        if selected_key is not None and selected_key in self._by_key:
            self.select_cat(self._by_key[selected_key])
        elif self._list.count():
            self._list.setCurrentRow(0)
        else:
            self._render_for(None)

    def set_cache(self, cache: Optional['BreedingCache']):
        self._cache = cache
        # Re-render the currently selected cat with cached data
        cur = self._list.currentItem()
        if cur is not None:
            self._render_for(self._by_key.get(int(cur.data(Qt.UserRole))))

    def select_cat(self, cat: Optional[Cat]):
        if cat is None or cat.db_key not in self._by_key:
            return
        for i in range(self._list.count()):
            item = self._list.item(i)
            if int(item.data(Qt.UserRole)) == cat.db_key:
                self._list.setCurrentRow(i)
                self._list.scrollToItem(item)
                return

    def _refresh_list(self):
        query = self._search.text().strip().lower()
        current_key = None
        cur = self._list.currentItem()
        if cur is not None:
            current_key = int(cur.data(Qt.UserRole))

        self._list.clear()
        for cat in self._alive:
            if query and query not in cat.name.lower():
                continue
            text = f"{cat.name}  ({cat.gender_display})"
            if cat.is_blacklisted:
                text += f"  [{_tr('safe_breeding.list.blocked')}]"
            if cat.must_breed:
                text += f"  [{_tr('safe_breeding.list.must')}]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, cat.db_key)
            icon = _make_tag_icon(_cat_tags(cat), dot_size=10, spacing=3)
            if not icon.isNull():
                item.setIcon(icon)
            if cat.is_blacklisted:
                item.setForeground(QBrush(QColor(170, 100, 100)))
            if cat.must_breed:
                item.setForeground(QBrush(QColor(98, 194, 135)))
            self._list.addItem(item)
        if self._list.count() == 0:
            self._render_for(None)
            return
        if current_key is not None:
            for i in range(self._list.count()):
                item = self._list.item(i)
                if int(item.data(Qt.UserRole)) == current_key:
                    self._list.setCurrentRow(i)
                    return
        self._list.setCurrentRow(0)

    def _on_current_item_changed(self, current, previous):
        if current is None:
            self._render_for(None)
            return
        self._render_for(self._by_key.get(int(current.data(Qt.UserRole))))

    def _on_table_row_clicked(self, row: int, _column: int):
        if row < 0 or row >= len(self._table_row_cat_keys):
            return
        cat = self._by_key.get(self._table_row_cat_keys[row])
        if cat is not None:
            self.select_cat(cat)

    def _render_for(self, cat: Optional[Cat]):
        # This view is a ranking table. Keep sorting disabled so row indices
        # remain stable while we populate all columns for each candidate.
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        self._table_row_cat_keys = []
        if cat is None:
            self._title.setText(_tr("safe_breeding.title"))
            self._summary.setText(_tr("safe_breeding.summary_empty"))
            return

        cache = self._cache
        self._title.setText(_tr("safe_breeding.title_with_cat", name=cat.name))
        lover_keys = {
            lover.db_key
            for lover in getattr(cat, "lovers", [])
            if lover is not None and getattr(lover, "db_key", None) is not None
        }
        candidates: list[tuple[float, int, int, Cat]] = []
        for other in self._alive:
            if other is cat:
                continue
            ok, _ = can_breed(cat, other)
            if not ok:
                continue
            if cache is not None and cache.ready:
                shared, recent_shared = cache.get_shared(cat, other, recent_depth=3)
                rel = cache.get_risk(cat, other)
            else:
                shared, recent_shared = shared_ancestor_counts(cat, other, recent_depth=3)
                rel = risk_percent(cat, other)
            closest_recent_gen = 0
            if recent_shared:
                if cache is not None and cache.ready:
                    da = cache.get_ancestor_depths_for(cat)
                    db = cache.get_ancestor_depths_for(other)
                else:
                    da = _ancestor_depths(cat, max_depth=8)
                    db = _ancestor_depths(other, max_depth=8)
                common = set(da.keys()) & set(db.keys())
                recent_levels = [
                    max(da[anc], db[anc])
                    for anc in common
                    if da[anc] <= 3 and db[anc] <= 3
                ]
                closest_recent_gen = min(recent_levels) if recent_levels else 3
            # Sort by Risk% first so safest pairs appear at top.
            candidates.append((rel, recent_shared * 1000 + shared, closest_recent_gen, other))
        candidates.sort(key=lambda t: (t[0], t[1], (t[3].name or "").lower()))

        self._summary.setText(_tr("safe_breeding.summary", count=len(candidates)))
        self._table.setRowCount(len(candidates))
        for row, (rel, packed_shared, closest_recent_gen, other) in enumerate(candidates):
            self._table_row_cat_keys.append(other.db_key)
            shared = packed_shared % 1000
            risk_pct = int(round(rel))
            if risk_pct >= 100:
                tag, col = _tr("safe_breeding.tag.highly_inbred"), QColor(217, 119, 119)
            elif risk_pct >= 50:
                tag, col = _tr("safe_breeding.tag.moderately_inbred"), QColor(216, 181, 106)
            elif risk_pct >= 20:
                tag, col = _tr("safe_breeding.tag.slightly_inbred"), QColor(143, 201, 230)
            else:
                tag, col = _tr("safe_breeding.tag.not_inbred"), QColor(98, 194, 135)

            is_loved = other.db_key in lover_keys
            is_mutual_love = is_loved and cat.db_key in {
                lover.db_key
                for lover in getattr(other, "lovers", [])
                if lover is not None and getattr(lover, "db_key", None) is not None
            }
            if is_mutual_love:
                row_bg = QColor(132, 36, 88)
                row_fg = QColor(246, 229, 239)
            elif is_loved:
                row_bg = QColor(224, 176, 201)
                row_fg = QColor(52, 32, 44)
            else:
                row_bg = None
                row_fg = None

            heart = " ♥" if is_loved else ""
            name_item = QTableWidgetItem(f"{other.name}{heart} ({other.gender_display})")
            icon = _make_tag_icon(_cat_tags(other), dot_size=14, spacing=4)
            if not icon.isNull():
                name_item.setIcon(icon)
            rel_item = QTableWidgetItem(f"{risk_pct}%")
            shared_item = QTableWidgetItem(str(shared))
            risk_item = QTableWidgetItem(tag)
            rel_item.setData(Qt.UserRole, risk_pct)
            shared_item.setData(Qt.UserRole, shared)
            for it in (name_item, rel_item, shared_item, risk_item):
                it.setTextAlignment(Qt.AlignCenter)
                if row_bg is not None:
                    it.setBackground(QBrush(row_bg))
                    if row_fg is not None:
                        it.setForeground(QBrush(row_fg))
            risk_item.setForeground(QBrush(col))
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, rel_item)
            self._table.setItem(row, 2, shared_item)
            self._table.setItem(row, 3, risk_item)
