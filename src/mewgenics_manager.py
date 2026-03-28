#!/usr/bin/env python3
"""
Mewgenics Breeding Manager
External viewer for cat stats, room locations, and breeding pairs.
Parsing logic based on pzx521521/mewgenics-save-editor.

Requirements: pip install PySide6 lz4
"""

import sys
import re
import html
import json
import csv
import platform
import random
import lz4.block
import os
import math
import logging
import weakref
from pathlib import Path
from typing import Optional, Sequence

logger = logging.getLogger("mewgenics")

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableView, QPushButton, QLabel, QFileDialog, QHeaderView,
    QAbstractItemView, QSplitter, QFrame, QDialog, QGridLayout, QSizePolicy,
    QLineEdit, QListWidgetItem, QScrollArea, QToolButton,
    QTableWidget, QTableWidgetItem, QStyledItemDelegate, QStyle, QStyleOptionViewItem,
    QTextBrowser,
    QComboBox, QCheckBox, QMessageBox, QSpinBox, QDoubleSpinBox, QProgressBar, QTabWidget, QMenu,
)
from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
    QFileSystemWatcher, QItemSelectionModel, QSize, Signal, QRegularExpression, QTimer,
    QThread, QByteArray, QPointF,
)
from PySide6.QtGui import (
    QColor, QBrush, QAction, QActionGroup, QPalette, QFont, QKeySequence, QFontMetrics,
    QDoubleValidator, QRegularExpressionValidator, QPainter, QPixmap, QIcon,
    QPen, QPainterPath,
)

# ── Imports from extracted modules ─────────────────────────────────────────────
from save_parser import (
    BinaryReader, Cat, parse_save,
    FurnitureItem, FurnitureDefinition, FurnitureRoomSummary, summarize_furniture_room,
    build_furniture_room_summaries,
    STAT_NAMES, can_breed, risk_percent, kinship_coi,
    get_parents, get_grandparents,
    find_common_ancestors, shared_ancestor_counts,
    _ancestor_depths, _ancestor_paths, _build_ancestor_paths_batch,
    _ancestor_contributions,
    _coi_from_contribs, raw_coi,
    _is_hater_pair, _valid_str, _normalize_gender,
    _scan_blob_for_parent_uids,
    _read_visual_mutation_entries, _visual_mutation_chip_items,
    _VISUAL_MUTATION_FIELDS, _VISUAL_MUTATION_PART_LABELS,
    _appearance_group_names, _appearance_preview_text,
    _stimulation_inheritance_weight, _inheritance_candidates,
    set_visual_mut_data,
    GameData,
    _load_gpak_text_strings,
    _resolve_game_string,
    _malady_breakdown,
    ROOM_KEYS,
    FURNITURE_ROOM_STAT_KEYS, FURNITURE_ROOM_STAT_LABELS,
)

from breeding import (
    pair_projection,
    is_mutual_lover_pair,
    planner_inbreeding_penalty,
    planner_pair_allows_breeding,
    planner_pair_bias,
    score_pair as score_pair_factors,
    tracked_offspring,
)

from room_optimizer import (
    best_breeding_room_stimulation,
    OptimizationParams,
    RoomConfig,
    RoomType,
    build_room_configs,
)

# ── Imports from extracted utility modules ────────────────────────────────────
from mewgenics.constants import (
    _IDENT_RE,
    STAT_COLORS, ROOM_COLORS, PAIR_COLORS, STATUS_COLOR,
    _room_color, _room_tint, _room_key_from_display,
    COL_NAME, COL_AGE, COL_GEN, COL_ROOM, COL_STAT, COL_BL, COL_MB, COL_PIN,
    STAT_COLS, COL_SUM, COL_AGG, COL_LIB, COL_INBRD, COL_SEXUALITY,
    COL_RELNS, COL_REL, COL_ABIL, COL_MUTS, COL_GEN_DEPTH, COL_SRC,
    _W_STATUS, _W_STAT, _W_GEN, _W_RELNS, _W_REL, _W_TRAIT, _W_TRAIT_NARROW,
    _ZOOM_MIN, _ZOOM_MAX, _ZOOM_STEP,
    _CHIP_STYLE, _DEFECT_CHIP_STYLE, _SEC_STYLE, _NAME_STYLE, _META_STYLE,
    _WARN_STYLE, _SAFE_STYLE, _ANCS_STYLE, _PANEL_BG, _DETAIL_TEXT_STYLE, _NOTE_STYLE,
    _SIDEBAR_BTN,
)
from mewgenics.utils.paths import (
    _bundle_dir, _app_dir,
    APPDATA_SAVE_DIR, APPDATA_CONFIG_DIR, APP_CONFIG_PATH, LOCALES_DIR, APP_VERSION,
    _steam_library_paths,
    _blacklist_path, _must_breed_path, _pinned_path, _tags_path,
    _gender_overrides_path, _calibration_path, _planner_state_path, _breeding_cache_path,
)
from mewgenics.utils.config import (
    _load_app_config, _save_app_config,
    _coerce_int, _coerce_float, _coerce_bool,
    _saved_gpak_path, _saved_save_dir, _save_root_dir,
    _saved_default_save, _set_default_save,
    _save_current_view, _load_current_view,
    _set_save_dir, _candidate_gpak_paths, find_save_files,
    _saved_optimizer_flag, _set_optimizer_flag,
    _saved_room_optimizer_auto_recalc, _set_room_optimizer_auto_recalc,
    _load_ui_state, _save_ui_state,
    _load_splitter_states, _save_splitter_states,
    _restore_splitter_state, _save_splitter_state, _bind_splitter_persistence,
)
from mewgenics.utils.localization import (
    _SUPPORTED_LANGUAGES,
    _locale_log_path, _log_locale_event, _log_startup_environment,
    _load_locale_catalog, _saved_language, _set_saved_language,
    _set_current_language, _current_language, _tr,
    _language_label, _font_size_offset_label,
    _localized_room_display, _localized_status_abbrev,
    _refresh_localized_constants,
)
from mewgenics.utils.tags import (
    TAG_PRESET_COLORS, _TAG_DEFS, _TAG_ICON_CACHE, _TAG_PIX_CACHE, _PIN_ICON_CACHE,
    _load_tag_definitions, _save_tag_definitions,
    _tag_color, _tag_name, _next_tag_id, _cat_tags,
    _make_tag_icon, _make_tag_pixmap, _make_pin_icon,
)
from mewgenics.utils.thresholds import (
    _THRESHOLD_CONFIG_KEY, _THRESHOLD_DEFAULTS, _THRESHOLD_PREFERENCES,
    _normalize_threshold_preferences,
    _load_threshold_preferences, _save_threshold_preferences,
    _effective_thresholds_for_cats,
    _apply_threshold_preferences, _current_threshold_summary,
)
from mewgenics.utils.optimizer_settings import (
    _OPTIMIZER_SEARCH_SETTINGS_KEY, _OPTIMIZER_SEARCH_DEFAULTS,
    _normalize_optimizer_search_settings,
    _load_optimizer_search_settings, _save_optimizer_search_settings,
    _saved_optimizer_search_temperature, _saved_optimizer_search_neighbors,
    _default_room_priority_config, _normalize_room_priority_config,
    _load_room_priority_config, _save_room_priority_config,
)
from mewgenics.utils.planner_state import (
    _load_planner_state_blob, _save_planner_state_blob,
    _load_planner_state_value, _save_planner_state_value,
    _default_perfect_planner_foundation_pairs,
    _load_perfect_planner_foundation_pairs, _save_perfect_planner_foundation_pairs,
    _default_perfect_planner_selected_offspring,
    _load_perfect_planner_selected_offspring, _save_perfect_planner_selected_offspring,
    _planner_pair_uid_key,
    _planner_import_trait_display, _planner_import_traits_summary, _planner_import_traits_tooltip,
)
from mewgenics.utils.calibration import (
    _CALIBRATION_TRAIT_OPTIONS, _CALIBRATION_TRAIT_NUMERIC, _TRAIT_LEVEL_COLORS,
    _safe_float, _normalize_override_gender,
    _normalize_trait_override, _trait_numeric_override,
    _trait_label_from_value, _trait_level_color,
    _load_calibration_data, _save_calibration_data,
    _learn_gender_token_map, _apply_calibration_data, _apply_calibration,
    _load_gender_overrides,
)
from mewgenics.utils.cat_persistence import (
    _save_blacklist, _load_blacklist,
    _save_must_breed, _load_must_breed,
    _save_pinned, _load_pinned,
    _save_tags, _load_tags,
)
from mewgenics.utils.cat_analysis import (
    _cat_uid, _cat_base_sum,
    _is_exceptional_breeder, _has_eternal_youth,
    _donation_candidate_base_reason, _donation_candidate_reason, _is_donation_candidate,
    _relations_summary, _pair_breakpoint_analysis,
)
from mewgenics.utils.abilities import (
    _ABILITY_LOOKUP, _ABILITY_DESC, _MUTATION_DISPLAY_NAMES, _ABILITY_KEY_ALIASES,
    _mutation_display_name,
    _trait_selector_summary, _trait_selector_label,
    _trait_display_kind, _trait_description_preview, _trait_visible_detail,
    _ability_tip, _abilities_tooltip, _mutations_tooltip,
    _read_db_key_candidates,
    _ability_effect_lines, _mutation_effect_lines,
    _load_ability_descriptions,
    _trait_inheritance_probabilities,
    _cat_has_trait, _planner_trait_display_name,
)
from mewgenics.utils.game_data import (
    _reload_game_data, _set_gpak_path,
)
from mewgenics.utils.styling import (
    _ACCESSIBILITY_MIN_FONT_PX, _ACCESSIBILITY_MIN_FONT_PT, _FONT_SIZE_RE,
    _with_min_font_px, _enforce_min_font_in_widget_tree,
    _apply_font_offset_to_tree, _enable_manual_header_resize,
    _chip, _defect_chip, _sec, _vsep, _hsep, _sidebar_btn,
    _detail_text_block, _blend_qcolor,
)
from mewgenics.utils.table_state import (
    _table_view_state_key,
    _load_table_view_states, _save_table_view_states,
    _queue_table_view_state_save, _save_table_view_state, _restore_table_view_state,
    _capture_table_view_states, _restore_table_view_states,
    _configure_table_view_behavior,
)

_reload_game_data()
from mewgenics.utils.game_data import _GPAK_PATH, _FURNITURE_DATA, _VISUAL_MUT_DATA  # noqa: E402



# ── Imports from extracted models & workers ───────────────────────────────────
from mewgenics.models.breeding_cache import (
    BreedingCache, BreedingCacheWorker,
    _breeding_cache_fingerprint, _breeding_save_signature,
)
from mewgenics.models.cat_table_model import (
    NameTagDelegate, CatTableModel,
    _SortByUserRoleItem, _SortKeyItem,
)
from mewgenics.models.room_filter_model import RoomFilterModel
from mewgenics.workers.save_loader import SaveLoadWorker
from mewgenics.workers.room_refresh import QuickRoomRefreshWorker
from mewgenics.workers.optimizer_worker import RoomOptimizerWorker


# ── Module-level initialization ───────────────────────────────────────────────
_log_startup_environment()
_set_current_language(_saved_language())
_refresh_localized_constants()
_load_tag_definitions()
_apply_threshold_preferences(_load_threshold_preferences())

# Re-import mutable state that was just initialized above
from mewgenics.utils.localization import ROOM_DISPLAY, STATUS_ABBREV, COLUMNS  # noqa: E402
from mewgenics.utils.thresholds import EXCEPTIONAL_SUM_THRESHOLD, DONATION_SUM_THRESHOLD, DONATION_MAX_TOP_STAT  # noqa: E402



# ── Imports from extracted dialogs & panels ──────────────────────────────────
from mewgenics.dialogs import (
    TagManagerDialog,
    ThresholdPreferencesDialog,
    SharedOptimizerSearchSettingsDialog,
    SaveSelectorDialog,
)
from mewgenics.panels.cat_detail import CatDetailPanel
from mewgenics.panels.room_priority import RoomPriorityPanel


class FamilyTreeBrowserView(QWidget):
    """
    Dedicated tree-browsing view:
    left side = cat list, right side = visual family tree for selected cat.
    """
    COL_NAME = 0
    COL_LOC = 1
    COL_GEN = 2
    COL_AGE = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QListWidget { background:#0d0d1c; color:#ddd; border:1px solid #1e1e38; }"
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
            "QScrollArea { border:none; background:#0a0a18; }"
        )
        self._cats: list[Cat] = []
        self._by_key: dict[int, Cat] = {}
        self._alive_only: bool = True

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # Left pane: search + list
        left = QWidget()
        left.setFixedWidth(390)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)
        lv.addWidget(QLabel(_tr("family_tree.cats"), styleSheet="color:#666; font-size:10px; font-weight:bold;"))
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(6)
        self._all_btn = _sidebar_btn(_tr("family_tree.filter_all"))
        self._alive_btn = _sidebar_btn(_tr("family_tree.filter_alive"))
        self._all_btn.setCheckable(True)
        self._alive_btn.setCheckable(True)
        self._alive_btn.setChecked(True)
        self._all_btn.clicked.connect(lambda: self._set_alive_only(False))
        self._alive_btn.clicked.connect(lambda: self._set_alive_only(True))
        mode_row.addWidget(self._all_btn)
        mode_row.addWidget(self._alive_btn)
        lv.addLayout(mode_row)
        self._search = QLineEdit()
        self._search.setPlaceholderText(_tr("family_tree.search_placeholder"))
        lv.addWidget(self._search)
        self._list = QTableWidget(0, 4)
        self._list.setHorizontalHeaderLabels([
            "Name",
            "Location",
            "Generation",
            "Age",
        ])
        self._list.verticalHeader().setVisible(False)
        self._list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._list.setFocusPolicy(Qt.NoFocus)
        self._list.setWordWrap(False)
        self._list.setSortingEnabled(True)
        self._list.sortByColumn(self.COL_NAME, Qt.SortOrder.AscendingOrder)
        hh = self._list.horizontalHeader()
        hh.setStretchLastSection(False)
        # Keep the name column compact by default; users can still widen it.
        hh.setSectionResizeMode(self.COL_NAME, QHeaderView.Interactive)
        self._list.setColumnWidth(self.COL_NAME, 150)
        hh.setSectionResizeMode(self.COL_LOC, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_GEN, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_AGE, QHeaderView.ResizeToContents)
        lv.addWidget(self._list, 1)
        root.addWidget(left)

        # Right pane: tree
        self._tree_scroll = QScrollArea()
        self._tree_scroll.setWidgetResizable(True)
        self._tree_content = QWidget()
        self._tree_scroll.setWidget(self._tree_content)
        root.addWidget(self._tree_scroll, 1)

        self._search.textChanged.connect(self._refresh_list)
        self._list.currentCellChanged.connect(self._on_current_item_changed)
        _enforce_min_font_in_widget_tree(self)
        self._refresh_filter_button_labels()

    def _refresh_filter_button_labels(self):
        total = len(self._cats)
        alive = sum(1 for c in self._cats if c.status != "Gone")
        self._all_btn.setText(f"{_tr('family_tree.filter_all')} ({total})")
        self._alive_btn.setText(f"{_tr('family_tree.filter_alive')} ({alive})")

    def set_cats(self, cats: list[Cat]):
        selected_key = None
        cur = self._list.currentItem()
        if cur is not None:
            selected_key = int(cur.data(Qt.UserRole))
        self._cats = sorted(cats, key=lambda c: (c.name or "").lower())
        self._by_key = {c.db_key: c for c in self._cats}
        self._refresh_filter_button_labels()
        self._refresh_list()
        if selected_key is not None and selected_key in self._by_key:
            self.select_cat(self._by_key[selected_key])
        elif self._list.rowCount():
            self._list.setCurrentCell(0, self.COL_NAME)
        else:
            self._render_tree(None)

    def select_cat(self, cat: Optional[Cat]):
        if cat is None:
            return
        for row in range(self._list.rowCount()):
            item = self._list.item(row, self.COL_NAME)
            if item is not None and int(item.data(Qt.UserRole)) == cat.db_key:
                self._list.setCurrentCell(row, self.COL_NAME)
                self._list.scrollToItem(item)
                return

    def _open_cat_from_tree(self, cat: Optional[Cat]):
        if cat is None:
            return
        # If a gone cat is clicked while Alive filter is active, switch to All.
        if self._alive_only and cat.status == "Gone":
            self._set_alive_only(False)
        # Ensure search does not hide the clicked target.
        if self._search.text():
            self._search.clear()
        self.select_cat(cat)

    def _gen_age_text(self, c: Optional[Cat]) -> str:
        if c is None or c.status == "Gone":
            return ""
        age = "?"
        if getattr(c, "age", None) is not None:
            age = str(c.age)
        return _tr("family_tree.gen_age", generation=c.generation, age=age)

    def _set_alive_only(self, enabled: bool):
        self._alive_only = enabled
        self._alive_btn.setChecked(enabled)
        self._all_btn.setChecked(not enabled)
        self._refresh_list()

    def _refresh_list(self):
        query = self._search.text().strip().lower()
        current_key = None
        cur = self._list.currentItem()
        if cur is not None:
            current_key = int(cur.data(Qt.UserRole))

        self._list.setSortingEnabled(False)
        self._list.clearContents()
        self._list.setRowCount(0)
        for cat in self._cats:
            if self._alive_only and cat.status == "Gone":
                continue
            if query and query not in cat.name.lower():
                continue
            row = self._list.rowCount()
            self._list.insertRow(row)

            name_item = QTableWidgetItem(cat.name)
            name_item.setData(Qt.UserRole, cat.db_key)
            icon = _make_tag_icon(_cat_tags(cat), dot_size=10, spacing=3)
            if not icon.isNull():
                name_item.setIcon(icon)
            name_item.setToolTip(cat.name)
            self._list.setItem(row, self.COL_NAME, name_item)

            if cat.status == "In House":
                location_text = cat.room_display or _tr("status.in_house")
            else:
                location_text = _tr("status.gone") if cat.status == "Gone" else _tr("status.adventure")
            loc_item = QTableWidgetItem(location_text)
            loc_item.setTextAlignment(Qt.AlignCenter)
            self._list.setItem(row, self.COL_LOC, loc_item)

            gen_item = _SortKeyItem(str(cat.generation))
            gen_item.setData(Qt.UserRole, cat.generation)
            gen_item.setTextAlignment(Qt.AlignCenter)
            self._list.setItem(row, self.COL_GEN, gen_item)

            age_value = getattr(cat, "age", None)
            if cat.status == "Gone":
                age_item = _SortKeyItem("—")
                age_item.setData(Qt.UserRole, 10**9)
            else:
                age_item = _SortKeyItem(str(age_value) if age_value is not None else "—")
                age_item.setData(Qt.UserRole, age_value if age_value is not None else 10**9)
            age_item.setTextAlignment(Qt.AlignCenter)
            self._list.setItem(row, self.COL_AGE, age_item)

        self._list.setSortingEnabled(True)
        self._list.sortByColumn(self.COL_NAME, Qt.SortOrder.AscendingOrder)

        if self._list.rowCount() == 0:
            self._render_tree(None)
            return
        if current_key is not None:
            for row in range(self._list.rowCount()):
                it = self._list.item(row, self.COL_NAME)
                if it is not None and int(it.data(Qt.UserRole)) == current_key:
                    self._list.setCurrentCell(row, self.COL_NAME)
                    return
        self._list.setCurrentCell(0, self.COL_NAME)

    def _on_current_item_changed(self, current_row, current_column, previous_row, previous_column):
        if current_row < 0:
            self._render_tree(None)
            return
        current = self._list.item(current_row, self.COL_NAME)
        if current is None:
            self._render_tree(None)
            return
        cat = self._by_key.get(int(current.data(Qt.UserRole)))
        self._render_tree(cat)

    def _render_tree(self, cat: Optional[Cat]):
        self._tree_content = QWidget()
        self._tree_scroll.setWidget(self._tree_content)

        root = QVBoxLayout(self._tree_content)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(10)

        if cat is None:
            root.addWidget(QLabel(_tr("family_tree.no_match"), styleSheet="color:#666; font-size:12px;"))
            root.addStretch()
            return

        title = QLabel(_tr("family_tree.title", name=cat.name))
        title.setStyleSheet("color:#ddd; font-size:16px; font-weight:bold;")
        root.addWidget(title)
        root.addWidget(QLabel(_tr("family_tree.click_hint"), styleSheet="color:#666; font-size:11px;"))

        def cat_box(c: Optional[Cat], highlight=False):
            if c is None:
                btn = QPushButton(_tr("family_tree.unknown"))
                btn.setEnabled(False)
                btn.setStyleSheet(
                    "QPushButton { color:#303040; font-size:10px; padding:7px 10px;"
                    " background:#0e0e1c; border:1px solid #18182a; border-radius:6px; }")
                return btn
            line2 = c.gender_display
            if c.room_display:
                line2 += f"  {c.room_display}"
            gen_age = self._gen_age_text(c)
            if gen_age:
                line2 += f"  |  {gen_age}"
            if c.status == "Gone":
                line2 += f"  ({_tr('status.gone')})"
            bg = "#1d2f4a" if highlight else "#131326"
            border = "#3b5f95" if highlight else "#252545"
            btn = QPushButton(f"{c.name}\n{line2}")
            icon = _make_tag_icon(_cat_tags(c), dot_size=14, spacing=4)
            if not icon.isNull():
                btn.setIcon(icon)
            btn.setStyleSheet(
                f"QPushButton {{ color:#ddd; font-size:10px; padding:7px 10px;"
                f" background:{bg}; border:1px solid {border}; border-radius:6px; }}"
                "QPushButton:hover { background:#1a2a46; }")
            if c is not cat:
                btn.clicked.connect(lambda checked=False, target=c: self._open_cat_from_tree(target))
            else:
                btn.setEnabled(False)
            btn.setMinimumWidth(120)
            return btn

        def row_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("color:#444; font-weight:bold; letter-spacing:1px;")
            lbl.setFixedWidth(row_label_width)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return lbl

        def add_generation_row(label: str, cats_row: list[Optional[Cat]], highlight_self=False):
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(row_label(label))
            for c in cats_row:
                row.addWidget(cat_box(c, highlight=highlight_self and c is cat))
            row.addStretch()
            root.addLayout(row)

        def add_arrow():
            a = QLabel("↓")
            a.setStyleSheet("color:#2f3f66; font-size:16px;")
            a.setAlignment(Qt.AlignCenter)
            root.addWidget(a)

        def _dedupe_keep_order(items: list[Cat]) -> list[Cat]:
            seen = set()
            out: list[Cat] = []
            for item in items:
                sid = id(item)
                if sid in seen:
                    continue
                seen.add(sid)
                out.append(item)
            return out

        def _ancestor_row_label(level: int) -> str:
            if level == 1:
                return _tr("family_tree.level.parents")
            if level == 2:
                return _tr("family_tree.level.grandparents")
            if level == 3:
                return _tr("family_tree.level.great_grandparents")
            return _tr("family_tree.level.n_great_grandparents", count=level - 2)

        # Build all known ancestor levels (1=parents, 2=grandparents, ...).
        ancestor_levels: list[list[Cat]] = []
        frontier: list[Cat] = [cat]
        for _ in range(8):
            nxt: list[Cat] = []
            for node in frontier:
                if node.parent_a is not None:
                    nxt.append(node.parent_a)
                if node.parent_b is not None:
                    nxt.append(node.parent_b)
            nxt = _dedupe_keep_order(nxt)
            if not nxt:
                break
            ancestor_levels.append(nxt)
            frontier = nxt

        # Dynamic row-label gutter width: based on the longest visible label and
        # current font metrics, so it tracks zoom/font-size changes.
        label_texts = ["SELF", "CHILDREN", "GRANDCHILDREN"] + [
            _ancestor_row_label(i) for i in range(1, len(ancestor_levels) + 1)
        ]
        label_font = QFont(self.font())
        label_font.setBold(True)
        fm = QFontMetrics(label_font)
        max_text_px = max(fm.horizontalAdvance(t) for t in label_texts)
        # Row labels use letter-spacing:1px in stylesheet; account for that so
        # long prefixes like "10x " are fully measured.
        max_letter_spacing_px = max(max(len(t) - 1, 0) for t in label_texts)
        row_label_width = max(120, max_text_px + max_letter_spacing_px + 24)

        children = list(cat.children)
        grandchildren: list[Cat] = []
        for child in children:
            grandchildren.extend(child.children)
        grandchildren = list({id(c): c for c in grandchildren}.values())

        # Render oldest ancestors at top, then down to self.
        for idx in range(len(ancestor_levels), 0, -1):
            level_nodes = ancestor_levels[idx - 1]
            add_generation_row(_ancestor_row_label(idx), level_nodes[:12])
            if len(level_nodes) > 12:
                root.addWidget(QLabel(
                    f"… and {len(level_nodes)-12} more in {_ancestor_row_label(idx)}",
                    styleSheet="color:#555; font-size:10px;"))
            add_arrow()
        add_generation_row("SELF", [cat], highlight_self=True)

        if children:
            add_arrow()
            add_generation_row("CHILDREN", children[:10])
            if len(children) > 10:
                root.addWidget(QLabel(f"… and {len(children)-10} more children", styleSheet="color:#555; font-size:10px;"))
        if grandchildren:
            add_arrow()
            add_generation_row("GRANDCHILDREN", grandchildren[:10])
            if len(grandchildren) > 10:
                root.addWidget(QLabel(f"… and {len(grandchildren)-10} more grandchildren", styleSheet="color:#555; font-size:10px;"))
        if not any([ancestor_levels, children, grandchildren]):
            root.addWidget(QLabel("No known lineage data for this cat yet.", styleSheet="color:#666; font-size:12px;"))

        root.addStretch()
        _enforce_min_font_in_widget_tree(self._tree_content)


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


class BreedingPartnersView(QWidget):
    """Dedicated view for mutual and one-way lover rows plus room mismatch hints."""

    COL_RELATION = 0
    COL_CAT_A = 1
    COL_CAT_B = 2
    COL_ROOM_A = 3
    COL_ROOM_B = 4
    COL_STATUS = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; }"
            "QHeaderView::section { background:#151532; color:#7d8bb0; border:none; padding:4px; font-weight:bold; }"
        )
        self._cats: list[Cat] = []
        self._pairs: list[dict[str, object]] = []
        self._navigate_to_cat_callback = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        self._title = QLabel()
        self._title.setStyleSheet("color:#ddd; font-size:18px; font-weight:bold;")
        self._summary = QLabel("")
        self._summary.setStyleSheet("color:#666; font-size:11px;")
        header.addWidget(self._title)
        header.addStretch()
        header.addWidget(self._summary)
        root.addLayout(header)

        self._search = QLineEdit()
        root.addWidget(self._search)

        self._table = QTableWidget(0, 6)
        self._table.setIconSize(QSize(60, 20))
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._table.setHorizontalHeaderLabels([
            _tr("breeding_partners.table.relation"),
            _tr("breeding_partners.table.cat_a"),
            _tr("breeding_partners.table.cat_b"),
            _tr("breeding_partners.table.room_a"),
            _tr("breeding_partners.table.room_b"),
            _tr("breeding_partners.table.status"),
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(True)
        hh = self._table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSortIndicatorShown(True)
        hh.setSectionResizeMode(self.COL_RELATION, QHeaderView.Interactive)
        hh.setSectionResizeMode(self.COL_CAT_A, QHeaderView.Interactive)
        hh.setSectionResizeMode(self.COL_CAT_B, QHeaderView.Interactive)
        hh.setSectionResizeMode(self.COL_ROOM_A, QHeaderView.Interactive)
        hh.setSectionResizeMode(self.COL_ROOM_B, QHeaderView.Interactive)
        hh.setSectionResizeMode(self.COL_STATUS, QHeaderView.Interactive)
        self._table.setColumnWidth(self.COL_RELATION, 110)
        self._table.setColumnWidth(self.COL_CAT_A, 160)
        self._table.setColumnWidth(self.COL_CAT_B, 160)
        self._table.setColumnWidth(self.COL_ROOM_A, 110)
        self._table.setColumnWidth(self.COL_ROOM_B, 110)
        self._table.setColumnWidth(self.COL_STATUS, 280)
        root.addWidget(self._table, 1)

        self._search.textChanged.connect(self._refresh_table)
        self._table.itemClicked.connect(self._on_cat_cell_clicked)
        _enforce_min_font_in_widget_tree(self)
        self._table.sortByColumn(self.COL_RELATION, Qt.AscendingOrder)
        self.retranslate_ui()

    def _cat_label(self, cat, *, hide_gone: bool = False) -> str:
        if hide_gone and cat.status == "Gone":
            return ""
        label = f"{cat.name} ({cat.gender_display})"
        if cat.status == "Gone":
            label += " (gone)"
        return label

    def _cat_room_label(self, cat) -> str:
        if cat.status == "In House":
            return cat.room_display or _tr("status.in_house", default="In House")
        if cat.status == "Gone":
            return _tr("status.gone", default="Gone")
        return _tr("status.adventure", default="Away")

    def _cat_status_label(self, cat) -> str:
        label = cat.name
        if cat.status == "Gone":
            label += " (gone)"
        return label

    def _relation_label(self, is_mutual: bool) -> str:
        return _tr(
            "breeding_partners.relation.mutual" if is_mutual else "breeding_partners.relation.one_way",
            default="Mutual" if is_mutual else "One way",
        )

    def _love_status_text(self, cat_a, cat_b, is_mutual: bool) -> str:
        cat_a_label = self._cat_status_label(cat_a)
        cat_b_label = self._cat_status_label(cat_b)
        if is_mutual:
            return f"{cat_a_label} <-> {cat_b_label}"
        return f"{cat_a_label} --> {cat_b_label}"

    def set_navigate_to_cat_callback(self, callback):
        self._navigate_to_cat_callback = callback

    def set_cats(self, cats: list[Cat]):
        self._cats = cats
        self._pairs = []
        seen: set[tuple[str, int, int]] = set()
        all_cats = [cat for cat in cats if cat is not None]
        cat_keys = {cat.db_key for cat in all_cats}
        lover_key_map: dict[int, set[int]] = {
            cat.db_key: {
                lover.db_key
                for lover in getattr(cat, "lovers", [])
                if lover is not None and getattr(lover, "db_key", None) is not None and lover is not cat
            }
            for cat in all_cats
        }
        for cat in all_cats:
            for lover in getattr(cat, "lovers", []):
                if lover is None or lover is cat or getattr(lover, "db_key", None) not in cat_keys:
                    continue
                mutual = is_mutual_lover_pair(cat, lover, lover_key_map)
                key = ("mutual",) + tuple(sorted((cat.db_key, lover.db_key))) if mutual else ("one_way", cat.db_key, lover.db_key)
                if key in seen:
                    continue
                seen.add(key)
                if mutual and cat.db_key > lover.db_key:
                    cat_a, cat_b = lover, cat
                else:
                    cat_a, cat_b = cat, lover
                same_room = bool(
                    cat_a.room
                    and cat_b.room
                    and cat_a.room == cat_b.room
                    and cat_a.status == cat_b.status == "In House"
                )
                self._pairs.append({
                    "cat_a": cat_a,
                    "cat_b": cat_b,
                    "same_room": same_room,
                    "is_mutual": mutual,
                })
        self._pairs.sort(key=lambda p: (
            not bool(p["is_mutual"]),
            not bool(p["same_room"]),
            str(p["cat_a"].name).lower(),
            str(p["cat_b"].name).lower(),
        ))
        self._refresh_table()

    def set_cache(self, cache: Optional['BreedingCache']):
        """Breeding pair detection does not depend on the shared breeding cache."""
        return None

    def _refresh_table(self):
        query = self._search.text().strip().lower()
        pairs = self._pairs
        if query:
            pairs = [
                p for p in pairs
                if query in " ".join([
                    self._relation_label(bool(p["is_mutual"])).lower(),
                    self._cat_label(p["cat_a"]).lower(),
                    self._cat_label(p["cat_b"]).lower(),
                    self._cat_room_label(p["cat_a"]).lower(),
                    self._cat_room_label(p["cat_b"]).lower(),
                    self._love_status_text(p["cat_a"], p["cat_b"], bool(p["is_mutual"])).lower(),
                ])
            ]
        pairs = [p for p in pairs if p["cat_a"].status != "Gone"]

        # Sorting is intentionally disabled here so row insertion order stays
        # deterministic while we rebuild the rows, then we restore the active sort.
        self._table.setSortingEnabled(False)
        sort_col = self._table.horizontalHeader().sortIndicatorSection()
        sort_order = self._table.horizontalHeader().sortIndicatorOrder()
        self._table.setRowCount(len(pairs))
        mismatch_count = 0
        mutual_count = 0
        for row, pair in enumerate(pairs):
            is_mutual = bool(pair["is_mutual"])
            if is_mutual:
                mutual_count += 1
            same_room = bool(pair["same_room"])
            if not same_room:
                mismatch_count += 1
            relation_text = self._relation_label(is_mutual)
            relation_color = QColor(98, 194, 135) if is_mutual else QColor(216, 181, 106)
            item_relation = QTableWidgetItem(relation_text)
            item_relation.setTextAlignment(Qt.AlignCenter)
            item_relation.setForeground(QBrush(relation_color))
            relation_font = item_relation.font()
            relation_font.setBold(True)
            item_relation.setFont(relation_font)

            item_a = QTableWidgetItem(self._cat_label(pair["cat_a"], hide_gone=True))
            link_font = QFont()
            link_font.setUnderline(True)
            item_a.setFont(link_font)
            item_a.setForeground(QBrush(QColor(100, 149, 237)))
            if item_a.text():
                icon_a = _make_tag_icon(_cat_tags(pair['cat_a']), dot_size=14, spacing=4)
                if not icon_a.isNull():
                    item_a.setIcon(icon_a)
            item_b = QTableWidgetItem(self._cat_label(pair["cat_b"]))
            item_b.setFont(link_font)
            item_b.setForeground(QBrush(QColor(100, 149, 237)))
            icon_b = _make_tag_icon(_cat_tags(pair['cat_b']), dot_size=14, spacing=4)
            if not icon_b.isNull():
                item_b.setIcon(icon_b)
            items = [
                item_relation,
                item_a,
                item_b,
                QTableWidgetItem(self._cat_room_label(pair["cat_a"])),
                QTableWidgetItem(self._cat_room_label(pair["cat_b"])),
                QTableWidgetItem(self._love_status_text(pair["cat_a"], pair["cat_b"], is_mutual)),
            ]
            items[self.COL_STATUS].setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            items[self.COL_STATUS].setForeground(QBrush(relation_color))
            if not same_room:
                for item in items[:5]:
                    item.setBackground(QBrush(QColor(48, 36, 14)))
            for col, item in enumerate(items):
                self._table.setItem(row, col, item)

        total = len(self._pairs)
        shown = len(pairs)
        self._table.setSortingEnabled(True)
        if sort_col != self.COL_RELATION or sort_order != Qt.AscendingOrder:
            self._table.sortByColumn(sort_col, sort_order)
        self._summary.setText(_tr("breeding_partners.summary",
                                   shown=shown, total=total, mutual=mutual_count, one_way=shown - mutual_count, mismatches=mismatch_count))

    def _on_cat_cell_clicked(self, item):
        """Handle clicks on cat names to navigate to the cat in the main view."""
        col = self._table.column(item)
        # Only handle clicks on Cat A or Cat B.
        if col not in (self.COL_CAT_A, self.COL_CAT_B):
            return

        cat_name = item.text()
        if not cat_name or not self._navigate_to_cat_callback:
            return

        # Call the navigate callback with the cat name
        self._navigate_to_cat_callback(cat_name)

    def retranslate_ui(self):
        self._title.setText(_tr("breeding_partners.title"))
        self._search.setPlaceholderText(_tr("breeding_partners.search_placeholder"))
        self._table.setHorizontalHeaderLabels([
            _tr("breeding_partners.table.relation"),
            _tr("breeding_partners.table.cat_a"),
            _tr("breeding_partners.table.cat_b"),
            _tr("breeding_partners.table.room_a"),
            _tr("breeding_partners.table.room_b"),
            _tr("breeding_partners.table.status"),
        ])
        self._refresh_table()



# ── Room Optimizer View ───────────────────────────────────────────────────────

class RoomOptimizerView(QWidget):
    """View for optimizing cat room distribution to maximize breeding outcomes."""

    @staticmethod
    def _set_toggle_button_label(btn: QPushButton, label_key: str):
        defaults = {
            "room_optimizer.toggle.minimize_variance": "Minimize Variance",
            "room_optimizer.toggle.avoid_lovers": "Avoid Lovers",
            "room_optimizer.toggle.prefer_low_aggression": "Prefer Low Aggression",
            "room_optimizer.toggle.prefer_high_libido": "Prefer High Libido",
            "room_optimizer.toggle.maximize_throughput": "Maximize Throughput",
            "room_optimizer.toggle.use_sa": "More Depth",
        }
        state = _tr("common.on", default="On") if btn.isChecked() else _tr("common.off", default="Off")
        btn.setText(f"{_tr(label_key, default=defaults.get(label_key, label_key))}: {state}")

    @staticmethod
    def _bind_persistent_toggle(btn: QPushButton, label_key: str, key: str):
        RoomOptimizerView._set_toggle_button_label(btn, label_key)
        btn.toggled.connect(lambda checked: _set_optimizer_flag(key, checked))
        btn.toggled.connect(lambda _: RoomOptimizerView._set_toggle_button_label(btn, label_key))

    def _set_mode_button_text(self, enabled: bool):
        key = "room_optimizer.mode_family" if enabled else "room_optimizer.mode_pair"
        self._mode_toggle_btn.setText(_tr(key))
        self._mode_toggle_btn.setToolTip(_tr("room_optimizer.mode_tooltip"))

    @staticmethod
    def _style_room_action_button(btn: QPushButton, background: str, border: str, hover_background: str):
        btn.setCheckable(False)
        btn.setMinimumWidth(110)
        btn.setStyleSheet(
            "QPushButton { "
            f"background:{background}; color:#f1f1f1; border:1px solid {border}; "
            "border-radius:4px; padding:4px 10px; font-size:11px; font-weight:bold; }"
            f"QPushButton:hover {{ background:{hover_background}; }}"
            "QPushButton:pressed { background:#1a1a1a; }"
        )

    @staticmethod
    def _style_import_planner_button(btn: QPushButton, active: bool = False):
        if active:
            btn.setStyleSheet(
                "QPushButton { background:#2a3a5a; color:#aaddff; border:1px solid #4a6a9a; "
                "border-radius:4px; padding:6px 12px 6px 10px; font-size:11px; text-align:left; }"
                "QPushButton:hover { background:#3a4a6a; color:#ddd; }"
            )
        else:
            btn.setStyleSheet(
                "QPushButton { background:#2a2a5a; color:#bbbbee; border:1px solid #4a4a8a; "
                "border-radius:4px; padding:6px 12px 6px 10px; font-size:11px; text-align:left; }"
                "QPushButton:hover { background:#3a3a6a; color:#ddd; }"
            )

    def _set_room_action_button_texts(self):
        self._must_breed_action_btn.setText(_tr("bulk.toggle_must_breed"))
        self._must_breed_action_btn.setToolTip(_tr("bulk.toggle_must_breed.tooltip"))
        self._breeding_block_action_btn.setText(_tr("bulk.toggle_breeding_block"))
        self._breeding_block_action_btn.setToolTip(_tr("bulk.toggle_breeding_block.tooltip"))
        self._pin_action_btn.setText(_tr("bulk.toggle_pin", default="Toggle Pin"))
        self._pin_action_btn.setToolTip(_tr("bulk.toggle_pin.tooltip", default="Toggle pin for selected cats"))

    def _current_room_data(self) -> Optional[dict]:
        selected_ranges = self._table.selectedRanges()
        if not selected_ranges:
            return None
        row = selected_ranges[0].topRow()
        room_item = self._table.item(row, 0)
        if room_item is None:
            return None
        data = room_item.data(Qt.UserRole)
        return data if isinstance(data, dict) else None

    def _room_cats_from_data(self, data: Optional[dict]) -> list[Cat]:
        if not data:
            return []
        cat_keys: list[int] = []
        for key in data.get("cat_keys", []) or []:
            try:
                cat_keys.append(int(key))
            except (TypeError, ValueError):
                continue
        if not cat_keys and data.get("room") == "Excluded":
            for row in data.get("excluded_cat_rows", []) or []:
                try:
                    cat_keys.append(int(row.get("db_key")))
                except (TypeError, ValueError):
                    continue
        if not cat_keys:
            wanted_names = {
                str(name).split(" (", 1)[0]
                for name in (data.get("cats", []) or [])
                if name
            }
            if not wanted_names:
                return []
            return [cat for cat in self._cats if cat.name in wanted_names]
        lookup = getattr(self, "_cat_lookup", None) or {cat.db_key: cat for cat in self._cats}
        seen: set[int] = set()
        cats: list[Cat] = []
        for key in cat_keys:
            if key in seen:
                continue
            seen.add(key)
            cat = lookup.get(key)
            if cat is not None:
                cats.append(cat)
        return cats

    def _refresh_main_model(self):
        mw = self.window()
        source_model = getattr(mw, "_source_model", None)
        if source_model is None or source_model.rowCount() == 0:
            return
        top_left = source_model.index(0, COL_BL)
        bottom_right = source_model.index(max(0, source_model.rowCount() - 1), COL_PIN)
        source_model.dataChanged.emit(
            top_left,
            bottom_right,
            [Qt.DisplayRole, Qt.CheckStateRole, Qt.ToolTipRole],
        )
        source_model.blacklistChanged.emit()

    def _apply_room_action(self, action: str):
        cats = self._room_cats_from_data(self._current_room_data())
        mw = self.window()
        status_bar = mw.statusBar() if hasattr(mw, "statusBar") else None
        if not cats:
            if status_bar is not None:
                status_bar.showMessage("Select a room first, then click a room action.")
            return

        changed = 0
        for cat in cats:
            if action == "must_breed":
                cat.must_breed = not cat.must_breed
                if cat.must_breed:
                    cat.is_blacklisted = False
            elif action == "breeding_block":
                cat.is_blacklisted = not cat.is_blacklisted
                if cat.is_blacklisted:
                    cat.must_breed = False
            elif action == "pin":
                cat.is_pinned = not cat.is_pinned
            changed += 1

        self._refresh_main_model()
        self._refresh_room_action_buttons()

        if action == "must_breed":
            if status_bar is not None:
                status_bar.showMessage(_tr("bulk.status.toggled_must_breed", default="Toggled must breed for {count} selected cats", count=changed))
        elif action == "breeding_block":
            if status_bar is not None:
                status_bar.showMessage(_tr("bulk.status.toggled_breeding_block", default="Toggled breeding block for {count} selected cats", count=changed))
        else:
            if status_bar is not None:
                status_bar.showMessage(_tr("bulk.status.toggled_pin", default="Toggled pin for {count} selected cats", count=changed))

    def _refresh_room_action_buttons(self):
        cats = self._room_cats_from_data(self._current_room_data())
        enabled = bool(cats)
        for btn in (self._must_breed_action_btn, self._breeding_block_action_btn, self._pin_action_btn):
            btn.setEnabled(enabled)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; }"
            "QHeaderView::section { background:#151532; color:#7d8bb0; border:none; padding:4px; font-weight:bold; }"
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._cats: list[Cat] = []
        self._cache: Optional[BreedingCache] = None
        self._optimizer_worker: Optional[RoomOptimizerWorker] = None
        self._auto_recalculate = _saved_room_optimizer_auto_recalc()
        self._planner_view: Optional['MutationDisorderPlannerView'] = None
        self._planner_traits: list[dict] = []
        self._available_rooms: list[str] = list(ROOM_DISPLAY.keys())
        self._room_summaries: dict[str, FurnitureRoomSummary] = {}
        self._save_path: Optional[str] = None
        self._session_state: dict = _load_planner_state_value("room_optimizer_state", {})
        self._restoring_session_state = False
        self._pending_initial_restore_run = False
        self._selected_room_data: Optional[dict] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Header
        header = QHBoxLayout()
        self._title = QLabel()
        self._title.setStyleSheet("color:#ddd; font-size:18px; font-weight:bold;")
        self._summary = QLabel("")
        self._summary.setStyleSheet("color:#666; font-size:11px;")
        self._summary.setWordWrap(True)
        self._summary.setMaximumHeight(50)
        self._summary.setAlignment(Qt.AlignRight | Qt.AlignTop)
        header.addWidget(self._title)
        header.addWidget(self._summary, 1)  # stretch=1 to fill space
        root.addLayout(header)

        self._top_actions = QWidget()
        self._top_actions.setStyleSheet("background:transparent;")
        self._top_actions_layout = QHBoxLayout(self._top_actions)
        self._top_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._top_actions_layout.setSpacing(8)
        self._top_actions_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addWidget(self._top_actions)

        # Room priority panel
        self._room_priority_panel = RoomPriorityPanel()
        self._room_priority_panel.setStyleSheet("background:transparent;")
        self._room_priority_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._configure_rooms_tab = QWidget()
        self._configure_rooms_tab.setStyleSheet("background:#0a0a18;")
        configure_rooms_layout = QVBoxLayout(self._configure_rooms_tab)
        configure_rooms_layout.setContentsMargins(0, 0, 0, 0)
        configure_rooms_layout.setSpacing(8)
        configure_rooms_layout.addWidget(self._room_priority_panel, 1)
        self._setup_tab = QWidget()
        self._setup_tab.setStyleSheet("background:#0a0a18;")
        self._setup_tab_layout = QVBoxLayout(self._setup_tab)
        self._setup_tab_layout.setContentsMargins(0, 0, 0, 0)
        self._setup_tab_layout.setSpacing(8)

        self._setup_splitter = QSplitter(Qt.Horizontal)
        self._setup_splitter.setObjectName("room_optimizer_setup_splitter")
        self._setup_splitter.setChildrenCollapsible(False)
        self._setup_splitter.setStyleSheet("QSplitter::handle:horizontal { background:#1e1e38; }")
        self._setup_tab_layout.addWidget(self._setup_splitter, 1)

        controls_wrap = QScrollArea()
        controls_wrap.setWidgetResizable(True)
        controls_wrap.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        controls_wrap.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        controls_wrap.setFrameShape(QFrame.NoFrame)
        controls_wrap.setStyleSheet("QScrollArea { border:none; background:transparent; }")

        controls_box = QWidget()
        self._setup_controls_layout = QVBoxLayout(controls_box)
        self._setup_controls_layout.setSpacing(8)
        self._setup_controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_wrap.setWidget(controls_box)

        self._import_planner_btn = QPushButton()
        self._import_planner_btn.setToolTip("")
        self._style_import_planner_button(self._import_planner_btn, active=False)
        self._import_planner_btn.clicked.connect(self._import_from_planner)

        self._setup_stats_row = QWidget()
        self._setup_stats_row.setStyleSheet("background:transparent;")
        self._setup_stats_row_layout = QHBoxLayout(self._setup_stats_row)
        self._setup_stats_row_layout.setContentsMargins(0, 0, 0, 0)
        self._setup_stats_row_layout.setSpacing(10)

        self._min_stats_box = QWidget()
        self._min_stats_box.setStyleSheet("background:transparent;")
        self._min_stats_box_layout = QHBoxLayout(self._min_stats_box)
        self._min_stats_box_layout.setContentsMargins(0, 0, 0, 0)
        self._min_stats_box_layout.setSpacing(6)
        self._min_stats_label = QLabel()
        self._min_stats_label.setStyleSheet("color:#888; font-size:11px;")
        self._min_stats_box_layout.addWidget(self._min_stats_label)
        self._min_stats_input = QLineEdit()
        self._min_stats_input.setPlaceholderText("")
        self._min_stats_input.setFixedWidth(60)
        self._min_stats_input.setStyleSheet(
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
        )
        self._min_stats_input.textChanged.connect(lambda _: self._save_session_state())
        self._min_stats_box_layout.addWidget(self._min_stats_input)
        self._setup_stats_row_layout.addWidget(self._min_stats_box)

        self._max_risk_box = QWidget()
        self._max_risk_box.setStyleSheet("background:transparent;")
        self._max_risk_box_layout = QHBoxLayout(self._max_risk_box)
        self._max_risk_box_layout.setContentsMargins(0, 0, 0, 0)
        self._max_risk_box_layout.setSpacing(6)
        self._max_risk_label = QLabel()
        self._max_risk_label.setStyleSheet("color:#888; font-size:11px;")
        self._max_risk_box_layout.addWidget(self._max_risk_label)
        self._max_risk_input = QLineEdit()
        self._max_risk_input.setPlaceholderText("")
        self._max_risk_input.setFixedWidth(60)
        self._max_risk_input.setStyleSheet(
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
        )
        self._max_risk_input.textChanged.connect(lambda _: self._save_session_state())
        self._max_risk_box_layout.addWidget(self._max_risk_input)
        self._setup_stats_row_layout.addWidget(self._max_risk_box)

        self._shared_search_note = QLabel(_tr(
            "menu.settings.optimizer_search_settings.summary",
            default="Shared annealing settings live in Settings and apply to both planners.",
        ))
        self._shared_search_note.setStyleSheet("color:#8d8da8; font-size:11px;")
        self._shared_search_note.setWordWrap(True)
        self._setup_controls_layout.addWidget(self._shared_search_note)

        self._mode_toggle_btn = QPushButton()
        self._mode_toggle_btn.setCheckable(True)
        self._mode_toggle_btn.setChecked(False)
        self._mode_toggle_btn.setToolTip("")
        self._mode_toggle_btn.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:checked { background:#3a2f54; color:#ddd; border:1px solid #6a5a9a; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._mode_toggle_btn.toggled.connect(self._on_optimizer_mode_toggled)
        self._mode_toggle_btn.toggled.connect(lambda _: self._save_session_state())
        self._setup_controls_layout.addWidget(self._mode_toggle_btn)

        self._minimize_variance_checkbox = QPushButton()
        self._minimize_variance_checkbox.setCheckable(True)
        self._minimize_variance_checkbox.setChecked(_saved_optimizer_flag("minimize_variance", True))
        self._minimize_variance_checkbox.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:checked { background:#2a4a5a; color:#ddd; border:1px solid #4a6a7a; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._bind_persistent_toggle(self._minimize_variance_checkbox, "room_optimizer.toggle.minimize_variance", "minimize_variance")
        self._minimize_variance_checkbox.toggled.connect(lambda _: self._save_session_state())
        self._setup_controls_layout.addWidget(self._minimize_variance_checkbox)

        self._avoid_lovers_checkbox = QPushButton()
        self._avoid_lovers_checkbox.setCheckable(True)
        self._avoid_lovers_checkbox.setChecked(_saved_optimizer_flag("avoid_lovers", True))
        self._avoid_lovers_checkbox.setToolTip(_tr("room_optimizer.tooltip.avoid_lovers"))
        self._avoid_lovers_checkbox.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:checked { background:#5a3a2a; color:#ddd; border:1px solid #8a5a4a; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._bind_persistent_toggle(self._avoid_lovers_checkbox, "room_optimizer.toggle.avoid_lovers", "avoid_lovers")
        self._avoid_lovers_checkbox.toggled.connect(lambda _: self._save_session_state())
        self._setup_controls_layout.addWidget(self._avoid_lovers_checkbox)

        self._prefer_low_aggression_checkbox = QPushButton()
        self._prefer_low_aggression_checkbox.setCheckable(True)
        self._prefer_low_aggression_checkbox.setChecked(_saved_optimizer_flag("prefer_low_aggression", True))
        self._prefer_low_aggression_checkbox.setToolTip(_tr("room_optimizer.tooltip.prefer_low_aggression"))
        self._prefer_low_aggression_checkbox.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:checked { background:#4a2a2a; color:#ddd; border:1px solid #7a4a4a; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._bind_persistent_toggle(self._prefer_low_aggression_checkbox, "room_optimizer.toggle.prefer_low_aggression", "prefer_low_aggression")
        self._prefer_low_aggression_checkbox.toggled.connect(lambda _: self._save_session_state())
        self._setup_controls_layout.addWidget(self._prefer_low_aggression_checkbox)

        self._prefer_high_libido_checkbox = QPushButton()
        self._prefer_high_libido_checkbox.setCheckable(True)
        self._prefer_high_libido_checkbox.setChecked(_saved_optimizer_flag("prefer_high_libido", True))
        self._prefer_high_libido_checkbox.setToolTip(_tr("room_optimizer.tooltip.prefer_high_libido"))
        self._prefer_high_libido_checkbox.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:checked { background:#2a4a36; color:#ddd; border:1px solid #4a7a5a; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._bind_persistent_toggle(self._prefer_high_libido_checkbox, "room_optimizer.toggle.prefer_high_libido", "prefer_high_libido")
        self._prefer_high_libido_checkbox.toggled.connect(lambda _: self._save_session_state())
        self._setup_controls_layout.addWidget(self._prefer_high_libido_checkbox)

        self._maximize_throughput_checkbox = QPushButton()
        self._maximize_throughput_checkbox.setCheckable(True)
        self._maximize_throughput_checkbox.setChecked(_saved_optimizer_flag("maximize_throughput", False))
        self._maximize_throughput_checkbox.setToolTip(_tr("room_optimizer.tooltip.maximize_throughput"))
        self._maximize_throughput_checkbox.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:checked { background:#304a2a; color:#e6f6dd; border:1px solid #5b8750; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._bind_persistent_toggle(
            self._maximize_throughput_checkbox,
            "room_optimizer.toggle.maximize_throughput",
            "maximize_throughput",
        )
        self._maximize_throughput_checkbox.toggled.connect(lambda _: self._save_session_state())
        self._setup_controls_layout.addWidget(self._maximize_throughput_checkbox)
        self._setup_controls_layout.addStretch(1)

        self._setup_info_panel = QWidget()
        self._setup_info_panel.setStyleSheet("background:transparent;")
        self._setup_info_panel_layout = QVBoxLayout(self._setup_info_panel)
        self._setup_info_panel_layout.setContentsMargins(0, 0, 0, 0)
        self._setup_info_panel_layout.setSpacing(8)

        self._setup_info_title = QLabel()
        self._setup_info_title.setStyleSheet("color:#ddd; font-size:14px; font-weight:bold;")
        self._setup_info_title.setWordWrap(True)
        self._setup_info_panel_layout.addWidget(self._setup_info_title)

        self._setup_info_subtitle = QLabel("")
        self._setup_info_subtitle.setStyleSheet("color:#8d8da8; font-size:11px;")
        self._setup_info_subtitle.setWordWrap(True)
        self._setup_info_panel_layout.addWidget(self._setup_info_subtitle)

        self._setup_info_browser = QTextBrowser()
        self._setup_info_browser.setOpenExternalLinks(False)
        self._setup_info_browser.setFocusPolicy(Qt.NoFocus)
        self._setup_info_browser.setFrameShape(QFrame.NoFrame)
        self._setup_info_browser.setStyleSheet(
            "QTextBrowser { background:#0d0d1c; color:#ddd; border:1px solid #26264a; "
            "border-radius:6px; padding:10px; }"
            "QTextBrowser h2 { color:#f0f0ff; margin-top: 4px; margin-bottom: 8px; }"
            "QTextBrowser h3 { color:#c9d6ff; margin-top: 10px; margin-bottom: 4px; }"
            "QTextBrowser ul { margin-left: 18px; }"
            "QTextBrowser li { margin-bottom: 6px; }"
            "QTextBrowser p { margin-top: 4px; margin-bottom: 8px; }"
            "QTextBrowser .muted { color:#8d8da8; }"
        )
        self._setup_info_panel_layout.addWidget(self._setup_info_browser, 1)

        self._optimize_btn = QPushButton()
        self._optimize_btn.clicked.connect(lambda: self._calculate_optimal_distribution(use_sa=self._deep_optimize_btn.isChecked()))
        self._optimize_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._optimize_btn.setStyleSheet(
            "QPushButton { background:#1f5f4a; color:#f2f7f3; border:1px solid #3f8f72; "
            "border-radius:4px; padding:6px 14px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#26735a; }"
            "QPushButton:pressed { background:#184b3a; }"
        )

        self._deep_optimize_btn = QPushButton()
        self._deep_optimize_btn.setCheckable(True)
        self._deep_optimize_btn.setChecked(_saved_optimizer_flag("use_sa", False))
        self._deep_optimize_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._deep_optimize_btn.setStyleSheet(
            "QPushButton { background:#2a2a5a; color:#bbbbee; border:1px solid #4a4a8a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#3a3a6a; color:#ddd; }"
            "QPushButton:checked { background:#3a5a3a; color:#aaffaa; border:1px solid #4a8a4a; }"
            "QPushButton:disabled { background:#1a1a32; color:#555; border-color:#2a2a4a; }"
        )
        self._bind_persistent_toggle(self._deep_optimize_btn, "room_optimizer.toggle.use_sa", "use_sa")
        self._deep_optimize_btn.toggled.connect(lambda _: self._save_session_state())
        self._import_planner_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._top_actions_layout.addWidget(self._setup_stats_row)
        self._top_actions_layout.addWidget(self._optimize_btn)
        self._top_actions_layout.addWidget(self._deep_optimize_btn)
        self._top_actions_layout.addWidget(self._import_planner_btn)
        self._top_actions_layout.addStretch(1)
        self._setup_splitter.addWidget(controls_wrap)
        self._setup_splitter.addWidget(self._setup_info_panel)
        self._setup_splitter.setStretchFactor(0, 3)
        self._setup_splitter.setStretchFactor(1, 2)
        self._setup_splitter.setSizes([540, 360])

        room_actions_box = QWidget()
        room_actions = QHBoxLayout(room_actions_box)
        room_actions.setContentsMargins(0, 0, 0, 0)
        room_actions.setSpacing(8)

        self._must_breed_action_btn = QPushButton()
        RoomOptimizerView._style_room_action_button(
            self._must_breed_action_btn,
            "#3b355f",
            "#5d58a0",
            "#49417a",
        )
        self._must_breed_action_btn.clicked.connect(lambda: self._apply_room_action("must_breed"))
        room_actions.addWidget(self._must_breed_action_btn)

        self._breeding_block_action_btn = QPushButton()
        RoomOptimizerView._style_room_action_button(
            self._breeding_block_action_btn,
            "#5a2d22",
            "#8b4c3e",
            "#6c382a",
        )
        self._breeding_block_action_btn.clicked.connect(lambda: self._apply_room_action("breeding_block"))
        room_actions.addWidget(self._breeding_block_action_btn)

        self._pin_action_btn = QPushButton()
        RoomOptimizerView._style_room_action_button(
            self._pin_action_btn,
            "#2a3a2a",
            "#4a6a4a",
            "#3a4a3a",
        )
        self._pin_action_btn.setMinimumWidth(90)
        self._pin_action_btn.clicked.connect(lambda: self._apply_room_action("pin"))
        room_actions.addWidget(self._pin_action_btn)

        room_actions.addStretch()
        root.addWidget(room_actions_box)
        room_actions_box.hide()

        # Splitter to hold table and details pane
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.setObjectName("room_optimizer_splitter")
        self._splitter.setStyleSheet("QSplitter::handle:vertical { background:#1e1e38; }")
        
        # Results table
        self._table = QTableWidget(0, 7)
        self._table.setIconSize(QSize(60, 20))
        self._table.setHorizontalHeaderLabels([
            _tr("room_optimizer.table.room"),
            _tr("room_optimizer.table.type", default="Type"),
            _tr("room_optimizer.table.cats"),
            _tr("room_optimizer.table.expected_pairs"),
            _tr("room_optimizer.table.avg_stats"),
            _tr("room_optimizer.table.risk"),
            _tr("room_optimizer.table.details"),
        ])
        self._set_room_action_button_texts()
        if hasattr(self, "_details_pane") and self._details_pane is not None:
            self._details_pane.retranslate_ui()
        if hasattr(self, "_cat_locator") and self._cat_locator is not None:
            self._cat_locator.retranslate_ui()
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.verticalHeader().setMinimumSectionSize(24)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(False)

        hh = self._table.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.Interactive)
        hh.setSectionResizeMode(6, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 140)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(2, 290)
        self._table.setColumnWidth(3, 96)
        self._table.setColumnWidth(4, 88)
        self._table.setColumnWidth(5, 72)
        self._table.setStyleSheet(
            self._table.styleSheet()
            + "QTableWidget::item { padding:4px 8px; }"
            + "QHeaderView::section { padding:5px 8px; }"
        )
        self._table.itemSelectionChanged.connect(self._on_table_selection_changed)

        self._splitter.addWidget(self._table)

        # Bottom tabs: Configure Rooms, Setup, Breeding Pairs, Cat Locator
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #1e1e38; background:#0a0a18; }"
            "QTabBar::tab { background:#14142a; color:#888; padding:6px 14px; border:1px solid #1e1e38;"
            " border-bottom:none; margin-right:2px; font-size:11px; }"
            "QTabBar::tab:selected { background:#1a1a36; color:#ddd; font-weight:bold; }"
            "QTabBar::tab:hover { background:#1e1e3a; color:#bbb; }"
        )

        # Tab 0: Configure Rooms
        self._bottom_tabs.addTab(self._configure_rooms_tab, _tr("room_optimizer.tab.configure_rooms"))

        # Tab 1: Setup
        self._bottom_tabs.addTab(self._setup_tab, _tr("room_optimizer.tab.setup"))

        # Tab 2: Breeding Pairs (existing detail panel)
        self._details_pane = RoomOptimizerDetailPanel()
        self._details_pane._navigate_to_cat_callback = self._navigate_to_cat_from_breeding_pairs
        self._bottom_tabs.addTab(self._details_pane, _tr("room_optimizer.tab.breeding_pairs"))

        # Tab 3: Cat Locator
        self._cat_locator = RoomOptimizerCatLocator()
        self._bottom_tabs.addTab(self._cat_locator, _tr("room_optimizer.tab.cat_locator"))
        self._bottom_tabs.setCurrentIndex(2)
        self._bottom_tabs.currentChanged.connect(lambda _: self._save_session_state())

        self._splitter.addWidget(self._bottom_tabs)
        self._splitter.setSizes([180, 420])

        root.addWidget(self._splitter, 1)

        _enforce_min_font_in_widget_tree(self)
        self.retranslate_ui()
        self._restore_session_state()
        self._pending_initial_restore_run = bool(self._session_state.get("has_run", False))
        self._refresh_room_action_buttons()

    def _on_optimizer_mode_toggled(self, enabled: bool):
        self._set_mode_button_text(enabled)
        self._minimize_variance_checkbox.setChecked(False if enabled else _saved_optimizer_flag("minimize_variance", True))
        self._minimize_variance_checkbox.setEnabled(not enabled)
        self._minimize_variance_checkbox.setToolTip("" if not enabled else _tr("room_optimizer.tooltip.variance"))
        if hasattr(self, "_deep_optimize_btn"):
            self._deep_optimize_btn.setEnabled(True)
            self._deep_optimize_btn.setToolTip(
                _tr("room_optimizer.more_depth_tooltip", default="Use simulated annealing for a slower, deeper search.")
            )
        if hasattr(self, "_maximize_throughput_checkbox"):
            self._maximize_throughput_checkbox.setEnabled(not enabled)
        self._save_session_state()

    def _on_table_selection_changed(self):
        selected_ranges = self._table.selectedRanges()
        if not selected_ranges:
            self._selected_room_data = None
            self._details_pane.show_room(None)
            self._refresh_room_action_buttons()
            return

        row = selected_ranges[0].topRow()
        room_item = self._table.item(row, 0)
        if room_item:
            details_data = room_item.data(Qt.UserRole)
            self._selected_room_data = details_data if isinstance(details_data, dict) else None
            self._details_pane.show_room(self._selected_room_data)
            self._refresh_room_action_buttons()
        else:
            self._selected_room_data = None
            self._details_pane.show_room(None)
            self._refresh_room_action_buttons()

    def set_cats(self, cats: list[Cat], excluded_keys: set[int] = None):
        self._cats = cats
        self._cat_lookup = {cat.db_key: cat for cat in cats}
        # Combine explicit excluded_keys with blacklisted cats
        blacklisted_keys = {c.db_key for c in cats if c.is_blacklisted}
        self._excluded_keys = (excluded_keys or set()) | blacklisted_keys
        alive_count = len([c for c in cats if c.status != 'Gone'])
        excluded_count = len([c for c in cats if c.status != 'Gone' and c.db_key in self._excluded_keys])
        if excluded_count > 0:
            self._summary.setText(_tr("room_optimizer.summary.with_excluded",
                                       alive=alive_count, excluded=excluded_count))
        else:
            self._summary.setText(_tr("room_optimizer.summary.no_excluded",
                                       alive=alive_count))
        self._restore_session_state()
        self._on_planner_traits_changed()
        alive_count = len([c for c in self._cats if c.status != "Gone"])
        if self._pending_initial_restore_run and alive_count >= 2:
            self._pending_initial_restore_run = False
            self._calculate_optimal_distribution(use_sa=bool(self._session_state.get("use_sa", False)))
        elif self._auto_recalculate and self._session_state.get("has_run") and alive_count >= 2:
            self._calculate_optimal_distribution(use_sa=bool(self._session_state.get("use_sa", False)))

    def set_available_rooms(self, rooms: list[str]):
        ordered = [room for room in ROOM_DISPLAY.keys() if room in set(rooms)]
        self._available_rooms = ordered or list(ROOM_DISPLAY.keys())
        if hasattr(self, "_room_priority_panel") and self._room_priority_panel is not None:
            self._room_priority_panel.set_available_rooms(self._available_rooms)

    def get_available_rooms(self) -> list[str]:
        return list(self._available_rooms)

    def set_room_summaries(self, summaries: list[FurnitureRoomSummary] | dict[str, FurnitureRoomSummary]):
        if isinstance(summaries, dict):
            self._room_summaries = {
                room: summary
                for room, summary in summaries.items()
                if room and isinstance(summary, FurnitureRoomSummary)
            }
        else:
            self._room_summaries = {
                summary.room: summary
                for summary in summaries
                if isinstance(summary, FurnitureRoomSummary) and summary.room
            }
        self._room_priority_panel.set_room_summaries(self._room_summaries)

    @property
    def room_priority_panel(self):
        return self._room_priority_panel

    @property
    def cat_locator(self):
        return self._cat_locator

    @property
    def save_path(self) -> Optional[str]:
        return self._save_path

    def save_session_state(self, **kwargs):
        self._save_session_state(**kwargs)

    def on_planner_traits_changed(self):
        self._on_planner_traits_changed()

    def get_room_config(self) -> list[dict]:
        return self._room_priority_panel.get_config()

    def _navigate_to_cat_from_breeding_pairs(self, cat_name_formatted: str):
        """Navigate to a cat by its formatted name (e.g. 'Fluffy (Female)')."""
        # Extract the cat name part (before the gender)
        cat_name = cat_name_formatted.split(" (")[0] if " (" in cat_name_formatted else cat_name_formatted

        # Find the cat by name
        for cat in self._cats:
            if cat.name == cat_name:
                # Call the cat locator's callback if available
                if self._cat_locator._navigate_to_cat_callback:
                    self._cat_locator._navigate_to_cat_callback(cat.db_key)
                return

    def set_cache(self, cache: Optional['BreedingCache']):
        self._cache = cache

    def set_auto_recalculate(self, enabled: bool):
        self._auto_recalculate = bool(enabled)

    def set_save_path(self, save_path: Optional[str], *, refresh_existing: bool = True):
        self._save_path = save_path
        self._room_priority_panel.set_save_path(save_path)
        self._restore_session_state()
        self._pending_initial_restore_run = bool(self._session_state.get("has_run", False))
        if refresh_existing and self._cats:
            self.set_cats(self._cats, self._excluded_keys)
            return
        self._on_planner_traits_changed()

    def set_planner_view(self, planner: 'MutationDisorderPlannerView'):
        if self._planner_view is not None and hasattr(self._planner_view, "traitsChanged"):
            try:
                self._planner_view.traitsChanged.disconnect(self._on_planner_traits_changed)
            except (TypeError, RuntimeError):
                pass
        self._planner_view = planner
        if self._planner_view is not None and hasattr(self._planner_view, "traitsChanged"):
            try:
                self._planner_view.traitsChanged.connect(self._on_planner_traits_changed)
            except (TypeError, RuntimeError):
                pass
        self._on_planner_traits_changed()

    def _on_planner_traits_changed(self):
        self._planner_traits = self._planner_view.get_selected_traits() if self._planner_view is not None else []
        if not self._planner_traits:
            self._import_planner_btn.setText(_tr("room_optimizer.import_none", default="No Mutations Imported"))
            self._import_planner_btn.setToolTip(self._import_planner_button_tooltip())
            self._style_import_planner_button(self._import_planner_btn, active=False)
            return
        self._import_from_planner()

    def _import_planner_button_tooltip(self) -> str:
        return _planner_import_traits_tooltip(
            self._planner_traits,
            empty_text=_tr("room_optimizer.import_none_tooltip"),
        )

    def _session_state_payload(self, *, has_run: Optional[bool] = None, use_sa: Optional[bool] = None) -> dict:
        state = dict(self._session_state) if isinstance(self._session_state, dict) else {}
        state.update({
            "min_stats": self._min_stats_input.text().strip(),
            "max_risk": self._max_risk_input.text().strip(),
            "mode_family": bool(self._mode_toggle_btn.isChecked()),
            "minimize_variance": bool(self._minimize_variance_checkbox.isChecked()),
            "avoid_lovers": bool(self._avoid_lovers_checkbox.isChecked()),
            "prefer_low_aggression": bool(self._prefer_low_aggression_checkbox.isChecked()),
            "prefer_high_libido": bool(self._prefer_high_libido_checkbox.isChecked()),
            "maximize_throughput": bool(self._maximize_throughput_checkbox.isChecked()),
            "bottom_tab_index": int(self._bottom_tabs.currentIndex()) if hasattr(self, "_bottom_tabs") else 2,
        })
        if use_sa is not None:
            state["use_sa"] = bool(use_sa)
        else:
            state["use_sa"] = bool(state.get("use_sa", False))
        if has_run is not None:
            state["has_run"] = bool(has_run)
        else:
            state["has_run"] = bool(state.get("has_run", False))
        return state

    def _save_session_state(self, *, has_run: Optional[bool] = None, use_sa: Optional[bool] = None):
        if getattr(self, "_restoring_session_state", False):
            return
        self._session_state = self._session_state_payload(has_run=has_run, use_sa=use_sa)
        _save_planner_state_value("room_optimizer_state", self._session_state, self._save_path)

    def _restore_session_state(self):
        state = _load_planner_state_value("room_optimizer_state", {}, self._save_path)
        if not isinstance(state, dict):
            state = {}
        self._session_state = state
        self._restoring_session_state = True
        try:
            self._min_stats_input.setText(str(state.get("min_stats", "") or ""))
            self._max_risk_input.setText(str(state.get("max_risk", "") or ""))
            mode_family = bool(state.get("mode_family", False))
            self._mode_toggle_btn.setChecked(mode_family)
            if not mode_family:
                self._minimize_variance_checkbox.setChecked(bool(state.get("minimize_variance", self._minimize_variance_checkbox.isChecked())))
            else:
                self._minimize_variance_checkbox.setChecked(False)
            self._avoid_lovers_checkbox.setChecked(bool(state.get("avoid_lovers", self._avoid_lovers_checkbox.isChecked())))
            self._prefer_low_aggression_checkbox.setChecked(bool(state.get("prefer_low_aggression", self._prefer_low_aggression_checkbox.isChecked())))
            self._prefer_high_libido_checkbox.setChecked(bool(state.get("prefer_high_libido", self._prefer_high_libido_checkbox.isChecked())))
            self._maximize_throughput_checkbox.setChecked(bool(state.get("maximize_throughput", self._maximize_throughput_checkbox.isChecked())))
            self._deep_optimize_btn.setChecked(bool(state.get("use_sa", False)))
            if hasattr(self, "_bottom_tabs"):
                tab_index = state.get("bottom_tab_index", self._bottom_tabs.currentIndex())
                try:
                    self._bottom_tabs.setCurrentIndex(max(0, min(self._bottom_tabs.count() - 1, int(tab_index))))
                except (TypeError, ValueError):
                    self._bottom_tabs.setCurrentIndex(2)
        finally:
            self._restoring_session_state = False
        if self._save_path is not None:
            # Make the restored state durable immediately once we're bound to a save.
            self._save_session_state()
            _save_room_priority_config(self._room_priority_panel.get_config(), self._save_path)
        if self._planner_view is not None:
            self._planner_traits = self._planner_view.get_selected_traits()
        return bool(state.get("has_run", False))

    def reset_to_defaults(self):
        """Restore the room optimizer controls to their built-in defaults."""
        self._session_state = {}
        self._restoring_session_state = True
        try:
            self._min_stats_input.setText("")
            self._max_risk_input.setText("")
            self._mode_toggle_btn.setChecked(False)
            self._minimize_variance_checkbox.setChecked(True)
            self._avoid_lovers_checkbox.setChecked(True)
            self._prefer_low_aggression_checkbox.setChecked(True)
            self._prefer_high_libido_checkbox.setChecked(True)
            self._maximize_throughput_checkbox.setChecked(False)
            self._deep_optimize_btn.setChecked(False)
            if hasattr(self, "_bottom_tabs"):
                self._bottom_tabs.setCurrentIndex(2)
            self._room_priority_panel.reset_to_defaults()
        finally:
            self._restoring_session_state = False
        self._pending_initial_restore_run = False
        self.retranslate_ui()
        self._save_session_state(has_run=False, use_sa=False)

    def _import_from_planner(self):
        if self._planner_view is None:
            return
        self._planner_traits = self._planner_view.get_selected_traits()
        if not self._planner_traits:
            self._import_planner_btn.setText(_tr("room_optimizer.import_none", default="No Mutations Imported"))
            self._import_planner_btn.setToolTip(self._import_planner_button_tooltip())
            self._style_import_planner_button(self._import_planner_btn, active=False)
            return
        summary = _planner_import_traits_summary(self._planner_traits)
        self._import_planner_btn.setText(_tr("room_optimizer.imported", summary=summary))
        self._import_planner_btn.setToolTip(self._import_planner_button_tooltip())
        self._style_import_planner_button(self._import_planner_btn, active=True)

    def _build_setup_info_html(self) -> str:
        def row(title: str, body: str) -> str:
            return (
                "<tr>"
                f"<td>{html.escape(title)}</td>"
                f"<td>{html.escape(body)}</td>"
                "</tr>"
            )

        title = html.escape(_tr("room_optimizer.setup_info.title", default="Optimizer Setup Guide"))
        subtitle = html.escape(
            _tr(
                "room_optimizer.setup_info.subtitle",
                default="The controls on the left shape how room layouts are scored before you calculate.",
            )
        )
        entries = [
            row(
                _tr("room_optimizer.min_stats"),
                "Filter out cats below this base-stat total.",
            ),
            row(
                _tr("room_optimizer.max_risk"),
                "Set the highest inbreeding risk the optimizer will allow.",
            ),
            row(
                _tr("room_optimizer.import_planner", default="Import Mutation Planner"),
                "Load traits from the breeding planner before you optimize.",
            ),
            row(
                _tr("room_optimizer.optimize_btn"),
                "Run the optimizer once using the current room and scoring settings.",
            ),
            row(
                _tr("room_optimizer.more_depth_calculation", default="More Depth Calculation"),
                "Run a slower simulated-annealing search for a deeper pass. Available in both Pair Quality and Family Separation modes.",
            ),
            row(
                _tr("menu.settings.optimizer_search_settings", default="Optimizer Search Settings"),
                "Open Settings to adjust the shared temperature and neighbor sampling values used by both planners.",
            ),
            row(
                "Optimizer Mode",
                "Switch between Pair Quality and Family Separation scoring.",
            ),
            row(
                _tr("room_optimizer.toggle.minimize_variance"),
                "Favor more even room pair counts. Only meaningful in Pair Quality mode.",
            ),
            row(
                _tr("room_optimizer.toggle.avoid_lovers"),
                "Keep mutual lovers in the same room.",
            ),
            row(
                _tr("room_optimizer.toggle.prefer_low_aggression"),
                "Prefer cats with lower aggression scores.",
            ),
            row(
                _tr("room_optimizer.toggle.prefer_high_libido"),
                "Prefer cats with higher libido scores.",
            ),
            row(
                _tr("room_optimizer.toggle.maximize_throughput"),
                "Favor layouts with the most simultaneous valid pairs.",
            ),
        ]
        return (
            "<style>"
            "table { border-collapse: collapse; width: 100%; }"
            "th, td { border: 1px solid #3a3a5f; padding: 4px 8px; vertical-align: top; }"
            "th { background: #1a1a38; color: #c9d6ff; text-align: left; }"
            "td { color: #ddd; }"
            "td:first-child { width: 34%; font-weight: bold; color: #f0f0ff; white-space: nowrap; }"
            "td:last-child { width: 66%; }"
            "</style>"
            f"<h2>{title}</h2>"
            f"<p class='muted'>{subtitle}</p>"
            "<table>"
            "<thead><tr><th>Optimizer options</th><th>Description</th></tr></thead>"
            "<tbody>"
            f"{''.join(entries)}"
            "</tbody></table>"
        )

    def retranslate_ui(self):
        self._title.setText(_tr("room_optimizer.title"))
        self._summary.setText(_tr("room_optimizer.summary_empty"))
        self._min_stats_label.setText(_tr("room_optimizer.min_stats"))
        self._min_stats_input.setPlaceholderText(_tr("room_optimizer.placeholder.min_stats"))
        self._max_risk_label.setText(_tr("room_optimizer.max_risk"))
        self._max_risk_input.setPlaceholderText(_tr("room_optimizer.placeholder.max_risk"))
        self._min_stats_label.setToolTip(_tr("room_optimizer.min_stats_tooltip", default="Minimum base-stat total a cat must meet to be considered."))
        self._min_stats_input.setToolTip(_tr("room_optimizer.min_stats_tooltip", default="Minimum base-stat total a cat must meet to be considered."))
        self._max_risk_label.setToolTip(_tr("room_optimizer.max_risk_tooltip", default="Highest inbreeding risk percentage the optimizer will accept."))
        self._max_risk_input.setToolTip(_tr("room_optimizer.max_risk_tooltip", default="Highest inbreeding risk percentage the optimizer will accept."))
        self._optimize_btn.setToolTip(
            _tr(
                "room_optimizer.optimize_btn_tooltip",
                default="Run the optimizer once using the current room and scoring settings.",
            )
        )
        self._optimize_btn.setText(_tr("room_optimizer.optimize_btn"))
        self._set_mode_button_text(self._mode_toggle_btn.isChecked())
        RoomOptimizerView._set_toggle_button_label(self._deep_optimize_btn, "room_optimizer.toggle.use_sa")
        self._deep_optimize_btn.setEnabled(True)
        self._deep_optimize_btn.setToolTip(
            _tr("room_optimizer.more_depth_tooltip", default="Use simulated annealing for a slower, deeper search.")
        )
        self._minimize_variance_checkbox.setEnabled(not self._mode_toggle_btn.isChecked())
        self._minimize_variance_checkbox.setToolTip(
            "" if not self._mode_toggle_btn.isChecked() else _tr("room_optimizer.tooltip.variance")
        )
        self._maximize_throughput_checkbox.setEnabled(not self._mode_toggle_btn.isChecked())
        if self._planner_traits and self._planner_view is not None:
            self._import_from_planner()
        else:
            self._import_planner_btn.setText(_tr("room_optimizer.import_none", default="No Mutations Imported"))
            self._import_planner_btn.setToolTip(self._import_planner_button_tooltip())
            self._style_import_planner_button(self._import_planner_btn, active=False)
        # Refresh toggle button labels
        RoomOptimizerView._set_toggle_button_label(self._minimize_variance_checkbox, "room_optimizer.toggle.minimize_variance")
        RoomOptimizerView._set_toggle_button_label(self._avoid_lovers_checkbox, "room_optimizer.toggle.avoid_lovers")
        RoomOptimizerView._set_toggle_button_label(self._prefer_low_aggression_checkbox, "room_optimizer.toggle.prefer_low_aggression")
        RoomOptimizerView._set_toggle_button_label(self._prefer_high_libido_checkbox, "room_optimizer.toggle.prefer_high_libido")
        RoomOptimizerView._set_toggle_button_label(self._maximize_throughput_checkbox, "room_optimizer.toggle.maximize_throughput")
        self._maximize_throughput_checkbox.setToolTip(_tr("room_optimizer.tooltip.maximize_throughput"))
        if hasattr(self, "_shared_search_note"):
            self._shared_search_note.setText(_tr(
                "menu.settings.optimizer_search_settings.summary",
                default="Shared annealing settings live in Settings and apply to both planners.",
            ))
        self._import_planner_btn.setToolTip(self._import_planner_button_tooltip())
        self._setup_info_title.setText(_tr("room_optimizer.setup_info.title", default="Optimizer Setup Guide"))
        self._setup_info_subtitle.setText(
            _tr(
                "room_optimizer.setup_info.subtitle",
                default="The controls on the left shape how room layouts are scored before you calculate.",
            )
        )
        self._setup_info_browser.setHtml(self._build_setup_info_html())
        # Refresh tab titles
        self._bottom_tabs.setTabText(0, _tr("room_optimizer.tab.configure_rooms"))
        self._bottom_tabs.setTabText(1, _tr("room_optimizer.tab.setup"))
        self._bottom_tabs.setTabText(2, _tr("room_optimizer.tab.breeding_pairs"))
        self._bottom_tabs.setTabText(3, _tr("room_optimizer.tab.cat_locator"))
        self._table.setHorizontalHeaderLabels([
            _tr("room_optimizer.table.room"),
            _tr("room_optimizer.table.type", default="Type"),
            _tr("room_optimizer.table.cats"),
            _tr("room_optimizer.table.expected_pairs"),
            _tr("room_optimizer.table.avg_stats"),
            _tr("room_optimizer.table.risk"),
            _tr("room_optimizer.table.details"),
        ])

    def _calculate_optimal_distribution(self, use_sa: bool = False):
        """Kick off background optimizer worker."""
        if self._optimizer_worker is not None and self._optimizer_worker.isRunning():
            return  # already running

        min_stats = 0
        try:
            if self._min_stats_input.text().strip():
                min_stats = int(self._min_stats_input.text().strip())
        except ValueError:
            pass

        max_risk = 10.0
        try:
            if self._max_risk_input.text().strip():
                max_risk = float(self._max_risk_input.text().strip())
        except ValueError:
            pass

        sa_temperature = _saved_optimizer_search_temperature()
        sa_neighbors = _saved_optimizer_search_neighbors()
        maximize_throughput = bool(self._maximize_throughput_checkbox.isChecked()) if hasattr(self, "_maximize_throughput_checkbox") else False
        mode_family = self._mode_toggle_btn.isChecked()

        params = {
            "min_stats": min_stats,
            "max_risk": max_risk,
            "minimize_variance": self._minimize_variance_checkbox.isChecked(),
            "avoid_lovers": self._avoid_lovers_checkbox.isChecked(),
            "prefer_low_aggression": self._prefer_low_aggression_checkbox.isChecked(),
            "prefer_high_libido": self._prefer_high_libido_checkbox.isChecked(),
            "maximize_throughput": maximize_throughput and not mode_family,
            "sa_temperature": sa_temperature,
            "sa_neighbors": sa_neighbors,
            "mode_family": mode_family,
            "use_sa": use_sa,
            "planner_traits": list(self._planner_traits),
            "available_rooms": list(getattr(self, "_available_rooms", [])),
            "room_config": self._room_priority_panel.get_config(),
            "room_stats": dict(self._room_summaries),
        }
        self._save_session_state(has_run=True, use_sa=use_sa)

        self._optimize_btn.setEnabled(False)
        self._summary.setText(_tr("room_optimizer.status.calculating"))

        worker = RoomOptimizerWorker(
            self._cats,
            getattr(self, "_excluded_keys", set()),
            self._cache,
            params,
            parent=self,
        )
        worker.finished.connect(self._on_optimizer_result)
        self._optimizer_worker = worker
        worker.start()

    def _on_optimizer_result(self, result: dict):
        self._optimizer_worker = None
        self._optimize_btn.setEnabled(True)

        if "error" in result:
            self._table.setRowCount(0)
            self._selected_room_data = None
            self._refresh_room_action_buttons()
            self._summary.setText(_tr("room_optimizer.status.error", message=result["error"]))
            return

        room_rows = result["room_rows"]
        locator_data = result["locator_data"]
        excluded_rows = result["excluded_rows"]
        mode_family = result["mode_family"]
        min_stats = result["min_stats"]
        max_risk = result["max_risk"]
        minimize_variance = result["minimize_variance"]
        avoid_lovers = result["avoid_lovers"]
        prefer_low_aggression = result["prefer_low_aggression"]
        prefer_high_libido = result["prefer_high_libido"]
        maximize_throughput = result.get("maximize_throughput", False)
        sa_temperature = float(result.get("sa_temperature", 0.0) or 0.0)
        sa_neighbors = int(result.get("sa_neighbors", 0) or 0)
        use_sa = result.get("use_sa", False)

        self._cat_locator.show_assignments(locator_data)

        # Prevent Qt from reshuffling rows while we are still inserting items.
        # If sorting stays on here, the room labels and cat lists can get split
        # across different rows as the table keeps resorting itself.
        sorting_was_enabled = self._table.isSortingEnabled()
        header = self._table.horizontalHeader()
        sort_column = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        self._table.setSortingEnabled(False)

        self._table.setRowCount(0)
        self._selected_room_data = None
        self._details_pane.show_room(None)
        self._refresh_room_action_buttons()

        row_idx = 0
        total_pairs = 0
        total_assigned = 0

        for room_data in room_rows:
            room_label = room_data["room_label"]
            room_key = room_data.get("room")
            is_fallback = bool(room_data.get("is_fallback"))
            cat_names = room_data["cat_names"]
            cat_keys = room_data.get("cat_keys", [])
            room_pairs = room_data["pairs"]
            avg_stats = room_data["avg_stats"]
            avg_risk = room_data["avg_risk"]
            room_capacity = room_data.get("capacity")
            room_stim = room_data.get("base_stim")

            best_pairs_count = room_data.get("best_pairs_count", len(room_pairs))
            total_assigned += len(cat_names)
            total_pairs += best_pairs_count

            self._table.insertRow(row_idx)
            room_color = _room_color(room_key)
            room_bg = _room_tint(room_key, strength=0.16, lift=14)

            room_item = QTableWidgetItem(room_label)
            room_item.setTextAlignment(Qt.AlignCenter)
            room_item.setForeground(QBrush(room_color))
            room_item.setBackground(QBrush(room_bg))
            room_item.setToolTip(
                f"Capacity: {'∞' if room_capacity in (None, 0) else int(room_capacity)}\n"
                f"Base stimulation: {float(room_stim or 0.0):.0f}"
            )

            type_item = QTableWidgetItem(
                _tr("room_optimizer.table.fallback", default="Fallback")
                if is_fallback
                else _tr("room_optimizer.table.breeding", default="Breeding")
            )
            type_item.setTextAlignment(Qt.AlignCenter)
            type_item.setForeground(QBrush(QColor(208, 208, 224) if is_fallback else QColor(147, 224, 160)))
            type_item.setBackground(QBrush(room_bg))

            cats_item = QTableWidgetItem(", ".join(cat_names) or "—")
            cats_item.setBackground(QBrush(room_bg))

            pairs_item = QTableWidgetItem(str(best_pairs_count))
            pairs_item.setTextAlignment(Qt.AlignCenter)
            pairs_item.setBackground(QBrush(room_bg))

            stats_item = QTableWidgetItem(f"{avg_stats:.1f}")
            stats_item.setTextAlignment(Qt.AlignCenter)
            stats_item.setBackground(QBrush(room_bg))
            if avg_stats >= 200:
                stats_item.setForeground(QBrush(QColor(98, 194, 135)))
            elif avg_stats >= 150:
                stats_item.setForeground(QBrush(QColor(143, 201, 230)))
            else:
                stats_item.setForeground(QBrush(QColor(190, 145, 40)))

            risk_item = QTableWidgetItem(f"{avg_risk:.0f}%")
            risk_item.setTextAlignment(Qt.AlignCenter)
            risk_item.setBackground(QBrush(room_bg))
            if avg_risk >= 50:
                risk_item.setForeground(QBrush(QColor(217, 119, 119)))
            elif avg_risk >= 20:
                risk_item.setForeground(QBrush(QColor(216, 181, 106)))
            else:
                risk_item.setForeground(QBrush(QColor(98, 194, 135)))

            details_lines = []
            for p in room_pairs[:3]:
                details_lines.append(
                    f"{p['cat_a']} × {p['cat_b']} "
                    f"(stats: {p['avg_stats']:.0f}, risk: {p['risk']:.0f}%)"
                )
            if len(room_pairs) > 3:
                details_lines.append(f"... and {len(room_pairs) - 3} more")
            details_item = QTableWidgetItem("; ".join(details_lines) or "—")
            details_item.setBackground(QBrush(room_bg))

            room_item.setData(Qt.UserRole, {
                "room": room_label,
                "cats": cat_names,
                "cat_keys": cat_keys,
                "total_pairs": best_pairs_count,
                "avg_stats": avg_stats,
                "avg_risk": avg_risk,
                "excluded_cats": [],
                "pairs": room_pairs,
            })

            self._table.setItem(row_idx, 0, room_item)
            self._table.setItem(row_idx, 1, type_item)
            self._table.setItem(row_idx, 2, cats_item)
            self._table.setItem(row_idx, 3, pairs_item)
            self._table.setItem(row_idx, 4, stats_item)
            self._table.setItem(row_idx, 5, risk_item)
            self._table.setItem(row_idx, 6, details_item)
            row_idx += 1

        if excluded_rows:
            excluded_names = [r["name"] for r in excluded_rows]
            excluded_keys = [r.get("db_key") for r in excluded_rows if r.get("db_key") is not None]
            self._table.insertRow(row_idx)
            excluded_room_item = QTableWidgetItem("Excluded")
            excluded_room_item.setTextAlignment(Qt.AlignCenter)
            excluded_room_item.setForeground(QBrush(QColor(170, 120, 120)))
            excluded_room_item.setData(Qt.UserRole, {
                "room": "Excluded",
                "cats": excluded_names,
                "cat_keys": excluded_keys,
                "total_pairs": 0,
                "avg_stats": 0.0,
                "avg_risk": 0.0,
                "excluded_cats": excluded_names,
                "excluded_cat_rows": excluded_rows,
                "pairs": [],
            })
            self._table.setItem(row_idx, 0, excluded_room_item)
            excluded_type_item = QTableWidgetItem("—")
            excluded_type_item.setTextAlignment(Qt.AlignCenter)
            excluded_type_item.setForeground(QBrush(QColor(120, 120, 130)))
            self._table.setItem(row_idx, 1, excluded_type_item)
            self._table.setItem(row_idx, 2, QTableWidgetItem(f"{len(excluded_rows)} excluded cats"))
            for col in (3, 4, 5):
                dash = QTableWidgetItem("—")
                dash.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(row_idx, col, dash)
            self._table.setItem(row_idx, 6, QTableWidgetItem("Excluded from optimizer breeding calculations"))
            row_idx += 1

        filter_info = [f"mode: {'family separation' if mode_family else 'pair quality'}"]
        filter_info.append(f"depth: {'SA' if use_sa else 'greedy'}")
        if min_stats > 0:
            filter_info.append(f"min stats: {min_stats}")
        if max_risk < 100:
            filter_info.append(f"max risk: {max_risk}%")
        if (not mode_family) and minimize_variance:
            filter_info.append("variance: on")
        if prefer_low_aggression:
            filter_info.append("prefer low aggression")
        if prefer_high_libido:
            filter_info.append("prefer high libido")
        if maximize_throughput and not mode_family:
            filter_info.append("maximize throughput")
        if use_sa:
            filter_info.append(f"temp: {sa_temperature:g}")
            filter_info.append(f"neighbors: {sa_neighbors}")
        if avoid_lovers:
            filter_info.append("keep lovers together")
        filter_str = f"  |  Filters: {', '.join(filter_info)}" if filter_info else ""

        self._summary.setText(
            f"Optimized {total_assigned} cats into {len(room_rows)} rooms  |  "
            f"{total_pairs} total breeding pairs{filter_str}"
        )

        if sorting_was_enabled:
            self._table.setSortingEnabled(True)
            if sort_column is not None and sort_column >= 0:
                self._table.sortByColumn(sort_column, sort_order)
        else:
            self._table.setSortingEnabled(False)


class RoomOptimizerCatLocator(QWidget):
    """Shows all cats with their current location vs assigned room, sorted by room priority."""

    COL_CAT = 0
    COL_AGE = 1
    COL_CURRENT = 2
    COL_MOVE_TO = 3
    COL_ACTION = 4

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:#0a0a18;")
        self._navigate_to_cat_callback = None
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        self._summary = QLabel(_tr("room_optimizer.locator.summary.empty"))
        self._summary.setStyleSheet("color:#888; font-size:11px;")
        root.addWidget(self._summary)

        self._table = QTableWidget(0, 5)
        self._table.setIconSize(QSize(60, 20))
        self._table.setHorizontalHeaderLabels([
            _tr("room_optimizer.locator.table.cat"),
            _tr("room_optimizer.locator.table.age"),
            _tr("room_optimizer.locator.table.currently_in"),
            _tr("room_optimizer.locator.table.move_to"),
            _tr("room_optimizer.locator.table.action"),
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setMouseTracking(True)
        self._table.cellClicked.connect(self._on_cat_clicked)
        self._table.cellEntered.connect(lambda r, c: self._table.setCursor(
            Qt.PointingHandCursor if c == self.COL_CAT else Qt.ArrowCursor
        ))
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(self.COL_CAT, QHeaderView.Interactive)
        hh.setSectionResizeMode(self.COL_AGE, QHeaderView.Interactive)
        hh.setSectionResizeMode(self.COL_CURRENT, QHeaderView.Interactive)
        hh.setSectionResizeMode(self.COL_MOVE_TO, QHeaderView.Interactive)
        hh.setSectionResizeMode(self.COL_ACTION, QHeaderView.Interactive)
        self._table.setColumnWidth(self.COL_CAT, 220)
        self._table.setColumnWidth(self.COL_AGE, 45)
        self._table.setColumnWidth(self.COL_CURRENT, 140)
        self._table.setColumnWidth(self.COL_MOVE_TO, 140)
        self._table.setColumnWidth(self.COL_ACTION, 65)
        self._table.setStyleSheet("""
            QTableWidget {
                background:#0d0d1c; alternate-background-color:#131326;
                color:#ddd; border:1px solid #26264a; font-size:12px;
            }
            QTableWidget::item { padding:3px 6px; }
            QHeaderView::section {
                background:#16213e; color:#888; padding:5px 4px;
                border:none; border-bottom:1px solid #1e1e38;
                border-right:1px solid #16213e; font-size:11px; font-weight:bold;
            }
        """)
        root.addWidget(self._table, 1)

    def set_navigate_to_cat_callback(self, callback):
        self._navigate_to_cat_callback = callback

    @staticmethod
    def _pair_color(room_order: float | int) -> QColor:
        try:
            rank = max(1, int(float(room_order or 0)) + 1)
        except (TypeError, ValueError):
            rank = 1
        return PAIR_COLORS[(rank - 1) % len(PAIR_COLORS)]

    @staticmethod
    def _pair_tint(color: QColor, strength: float = 0.28, lift: int = 18) -> QColor:
        return QColor(
            min(255, int(color.red() * strength) + lift),
            min(255, int(color.green() * strength) + lift),
            min(255, int(color.blue() * strength) + lift),
        )

    def show_assignments(self, all_assignments: list[dict]):
        """
        all_assignments: list of dicts with keys:
            name, gender_display, age, current_room, assigned_room, room_order, needs_move
        Sorted by room_order (Priority 1 first, Fallback last).
        """
        # Sort by assigned room priority, then by name within each room
        all_assignments.sort(key=lambda d: (d.get("room_order", 999), (d["name"] or "").lower()))

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(all_assignments))

        moves_needed = 0
        for row, info in enumerate(all_assignments):
            heart = " ♥" if info.get("has_lover") else ""
            name_item = QTableWidgetItem(f"{info['name']}{heart} ({info['gender_display']})")
            name_item.setData(Qt.UserRole, info.get("db_key"))
            icon = _make_tag_icon(info.get("tags", []))
            if not icon.isNull():
                name_item.setIcon(icon)
            name_item.setForeground(QColor("#5b9bd5"))
            name_item.setToolTip(_tr("room_optimizer.locator.tooltip.jump_to_cat"))

            age_val = info.get("age")
            if isinstance(age_val, (int, float)):
                age_item = _SortByUserRoleItem(f"{age_val:.2f}" if isinstance(age_val, float) else str(age_val))
                age_item.setData(Qt.UserRole, float(age_val))
            else:
                age_item = _SortByUserRoleItem(str(age_val) if age_val is not None else "?")
                age_item.setData(Qt.UserRole, 0.0)
            age_item.setTextAlignment(Qt.AlignCenter)

            current_item = QTableWidgetItem(info["current_room"])

            assigned_item = _SortByUserRoleItem(info["assigned_room"])
            # Store room_order so sorting this column keeps room priority order
            assigned_item.setData(Qt.UserRole, info.get("room_order", 999))

            row_room_key = info.get("current_room_key") or _room_key_from_display(info.get("current_room"))
            row_bg = _room_tint(row_room_key, strength=0.18, lift=14)
            if row_room_key is None:
                row_bg = self._pair_tint(self._pair_color(info.get("room_order", row)), strength=0.18, lift=14)
            for it in (name_item, age_item, current_item):
                it.setBackground(QBrush(row_bg))

            move_room_key = info.get("assigned_room_key") or _room_key_from_display(info.get("assigned_room"))
            if move_room_key is not None:
                move_color = _room_color(move_room_key)
                move_bg = _room_tint(move_room_key, strength=0.24, lift=18)
                assigned_item.setBackground(QBrush(move_bg))
                assigned_item.setForeground(QBrush(move_color))
            else:
                move_color = self._pair_color(info.get("room_order", row))
                move_bg = self._pair_tint(move_color, strength=0.36, lift=22)
                assigned_item.setBackground(QBrush(move_bg))
                assigned_item.setForeground(QBrush(move_color))

            needs_move = info.get("needs_move", False)
            if needs_move:
                moves_needed += 1
                action_item = QTableWidgetItem(_tr("room_optimizer.locator.action.move"))
                action_item.setTextAlignment(Qt.AlignCenter)
                action_item.setForeground(QBrush(QColor(216, 181, 106)))
                action_item.setBackground(QBrush(row_bg))
            else:
                action_item = QTableWidgetItem(_tr("room_optimizer.locator.action.ok"))
                action_item.setTextAlignment(Qt.AlignCenter)
                action_item.setForeground(QBrush(QColor(98, 194, 135)))
                action_item.setBackground(QBrush(row_bg))

            self._table.setItem(row, self.COL_CAT, name_item)
            self._table.setItem(row, self.COL_AGE, age_item)
            self._table.setItem(row, self.COL_CURRENT, current_item)
            self._table.setItem(row, self.COL_MOVE_TO, assigned_item)
            self._table.setItem(row, self.COL_ACTION, action_item)

        self._table.setSortingEnabled(True)
        # Default sort: by Move To column (room priority order)
        self._table.sortByColumn(self.COL_MOVE_TO, Qt.AscendingOrder)

        total = len(all_assignments)
        stay = total - moves_needed
        self._summary.setText(
            _tr("room_optimizer.locator.summary.with_counts", total=total, moves=moves_needed, stay=stay)
        )

    def retranslate_ui(self):
        self._table.setHorizontalHeaderLabels([
            _tr("room_optimizer.locator.table.cat"),
            _tr("room_optimizer.locator.table.age"),
            _tr("room_optimizer.locator.table.currently_in"),
            _tr("room_optimizer.locator.table.move_to"),
            _tr("room_optimizer.locator.table.action"),
        ])
        if self._table.rowCount() == 0:
            self._summary.setText(_tr("room_optimizer.locator.summary.empty"))

    def _on_cat_clicked(self, row: int, col: int):
        if col != self.COL_CAT:
            return
        item = self._table.item(row, col)
        if item is None:
            return
        db_key = item.data(Qt.UserRole)
        if db_key is not None and self._navigate_to_cat_callback is not None:
            self._navigate_to_cat_callback(db_key)

    def clear(self):
        self._table.setRowCount(0)
        self._summary.setText(_tr("room_optimizer.locator.summary.empty"))


class RoomOptimizerDetailPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:#0a0a18; border-top:1px solid #1e1e38;")
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(8)

        # Header with summary label and best pairs toggle
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        self._summary = QLabel(_tr("room_optimizer.detail.summary.select_room"))
        self._summary.setStyleSheet("color:#aaa; font-size:12px;")
        self._summary.setWordWrap(True)
        hdr.addWidget(self._summary, 1)

        self._best_pairs_btn = QPushButton(_tr("room_optimizer.detail.toggle.all_pairs"))
        self._best_pairs_btn.setCheckable(True)
        self._best_pairs_btn.setChecked(False)
        self._best_pairs_btn.setMinimumWidth(90)
        self._best_pairs_btn.setStyleSheet(
            "QPushButton { background:#1e1e38; color:#ccc; border:1px solid #2a2a4a; padding:4px;"
            "             font-size:11px; border-radius:3px; }"
            "QPushButton:hover { background:#252555; }"
            "QPushButton:checked { background:#3a5a7a; color:#fff; }"
        )
        self._best_pairs_btn.setToolTip(_tr("room_optimizer.detail.toggle.tooltip"))
        self._best_pairs_btn.clicked.connect(self._on_toggle_best_pairs)
        hdr.addWidget(self._best_pairs_btn)

        root.addLayout(hdr)

        self._current_data: Optional[dict] = None
        self._navigate_to_cat_callback = None  # Callback to navigate to a cat by name

        self._pairs_table = QTableWidget(0, 15)
        self._pairs_table.setHorizontalHeaderLabels([
            _tr("room_optimizer.detail.table.cat_a"),
            _tr("room_optimizer.detail.table.cat_b"),
            "\u2665",
            "STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK",
            _tr("room_optimizer.detail.table.sum"),
            _tr("room_optimizer.detail.table.avg"),
            _tr("room_optimizer.detail.table.risk"),
            _tr("room_optimizer.detail.table.rank"),
            _tr("room_optimizer.detail.table.mutations", default="Mutations"),
        ])
        self._pairs_table.verticalHeader().setVisible(False)
        self._pairs_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._pairs_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._pairs_table.setFocusPolicy(Qt.NoFocus)
        self._pairs_table.setWordWrap(False)
        self._pairs_table.setAlternatingRowColors(True)
        hh = self._pairs_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        for col in range(2, 14):
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
        hh.setSectionResizeMode(14, QHeaderView.Stretch)
        self._pairs_table.setColumnWidth(0, 120)
        self._pairs_table.setColumnWidth(1, 120)
        self._pairs_table.setColumnWidth(2, 24)
        for col in range(3, 10):
            self._pairs_table.setColumnWidth(col, 40)
        self._pairs_table.setColumnWidth(10, 60)
        self._pairs_table.setColumnWidth(11, 50)
        self._pairs_table.setColumnWidth(12, 75)
        self._pairs_table.setColumnWidth(13, 50)
        self._pairs_table.setStyleSheet("""
            QTableWidget {
                background:#0d0d1c; alternate-background-color:#131326;
                color:#ddd; border:1px solid #26264a; font-size:12px;
            }
            QTableWidget::item { padding:3px 4px; }
            QHeaderView::section {
                background:#16213e; color:#888; padding:5px 4px;
                border:none; border-bottom:1px solid #1e1e38;
                border-right:1px solid #16213e; font-size:11px; font-weight:bold;
            }
        """)
        self._pairs_table.itemClicked.connect(self._on_pair_cell_clicked)
        root.addWidget(self._pairs_table, 1)

        self._excluded_table = QTableWidget(0, 12)
        self._excluded_table.setHorizontalHeaderLabels([
            _tr("room_optimizer.detail.excluded.cat"), "STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK",
            _tr("room_optimizer.detail.excluded.sum"),
            _tr("room_optimizer.detail.excluded.agg"),
            _tr("room_optimizer.detail.excluded.lib"),
            _tr("room_optimizer.detail.excluded.inbred"),
        ])
        self._excluded_table.verticalHeader().setVisible(False)
        self._excluded_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._excluded_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._excluded_table.setFocusPolicy(Qt.NoFocus)
        self._excluded_table.setAlternatingRowColors(True)
        self._excluded_table.hide()
        ex_hh = self._excluded_table.horizontalHeader()
        ex_hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 9):
            ex_hh.setSectionResizeMode(col, QHeaderView.Interactive)
        for col in range(1, 8):
            self._excluded_table.setColumnWidth(col, 50)
        self._excluded_table.setColumnWidth(8, 60)
        for col in range(9, 12):
            self._excluded_table.setColumnWidth(col, 60)
            ex_hh.setSectionResizeMode(col, QHeaderView.Interactive)
        self._excluded_table.setStyleSheet("""
            QTableWidget {
                background:#0d0d1c; alternate-background-color:#131326;
                color:#ddd; border:1px solid #26264a; font-size:12px;
            }
            QTableWidget::item { padding:3px 4px; }
            QHeaderView::section {
                background:#16213e; color:#888; padding:5px 4px;
                border:none; border-bottom:1px solid #1e1e38;
                border-right:1px solid #16213e; font-size:11px; font-weight:bold;
            }
        """)
        root.addWidget(self._excluded_table, 1)

    def retranslate_ui(self):
        self._best_pairs_btn.setText(
            _tr("room_optimizer.detail.toggle.best_pairs")
            if self._best_pairs_btn.isChecked()
            else _tr("room_optimizer.detail.toggle.all_pairs")
        )
        self._best_pairs_btn.setToolTip(_tr("room_optimizer.detail.toggle.tooltip"))
        self._pairs_table.setHorizontalHeaderLabels([
            _tr("room_optimizer.detail.table.cat_a"),
            _tr("room_optimizer.detail.table.cat_b"),
            "\u2665",
            "STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK",
            _tr("room_optimizer.detail.table.sum"),
            _tr("room_optimizer.detail.table.avg"),
            _tr("room_optimizer.detail.table.risk"),
            _tr("room_optimizer.detail.table.rank"),
            _tr("room_optimizer.detail.table.mutations", default="Mutations"),
        ])
        self._excluded_table.setHorizontalHeaderLabels([
            _tr("room_optimizer.detail.excluded.cat"), "STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK",
            _tr("room_optimizer.detail.excluded.sum"),
            _tr("room_optimizer.detail.excluded.agg"),
            _tr("room_optimizer.detail.excluded.lib"),
            _tr("room_optimizer.detail.excluded.inbred"),
        ])

    def _on_pair_cell_clicked(self, item):
        """Handle clicks on cat names to navigate to the cat in the main view."""
        col = self._pairs_table.column(item)
        # Only handle clicks on Cat A (column 0) or Cat B (column 1)
        if col not in (0, 1):
            return

        cat_name = item.text().replace(" \u2665", "")
        if not cat_name or not self._navigate_to_cat_callback:
            return

        # Call the navigate callback with the cat name
        self._navigate_to_cat_callback(cat_name)

    def _on_toggle_best_pairs(self):
        """Re-render pairs table based on toggle state."""
        checked = self._best_pairs_btn.isChecked()
        self._best_pairs_btn.setText(
            _tr("room_optimizer.detail.toggle.best_pairs")
            if checked
            else _tr("room_optimizer.detail.toggle.all_pairs")
        )
        if self._current_data:
            self.show_room(self._current_data)

    @staticmethod
    def _apply_best_pairs_filter(pairs: list[dict]) -> list[dict]:
        """Greedy non-overlapping pair selection. Lover pairs take priority."""
        # Sort lover pairs first so they get picked before rank-based pairs
        sorted_pairs = sorted(enumerate(pairs), key=lambda ip: (not ip[1].get("is_lovers"), ip[0]))
        sorted_pairs = [p for _, p in sorted_pairs]
        used = set()
        result = []
        for pair in sorted_pairs:
            a, b = pair["cat_a"], pair["cat_b"]
            if a not in used and b not in used:
                result.append(pair)
                used.add(a)
                used.add(b)
        # Re-sort by original rank for display
        result.sort(key=lambda p: p.get("_original_rank", 0))
        return result

    @staticmethod
    def _range_background(lo: int, hi: int) -> QColor:
        base = STAT_COLORS.get(max(lo, hi), QColor(100, 100, 115))
        if lo != hi:
            return QColor(
                min(255, int(base.red() * 0.55) + 22),
                min(255, int(base.green() * 0.55) + 22),
                min(255, int(base.blue() * 0.55) + 22),
            )
        return QColor(
            min(255, int(base.red() * 0.7) + 18),
            min(255, int(base.green() * 0.7) + 18),
            min(255, int(base.blue() * 0.7) + 18),
        )

    @staticmethod
    def _pair_color(room_order: int) -> QColor:
        rank = max(1, int(room_order or 1))
        return PAIR_COLORS[(rank - 1) % len(PAIR_COLORS)]

    @staticmethod
    def _pair_tint(color: QColor, strength: float = 0.28, lift: int = 18) -> QColor:
        return QColor(
            min(255, int(color.red() * strength) + lift),
            min(255, int(color.green() * strength) + lift),
            min(255, int(color.blue() * strength) + lift),
        )

    def show_room(self, data: Optional[dict]):
        if not data:
            self._summary.setText(_tr("room_optimizer.detail.summary.select_room"))
            self._summary.setToolTip("")
            self._pairs_table.setRowCount(0)
            self._pairs_table.show()
            self._excluded_table.hide()
            return

        self._current_data = data

        room = data.get("room", _tr("common.unknown", default="Unknown"))
        cats = data.get("cats", [])
        total_pairs = int(data.get("total_pairs", 0))
        avg_stats = float(data.get("avg_stats", 0))
        avg_risk = float(data.get("avg_risk", 0))
        pairs = data.get("pairs", [])
        excluded_cats = data.get("excluded_cats", [])
        excluded_cat_rows = data.get("excluded_cat_rows", [])

        if room == "Excluded":
            self._pairs_table.hide()
            self._excluded_table.show()
            self._summary.setText(
                _tr("room_optimizer.detail.summary.excluded", count=len(excluded_cat_rows))
            )
            self._summary.setToolTip(_tr("room_optimizer.detail.summary.excluded_tooltip"))
            self._excluded_table.setRowCount(len(excluded_cat_rows))
            for row_idx, cat_row in enumerate(excluded_cat_rows):
                name_item = QTableWidgetItem(cat_row["name"])
                icon = _make_tag_icon(cat_row.get("tags", []))
                if not icon.isNull():
                    name_item.setIcon(icon)
                self._excluded_table.setItem(row_idx, 0, name_item)
                for stat_col, stat in enumerate(STAT_NAMES, start=1):
                    value = int(cat_row["stats"].get(stat, 0))
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setBackground(QBrush(STAT_COLORS.get(value, QColor(100, 100, 115))))
                    self._excluded_table.setItem(row_idx, stat_col, item)
                sum_item = QTableWidgetItem(str(int(cat_row["sum"])))
                sum_item.setTextAlignment(Qt.AlignCenter)
                self._excluded_table.setItem(row_idx, 8, sum_item)
                for trait_col, trait_key in enumerate(("aggression", "libido", "inbredness"), start=9):
                    trait_text = cat_row["traits"][trait_key]
                    trait_display = trait_text.replace("average", "avg")
                    trait_item = QTableWidgetItem(trait_display)
                    trait_item.setTextAlignment(Qt.AlignCenter)
                    trait_item.setBackground(QBrush(_trait_level_color(trait_text)))
                    self._excluded_table.setItem(row_idx, trait_col, trait_item)
            return

        self._pairs_table.show()
        self._excluded_table.hide()

        def _compact_names(names: list[str], limit: int = 8) -> str:
            if len(names) <= limit:
                return ", ".join(names)
            shown = ", ".join(names[:limit])
            return f"{shown}, ... (+{len(names) - limit} more)"

        cats_text = _compact_names(cats)
        self._summary.setText(
            _tr(
                "room_optimizer.detail.summary.room",
                room=room,
                pairs=total_pairs,
                avg=f"{avg_stats:.1f}",
                risk=f"{avg_risk:.0f}",
            )
        )
        self._summary.setToolTip(
            _tr("room_optimizer.detail.summary.cats", cats=", ".join(cats)) if cats else ""
        )

        # Preserve original rank before filtering
        for i, pair in enumerate(pairs, 1):
            pair["_original_rank"] = i

        # Apply best pairs filter if enabled
        if self._best_pairs_btn.isChecked():
            pairs = self._apply_best_pairs_filter(pairs)

        self._pairs_table.setRowCount(len(pairs))
        for i, pair in enumerate(pairs, 1):
            # Cat A and B items with hyperlink styling
            cat_a_text = pair['cat_a']
            cat_b_text = pair['cat_b']
            if pair.get("cat_a_has_lover"):
                cat_a_text += " \u2665"
            if pair.get("cat_b_has_lover"):
                cat_b_text += " \u2665"
            cat_a_item = QTableWidgetItem(cat_a_text)
            cat_b_item = QTableWidgetItem(cat_b_text)
            # Style as hyperlinks
            hyperlink_color = QColor(0x5b9bd5)  # Blue
            cat_a_item.setForeground(QBrush(hyperlink_color))
            cat_b_item.setForeground(QBrush(hyperlink_color))
            font = cat_a_item.font()
            font.setUnderline(True)
            cat_a_item.setFont(font)
            cat_b_item.setFont(font)
            cat_a_item.setToolTip(_tr("room_optimizer.locator.tooltip.jump_to_cat"))
            cat_b_item.setToolTip(_tr("room_optimizer.locator.tooltip.jump_to_cat"))
            sum_lo, sum_hi = pair.get("sum_range", (0, 0))
            sum_item = QTableWidgetItem(f"{sum_lo}-{sum_hi}")
            sum_item.setToolTip(
                _tr("room_optimizer.detail.tooltip.sum_range", lo=sum_lo, hi=sum_hi)
            )
            avg_item = QTableWidgetItem(f"{pair['avg_stats']:.1f}")
            stat_ranges = pair.get("stat_ranges", {})
            stat_items = []
            for stat in STAT_NAMES:
                lo, hi = stat_ranges.get(stat, (0, 0))
                item = QTableWidgetItem(f"{lo}-{hi}")
                item.setToolTip(_tr("room_optimizer.detail.tooltip.stat_range", stat=stat.upper(), lo=lo, hi=hi))
                item.setBackground(QBrush(self._range_background(lo, hi)))
                stat_items.append(item)
            risk_item = QTableWidgetItem(f"{pair['risk']:.0f}%")
            rank_item = QTableWidgetItem(str(pair.get("_original_rank", i)))

            for item in stat_items:
                item.setTextAlignment(Qt.AlignCenter)
            sum_item.setTextAlignment(Qt.AlignCenter)
            avg_item.setTextAlignment(Qt.AlignCenter)
            risk_item.setTextAlignment(Qt.AlignCenter)
            rank_item.setTextAlignment(Qt.AlignCenter)
            sum_item.setBackground(QBrush(self._range_background(sum_lo // len(STAT_NAMES), sum_hi // len(STAT_NAMES))))
            avg_item.setBackground(QBrush(self._range_background(int(pair['avg_stats']), int(pair['avg_stats']))))

            risk = float(pair["risk"])
            if risk >= 50:
                risk_item.setForeground(QBrush(QColor(217, 119, 119)))
            elif risk >= 20:
                risk_item.setForeground(QBrush(QColor(216, 181, 106)))
            else:
                risk_item.setForeground(QBrush(QColor(98, 194, 135)))

            self._pairs_table.setItem(i - 1, 0, cat_a_item)
            self._pairs_table.setItem(i - 1, 1, cat_b_item)
            # Lovers indicator column
            lover_item = QTableWidgetItem("\u2665" if pair.get("is_lovers") else "")
            lover_item.setTextAlignment(Qt.AlignCenter)
            if pair.get("is_lovers"):
                lover_item.setForeground(QBrush(QColor(220, 100, 120)))
                lover_item.setToolTip("Mutual lovers")
            self._pairs_table.setItem(i - 1, 2, lover_item)
            for j, item in enumerate(stat_items, 3):
                self._pairs_table.setItem(i - 1, j, item)
            self._pairs_table.setItem(i - 1, 10, sum_item)
            self._pairs_table.setItem(i - 1, 11, avg_item)
            self._pairs_table.setItem(i - 1, 12, risk_item)
            self._pairs_table.setItem(i - 1, 13, rank_item)

            mutations = pair.get("mutations") or []
            if mutations:
                shown = [f"{name} {prob * 100:.0f}%" for name, prob in mutations[:4]]
                cell_text = ", ".join(shown)
                if len(mutations) > 4:
                    cell_text += f" (+{len(mutations) - 4})"
                tooltip_lines = [f"{name}: {prob * 100:.0f}%" for name, prob in mutations]
                mut_item = QTableWidgetItem(cell_text)
                mut_item.setToolTip("\n".join(tooltip_lines))
            else:
                mut_item = QTableWidgetItem("—")
            self._pairs_table.setItem(i - 1, 14, mut_item)


class PerfectPlannerDetailPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:#0a0a18; border-top:1px solid #1e1e38;")
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 8)
        root.setSpacing(6)

        self._summary = QLabel(_tr("perfect_planner.detail.summary.select_stage"))
        self._summary.setStyleSheet("color:#aaa; font-size:11px;")
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)

        self._context = QLabel("")
        self._context.setStyleSheet("color:#7d8bb0; font-size:10px; font-style:italic;")
        self._context.setWordWrap(True)
        self._context.hide()
        root.addWidget(self._context)

        self._actions_table = QTableWidget(0, 3)
        self._actions_table.setHorizontalHeaderLabels([
            _tr("perfect_planner.detail.table.target", default="Target"),
            _tr("perfect_planner.table.coverage", default="7s"),
            _tr("perfect_planner.table.risk", default="Risk%"),
        ])
        self._actions_table.verticalHeader().setVisible(False)
        self._actions_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._actions_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._actions_table.setFocusPolicy(Qt.NoFocus)
        self._actions_table.setWordWrap(True)
        self._actions_table.setAlternatingRowColors(True)
        self._actions_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        hh = self._actions_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        self._actions_table.setColumnWidth(0, 450)
        self._actions_table.setColumnWidth(1, 52)
        self._actions_table.setColumnWidth(2, 52)
        self._actions_table.verticalHeader().setDefaultSectionSize(24)
        self._actions_table.setStyleSheet("""
            QTableWidget {
                background:#0d0d1c; alternate-background-color:#131326;
                color:#ddd; border:1px solid #26264a; font-size:10px;
            }
            QTableWidget::item { padding:2px 4px; }
            QHeaderView::section {
                background:#16213e; color:#888; padding:5px 4px;
                border:none; border-bottom:1px solid #1e1e38;
                border-right:1px solid #16213e; font-size:10px; font-weight:bold;
            }
        """)
        root.addWidget(self._actions_table, 1)

        self._excluded_table = QTableWidget(0, 12)
        self._excluded_table.setHorizontalHeaderLabels([
            _tr("perfect_planner.detail.excluded.cat"), "STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK",
            _tr("perfect_planner.detail.excluded.sum"),
            _tr("perfect_planner.detail.excluded.agg"),
            _tr("perfect_planner.detail.excluded.lib"),
            _tr("perfect_planner.detail.excluded.inbred"),
        ])
        self._excluded_table.verticalHeader().setVisible(False)
        self._excluded_table.setSelectionMode(QAbstractItemView.NoSelection)
        self._excluded_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._excluded_table.setFocusPolicy(Qt.NoFocus)
        self._excluded_table.setAlternatingRowColors(True)
        self._excluded_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._excluded_table.hide()
        ex_hh = self._excluded_table.horizontalHeader()
        ex_hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 9):
            ex_hh.setSectionResizeMode(col, QHeaderView.Interactive)
        for col in range(1, 8):
            self._excluded_table.setColumnWidth(col, 50)
        self._excluded_table.setColumnWidth(8, 60)
        for col in range(9, 12):
            self._excluded_table.setColumnWidth(col, 60)
            ex_hh.setSectionResizeMode(col, QHeaderView.Interactive)
        self._excluded_table.verticalHeader().setDefaultSectionSize(22)
        self._excluded_table.setStyleSheet("""
            QTableWidget {
                background:#0d0d1c; alternate-background-color:#131326;
                color:#ddd; border:1px solid #26264a; font-size:10px;
            }
            QTableWidget::item { padding:2px 3px; }
            QHeaderView::section {
                background:#16213e; color:#888; padding:5px 4px;
                border:none; border-bottom:1px solid #1e1e38;
                border-right:1px solid #16213e; font-size:10px; font-weight:bold;
            }
        """)
        root.addWidget(self._excluded_table, 1)

    def retranslate_ui(self):
        self._actions_table.setHorizontalHeaderLabels([
            _tr("perfect_planner.detail.table.target", default="Target"),
            _tr("perfect_planner.table.coverage", default="7s"),
            _tr("perfect_planner.table.risk", default="Risk%"),
        ])
        self._excluded_table.setHorizontalHeaderLabels([
            _tr("perfect_planner.detail.excluded.cat"), "STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK",
            _tr("perfect_planner.detail.excluded.sum"),
            _tr("perfect_planner.detail.excluded.agg"),
            _tr("perfect_planner.detail.excluded.lib"),
            _tr("perfect_planner.detail.excluded.inbred"),
        ])

    @staticmethod
    def _build_target_grid(action: dict) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(2)
        grid.setVerticalSpacing(1)

        target_grid = action.get("target_grid") or {}
        parents = target_grid.get("parents", [])
        offspring = target_grid.get("offspring", {})
        mutation_summary = action.get("mutation_summary") or {}
        parent_summaries = []
        if isinstance(mutation_summary, dict):
            parent_summaries = list(mutation_summary.get("parents", []) or [])
        pair_summary = mutation_summary.get("pair") if isinstance(mutation_summary, dict) else None

        def _style_trait_label(lbl: QLabel, summary: Optional[dict], *, alpha: int, label: str, base_style: str):
            if not summary:
                lbl.setStyleSheet(base_style)
                return
            ratio = float(summary.get("ratio", 0.0))
            if abs(ratio) <= 1e-6:
                lbl.setStyleSheet(base_style)
                return
            color = _planner_trait_color(ratio)
            color.setAlpha(alpha)
            border = QColor(color).lighter(135)
            border.setAlpha(min(255, alpha + 50))
            lbl.setStyleSheet(
                base_style
                + f"background-color: rgba({color.red()},{color.green()},{color.blue()},{color.alpha()});"
                + f" border:1px solid rgba({border.red()},{border.green()},{border.blue()},{border.alpha()});"
                + " border-radius:3px; padding:1px 4px; color:#fff;"
            )
            tooltip = _planner_trait_tooltip(summary, label=label)
            if tooltip:
                lbl.setToolTip(tooltip)

        name_col_width = 76
        for row_idx, header in enumerate(["", *STAT_NAMES, "Sum"]):
            if row_idx == 0:
                continue
            hdr = QLabel(header)
            hdr.setAlignment(Qt.AlignCenter)
            hdr.setStyleSheet("color:#6f7fa0; font-size:8px; font-weight:bold;")
            grid.addWidget(hdr, 0, row_idx)

        def _parent_row(row: int, parent: dict):
            name = QLabel(parent.get("name", ""))
            name.setWordWrap(True)
            name.setMinimumWidth(name_col_width)
            _style_trait_label(
                name,
                parent_summaries[row - 1] if row - 1 < len(parent_summaries) else None,
                alpha=150,
                label=parent.get("name", "Parent"),
                base_style="color:#ddd; font-size:9px; font-weight:bold;",
            )
            if not name.toolTip():
                name.setToolTip(parent.get("name", ""))
            grid.addWidget(name, row, 0)
            for col, stat in enumerate(STAT_NAMES, 1):
                value = int(parent.get("stats", {}).get(stat, 0))
                c = STAT_COLORS.get(value, QColor(100, 100, 115))
                lbl = QLabel(str(value))
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet(
                    f"background:rgb({c.red()},{c.green()},{c.blue()});"
                    "color:#fff; font-size:9px; font-weight:bold;"
                    "border-radius:2px; padding:1px 4px;"
                )
                grid.addWidget(lbl, row, col)
            sum_lbl = QLabel(str(int(parent.get("sum", 0))))
            sum_lbl.setAlignment(Qt.AlignCenter)
            sum_lbl.setStyleSheet("color:#9aa6ba; font-size:9px; font-weight:bold;")
            grid.addWidget(sum_lbl, row, len(STAT_NAMES) + 1)

        def _offspring_row(row: int, info: dict):
            name = QLabel(_tr("perfect_planner.detail.offspring"))
            _style_trait_label(
                name,
                pair_summary,
                alpha=120,
                label=_tr("perfect_planner.detail.offspring"),
                base_style="color:#777; font-size:8px; font-style:italic;",
            )
            if not name.toolTip():
                name.setToolTip(_tr("perfect_planner.detail.offspring"))
            grid.addWidget(name, row, 0)
            sum_lo, sum_hi = info.get("sum_range", (0, 0))
            for col, stat in enumerate(STAT_NAMES, 1):
                stat_info = info.get("stats", {}).get(stat, {})
                lo = int(stat_info.get("lo", 0))
                hi = int(stat_info.get("hi", 0))
                expected = float(stat_info.get("expected", hi))
                hi_color = STAT_COLORS.get(hi, QColor(100, 100, 115))
                if lo == hi:
                    text = f"{lo}"
                else:
                    text = f"{lo}-{hi}\n{expected:.1f}"
                lbl = QLabel(text)
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setToolTip(_tr("perfect_planner.detail.tooltip.stat", stat=stat, lo=lo, hi=hi, expected=f"{expected:.1f}"))
                lbl.setStyleSheet(
                    f"background:rgba({hi_color.red()},{hi_color.green()},{hi_color.blue()},110);"
                    f"color:rgb({hi_color.red()},{hi_color.green()},{hi_color.blue()});"
                    "font-size:8px; font-weight:bold; border-radius:2px; padding:1px 3px;"
                )
                grid.addWidget(lbl, row, col)
            if sum_lo == sum_hi:
                sum_text = str(sum_lo)
            else:
                sum_text = f"{sum_lo}-{sum_hi}"
            sum_lbl = QLabel(sum_text)
            sum_lbl.setAlignment(Qt.AlignCenter)
            sum_lbl.setStyleSheet("color:#777; font-size:9px; font-weight:bold;")
            grid.addWidget(sum_lbl, row, len(STAT_NAMES) + 1)

        if len(parents) >= 1:
            _parent_row(1, parents[0])
        if len(parents) >= 2:
            _parent_row(2, parents[1])
        _offspring_row(3, offspring)
        container.setFixedHeight(84)
        return container

    def show_stage(self, data: Optional[dict], context_note: Optional[str] = None):
        if not data:
            self._summary.setText(_tr("perfect_planner.detail.summary.select_stage"))
            self._summary.setToolTip("")
            self._context.setText("")
            self._context.hide()
            self._actions_table.setRowCount(0)
            self._actions_table.show()
            self._excluded_table.hide()
            return

        if data.get("stage") == _tr("perfect_planner.stage.excluded"):
            rows = data.get("excluded_cat_rows", [])
            self._summary.setText(_tr("perfect_planner.detail.summary.excluded", count=len(rows)))
            self._summary.setToolTip(_tr("perfect_planner.detail.summary.excluded_tooltip"))
            self._context.setText(context_note or "")
            self._context.setVisible(bool(context_note))
            self._actions_table.hide()
            self._excluded_table.show()
            self._excluded_table.setRowCount(len(rows))
            for row_idx, cat_row in enumerate(rows):
                name_item = QTableWidgetItem(cat_row["name"])
                icon = _make_tag_icon(cat_row.get("tags", []))
                if not icon.isNull():
                    name_item.setIcon(icon)
                self._excluded_table.setItem(row_idx, 0, name_item)
                for stat_col, stat in enumerate(STAT_NAMES, start=1):
                    value = int(cat_row["stats"].get(stat, 0))
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setBackground(QBrush(STAT_COLORS.get(value, QColor(100, 100, 115))))
                    self._excluded_table.setItem(row_idx, stat_col, item)
                sum_item = QTableWidgetItem(str(int(cat_row["sum"])))
                sum_item.setTextAlignment(Qt.AlignCenter)
                self._excluded_table.setItem(row_idx, 8, sum_item)
                for trait_col, trait_key in enumerate(("aggression", "libido", "inbredness"), start=9):
                    trait_text = cat_row["traits"][trait_key]
                    trait_display = trait_text.replace("average", "avg")
                    trait_item = QTableWidgetItem(trait_display)
                    trait_item.setTextAlignment(Qt.AlignCenter)
                    trait_item.setBackground(QBrush(_trait_level_color(trait_text)))
                    self._excluded_table.setItem(row_idx, trait_col, trait_item)
            return

        self._actions_table.show()
        self._excluded_table.hide()

        stage_label = data.get("stage", "")
        self._summary.setText(stage_label)
        self._summary.setToolTip("")
        self._context.setText(context_note or "")
        self._context.setVisible(bool(context_note))

        actions = data.get("actions", [])
        self._actions_table.setRowCount(len(actions))
        for row, action in enumerate(actions):
            coverage_value = action.get("coverage_value")
            if coverage_value is None:
                coverage_value = 0.0
            coverage_item = QTableWidgetItem(f"{float(coverage_value):.1f}/7")
            coverage_item.setTextAlignment(Qt.AlignCenter)
            if float(coverage_value) >= 6.0:
                coverage_item.setForeground(QBrush(QColor(98, 194, 135)))
            elif float(coverage_value) >= 4.5:
                coverage_item.setForeground(QBrush(QColor(216, 181, 106)))
            else:
                coverage_item.setForeground(QBrush(QColor(190, 145, 40)))

            risk_value = action.get("risk")
            risk_item = QTableWidgetItem("—" if risk_value is None else f"{float(risk_value):.0f}%")
            risk_item.setTextAlignment(Qt.AlignCenter)
            if risk_value is not None:
                risk = float(risk_value)
                if risk >= 50:
                    risk_item.setForeground(QBrush(QColor(217, 119, 119)))
                elif risk >= 20:
                    risk_item.setForeground(QBrush(QColor(216, 181, 106)))
                else:
                    risk_item.setForeground(QBrush(QColor(98, 194, 135)))

            if action.get("target_grid"):
                self._actions_table.setCellWidget(row, 0, self._build_target_grid(action))
            else:
                target_item = QTableWidgetItem(action.get("target", ""))
                self._actions_table.setItem(row, 0, target_item)
            self._actions_table.setItem(row, 1, coverage_item)
            self._actions_table.setItem(row, 2, risk_item)

        self._actions_table.resizeRowsToContents()


class PerfectPlannerGuidePanel(QWidget):
    """Read-only guide for how the Perfect 7 planner is meant to be used."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QTextBrowser { background:#0d0d1c; color:#ddd; border:1px solid #26264a; "
            "border-radius:6px; padding:10px; font-size:12px; }"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self._title = QLabel(_tr("perfect_planner.guide.title", default="Planner Guide"))
        self._title.setStyleSheet("color:#ddd; font-size:18px; font-weight:bold;")
        root.addWidget(self._title)

        self._subtitle = QLabel(_tr(
            "perfect_planner.guide.subtitle",
            default="A built-in README for the perfect-line workflow.",
        ))
        self._subtitle.setStyleSheet("color:#8d8da8; font-size:11px;")
        self._subtitle.setWordWrap(True)
        root.addWidget(self._subtitle)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setFocusPolicy(Qt.NoFocus)
        self._browser.setFrameShape(QFrame.NoFrame)
        self._browser.setStyleSheet(
            "QTextBrowser { background:#0d0d1c; color:#ddd; border:1px solid #26264a; "
            "border-radius:6px; padding:10px; }"
            "QTextBrowser h2 { color:#f0f0ff; margin-top: 6px; margin-bottom: 6px; }"
            "QTextBrowser h3 { color:#c9d6ff; margin-top: 12px; margin-bottom: 4px; }"
            "QTextBrowser ul, QTextBrowser ol { margin-left: 18px; }"
            "QTextBrowser li { margin-bottom: 4px; }"
            "QTextBrowser p { margin-top: 4px; margin-bottom: 8px; }"
            "QTextBrowser .muted { color:#8d8da8; }"
        )
        root.addWidget(self._browser, 1)

        self.retranslate_ui()
        _enforce_min_font_in_widget_tree(self)

    def retranslate_ui(self):
        self._title.setText(_tr("perfect_planner.guide.title", default="Planner Guide"))
        self._subtitle.setText(_tr(
            "perfect_planner.guide.subtitle",
            default="A built-in README for the perfect-line workflow.",
        ))
        self._browser.setHtml(self._build_html())

    @staticmethod
    def _esc(text: str) -> str:
        return html.escape(text or "")

    def _build_html(self) -> str:
        stage1_details = self._esc(_tr("perfect_planner.stage1.details"))
        stage1_note1 = self._esc(_tr("perfect_planner.stage1.note1"))
        stage1_note2 = self._esc(_tr("perfect_planner.stage1.note2"))
        stage2_details = self._esc(_tr("perfect_planner.stage2.details"))
        stage3_details = self._esc(_tr("perfect_planner.stage3.details"))
        stage4_details = self._esc(_tr("perfect_planner.stage4.details"))
        description = self._esc(_tr("perfect_planner.description"))
        guide_note = self._esc(
            "Foundation pair edits and offspring selections refresh the plan automatically."
        )

        return f"""
        <html>
          <body style="font-family:Segoe UI, Arial, sans-serif; line-height:1.45;">
            <h2>{self._esc(_tr("perfect_planner.guide.title", default="Planner Guide"))}</h2>
            <p>{description}</p>

            <h3>Where to look</h3>
            <ul>
              <li><strong>Stage Details</strong> uses the wider layout now: parent pair, projected stat spread, coverage, and risk only.</li>
              <li><strong>Planner Guide</strong> holds the longer explanations that used to repeat in the lower-left pane.</li>
              <li><strong>Foundation Pairs</strong> is the one-time setup area for the starting lines you want to use.</li>
              <li><strong>Offspring Tracker</strong> is where you pick a keeper child for each pair and keep that choice over time.</li>
              <li><strong>Cat Locator</strong> keeps the room-moving side of the plan visible, including offspring.</li>
            </ul>

            <h3>How to use it</h3>
            <ol>
              <li>Pick your starting pairs in the Foundation Pairs tab.</li>
              <li>Set how many starting pairs you want with <strong>Start pairs</strong> and click <strong>Build Perfect 7 Plan</strong>.</li>
              <li>Use the stage table above to jump between the four planning stages.</li>
              <li>Read the focused stage notes on the left when you need the active action list without all the duplicate text.</li>
              <li>Use the Offspring Tracker to pick one keeper offspring per pair; the choice is saved and the plan refreshes.</li>
              <li>Use the Cat Locator to see where parents, offspring, and rotation candidates should live.</li>
            </ol>

            <h3>Stage map</h3>
            <ul>
              <li><strong>{self._esc(_tr("perfect_planner.stage1.title"))}</strong>: {stage1_details}</li>
              <li><strong>{self._esc(_tr("perfect_planner.stage2.title"))}</strong>: {stage2_details}</li>
              <li><strong>{self._esc(_tr("perfect_planner.stage3.title"))}</strong>: {stage3_details}</li>
              <li><strong>{self._esc(_tr("perfect_planner.stage4.title"))}</strong>: {stage4_details}</li>
            </ul>

            <h3>Working rules</h3>
            <ul>
              <li>{stage1_note1}</li>
              <li>{stage1_note2}</li>
              <li>{self._esc(_tr("perfect_planner.stage2.note1"))}</li>
              <li>{self._esc(_tr("perfect_planner.stage3.note1"))}</li>
              <li>{self._esc(_tr("perfect_planner.stage4.note1"))}</li>
              <li><span style="color:#8d8da8;">{guide_note}</span></li>
            </ul>
          </body>
        </html>
        """


class PerfectPlannerOffspringTracker(QWidget):
    """Track the actual and projected offspring for Perfect 7 planner pairs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; }"
            "QHeaderView::section { background:#151532; color:#7d8bb0; border:none; padding:4px; font-weight:bold; }"
        )
        self._rows: list[dict] = []
        self._render_rows: list[dict] = []
        self._selected_offspring_by_pair: dict[tuple[int, int], int] = {}
        self._save_path: Optional[str] = None
        self._selected_child_uid_by_pair_key: dict[str, str] = _load_perfect_planner_selected_offspring(self._save_path)
        self._navigate_to_cat_callback = None
        self._select_offspring_callback = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        self._title = QLabel(_tr("perfect_planner.offspring_tracker.title", default="Offspring Tracker"))
        self._title.setStyleSheet("color:#ddd; font-size:18px; font-weight:bold;")
        self._summary = QLabel(_tr(
            "perfect_planner.offspring_tracker.summary_empty",
            default="Build a plan to track offspring outcomes.",
        ))
        self._summary.setStyleSheet("color:#666; font-size:11px;")
        header.addWidget(self._title)
        header.addStretch()
        header.addWidget(self._summary)
        root.addLayout(header)

        self._desc = QLabel(_tr(
            "perfect_planner.offspring_tracker.description",
            default="Track each planned pair, any kittens already in the save, and the projected stat / inbreeding outcome.",
        ))
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet("color:#8d8da8; font-size:11px;")
        root.addWidget(self._desc)

        self._table = QTableWidget(0, 16)
        self._table.setIconSize(QSize(60, 20))
        self._table.setHorizontalHeaderLabels([
            _tr("perfect_planner.offspring_tracker.table.parent_a", default="Parent A"),
            _tr("perfect_planner.offspring_tracker.table.parent_b", default="Parent B"),
            _tr("perfect_planner.offspring_tracker.table.offspring", default="Offspring"),
            "Sel",
            "Age",
            "STR",
            "DEX",
            "CON",
            "INT",
            "SPD",
            "CHA",
            "LCK",
            "Agg",
            "Lib",
            "Inbred",
            "Notes",
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(True)
        self._table.setSortingEnabled(False)
        hh = self._table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignCenter)
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        for col in range(5, 12):
            hh.setSectionResizeMode(col, QHeaderView.Fixed)
        for col in range(12, 15):
            hh.setSectionResizeMode(col, QHeaderView.Fixed)
        hh.setSectionResizeMode(15, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 145)
        self._table.setColumnWidth(1, 145)
        self._table.setColumnWidth(2, 145)
        self._table.setColumnWidth(3, 24)
        self._table.setColumnWidth(4, 44)
        for col in range(5, 12):
            self._table.setColumnWidth(col, 44)
        self._table.setColumnWidth(12, 52)
        self._table.setColumnWidth(13, 52)
        self._table.setColumnWidth(14, 60)
        self._table.setColumnWidth(15, 100)
        self._table.setStyleSheet("""
            QTableWidget {
                background:#101023;
                color:#ddd;
                border:1px solid #26264a;
                font-size:9px;
            }
            QTableWidget::item { padding:1px 2px; }
            QHeaderView::section {
                background:#151532;
                color:#7d8bb0;
                border:none;
                border-bottom:1px solid #26264a;
                padding:2px 2px;
                font-weight:bold;
                font-size:8px;
            }
        """)
        self._table.cellClicked.connect(self._on_cell_clicked)
        root.addWidget(self._table, 1)

        self.retranslate_ui()
        _enforce_min_font_in_widget_tree(self)
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setSortIndicatorShown(False)

    def set_navigate_to_cat_callback(self, callback):
        self._navigate_to_cat_callback = callback

    def retranslate_ui(self):
        self._title.setText(_tr("perfect_planner.offspring_tracker.title", default="Offspring Tracker"))
        self._desc.setText(_tr(
            "perfect_planner.offspring_tracker.description",
            default="Track each planned pair, any kittens already in the save, and the projected stat / inbreeding outcome.",
        ))
        self._table.setHorizontalHeaderLabels([
            _tr("perfect_planner.offspring_tracker.table.parent_a", default="Parent A"),
            _tr("perfect_planner.offspring_tracker.table.parent_b", default="Parent B"),
            _tr("perfect_planner.offspring_tracker.table.offspring", default="Offspring"),
            "Sel",
            "Age",
            "STR",
            "DEX",
            "CON",
            "INT",
            "SPD",
            "CHA",
            "LCK",
            "Agg",
            "Lib",
            "Inbred",
            "Notes",
        ])
        if self._rows:
            self.set_rows(self._rows)
        else:
            self._summary.setText(_tr(
                "perfect_planner.offspring_tracker.summary_empty",
                default="Build a plan to track offspring outcomes.",
            ))

    @staticmethod
    def _parent_caption(cat: Cat) -> str:
        room = cat.room_display or cat.status or "?"
        heart = " ♥" if getattr(cat, "lovers", None) else ""
        return f"{cat.name}{heart}\n{cat.gender_display} · {room}"

    @staticmethod
    def _parent_tooltip(cat: Cat) -> str:
        room = cat.room_display or cat.status or "?"
        return (
            f"Room: {room}\n"
            f"Generation: {getattr(cat, 'generation', 0)}\n"
            f"Base sum: {sum(cat.base_stats.values())}"
        )

    @staticmethod
    def _offspring_caption(children: list[Cat]) -> str:
        if not children:
            return "No tracked offspring yet"

        lines = [f"Tracked offspring ({len(children)})"]
        for child in children[:3]:
            lines.append(f"{child.name} ({child.gender_display})")
        if len(children) > 3:
            lines.append(f"+{len(children) - 3} more")
        return "\n".join(lines)

    @staticmethod
    def _offspring_tooltip(children: list[Cat]) -> str:
        if not children:
            return "No tracked offspring are recorded for this pair yet."
        return "\n".join(
            f"{child.name} ({child.gender_display}) - {child.room_display or child.status or '?'}"
            for child in children
        )

    @staticmethod
    def _pair_key_for_cats(cat_a: Cat, cat_b: Cat) -> tuple[int, int]:
        a_key, b_key = cat_a.db_key, cat_b.db_key
        return (a_key, b_key) if a_key < b_key else (b_key, a_key)

    @staticmethod
    def _pair_uid_key(cat_a: Cat, cat_b: Cat) -> str:
        a_uid = _cat_uid(cat_a)
        b_uid = _cat_uid(cat_b)
        if not a_uid or not b_uid:
            return ""
        left, right = sorted((a_uid, b_uid))
        return f"{left}|{right}"

    def _set_selected_child(self, cat_a: Cat, cat_b: Cat, child: Optional[Cat]) -> bool:
        pair_key = self._pair_key_for_cats(cat_a, cat_b)
        pair_uid_key = self._pair_uid_key(cat_a, cat_b)
        current = self._selected_offspring_by_pair.get(pair_key)
        child_uid = _cat_uid(child) if child is not None else ""

        if child is None:
            self._selected_offspring_by_pair.pop(pair_key, None)
            if pair_uid_key:
                self._selected_child_uid_by_pair_key.pop(pair_uid_key, None)
            _save_perfect_planner_selected_offspring(self._selected_child_uid_by_pair_key, self._save_path)
            return False

        if current == child.db_key:
            self._selected_offspring_by_pair.pop(pair_key, None)
            if pair_uid_key:
                self._selected_child_uid_by_pair_key.pop(pair_uid_key, None)
            _save_perfect_planner_selected_offspring(self._selected_child_uid_by_pair_key, self._save_path)
            return False

        self._selected_offspring_by_pair[pair_key] = child.db_key
        if pair_uid_key and child_uid:
            self._selected_child_uid_by_pair_key[pair_uid_key] = child_uid
            _save_perfect_planner_selected_offspring(self._selected_child_uid_by_pair_key, self._save_path)
        return True

    @staticmethod
    def _compact_stat_lines(values: dict[str, int] | dict[str, float], *, expected: bool = False) -> list[str]:
        def _fmt(stat: str) -> str:
            prefix = stat[:3].title()
            val = values.get(stat, 0)
            return f"{prefix} {val:.1f}" if expected else f"{prefix} {int(val)}"

        return [
            " | ".join(_fmt(stat) for stat in STAT_NAMES[:4]),
            " | ".join(_fmt(stat) for stat in STAT_NAMES[4:]),
        ]

    @staticmethod
    def _born_stats_caption(cat: Cat) -> str:
        return "\n".join(["Actual"] + PerfectPlannerOffspringTracker._compact_stat_lines(cat.base_stats))

    @staticmethod
    def _expected_stats_caption(projection: dict) -> str:
        stat_ranges = projection.get("stat_ranges", {})

        def _fmt(stat: str) -> str:
            lo, hi = stat_ranges.get(stat, (0, 0))
            prefix = stat[:3].title()
            return f"{prefix} {lo}" if lo == hi else f"{prefix} {lo}-{hi}"

        return "\n".join([
            "Expected",
            " | ".join(_fmt(stat) for stat in STAT_NAMES[:4]),
            " | ".join(_fmt(stat) for stat in STAT_NAMES[4:]),
        ])

    @staticmethod
    def _born_attributes_caption(cat: Cat) -> str:
        inbred = _trait_label_from_value("inbredness", getattr(cat, "inbredness", 0.0)) or "unknown"
        aggression = _trait_label_from_value("aggression", getattr(cat, "aggression", 0.0)) or "unknown"
        libido = _trait_label_from_value("libido", getattr(cat, "libido", 0.0)) or "unknown"
        return f"Inbred {inbred} | Agg {aggression} | Lib {libido}"

    @staticmethod
    def _expected_attributes_caption(cat_a: Cat, cat_b: Cat, coi: float, risk: float, shared_total: int, shared_recent: int) -> str:
        inbred = _trait_label_from_value("inbredness", coi) or "unknown"
        aggression = _trait_label_from_value("aggression", (getattr(cat_a, "aggression", 0.0) + getattr(cat_b, "aggression", 0.0)) / 2.0) or "unknown"
        libido = _trait_label_from_value("libido", (getattr(cat_a, "libido", 0.0) + getattr(cat_b, "libido", 0.0)) / 2.0) or "unknown"
        return f"Inbred {inbred} | Agg {aggression} | Lib {libido}"

    @staticmethod
    def _metric_item(label: str, detail: str, bg: QColor, tooltip: str) -> QTableWidgetItem:
        item = QTableWidgetItem(label)
        item.setTextAlignment(Qt.AlignCenter)
        item.setBackground(QBrush(bg))
        item.setForeground(QBrush(QColor(255, 255, 255)))
        item.setToolTip(tooltip)
        return item

    def _build_attributes_widget(
        self,
        aggression_value: float,
        libido_value: float,
        inbred_value: float,
    ) -> QWidget:
        wrapper = QFrame()
        wrapper.setStyleSheet("QFrame { background: transparent; border: none; }")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(2)

        values = [
            ("aggression", aggression_value),
            ("libido", libido_value),
            ("inbredness", inbred_value),
        ]
        for col, (field, value) in enumerate(values):
            header = QLabel(field.title())
            header.setAlignment(Qt.AlignCenter)
            header.setStyleSheet("color:#9ca6c7; font-size:8px; font-weight:bold;")
            grid.addWidget(header, 0, col)

            label = _trait_label_from_value(field, value) or "unknown"
            item = QLabel(label)
            item.setAlignment(Qt.AlignCenter)
            item.setStyleSheet(
                f"background:{_trait_level_color(label).name()}; color:#fff; "
                "font-size:9px; font-weight:bold; border-radius:3px; padding:1px 4px;"
            )
            item.setToolTip(f"{field.title()}: {value:.3f} ({label})")
            grid.addWidget(item, 1, col)

        layout.addLayout(grid)
        wrapper.setToolTip(
            f"Aggression: {aggression_value:.3f} ({_trait_label_from_value('aggression', aggression_value) or 'unknown'})\n"
            f"Libido: {libido_value:.3f} ({_trait_label_from_value('libido', libido_value) or 'unknown'})\n"
            f"Inbredness: {inbred_value:.3f} ({_trait_label_from_value('inbredness', inbred_value) or 'unknown'})"
        )
        return wrapper

    @staticmethod
    def _stats_caption(projection: dict) -> str:
        stat_ranges = projection.get("stat_ranges", {})
        first_line: list[str] = []
        second_line: list[str] = []
        for stat in STAT_NAMES[:4]:
            lo, hi = stat_ranges.get(stat, (0, 0))
            first_line.append(f"{stat} {lo}" if lo == hi else f"{stat} {lo}-{hi}")
        for stat in STAT_NAMES[4:]:
            lo, hi = stat_ranges.get(stat, (0, 0))
            second_line.append(f"{stat} {lo}" if lo == hi else f"{stat} {lo}-{hi}")

        sum_lo, sum_hi = projection.get("sum_range", (0, 0))
        avg_expected = float(projection.get("avg_expected", 0.0))
        seven_plus = float(projection.get("seven_plus_total", 0.0))
        return "\n".join([
            "Stats",
            " | ".join(first_line),
            " | ".join(second_line),
            f"Sum {sum_lo}-{sum_hi} | Avg {avg_expected:.1f} | 7+ {seven_plus:.1f}/7",
        ])

    @staticmethod
    def _stats_tooltip(projection: dict) -> str:
        stat_ranges = projection.get("stat_ranges", {})
        expected_stats = projection.get("expected_stats", {})
        lines = ["Projected stat ranges:"]
        for stat in STAT_NAMES:
            lo, hi = stat_ranges.get(stat, (0, 0))
            expected = float(expected_stats.get(stat, hi))
            lines.append(f"  {stat}: {lo}-{hi} (expected {expected:.1f})")
        locked = ", ".join(projection.get("locked_stats", ())) or "none"
        reachable = ", ".join(projection.get("reachable_stats", ())) or "none"
        missing = ", ".join(projection.get("missing_stats", ())) or "none"
        sum_lo, sum_hi = projection.get("sum_range", (0, 0))
        lines.extend([
            f"Sum range: {sum_lo}-{sum_hi}",
            f"Locked stats: {locked}",
            f"Reachable stats: {reachable}",
            f"Missing stats: {missing}",
        ])
        return "\n".join(lines)

    @staticmethod
    def _notes_caption(projection: dict, coi: float, risk: float, shared_total: int, shared_recent: int) -> str:
        locked = ", ".join(projection.get("locked_stats", ())) or "none"
        reachable = ", ".join(projection.get("reachable_stats", ())) or "none"
        missing = ", ".join(projection.get("missing_stats", ())) or "none"
        label = _trait_label_from_value("inbredness", coi) or "unknown"
        return (
            f"Lck {locked} | Rch {reachable} | Miss {missing} | "
            f"Inbred {label} | R {risk:.1f}% | Sh {shared_total}/{shared_recent}"
        )

    @staticmethod
    def _inbredness_caption(coi: float, risk: float, shared_total: int, shared_recent: int) -> str:
        label = _trait_label_from_value("inbredness", coi) or "unknown"
        return "\n".join([
            "Inbredness",
            f"{label} | COI {coi * 100:.1f}% | Risk {risk:.1f}%",
            f"Shared {shared_total} total / {shared_recent} recent",
        ])

    @staticmethod
    def _inbredness_tooltip(coi: float, risk: float, shared_total: int, shared_recent: int) -> str:
        label = _trait_label_from_value("inbredness", coi) or "unknown"
        return (
            f"Inbredness label: {label}\n"
            f"Coefficient of inbreeding: {coi:.3f}\n"
            f"Birth defect risk: {risk:.1f}%\n"
            f"Shared ancestors: {shared_total} total, {shared_recent} recent"
        )

    @staticmethod
    def _stat_tint(color: QColor, strength: float = 0.26, lift: int = 16) -> QColor:
        return QColor(
            min(255, int(color.red() * strength) + lift),
            min(255, int(color.green() * strength) + lift),
            min(255, int(color.blue() * strength) + lift),
        )

    def _build_stats_widget(
        self,
        *,
        projection: dict,
        actual_stats: dict[str, int] | None = None,
        trait_values: dict[str, float] | None = None,
        detail_text: str = "",
    ) -> QWidget:
        table = QTableWidget(2, len(STAT_NAMES) + 3)
        table.setObjectName("offspringMetricsTable")
        table.setHorizontalHeaderLabels([s.upper() for s in STAT_NAMES] + ["AGG", "LIB", "INBRED"])
        table.setVerticalHeaderLabels(["Value", "Details"])
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setFocusPolicy(Qt.NoFocus)
        table.setAlternatingRowColors(False)
        table.setShowGrid(True)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setStyleSheet("""
            QTableWidget {
                background:#101023;
                color:#ddd;
                border:1px solid #26264a;
                font-size:9px;
            }
            QTableWidget::item { padding:1px 2px; }
            QHeaderView::section {
                background:#1a1a36;
                color:#9ca6c7;
                border:none;
                border-bottom:1px solid #26264a;
                padding:1px 2px;
                font-weight:bold;
                font-size:8px;
            }
        """)
        hh = table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignCenter)
        for col in range(len(STAT_NAMES) + 3):
            hh.setSectionResizeMode(col, QHeaderView.Stretch)
        table.verticalHeader().setDefaultSectionSize(18)
        table.horizontalHeader().setFixedHeight(16)

        stat_ranges = projection.get("stat_ranges", {})
        expected_stats = projection.get("expected_stats", {})
        stat_map = actual_stats or {}
        trait_map = trait_values or {}

        def _metric_item(text: str, bg: QColor, tooltip: str) -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            item.setBackground(QBrush(bg))
            item.setForeground(QBrush(QColor(255, 255, 255)))
            item.setToolTip(tooltip)
            return item

        for col, stat in enumerate(STAT_NAMES):
            if actual_stats is not None:
                value = int(stat_map.get(stat, 0))
                detail = "actual"
                base = STAT_COLORS.get(value, QColor(100, 100, 115))
                bg = self._stat_tint(base, strength=0.28, lift=18)
                tip = f"{stat}: {value}"
                text = str(value)
            else:
                lo, hi = stat_ranges.get(stat, (0, 0))
                detail = "projected"
                base = STAT_COLORS.get(max(lo, hi), QColor(100, 100, 115))
                bg = self._stat_tint(base, strength=0.22, lift=18)
                expected = float(expected_stats.get(stat, hi))
                text = f"{lo}" if lo == hi else f"{lo}-{hi}"
                tip = f"{stat}: {lo}-{hi} (expected {expected:.1f})"
            table.setItem(0, col, _metric_item(text, bg, tip))
            table.setItem(1, col, _metric_item(detail, QColor(22, 22, 43), tip))

        for offset, field in enumerate(("aggression", "libido", "inbredness"), start=len(STAT_NAMES)):
            value = float(trait_map.get(field, 0.0))
            text = _trait_label_from_value(field, value) or "unknown"
            detail = "actual" if actual_stats is not None else "projected"
            tip = f"{field.title()}: {value:.3f} ({text})"
            bg = _trait_level_color(text)
            table.setItem(0, offset, _metric_item(text, bg, tip))
            table.setItem(1, offset, _metric_item(detail, QColor(22, 22, 43), tip))

        if detail_text:
            table.setToolTip(detail_text)
        table.setFixedHeight(table.horizontalHeader().height() + sum(table.rowHeight(i) for i in range(table.rowCount())) + 6)
        wrapper = QFrame()
        wrapper.setStyleSheet("QFrame { background: transparent; border: none; }")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(table)
        return wrapper

    def set_rows(self, rows: list[dict]):
        restore_row = self._table.currentRow()
        restore_column = self._table.currentColumn()
        self._rows = list(rows)
        self._selected_offspring_by_pair = {}
        tracked_offspring = sum(len(row.get("known_offspring", [])) for row in self._rows)
        using_count = sum(1 for row in self._rows if row.get("source") == "using")
        suggested_count = len(self._rows) - using_count
        self._table.clearSpans()
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setSortIndicatorShown(False)
        try:

            if not self._rows:
                self._render_rows = []
                self._table.setRowCount(0)
                self._summary.setText(_tr(
                    "perfect_planner.offspring_tracker.summary_empty",
                    default="Build a plan to track offspring outcomes.",
                ))
                return

            self._summary.setText(_tr(
                "perfect_planner.offspring_tracker.summary",
                default="{pairs} pairs tracked | {offspring} known offspring already in the save",
                pairs=len(self._rows),
                offspring=tracked_offspring,
            ) + f" | {using_count} using, {suggested_count} suggested")

            render_rows: list[dict] = []
            for pair_row in self._rows:
                known_offspring = list(pair_row.get("known_offspring", []))
                if known_offspring:
                    for child_idx, child in enumerate(known_offspring, 1):
                        render_rows.append({
                            "pair": pair_row,
                            "child": child,
                            "child_index": child_idx,
                            "is_expected": False,
                        })
                else:
                    render_rows.append({
                        "pair": pair_row,
                        "child": None,
                        "child_index": 1,
                        "is_expected": True,
                    })

            self._render_rows = render_rows
            self._table.setRowCount(len(render_rows))
            row_idx = 0
            for pair_row in self._rows:
                cat_a = pair_row["cat_a"]
                cat_b = pair_row["cat_b"]
                projection = pair_row["projection"]
                known_offspring = list(pair_row.get("known_offspring", []))
                risk = float(pair_row.get("risk", 0.0))
                coi = float(pair_row.get("coi", 0.0))
                shared_total, shared_recent = pair_row.get("shared", (0, 0))
                pair_key = self._pair_key_for_cats(cat_a, cat_b)
                pair_uid_key = self._pair_uid_key(cat_a, cat_b)
                selected_child_uid = self._selected_child_uid_by_pair_key.get(pair_uid_key, "")
                selected_child_db = None
                if pair_uid_key:
                    for child in known_offspring:
                        if _cat_uid(child) and _cat_uid(child) == selected_child_uid:
                            selected_child_db = child.db_key
                            self._selected_offspring_by_pair[pair_key] = child.db_key
                            break
                    if selected_child_db is None:
                        self._selected_offspring_by_pair.pop(pair_key, None)

                span = len(known_offspring) if known_offspring else 1
                parent_a_item = QTableWidgetItem(self._parent_caption(cat_a))
                parent_a_item.setData(Qt.UserRole, cat_a.db_key)
                parent_a_item.setToolTip(self._parent_tooltip(cat_a))
                parent_a_item.setForeground(QBrush(QColor(100, 149, 237)))
                icon_a = _make_tag_icon(_cat_tags(cat_a), dot_size=14, spacing=4)
                if not icon_a.isNull():
                    parent_a_item.setIcon(icon_a)

                parent_b_item = QTableWidgetItem(self._parent_caption(cat_b))
                parent_b_item.setData(Qt.UserRole, cat_b.db_key)
                parent_b_item.setToolTip(self._parent_tooltip(cat_b))
                parent_b_item.setForeground(QBrush(QColor(100, 149, 237)))
                icon_b = _make_tag_icon(_cat_tags(cat_b), dot_size=14, spacing=4)
                if not icon_b.isNull():
                    parent_b_item.setIcon(icon_b)

                if span > 1:
                    self._table.setSpan(row_idx, 0, span, 1)
                    self._table.setSpan(row_idx, 1, span, 1)

                self._table.setItem(row_idx, 0, parent_a_item)
                self._table.setItem(row_idx, 1, parent_b_item)

                for child_offset in range(span):
                    current_row = row_idx + child_offset
                    child = known_offspring[child_offset] if known_offspring else None
                    render_row = self._render_rows[current_row]

                    if child is not None:
                        heart = " ♥" if getattr(child, "lovers", None) else ""
                        selected = selected_child_db == child.db_key
                        offspring_text = f"{child.name}{heart}"
                        age_text = str(child.age) if getattr(child, "age", None) is not None else "—"
                        offspring_color = QColor(98, 194, 135) if selected else QColor(100, 149, 237)
                    else:
                        offspring_text = "Not yet"
                        age_text = "—"
                        offspring_color = QColor(150, 150, 165)

                    offspring_item = QTableWidgetItem(offspring_text)
                    offspring_item.setToolTip(
                        self._offspring_tooltip(known_offspring) if child is None else f"{child.name} ({child.gender_display})"
                    )
                    offspring_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    offspring_item.setForeground(QBrush(offspring_color))
                    offspring_item.setData(Qt.UserRole, child.db_key if child is not None else None)
                    if child is not None:
                        f = offspring_item.font()
                        f.setUnderline(True)
                        offspring_item.setFont(f)
                        offspring_item.setForeground(QBrush(offspring_color))
                        lover_note = ""
                        if getattr(child, "lovers", None):
                            lover_note = "\nIn love with: " + ", ".join(other.name for other in child.lovers)
                        selected_note = "\nSelected for next breeding." if selected_child_db == child.db_key else ""
                        offspring_item.setToolTip(f"{child.name} ({child.gender_display}){lover_note}{selected_note}\nClick to open in the main cat view.")

                    self._table.setItem(current_row, 2, offspring_item)
                    sel_item = QTableWidgetItem("☑" if child is not None and selected_child_db == child.db_key else "☐")
                    sel_item.setTextAlignment(Qt.AlignCenter)
                    sel_item.setForeground(QBrush(QColor(98, 194, 135) if child is not None and selected_child_db == child.db_key else QColor(155, 168, 196)))
                    sel_item.setToolTip("Selected offspring for next breeding" if child is not None and selected_child_db == child.db_key else "Click to select this offspring")
                    self._table.setItem(current_row, 3, sel_item)
                    age_item = QTableWidgetItem(age_text)
                    age_item.setTextAlignment(Qt.AlignCenter)
                    age_item.setForeground(QBrush(QColor(98, 194, 135) if child is not None else QColor(155, 168, 196)))
                    age_item.setToolTip("Actual age" if child is not None else "Projected")
                    self._table.setItem(current_row, 4, age_item)
                    if child is not None:
                        stat_values = child.base_stats
                        trait_values = {
                            "aggression": float(getattr(child, "aggression", 0.0) or 0.0),
                            "libido": float(getattr(child, "libido", 0.0) or 0.0),
                            "inbredness": float(getattr(child, "inbredness", 0.0) or 0.0),
                        }
                    else:
                        stat_values = None
                        trait_values = {
                            "aggression": (getattr(cat_a, "aggression", 0.0) + getattr(cat_b, "aggression", 0.0)) / 2.0,
                            "libido": (getattr(cat_a, "libido", 0.0) + getattr(cat_b, "libido", 0.0)) / 2.0,
                            "inbredness": coi,
                        }

                    for stat_idx, stat in enumerate(STAT_NAMES, start=5):
                        if stat_values is not None:
                            val = int(stat_values.get(stat, 0))
                            label = str(val)
                            base = STAT_COLORS.get(val, QColor(100, 100, 115))
                            bg = self._stat_tint(base, strength=0.28, lift=18)
                            tip = f"Actual {stat}: {val}"
                        else:
                            lo, hi = projection["stat_ranges"].get(stat, (0, 0))
                            label = f"{lo}" if lo == hi else f"{lo}-{hi}"
                            base = STAT_COLORS.get(max(lo, hi), QColor(100, 100, 115))
                            bg = self._stat_tint(base, strength=0.22, lift=18)
                            tip = f"Projected {stat}: {lo}-{hi} (expected {float(projection.get('expected_stats', {}).get(stat, 0.0)):.1f})"
                        self._table.setItem(current_row, stat_idx, self._metric_item(label, "", bg, tip))

                    for trait_idx, field in enumerate(("aggression", "libido", "inbredness"), start=12):
                        value = float(trait_values[field])
                        label = _trait_label_from_value(field, value) or "unknown"
                        bg = _trait_level_color(label)
                        tip = f"{field.title()}: {value:.3f} ({label})"
                        self._table.setItem(current_row, trait_idx, self._metric_item(label, "", bg, tip))

                    note_text = "Projected" if child is None else ""
                    note_item = QTableWidgetItem(note_text)
                    note_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    note_item.setForeground(QBrush(QColor(216, 181, 106) if child is None else QColor(155, 168, 196)))
                    note_item.setToolTip("Projected offspring" if child is None else "")
                    self._table.setItem(current_row, 15, note_item)

                    self._table.setRowHeight(current_row, max(self._table.rowHeight(current_row), 38))

                row_idx += span
        finally:
            if 0 <= restore_row < self._table.rowCount() and 0 <= restore_column < self._table.columnCount():
                self._table.setCurrentCell(restore_row, restore_column)

    def set_save_path(self, save_path: Optional[str], *, refresh_existing: bool = True):
        self._save_path = save_path
        self._selected_child_uid_by_pair_key = _load_perfect_planner_selected_offspring(self._save_path)
        if refresh_existing and self._rows:
            self.set_rows(self._rows)

    def reset_to_defaults(self):
        self._selected_offspring_by_pair = {}
        self._selected_child_uid_by_pair_key = {}
        _save_perfect_planner_selected_offspring(self._selected_child_uid_by_pair_key, self._save_path)
        if self._rows:
            self.set_rows(self._rows)
        else:
            self._table.clearSelection()

    def clear(self):
        self._rows = []
        self._render_rows = []
        self._table.clearSpans()
        self._table.setRowCount(0)
        self._summary.setText(_tr(
            "perfect_planner.offspring_tracker.summary_empty",
            default="Build a plan to track offspring outcomes.",
        ))

    def _on_cell_clicked(self, row: int, column: int):
        if column == 2 and 0 <= row < len(self._render_rows):
            render_row = self._render_rows[row]
            child = render_row.get("child")
            if child is not None:
                pair_row = render_row.get("pair", {})
                cat_a = pair_row.get("cat_a")
                cat_b = pair_row.get("cat_b")
                if hasattr(cat_a, "db_key") and hasattr(cat_b, "db_key"):
                    self._set_selected_child(cat_a, cat_b, child)
                    self.set_rows(self._rows)
                if self._navigate_to_cat_callback is not None:
                    self._navigate_to_cat_callback(int(child.db_key))
                if self._select_offspring_callback is not None:
                    self._select_offspring_callback(render_row)
                return
            if self._select_offspring_callback is not None:
                self._select_offspring_callback(render_row)
            return
        if column == 3 and 0 <= row < len(self._render_rows):
            render_row = self._render_rows[row]
            child = render_row.get("child")
            if child is None:
                return
            pair_row = render_row.get("pair", {})
            cat_a = pair_row.get("cat_a")
            cat_b = pair_row.get("cat_b")
            if hasattr(cat_a, "db_key") and hasattr(cat_b, "db_key"):
                self._set_selected_child(cat_a, cat_b, child)
                self.set_rows(self._rows)
            if self._select_offspring_callback is not None:
                self._select_offspring_callback(render_row)
            return
        if column not in (0, 1):
            return
        if self._navigate_to_cat_callback is None:
            return
        item = self._table.item(row, column)
        if item is None:
            return
        db_key = item.data(Qt.UserRole)
        if db_key is not None:
            self._navigate_to_cat_callback(int(db_key))


class PerfectPlannerFoundationPairsPanel(QWidget):
    """Persistent editor for the four foundation breeding pairs."""

    configChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QComboBox { background:#1a1a32; color:#ddd; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:2px 6px; }"
            "QComboBox QAbstractItemView { background:#101023; color:#ddd; "
            "selection-background-color:#252545; }"
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:4px 8px; font-size:11px; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._cats: list[Cat] = []
        self._cat_by_uid: dict[str, Cat] = {}
        self._slots: list[dict] = []
        self._save_path: Optional[str] = None
        self._stored_config = _load_perfect_planner_foundation_pairs(self._save_path)
        self._slot_count = max(4, min(12, len(self._stored_config) or 4))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        self._title = QLabel(_tr("perfect_planner.foundation.title", default="Foundation Pairs"))
        self._title.setStyleSheet("color:#ddd; font-size:13px; font-weight:bold;")
        self._summary = QLabel("")
        self._summary.setStyleSheet("color:#666; font-size:11px;")
        header.addWidget(self._title)
        header.addStretch()
        header.addWidget(self._summary)
        root.addLayout(header)

        self._desc = QLabel(_tr(
            "perfect_planner.foundation.description",
            default="Pick the starting pairs you plan to use, then mark each one as suggested or actively used. The selections are saved alongside the current save file.",
        ))
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet("color:#8d8da8; font-size:11px;")
        root.addWidget(self._desc)

        self._rows_widget = QWidget()
        self._rows_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        root.addWidget(self._rows_widget)
        root.addStretch(1)

        self._apply_slot_count(self._slot_count, emit=False)
        self.set_config(self._stored_config)
        self._update_summary()
        _enforce_min_font_in_widget_tree(self)

    @staticmethod
    def _slot_color(slot_index: int) -> QColor:
        color = QColor(PAIR_COLORS[slot_index % len(PAIR_COLORS)])
        return color if color.isValid() else QColor(90, 90, 110)

    @staticmethod
    def _cat_label(cat: Cat) -> str:
        room = cat.room_display or cat.status or "?"
        return f"{cat.name} ({cat.gender_display}) · {room}"

    def _refresh_combo(self, combo: QComboBox, selected_uid: str):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("None", "")
        for cat in sorted(self._cats, key=lambda c: ((c.name or "").lower(), _cat_uid(c))):
            uid = _cat_uid(cat)
            if not uid:
                continue
            combo.addItem(self._cat_label(cat), uid)
            combo.setItemData(combo.count() - 1, self._cat_tooltip(cat), Qt.ToolTipRole)
        idx = combo.findData(selected_uid)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    @staticmethod
    def _cat_tooltip(cat: Cat) -> str:
        room = cat.room_display or cat.status or "?"
        return (
            f"{cat.name}\n"
            f"Room: {room}\n"
            f"Base sum: {sum(cat.base_stats.values())}"
        )

    def _slot_values(self, slot: dict) -> tuple[str, str, bool]:
        a_uid = str(slot["combo_a"].currentData() or "").strip().lower()
        b_uid = str(slot["combo_b"].currentData() or "").strip().lower()
        using = bool(slot["use_btn"].isChecked())
        return a_uid, b_uid, using

    def _update_slot_style(self, slot: dict):
        slot_index = slot["slot_index"]
        color = self._slot_color(slot_index)
        a_uid, b_uid, using = self._slot_values(slot)
        selected = bool(a_uid and b_uid)
        accent = color.lighter(125 if using else 102)
        bg = color.darker(220 if using else 260)
        state_text = _tr("perfect_planner.foundation.using", default="Using these") if using else _tr("perfect_planner.foundation.suggested", default="Suggested")
        if selected:
            slot["state_lbl"].setText(state_text)
            slot["state_lbl"].setStyleSheet(
                f"color:#fff; background:rgba({accent.red()},{accent.green()},{accent.blue()},160);"
                " border:1px solid rgba(255,255,255,40); border-radius:4px; padding:2px 6px;"
                " font-size:10px; font-weight:bold;"
            )
        else:
            slot["state_lbl"].setText(_tr("perfect_planner.foundation.empty", default="Empty"))
            slot["state_lbl"].setStyleSheet(
                "color:#888; background:#15152e; border:1px solid #242447; "
                "border-radius:4px; padding:2px 6px; font-size:10px;"
            )
        if not selected and slot["use_btn"].isChecked():
            slot["use_btn"].blockSignals(True)
            slot["use_btn"].setChecked(False)
            slot["use_btn"].blockSignals(False)
        slot["use_btn"].setEnabled(selected)
        slot["use_btn"].setText(state_text)
        slot["use_btn"].setStyleSheet(
            "QPushButton { "
            f"background:rgba({bg.red()},{bg.green()},{bg.blue()},180); color:#f2f2f7; "
            f"border:1px solid rgba({accent.red()},{accent.green()},{accent.blue()},180);"
            " border-radius:4px; padding:4px 8px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#252545; color:#fff; }"
            "QPushButton:checked { background:#2a5a3a; color:#f0fff0; border-color:#4a8a5a; }"
        )
        slot["widget"].setStyleSheet(
            "QFrame { "
            f"background:rgba({max(16, accent.red()//5)},{max(16, accent.green()//5)},{max(16, accent.blue()//5)},120);"
            " border:1px solid #242447; border-radius:6px; }"
        )
        slot["idx_lbl"].setStyleSheet(
            "QLabel { "
            f"color:#fff; background:rgba({accent.red()},{accent.green()},{accent.blue()},190);"
            " border:1px solid rgba(255,255,255,30); border-radius:4px; padding:2px 4px;"
            " font-size:10px; font-weight:bold; }"
        )
        slot["swatch"].setStyleSheet(
            f"background:{accent.name()}; border-radius:3px;"
        )

    def _clear_slot_widgets(self):
        for slot in self._slots:
            self._rows_layout.removeWidget(slot["widget"])
            slot["widget"].deleteLater()
        self._slots = []

    def _apply_slot_count(self, count: int, emit: bool = True):
        count = max(1, min(12, int(count or 1)))
        if count == self._slot_count and len(self._slots) == count:
            return
        current = self._stored_config[:]
        self._clear_slot_widgets()
        self._slot_count = count
        if len(current) < count:
            current.extend([
                {"cat_a_uid": "", "cat_b_uid": "", "using": False}
                for _ in range(count - len(current))
            ])
        self._stored_config = current
        for slot_index in range(count):
            self._add_slot(slot_index, emit=False)
        self._update_summary()
        if emit:
            self.configChanged.emit()

    def set_slot_count(self, count: int):
        self._apply_slot_count(count, emit=False)
        for slot in self._slots:
            self._refresh_slot(slot)
        self._update_summary()

    def _save(self):
        self._sync_visible_to_stored()
        _save_perfect_planner_foundation_pairs(self._stored_config, self._save_path)
        self._update_summary()
        self.configChanged.emit()

    def _sync_visible_to_stored(self):
        for slot in self._slots:
            idx = slot["slot_index"]
            if idx >= len(self._stored_config):
                self._stored_config.extend([
                    {"cat_a_uid": "", "cat_b_uid": "", "using": False}
                    for _ in range(idx + 1 - len(self._stored_config))
                ])
            self._stored_config[idx] = {
                "cat_a_uid": str(slot["combo_a"].currentData() or "").strip().lower(),
                "cat_b_uid": str(slot["combo_b"].currentData() or "").strip().lower(),
                "using": bool(slot["use_btn"].isChecked()),
            }

    def _add_slot(self, slot_index: int, emit: bool = True):
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 6, 8, 6)
        row_layout.setSpacing(6)

        swatch = QLabel()
        swatch.setFixedWidth(6)
        swatch.setMinimumHeight(24)
        row_layout.addWidget(swatch)

        idx_lbl = QLabel(_tr("perfect_planner.foundation.slot", default="Pair {index}", index=slot_index + 1))
        idx_lbl.setFixedWidth(52)
        idx_lbl.setAlignment(Qt.AlignCenter)
        idx_lbl.setStyleSheet(
            "color:#fff; font-size:10px; font-weight:bold; border-radius:4px; padding:2px 4px;"
        )
        row_layout.addWidget(idx_lbl)

        combo_a = QComboBox()
        combo_a.setMinimumWidth(170)
        combo_a.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row_layout.addWidget(combo_a, 1)

        combo_b = QComboBox()
        combo_b.setMinimumWidth(170)
        combo_b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row_layout.addWidget(combo_b, 1)

        swap_btn = QPushButton("↔")
        swap_btn.setFixedWidth(28)
        row_layout.addWidget(swap_btn)

        clear_btn = QPushButton(_tr("common.clear", default="Clear"))
        clear_btn.setFixedWidth(64)
        row_layout.addWidget(clear_btn)

        use_btn = QPushButton()
        use_btn.setCheckable(True)
        use_btn.setMinimumWidth(110)
        row_layout.addWidget(use_btn)

        state_lbl = QLabel("")
        state_lbl.setFixedWidth(84)
        state_lbl.setAlignment(Qt.AlignCenter)
        row_layout.addWidget(state_lbl)

        slot = {
            "slot_index": slot_index,
            "widget": row,
            "swatch": swatch,
            "idx_lbl": idx_lbl,
            "combo_a": combo_a,
            "combo_b": combo_b,
            "swap_btn": swap_btn,
            "clear_btn": clear_btn,
            "use_btn": use_btn,
            "state_lbl": state_lbl,
        }
        self._slots.append(slot)
        self._rows_layout.addWidget(row)

        def _emit_change():
            self._save()

        def _refresh():
            self._update_slot_style(slot)
            self._update_summary()

        combo_a.currentIndexChanged.connect(lambda _: (_refresh(), _emit_change()))
        combo_b.currentIndexChanged.connect(lambda _: (_refresh(), _emit_change()))
        use_btn.toggled.connect(lambda _: (_refresh(), _emit_change()))
        swap_btn.clicked.connect(lambda: self._swap_slot(slot))
        clear_btn.clicked.connect(lambda: self._clear_slot(slot))

        self._refresh_slot(slot)
        if emit:
            self.configChanged.emit()

    def _refresh_slot(self, slot: dict):
        config_slot = self._stored_config[slot["slot_index"]] if slot["slot_index"] < len(self._stored_config) else {}
        self._refresh_combo(slot["combo_a"], str(config_slot.get("cat_a_uid") or "").strip().lower())
        self._refresh_combo(slot["combo_b"], str(config_slot.get("cat_b_uid") or "").strip().lower())
        slot["use_btn"].blockSignals(True)
        slot["use_btn"].setChecked(bool(config_slot.get("using", False)))
        slot["use_btn"].blockSignals(False)
        self._update_slot_style(slot)

    def _swap_slot(self, slot: dict):
        a_uid = slot["combo_a"].currentData()
        b_uid = slot["combo_b"].currentData()
        slot["combo_a"].blockSignals(True)
        slot["combo_b"].blockSignals(True)
        slot["combo_a"].setCurrentIndex(slot["combo_a"].findData(b_uid))
        slot["combo_b"].setCurrentIndex(slot["combo_b"].findData(a_uid))
        slot["combo_a"].blockSignals(False)
        slot["combo_b"].blockSignals(False)
        self._update_slot_style(slot)
        self._save()

    def _clear_slot(self, slot: dict):
        slot["combo_a"].blockSignals(True)
        slot["combo_b"].blockSignals(True)
        slot["combo_a"].setCurrentIndex(0)
        slot["combo_b"].setCurrentIndex(0)
        slot["combo_a"].blockSignals(False)
        slot["combo_b"].blockSignals(False)
        slot["use_btn"].blockSignals(True)
        slot["use_btn"].setChecked(False)
        slot["use_btn"].blockSignals(False)
        self._update_slot_style(slot)
        self._save()

    def _update_summary(self):
        filled = 0
        using = 0
        for slot in self._slots:
            a_uid, b_uid, is_using = self._slot_values(slot)
            if a_uid and b_uid:
                filled += 1
                if is_using:
                    using += 1
        suggested = filled - using
        self._summary.setText(_tr(
            "perfect_planner.foundation.summary",
            default="{filled} saved | {using} using | {suggested} suggested",
            filled=filled,
            using=using,
            suggested=suggested,
        ))

    def set_cats(self, cats: list[Cat]):
        self._cats = [cat for cat in cats if cat.status != "Gone"]
        self._cat_by_uid = {_cat_uid(cat): cat for cat in self._cats if _cat_uid(cat)}
        for slot in self._slots:
            slot_index = slot["slot_index"]
            config_slot = self._stored_config[slot_index] if slot_index < len(self._stored_config) else {}
            a_uid = str(config_slot.get("cat_a_uid") or "").strip().lower()
            b_uid = str(config_slot.get("cat_b_uid") or "").strip().lower()
            self._refresh_combo(slot["combo_a"], a_uid)
            self._refresh_combo(slot["combo_b"], b_uid)
            slot["use_btn"].blockSignals(True)
            slot["use_btn"].setChecked(bool(config_slot.get("using", False)))
            slot["use_btn"].blockSignals(False)
            self._update_slot_style(slot)
        self._update_summary()

    def get_config(self) -> list[dict]:
        self._sync_visible_to_stored()
        return list(self._stored_config)

    def set_config(self, config: list[dict]):
        normalized = []
        for i, slot in enumerate(config or []):
            if not isinstance(slot, dict):
                slot = {}
            normalized.append({
                "cat_a_uid": str(slot.get("cat_a_uid") or "").strip().lower(),
                "cat_b_uid": str(slot.get("cat_b_uid") or "").strip().lower(),
                "using": bool(slot.get("using", False)),
            })
        if not normalized:
            normalized = _default_perfect_planner_foundation_pairs()
        self._stored_config = normalized
        self._apply_slot_count(max(self._slot_count or 0, len(self._stored_config), 4), emit=False)
        for slot in self._slots:
            self._refresh_slot(slot)
        self._update_summary()

    def set_save_path(self, save_path: Optional[str], *, refresh_existing: bool = True):
        self._save_path = save_path
        self._stored_config = _load_perfect_planner_foundation_pairs(self._save_path)
        self.set_config(self._stored_config)
        if refresh_existing and self._cats:
            self.set_cats(self._cats)

    def reset_to_defaults(self):
        self.set_config(_default_perfect_planner_foundation_pairs())
        self._save()
        if self._cats:
            self.set_cats(self._cats)

    def retranslate_ui(self):
        self._title.setText(_tr("perfect_planner.foundation.title", default="Foundation Pairs"))
        self._desc.setText(_tr(
            "perfect_planner.foundation.description",
            default="Pick the starting pairs you plan to use, then mark each one as suggested or actively used. The selections are saved alongside the current save file.",
        ))
        for slot in self._slots:
            slot_index = slot["slot_index"]
            slot["idx_lbl"].setText(_tr("perfect_planner.foundation.slot", default="Pair {index}", index=slot_index + 1))
            self._update_slot_style(slot)
        self._update_summary()


class PerfectCatPlannerView(QWidget):
    """Stage-based planner for building perfect 7-base-stat lines."""

    @staticmethod
    def _set_toggle_button_label(btn: QPushButton, label: str):
        state = _tr("common.on") if btn.isChecked() else _tr("common.off")
        btn.setText(_tr("bulk.label_template", label=label, state=state))

    @staticmethod
    def _bind_persistent_toggle(btn: QPushButton, label_key: str, key: str, *, default: Optional[str] = None):
        PerfectCatPlannerView._set_toggle_button_label(btn, _tr(label_key, default=default))
        btn.toggled.connect(lambda checked: _set_optimizer_flag(key, checked))
        btn.toggled.connect(lambda _: PerfectCatPlannerView._set_toggle_button_label(btn, _tr(label_key, default=default)))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; }"
            "QHeaderView::section { background:#151532; color:#7d8bb0; border:none; padding:4px; font-weight:bold; }"
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
            "QSpinBox, QDoubleSpinBox { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:3px 6px; }"
        )
        self._cats: list[Cat] = []
        self._excluded_keys: set[int] = set()
        self._cache: Optional[BreedingCache] = None
        self._mutation_planner_view: Optional['MutationDisorderPlannerView'] = None
        self._mutation_planner_traits: list[dict] = []
        self._pending_stage_context: Optional[str] = None
        self._save_path: Optional[str] = None
        self._session_state: dict = _load_planner_state_value("perfect_planner_state", {})
        self._restoring_session_state = False
        self._import_mutation_btn: Optional[QPushButton] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        header = QHBoxLayout()
        self._title = QLabel(_tr("perfect_planner.title"))
        self._title.setStyleSheet("color:#ddd; font-size:18px; font-weight:bold;")
        self._summary = QLabel("")
        self._summary.setStyleSheet("color:#666; font-size:11px;")
        header.addWidget(self._title)
        header.addStretch()
        header.addWidget(self._summary)
        root.addLayout(header)

        self._desc = QLabel()
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet("color:#8d8da8; font-size:11px;")
        root.addWidget(self._desc)

        controls_wrap = QScrollArea()
        controls_wrap.setWidgetResizable(True)
        controls_wrap.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        controls_wrap.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        controls_wrap.setFrameShape(QFrame.NoFrame)
        controls_wrap.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        controls_box = QWidget()
        controls = QHBoxLayout(controls_box)
        controls.setSpacing(8)
        controls.setContentsMargins(0, 0, 0, 0)

        self._min_stats_label = QLabel(_tr("perfect_planner.min_stats"))
        self._min_stats_label.setStyleSheet("color:#888; font-size:11px;")
        controls.addWidget(self._min_stats_label)

        self._min_stats_input = QLineEdit()
        self._min_stats_input.setPlaceholderText(_tr("perfect_planner.placeholder.min_stats"))
        self._min_stats_input.setFixedWidth(60)
        self._min_stats_input.setStyleSheet(
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
        )
        self._min_stats_input.textChanged.connect(lambda _: self._save_session_state())
        controls.addWidget(self._min_stats_input)

        controls.addSpacing(12)

        self._max_risk_label = QLabel(_tr("perfect_planner.max_risk"))
        self._max_risk_label.setStyleSheet("color:#888; font-size:11px;")
        controls.addWidget(self._max_risk_label)

        self._max_risk_input = QLineEdit()
        self._max_risk_input.setPlaceholderText(_tr("perfect_planner.placeholder.max_risk"))
        self._max_risk_input.setFixedWidth(60)
        self._max_risk_input.setStyleSheet(
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
        )
        self._max_risk_input.textChanged.connect(lambda _: self._save_session_state())
        controls.addWidget(self._max_risk_input)

        controls.addSpacing(12)

        self._starter_label = QLabel(_tr("perfect_planner.start_pairs"))
        self._starter_label.setStyleSheet("color:#888; font-size:11px;")
        controls.addWidget(self._starter_label)
        self._starter_pairs_input = QSpinBox()
        self._starter_pairs_input.setRange(1, 12)
        self._starter_pairs_input.setValue(4)
        self._starter_pairs_input.setFixedWidth(60)
        self._starter_pairs_input.setToolTip(_tr("perfect_planner.start_pairs_tooltip"))
        self._starter_pairs_input.valueChanged.connect(lambda _: self._save_session_state())
        controls.addWidget(self._starter_pairs_input)

        controls.addSpacing(12)

        self._stimulation_label = QLabel(_tr("perfect_planner.stimulation"))
        self._stimulation_label.setStyleSheet("color:#888; font-size:11px;")
        controls.addWidget(self._stimulation_label)
        self._stimulation_input = QSpinBox()
        self._stimulation_input.setRange(0, 200)
        self._stimulation_input.setValue(50)
        self._stimulation_input.setFixedWidth(70)
        self._stimulation_input.setToolTip(_tr("perfect_planner.stimulation_tooltip"))
        self._stimulation_input.valueChanged.connect(lambda _: self._save_session_state())
        controls.addWidget(self._stimulation_input)

        controls.addSpacing(12)

        self._plan_btn = QPushButton(_tr("perfect_planner.build_plan"))
        self._plan_btn.setStyleSheet(
            "QPushButton { background:#1f5f4a; color:#f2f7f3; border:1px solid #3f8f72; "
            "border-radius:4px; padding:6px 14px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#26735a; }"
            "QPushButton:pressed { background:#184b3a; }"
        )
        self._plan_btn.clicked.connect(self._calculate_plan)
        controls.addWidget(self._plan_btn)

        controls.addSpacing(12)

        self._deep_optimize_btn = QPushButton()
        self._deep_optimize_btn.setCheckable(True)
        self._deep_optimize_btn.setChecked(_saved_optimizer_flag("perfect_planner_use_sa", False))
        self._deep_optimize_btn.setToolTip(_tr("perfect_planner.more_depth_tooltip", default="Use simulated annealing for a slower, deeper search."))
        self._deep_optimize_btn.setStyleSheet(
            "QPushButton { background:#2a2a5a; color:#bbbbee; border:1px solid #4a4a8a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#3a3a6a; color:#ddd; }"
            "QPushButton:checked { background:#4a4a7a; color:#f0f0ff; border-color:#6a6a9a; }"
            "QPushButton:pressed { background:#202048; }"
            "QPushButton:disabled { background:#1a1a32; color:#555; border-color:#2a2a4a; }"
        )
        self._bind_persistent_toggle(
            self._deep_optimize_btn,
            "perfect_planner.more_depth",
            "perfect_planner_use_sa",
            default="More Depth",
        )
        self._deep_optimize_btn.toggled.connect(lambda _: self._save_session_state())
        controls.addWidget(self._deep_optimize_btn)

        self._import_mutation_btn = QPushButton(_tr(
            "perfect_planner.import_mutation.button",
            default="Import Mutation Planner",
        ))
        self._import_mutation_btn.setMinimumWidth(182)
        self._import_mutation_btn.clicked.connect(self._import_mutation_traits)
        controls.addWidget(self._import_mutation_btn)
        self._sync_mutation_import_button_state()

        self._avoid_lovers_checkbox = QPushButton()
        self._avoid_lovers_checkbox.setCheckable(True)
        self._avoid_lovers_checkbox.setChecked(_saved_optimizer_flag("perfect_planner_avoid_lovers", False))
        self._avoid_lovers_checkbox.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:checked { background:#5a3a2a; color:#ddd; border:1px solid #8a5a4a; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._bind_persistent_toggle(self._avoid_lovers_checkbox, "perfect_planner.toggle.avoid_lovers", "perfect_planner_avoid_lovers")
        self._avoid_lovers_checkbox.toggled.connect(lambda _: self._save_session_state())
        controls.addWidget(self._avoid_lovers_checkbox)

        self._prefer_low_aggression_checkbox = QPushButton()
        self._prefer_low_aggression_checkbox.setCheckable(True)
        self._prefer_low_aggression_checkbox.setChecked(_saved_optimizer_flag("prefer_low_aggression", True))
        self._prefer_low_aggression_checkbox.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:checked { background:#4a2a2a; color:#ddd; border:1px solid #7a4a4a; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._bind_persistent_toggle(
            self._prefer_low_aggression_checkbox,
            "perfect_planner.toggle.prefer_low_aggression",
            "prefer_low_aggression",
        )
        self._prefer_low_aggression_checkbox.toggled.connect(lambda _: self._save_session_state())
        controls.addWidget(self._prefer_low_aggression_checkbox)

        self._prefer_high_libido_checkbox = QPushButton()
        self._prefer_high_libido_checkbox.setCheckable(True)
        self._prefer_high_libido_checkbox.setChecked(_saved_optimizer_flag("prefer_high_libido", True))
        self._prefer_high_libido_checkbox.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:checked { background:#2a4a36; color:#ddd; border:1px solid #4a7a5a; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._bind_persistent_toggle(
            self._prefer_high_libido_checkbox,
            "perfect_planner.toggle.prefer_high_libido",
            "prefer_high_libido",
        )
        self._prefer_high_libido_checkbox.toggled.connect(lambda _: self._save_session_state())
        controls.addWidget(self._prefer_high_libido_checkbox)

        controls.addStretch()

        controls_wrap.setWidget(controls_box)
        root.addWidget(controls_wrap)

        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.setObjectName("perfect_planner_main_splitter")
        self._splitter.setStyleSheet("QSplitter::handle:vertical { background:#1e1e38; }")
        self._selected_stage_row = 0
        self._plan_refresh_timer = QTimer(self)
        self._plan_refresh_timer.setSingleShot(True)
        self._plan_refresh_timer.timeout.connect(self._calculate_plan)

        self._table = QTableWidget(0, 6)
        self._table.setIconSize(QSize(60, 20))
        self._table.setHorizontalHeaderLabels([
            _tr("perfect_planner.table.stage"),
            _tr("perfect_planner.table.goal"),
            _tr("perfect_planner.table.pairs"),
            _tr("perfect_planner.table.coverage"),
            _tr("perfect_planner.table.risk"),
            _tr("perfect_planner.table.details"),
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hh = self._table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.Interactive)
        self._table.setColumnWidth(0, 100)
        self._table.setColumnWidth(1, 260)
        self._table.setColumnWidth(2, 60)
        self._table.setColumnWidth(3, 60)
        self._table.setColumnWidth(4, 70)
        self._table.setColumnWidth(5, 400)
        self._table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self._table.cellClicked.connect(self._on_stage_cell_clicked)
        self._splitter.addWidget(self._table)

        self._details_pane = PerfectPlannerDetailPanel()
        self._details_pane.setMinimumWidth(500)
        self._detail_actions_header = self._details_pane._actions_table.horizontalHeader()
        self._detail_actions_header.sectionResized.connect(lambda *_: self._save_session_state())
        self._detail_actions_header.sectionMoved.connect(lambda *_: self._save_session_state())
        self._detail_actions_header.sortIndicatorChanged.connect(lambda *_: self._save_session_state())
        self._bottom_splitter = QSplitter(Qt.Horizontal)
        self._bottom_splitter.setObjectName("perfect_planner_bottom_splitter")
        self._bottom_splitter.setStyleSheet("QSplitter::handle:horizontal { background:#1e1e38; }")
        self._bottom_splitter.setChildrenCollapsible(False)
        self._bottom_splitter.addWidget(self._details_pane)

        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.setStyleSheet(
            "QTabWidget::pane { border:1px solid #1e1e38; background:#0a0a18; }"
            "QTabBar::tab { background:#14142a; color:#888; padding:6px 14px; border:1px solid #1e1e38;"
            " border-bottom:none; margin-right:2px; font-size:11px; }"
            "QTabBar::tab:selected { background:#1a1a36; color:#ddd; font-weight:bold; }"
            "QTabBar::tab:hover { background:#1e1e3a; color:#bbb; }"
        )

        self._guide_panel = PerfectPlannerGuidePanel()
        self._bottom_tabs.addTab(self._guide_panel, _tr("perfect_planner.tab.planner_guide", default="Planner Guide"))

        self._foundation_panel = PerfectPlannerFoundationPairsPanel()
        self._foundation_panel.configChanged.connect(self._request_plan_refresh)
        self._bottom_tabs.addTab(self._foundation_panel, _tr("perfect_planner.tab.foundation_pairs", default="Foundation Pairs"))

        self._offspring_tracker = PerfectPlannerOffspringTracker()
        self._offspring_tracker._select_offspring_callback = self._on_offspring_selected
        self._bottom_tabs.addTab(
            self._offspring_tracker,
            _tr("perfect_planner.tab.offspring_tracker", default="Offspring Tracker"),
        )
        self._cat_locator = RoomOptimizerCatLocator()
        self._bottom_tabs.addTab(self._cat_locator, _tr("perfect_planner.tab.cat_locator"))
        self._bottom_tabs.setCurrentIndex(0)

        self._bottom_splitter.addWidget(self._bottom_tabs)
        self._bottom_splitter.setStretchFactor(0, 3)
        self._bottom_splitter.setStretchFactor(1, 2)
        self._bottom_splitter.setSizes([760, 520])
        self._splitter.addWidget(self._bottom_splitter)
        self._splitter.setSizes([200, 520])
        self._splitter.splitterMoved.connect(lambda *_: self._save_session_state())
        self._bottom_splitter.splitterMoved.connect(lambda *_: self._save_session_state())
        root.addWidget(self._splitter, 1)

        self.retranslate_ui()
        PerfectCatPlannerView._restore_session_state(self)
        _enforce_min_font_in_widget_tree(self)

    def retranslate_ui(self):
        self._title.setText(_tr("perfect_planner.title"))
        self._desc.setText(_tr("perfect_planner.description"))
        self._min_stats_label.setText(_tr("perfect_planner.min_stats"))
        self._min_stats_input.setPlaceholderText(_tr("perfect_planner.placeholder.min_stats"))
        self._max_risk_label.setText(_tr("perfect_planner.max_risk"))
        self._max_risk_input.setPlaceholderText(_tr("perfect_planner.placeholder.max_risk"))
        self._starter_label.setText(_tr("perfect_planner.start_pairs"))
        self._starter_pairs_input.setToolTip(_tr("perfect_planner.start_pairs_tooltip"))
        self._stimulation_label.setText(_tr("perfect_planner.stimulation"))
        self._stimulation_input.setToolTip(_tr("perfect_planner.stimulation_tooltip"))
        self._plan_btn.setText(_tr("perfect_planner.build_plan"))
        self._import_mutation_btn.setText(_tr(
            "perfect_planner.import_mutation.button",
            default="Import Mutation Planner",
        ))
        self._set_toggle_button_label(self._deep_optimize_btn, _tr("perfect_planner.more_depth", default="More Depth"))
        self._deep_optimize_btn.setToolTip(_tr("perfect_planner.more_depth_tooltip", default="Use simulated annealing for a slower, deeper search."))
        self._sync_mutation_import_button_state()
        self._table.setHorizontalHeaderLabels([
            _tr("perfect_planner.table.stage"),
            _tr("perfect_planner.table.goal"),
            _tr("perfect_planner.table.pairs"),
            _tr("perfect_planner.table.coverage"),
            _tr("perfect_planner.table.risk"),
            _tr("perfect_planner.table.details"),
        ])
        self._bottom_tabs.setTabText(0, _tr("perfect_planner.tab.planner_guide", default="Planner Guide"))
        self._bottom_tabs.setTabText(1, _tr("perfect_planner.tab.foundation_pairs", default="Foundation Pairs"))
        self._bottom_tabs.setTabText(2, _tr("perfect_planner.tab.offspring_tracker", default="Offspring Tracker"))
        self._bottom_tabs.setTabText(3, _tr("perfect_planner.tab.cat_locator"))
        self._guide_panel.retranslate_ui()
        self._foundation_panel.retranslate_ui()
        self._set_toggle_button_label(self._avoid_lovers_checkbox, _tr("perfect_planner.toggle.avoid_lovers"))
        self._set_toggle_button_label(self._prefer_low_aggression_checkbox, _tr("perfect_planner.toggle.prefer_low_aggression"))
        self._set_toggle_button_label(self._prefer_high_libido_checkbox, _tr("perfect_planner.toggle.prefer_high_libido"))
        self._details_pane.retranslate_ui()
        self._details_pane.show_stage(None)
        self._cat_locator.retranslate_ui()
        self._offspring_tracker.retranslate_ui()

    def _request_plan_refresh(self):
        if not self._cats:
            return
        self._plan_refresh_timer.start(80)

    def _stage_data_for_row(self, row: int) -> Optional[dict]:
        if not (0 <= row < self._table.rowCount()):
            return None
        stage_item = self._table.item(row, 0)
        if stage_item is None:
            return None
        data = stage_item.data(Qt.UserRole)
        return data if isinstance(data, dict) else None

    def _show_stage_row(self, row: int, context_note: Optional[str] = None):
        data = self._stage_data_for_row(row)
        if isinstance(data, dict):
            self._details_pane.show_stage(data, context_note=context_note)
        else:
            self._details_pane.show_stage(None)

    def _on_table_selection_changed(self):
        selected_ranges = self._table.selectedRanges()
        if not selected_ranges:
            self._details_pane.show_stage(None)
            self._pending_stage_context = None
            return
        row = selected_ranges[0].topRow()
        self._selected_stage_row = row
        self._show_stage_row(row, context_note=self._pending_stage_context)
        self._pending_stage_context = None

    def _on_stage_cell_clicked(self, row: int, column: int):
        if not (0 <= row < self._table.rowCount()):
            return
        self._selected_stage_row = row
        self._table.selectRow(row)
        self._show_stage_row(row, context_note=self._pending_stage_context)
        self._pending_stage_context = None

    def _on_offspring_selected(self, row: dict):
        if not row:
            return
        if self._table.rowCount() <= 0:
            return
        pair_row = row.get("pair", row)
        children = pair_row.get("known_offspring", [])
        if children:
            offspring_names = ", ".join(child.name for child in children[:3])
            if len(children) > 3:
                offspring_names += f" +{len(children) - 3} more"
        else:
            offspring_names = "No tracked offspring"
        selected_child = row.get("child")
        selected_child_text = f" | Selected: {selected_child.name}" if selected_child is not None else ""
        context_note = (
            f"Selected offspring pair: {pair_row['cat_a'].name} x {pair_row['cat_b'].name}"
            f"{selected_child_text} | "
            f"Offspring: {offspring_names}"
        )
        self._pending_stage_context = context_note
        self._show_stage_row(self._selected_stage_row, context_note=context_note)
        self._request_plan_refresh()

    @property
    def cat_locator(self):
        return self._cat_locator

    @property
    def offspring_tracker(self):
        return self._offspring_tracker

    def sync_mutation_traits(self):
        self._sync_mutation_traits()

    def sync_mutation_import_button_state(self):
        self._sync_mutation_import_button_state()

    def save_session_state(self, **kwargs):
        self._save_session_state(**kwargs)

    def set_cats(self, cats: list[Cat], excluded_keys: set[int] = None):
        self._cats = cats
        blacklisted_keys = {c.db_key for c in cats if c.is_blacklisted}
        self._excluded_keys = (excluded_keys or set()) | blacklisted_keys
        alive_count = len([c for c in cats if c.status != "Gone"])
        excluded_count = len([c for c in cats if c.status != "Gone" and c.db_key in self._excluded_keys])
        if excluded_count > 0:
            self._summary.setText(_tr("perfect_planner.summary.with_excluded", alive=alive_count, excluded=excluded_count))
        else:
            self._summary.setText(_tr("perfect_planner.summary.no_excluded", alive=alive_count))
        self._sync_mutation_traits()
        self._foundation_panel.set_cats([c for c in cats if c.status != "Gone" and c.db_key not in self._excluded_keys])
        if self._session_state.get("has_run") and len([c for c in cats if c.status != "Gone" and c.db_key not in self._excluded_keys]) >= 2:
            self._calculate_plan()

    def set_cache(self, cache: Optional['BreedingCache']):
        self._cache = cache

    def sync_from_room_config(self, room_config: list[dict], available_rooms: list[str] | None = None):
        room_configs = build_room_configs(room_config, available_rooms=available_rooms)
        if not room_configs:
            return

        stim = best_breeding_room_stimulation(room_configs, fallback=float(self._stimulation_input.value() or 50))
        stim_value = max(0, min(200, int(round(float(stim)))))

        self._stimulation_input.blockSignals(True)
        try:
            self._stimulation_input.setValue(stim_value)
        finally:
            self._stimulation_input.blockSignals(False)
        self._stimulation_input.setToolTip(
            f"{_tr('perfect_planner.stimulation_tooltip')} Current room default: {stim_value}"
        )

        self._save_session_state()

    def set_mutation_planner_view(self, planner: Optional['MutationDisorderPlannerView']):
        if self._mutation_planner_view is not None and hasattr(self._mutation_planner_view, "traitsChanged"):
            try:
                self._mutation_planner_view.traitsChanged.disconnect(self._on_mutation_traits_changed)
            except (TypeError, RuntimeError):
                pass
        self._mutation_planner_view = planner
        if self._mutation_planner_view is not None and hasattr(self._mutation_planner_view, "traitsChanged"):
            try:
                self._mutation_planner_view.traitsChanged.connect(self._on_mutation_traits_changed)
            except (TypeError, RuntimeError):
                pass
        self._sync_mutation_traits()
        self._sync_mutation_import_button_state()
        if self.isVisible() and self._cats:
            self._request_plan_refresh()

    def set_save_path(self, save_path: Optional[str], *, refresh_existing: bool = True):
        self._save_path = save_path
        self._foundation_panel.set_save_path(save_path, refresh_existing=refresh_existing)
        self._offspring_tracker.set_save_path(save_path, refresh_existing=refresh_existing)
        if refresh_existing and self._cats:
            self.set_cats(self._cats, self._excluded_keys)
            return
        self._restore_session_state()
        self._sync_mutation_traits()
        self._sync_mutation_import_button_state()

    def _sync_mutation_traits(self) -> bool:
        traits = self._mutation_planner_view.get_selected_traits() if self._mutation_planner_view is not None else []
        normalized = [dict(t) for t in traits]
        if normalized == self._mutation_planner_traits:
            return False
        self._mutation_planner_traits = normalized
        return True

    def _mutation_import_button_label(self) -> str:
        if not self._mutation_planner_traits:
            return _tr("room_optimizer.import_none", default="No Mutations Imported")
        summary = _planner_import_traits_summary(self._mutation_planner_traits)
        return _tr("room_optimizer.imported", summary=summary, default=f"Imported: {summary}")

    def _mutation_import_button_tooltip(self) -> str:
        return _planner_import_traits_tooltip(
            self._mutation_planner_traits,
            empty_text=_tr(
                "perfect_planner.import_mutation.tooltip_empty",
                default="Select traits in the mutation planner first.",
            ),
        )

    def _on_mutation_traits_changed(self):
        changed = self._sync_mutation_traits()
        self._sync_mutation_import_button_state()
        if changed and self.isVisible():
            self._request_plan_refresh()

    def _sync_mutation_import_button_state(self):
        if self._import_mutation_btn is None:
            return
        active = bool(self._mutation_planner_traits)
        self._import_mutation_btn.setText(self._mutation_import_button_label())
        RoomOptimizerView._style_import_planner_button(self._import_mutation_btn, active=active)
        self._import_mutation_btn.setEnabled(True)
        self._import_mutation_btn.setToolTip(self._mutation_import_button_tooltip())

    def _import_mutation_traits(self):
        if not self._sync_mutation_traits():
            # Even if nothing changed, the user explicitly requested a refresh.
            pass
        if not self._mutation_planner_traits:
            return
        self._sync_mutation_import_button_state()
        self._request_plan_refresh()

    def _session_state_payload(self, *, has_run: Optional[bool] = None) -> dict:
        state = dict(self._session_state) if isinstance(self._session_state, dict) else {}
        actions_table_header_state = ""
        try:
            actions_table_header_state = self._details_pane._actions_table.horizontalHeader().saveState().toBase64().data().decode("ascii")
        except Exception:
            actions_table_header_state = ""
        state.update({
            "min_stats": self._min_stats_input.text().strip(),
            "max_risk": self._max_risk_input.text().strip(),
            "starter_pairs": int(self._starter_pairs_input.value()),
            "stimulation": int(self._stimulation_input.value()),
            "use_sa": bool(self._deep_optimize_btn.isChecked()),
            "avoid_lovers": bool(self._avoid_lovers_checkbox.isChecked()),
            "prefer_low_aggression": bool(self._prefer_low_aggression_checkbox.isChecked()),
            "prefer_high_libido": bool(self._prefer_high_libido_checkbox.isChecked()),
            "splitter_sizes": list(self._splitter.sizes()) if hasattr(self, "_splitter") else [],
            "bottom_splitter_sizes": list(self._bottom_splitter.sizes()) if hasattr(self, "_bottom_splitter") else [],
            "actions_table_header_state": actions_table_header_state,
        })
        if has_run is not None:
            state["has_run"] = bool(has_run)
        else:
            state["has_run"] = bool(state.get("has_run", False))
        return state

    def _save_session_state(self, *, has_run: Optional[bool] = None):
        if getattr(self, "_restoring_session_state", False):
            return
        self._session_state = self._session_state_payload(has_run=has_run)
        _save_planner_state_value("perfect_planner_state", self._session_state, self._save_path)

    def _restore_session_state(self):
        state = _load_planner_state_value("perfect_planner_state", {}, self._save_path)
        if not isinstance(state, dict):
            state = {}
        self._session_state = state
        self._restoring_session_state = True
        try:
            self._min_stats_input.setText(str(state.get("min_stats", "") or ""))
            self._max_risk_input.setText(str(state.get("max_risk", "") or ""))
            self._starter_pairs_input.setValue(int(state.get("starter_pairs", 4) or 4))
            self._stimulation_input.setValue(int(state.get("stimulation", 50) or 50))
            self._deep_optimize_btn.setChecked(bool(state.get("use_sa", False)))
            self._avoid_lovers_checkbox.setChecked(bool(state.get("avoid_lovers", False)))
            self._prefer_low_aggression_checkbox.setChecked(bool(state.get("prefer_low_aggression", True)))
            self._prefer_high_libido_checkbox.setChecked(bool(state.get("prefer_high_libido", True)))
            splitter_sizes = state.get("splitter_sizes", [])
            if isinstance(splitter_sizes, list) and len(splitter_sizes) == 2:
                self._splitter.setSizes([
                    max(10, int(splitter_sizes[0] or 0)),
                    max(10, int(splitter_sizes[1] or 0)),
                ])
            bottom_splitter_sizes = state.get("bottom_splitter_sizes", [])
            if isinstance(bottom_splitter_sizes, list) and len(bottom_splitter_sizes) == 2:
                self._bottom_splitter.setSizes([
                    max(500, int(bottom_splitter_sizes[0] or 0)),
                    max(10, int(bottom_splitter_sizes[1] or 0)),
                ])
            actions_table_header_state = state.get("actions_table_header_state", "")
            if isinstance(actions_table_header_state, str) and actions_table_header_state:
                try:
                    self._details_pane._actions_table.horizontalHeader().restoreState(
                        QByteArray.fromBase64(actions_table_header_state.encode("ascii"))
                    )
                except Exception:
                    pass
        finally:
            self._restoring_session_state = False

    def reset_to_defaults(self):
        """Restore the perfect planner to its built-in default inputs and pane sizes."""
        self._session_state = {}
        self._restoring_session_state = True
        try:
            self._min_stats_input.setText("")
            self._max_risk_input.setText("")
            self._starter_pairs_input.setValue(4)
            self._stimulation_input.setValue(50)
            self._deep_optimize_btn.setChecked(False)
            self._avoid_lovers_checkbox.setChecked(False)
            self._prefer_low_aggression_checkbox.setChecked(True)
            self._prefer_high_libido_checkbox.setChecked(True)
            self._splitter.setSizes([200, 520])
            self._bottom_splitter.setSizes([760, 520])
            self._foundation_panel.reset_to_defaults()
            self._offspring_tracker.reset_to_defaults()
        finally:
            self._restoring_session_state = False
        self.retranslate_ui()
        self._save_session_state(has_run=False)

    def _run_sa_refinement(
        self,
        evaluated_pairs: list[dict],
        selected_pairs: list[dict],
        starter_pairs: int,
        sa_temperature: float,
        sa_neighbors: int,
    ) -> list[dict]:
        """
        Refine greedy perfect-planner pair picks using simulated annealing.

        The SA pass only works with pairs that already satisfy hard constraints:
        sexuality compatibility and max-risk filtering are enforced before this
        method is called.
        """
        if len(selected_pairs) < 2:
            return sorted(selected_pairs, key=lambda pair: pair["score"], reverse=True)

        pair_by_id = {pair["pair_index"]: pair for pair in evaluated_pairs}
        if len(pair_by_id) < 2:
            return sorted(selected_pairs, key=lambda pair: pair["score"], reverse=True)
        neighbors_per_temp = max(1, int(sa_neighbors))

        def _state_key(pair_ids: list[int]) -> tuple[int, ...]:
            return tuple(sorted(pair_ids))

        def _state_pairs(pair_ids: list[int]) -> list[dict]:
            return [pair_by_id[pid] for pid in pair_ids if pid in pair_by_id]

        def _state_score(pair_ids: list[int]) -> float:
            pairs = _state_pairs(pair_ids)
            if not pairs:
                return float("-inf")
            score = sum(pair["score"] for pair in pairs)
            score += len(pairs) * 1000.0
            return score

        def _cats_for_state(pair_ids: list[int], skip_index: Optional[int] = None) -> set[int]:
            used: set[int] = set()
            for idx, pid in enumerate(pair_ids):
                if skip_index is not None and idx == skip_index:
                    continue
                pair = pair_by_id.get(pid)
                if pair is None:
                    continue
                used.add(pair["cat_a"].db_key)
                used.add(pair["cat_b"].db_key)
            return used

        def _candidate_pool(blocked_pair_ids: set[int], used_cats: set[int]) -> list[int]:
            candidates: list[int] = []
            for pair in evaluated_pairs:
                pid = pair["pair_index"]
                if pid in blocked_pair_ids:
                    continue
                cat_ids = {pair["cat_a"].db_key, pair["cat_b"].db_key}
                if cat_ids & used_cats:
                    continue
                candidates.append(pid)
            return candidates

        def _neighbor(pair_ids: list[int]) -> Optional[list[int]]:
            if not pair_ids:
                return None

            if len(pair_ids) < starter_pairs and random.random() < 0.35:
                used_cats = _cats_for_state(pair_ids)
                blocked = set(pair_ids)
                candidates = _candidate_pool(blocked, used_cats)
                if candidates:
                    new_ids = pair_ids[:] + [random.choice(candidates)]
                    return list(_state_key(new_ids))

            if len(pair_ids) > 1 and random.random() < 0.15:
                drop_idx = random.randrange(len(pair_ids))
                new_ids = pair_ids[:drop_idx] + pair_ids[drop_idx + 1:]
                return list(_state_key(new_ids))

            replace_idx = random.randrange(len(pair_ids))
            used_cats = _cats_for_state(pair_ids, skip_index=replace_idx)
            blocked = set(pair_ids)
            blocked.discard(pair_ids[replace_idx])
            candidates = _candidate_pool(blocked, used_cats)
            if not candidates:
                return None
            new_ids = pair_ids[:]
            new_ids[replace_idx] = random.choice(candidates)
            return list(_state_key(new_ids))

        current_ids = list(_state_key([pair["pair_index"] for pair in selected_pairs]))
        current_score = _state_score(current_ids)
        best_ids = current_ids[:]
        best_score = current_score

        positive_deltas: list[float] = []
        probe_ids = current_ids[:]
        probe_score = current_score
        for _ in range(neighbors_per_temp):
            neighbor_ids = _neighbor(probe_ids)
            if neighbor_ids is None:
                break
            neighbor_score = _state_score(neighbor_ids)
            if neighbor_score > probe_score:
                positive_deltas.append(neighbor_score - probe_score)
            probe_ids = neighbor_ids
            probe_score = neighbor_score

        avg_delta = sum(positive_deltas) / len(positive_deltas) if positive_deltas else 1.0
        if sa_temperature > 0:
            temperature = float(sa_temperature)
        else:
            temperature = max(1.0, -avg_delta / math.log(0.8))

        while temperature > 0.1:
            for _ in range(neighbors_per_temp):
                neighbor_ids = _neighbor(current_ids)
                if neighbor_ids is None:
                    continue
                neighbor_score = _state_score(neighbor_ids)
                delta = neighbor_score - current_score
                if delta > 0 or math.exp(delta / temperature) > random.random():
                    current_ids = neighbor_ids
                    current_score = neighbor_score
                    if current_score > best_score:
                        best_ids = current_ids[:]
                        best_score = current_score
            temperature *= 0.9

        refined = _state_pairs(best_ids)
        refined.sort(key=lambda pair: pair["score"], reverse=True)
        return refined

    def _calculate_plan(self):
        self._save_session_state(has_run=True)
        excluded_keys = getattr(self, "_excluded_keys", set())
        alive_cats = [c for c in self._cats if c.status != "Gone" and c.db_key not in excluded_keys]
        excluded_cats = [c for c in self._cats if c.status != "Gone" and c.db_key in excluded_keys]

        min_stats = 0
        try:
            if self._min_stats_input.text().strip():
                min_stats = int(self._min_stats_input.text().strip())
        except ValueError:
            pass

        max_risk = 10.0
        try:
            if self._max_risk_input.text().strip():
                max_risk = float(self._max_risk_input.text().strip())
        except ValueError:
            pass

        starter_pairs = int(self._starter_pairs_input.value())
        stimulation = float(self._stimulation_input.value())
        sa_temperature = _saved_optimizer_search_temperature()
        sa_neighbors = _saved_optimizer_search_neighbors()
        use_sa = self._deep_optimize_btn.isChecked()
        avoid_lovers = self._avoid_lovers_checkbox.isChecked()
        prefer_low_aggression = self._prefer_low_aggression_checkbox.isChecked()
        prefer_high_libido = self._prefer_high_libido_checkbox.isChecked()
        self._sync_mutation_traits()
        planner_traits = list(self._mutation_planner_traits)

        def _mutation_payload(cat_a: Cat, cat_b: Cat) -> dict:
            if not planner_traits:
                return {}
            return {
                "pair": _planner_trait_summary_for_pair(cat_a, cat_b, planner_traits),
                "parents": [
                    _planner_trait_summary_for_cat(cat_a, planner_traits),
                    _planner_trait_summary_for_cat(cat_b, planner_traits),
                ],
            }

        def _stage_mutation_ratio(actions: list[dict]) -> float:
            ratios: list[float] = []
            for action in actions:
                summary = action.get("mutation_summary") or {}
                pair_summary = summary.get("pair") if isinstance(summary, dict) else None
                if isinstance(pair_summary, dict):
                    ratios.append(float(pair_summary.get("ratio", 0.0)))
            return sum(ratios) / len(ratios) if ratios else 0.0

        if min_stats > 0:
            alive_cats = [c for c in alive_cats if sum(c.base_stats.values()) >= min_stats]

        if len(alive_cats) < 2:
            self._table.setRowCount(0)
            self._details_pane.show_stage(None)
            self._cat_locator.clear()
            self._offspring_tracker.clear()
            self._summary.setText(_tr("perfect_planner.status.not_enough_cats"))
            return

        stat_sum = {cat.db_key: sum(cat.base_stats.values()) for cat in alive_cats}
        cache = self._cache
        parent_key_map = {
            cat.db_key: {parent.db_key for parent in get_parents(cat)}
            for cat in alive_cats
        }
        hater_key_map = {
            cat.db_key: {other.db_key for other in getattr(cat, "haters", [])}
            for cat in alive_cats
        }
        lover_key_map = {
            cat.db_key: {other.db_key for other in getattr(cat, "lovers", [])}
            for cat in alive_cats
        }
        has_mutual_lover = {
            cat.db_key
            for cat in alive_cats
            if any(cat.db_key in lover_key_map.get(o.db_key, set()) for o in getattr(cat, "lovers", []))
        }
        lover_locked: set[int] = has_mutual_lover if avoid_lovers else set()
        pair_eval_cache: dict[tuple[int, int], tuple[bool, str, float]] = {}
        pair_factor_cache: dict[tuple[int, int, float], object] = {}

        def _pair_factor_key(cat_a: Cat, cat_b: Cat, stimulation_value: float) -> tuple[int, int, float]:
            a_key, b_key = cat_a.db_key, cat_b.db_key
            return (a_key, b_key, float(stimulation_value)) if a_key < b_key else (b_key, a_key, float(stimulation_value))

        def _score_pair_cached(cat_a: Cat, cat_b: Cat, stimulation_value: float):
            key = _pair_factor_key(cat_a, cat_b, stimulation_value)
            cached = pair_factor_cache.get(key)
            if cached is None:
                cached = score_pair_factors(
                    cat_a,
                    cat_b,
                    hater_key_map=hater_key_map,
                    lover_key_map=lover_key_map,
                    avoid_lovers=avoid_lovers,
                    parent_key_map=parent_key_map,
                    pair_eval_cache=pair_eval_cache,
                    cache=cache,
                    stimulation=stimulation_value,
                    minimize_variance=False,
                    prefer_low_aggression=prefer_low_aggression,
                    prefer_high_libido=prefer_high_libido,
                    planner_traits=planner_traits,
                )
                pair_factor_cache[key] = cached
            return cached

        candidate_pairs = [(cat_a, cat_b) for i, cat_a in enumerate(alive_cats) for cat_b in alive_cats[i + 1:]]

        evaluated_pairs = []
        for pair_index, (cat_a, cat_b) in enumerate(candidate_pairs):
            if not planner_pair_allows_breeding(cat_a, cat_b):
                continue
            if avoid_lovers and (cat_a.db_key in lover_locked or cat_b.db_key in lover_locked):
                if not is_mutual_lover_pair(cat_a, cat_b, lover_key_map):
                    continue
            factors = _score_pair_cached(cat_a, cat_b, stimulation)
            if not factors.compatible or factors.risk > max_risk:
                continue

            projection = factors.projection
            founder_bonus = sum(1.0 for cat in (cat_a, cat_b) if not get_parents(cat)) * 2.0
            must_breed_bonus = 50.0 if cat_a.must_breed or cat_b.must_breed else 0.0
            personality = factors.personality_bonus * 3.0
            planner_bias = planner_pair_bias(cat_a, cat_b)
            ancestry_penalty = planner_inbreeding_penalty(cat_a, cat_b)
            progress_score = (
                projection["seven_plus_total"] * 16.0
                + len(projection["locked_stats"]) * 12.0
                + len(projection["reachable_stats"]) * 6.0
                - len(projection["missing_stats"]) * 7.0
                - projection["distance_total"] * 2.5
                - factors.risk * 1.2
                + founder_bonus
                + personality
                + must_breed_bonus
                + planner_bias
                - ancestry_penalty
                + factors.trait_bonus
                + factors.lover_bonus
            )

            evaluated_pairs.append({
                "pair_index": pair_index,
                "cat_a": cat_a,
                "cat_b": cat_b,
                "risk": factors.risk,
                "projection": projection,
                "score": progress_score,
                "personality": personality,
            })

        evaluated_pairs.sort(
            key=lambda pair: (
                pair["projection"]["seven_plus_total"],
                len(pair["projection"]["locked_stats"]),
                pair["score"],
                stat_sum[pair["cat_a"].db_key] + stat_sum[pair["cat_b"].db_key],
            ),
            reverse=True,
        )

        if hasattr(self, "_foundation_panel"):
            self._foundation_panel.set_slot_count(starter_pairs)
            foundation_slots = self._foundation_panel.get_config()[:starter_pairs]
        else:
            foundation_slots = _load_perfect_planner_foundation_pairs()[:starter_pairs]
        pair_lookup = {_cat_uid(cat): cat for cat in alive_cats if _cat_uid(cat)}
        selected_pairs_by_slot: list[Optional[dict]] = [None] * starter_pairs
        used_keys: set[int] = set()
        plan_notes: list[str] = []
        foundation_input_count = sum(
            1
            for slot in foundation_slots
            if str(slot.get("cat_a_uid") or "").strip() and str(slot.get("cat_b_uid") or "").strip()
        )
        manual_using_count = 0
        extra_foundation_ignored = False

        for slot_index, slot in enumerate(foundation_slots, 1):
            if slot_index > starter_pairs:
                extra_foundation_ignored = True
                break
            if not slot.get("using"):
                continue
            a_uid = str(slot.get("cat_a_uid") or "").strip().lower()
            b_uid = str(slot.get("cat_b_uid") or "").strip().lower()
            if not a_uid and not b_uid:
                continue
            if not a_uid or not b_uid:
                plan_notes.append(f"Foundation pair {slot_index} is missing one cat and was skipped.")
                continue

            cat_a = pair_lookup.get(a_uid)
            cat_b = pair_lookup.get(b_uid)
            if cat_a is None or cat_b is None:
                plan_notes.append(f"Foundation pair {slot_index} references a cat that is no longer available.")
                continue
            if cat_a.db_key == cat_b.db_key:
                plan_notes.append(f"Foundation pair {slot_index} uses the same cat twice and was skipped.")
                continue
            if cat_a.db_key in used_keys or cat_b.db_key in used_keys:
                plan_notes.append(f"Foundation pair {slot_index} reuses a cat from another pair and was skipped.")
                continue
            if not planner_pair_allows_breeding(cat_a, cat_b):
                plan_notes.append(f"Foundation pair {slot_index} is not a valid breeding pair.")
                continue

            factors = _score_pair_cached(cat_a, cat_b, stimulation)
            if not factors.compatible or factors.risk > max_risk:
                plan_notes.append(f"Foundation pair {slot_index} exceeded the current risk limit.")
                continue

            source = "using"
            manual_using_count += 1

            selected_pairs_by_slot[slot_index - 1] = {
                "pair_index": len(evaluated_pairs) + slot_index,
                "cat_a": cat_a,
                "cat_b": cat_b,
                "risk": factors.risk,
                "projection": factors.projection,
                "score": 999999.0,
                "personality": factors.personality_bonus * 3.0,
                "source": source,
                "slot_index": slot_index,
                "manual": True,
            }
            used_keys.add(cat_a.db_key)
            used_keys.add(cat_b.db_key)

        if extra_foundation_ignored:
            plan_notes.append("Extra foundation pairs beyond Start pairs were ignored.")

        target_pairs = starter_pairs
        for pair in evaluated_pairs:
            if all(slot is not None for slot in selected_pairs_by_slot):
                break
            cat_a = pair["cat_a"]
            cat_b = pair["cat_b"]
            if cat_a.db_key in used_keys or cat_b.db_key in used_keys:
                continue
            for slot_idx, slot in enumerate(selected_pairs_by_slot):
                if slot is None:
                    selected_pairs_by_slot[slot_idx] = {
                        **pair,
                        "source": "suggested",
                        "slot_index": slot_idx + 1,
                        "manual": False,
                    }
                    break
            used_keys.add(cat_a.db_key)
            used_keys.add(cat_b.db_key)

        selected_pairs = [pair for pair in selected_pairs_by_slot if pair is not None]

        if use_sa and len(selected_pairs) >= 2 and foundation_input_count == 0:
            selected_meta = {
                pair["pair_index"]: {
                    "source": pair.get("source", "suggested"),
                    "slot_index": pair.get("slot_index"),
                    "manual": pair.get("manual", False),
                }
                for pair in selected_pairs
            }
            selected_pairs = self._run_sa_refinement(
                evaluated_pairs,
                selected_pairs,
                starter_pairs,
                sa_temperature,
                sa_neighbors,
            )
            for pair in selected_pairs:
                pair.update(selected_meta.get(pair["pair_index"], {}))

        if not selected_pairs:
            self._table.setRowCount(0)
            self._details_pane.show_stage(None)
            self._cat_locator.clear()
            self._offspring_tracker.clear()
            self._summary.setText(_tr("perfect_planner.status.no_pairs_found"))
            return

        header = self._table.horizontalHeader()
        table_sorting_was_enabled = self._table.isSortingEnabled()
        had_sort_indicator = header.isSortIndicatorShown()
        sort_column = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        if table_sorting_was_enabled:
            self._table.setSortingEnabled(False)

        tracker_rows: list[dict] = []
        for idx, pair in enumerate(selected_pairs, 1):
            cat_a = pair["cat_a"]
            cat_b = pair["cat_b"]
            tracker_rows.append({
                "pair_index": idx,
                "cat_a": cat_a,
                "cat_b": cat_b,
                "known_offspring": tracked_offspring(cat_a, cat_b),
                "projection": pair["projection"],
                "risk": pair["risk"],
                "coi": kinship_coi(cat_a, cat_b),
                "shared": shared_ancestor_counts(cat_a, cat_b, recent_depth=3, max_depth=8),
                "source": pair.get("source", "suggested"),
                "slot_index": pair.get("slot_index"),
            })
        self._offspring_tracker.set_rows(tracker_rows)
        self._summary.setText(
            f"{len(selected_pairs)} pairs planned | {manual_using_count} using | {len(selected_pairs) - manual_using_count} suggested"
        )

        def _fmt_stats(stats: list[str]) -> str:
            return ", ".join(stats) if stats else "none"

        def _pair_name(pair: dict) -> str:
            return f"{pair['cat_a'].name} ({pair['cat_a'].gender_display}) x {pair['cat_b'].name} ({pair['cat_b'].gender_display})"

        def _stage1_target_grid(pair: dict) -> dict:
            projection = pair["projection"]
            return {
                "parents": [
                    {
                        "name": f"{pair['cat_a'].name}\n{pair['cat_a'].gender_display}",
                        "stats": pair["cat_a"].base_stats,
                        "sum": sum(pair["cat_a"].base_stats.values()),
                    },
                    {
                        "name": f"{pair['cat_b'].name}\n{pair['cat_b'].gender_display}",
                        "stats": pair["cat_b"].base_stats,
                        "sum": sum(pair["cat_b"].base_stats.values()),
                    },
                ],
                "offspring": {
                    "stats": {
                        stat: {
                            "lo": projection["stat_ranges"][stat][0],
                            "hi": projection["stat_ranges"][stat][1],
                            "expected": projection["expected_stats"][stat],
                        }
                        for stat in STAT_NAMES
                    },
                    "sum_range": projection["sum_range"],
                },
            }

        def _planner_pair_grid(cat_a: Cat, cat_b: Cat, projection: dict) -> dict:
            return {
                "parents": [
                    {
                        "name": f"{cat_a.name}\n{cat_a.gender_display}",
                        "stats": cat_a.base_stats,
                        "sum": sum(cat_a.base_stats.values()),
                    },
                    {
                        "name": f"{cat_b.name}\n{cat_b.gender_display}",
                        "stats": cat_b.base_stats,
                        "sum": sum(cat_b.base_stats.values()),
                    },
                ],
                "offspring": {
                    "stats": {
                        stat: {
                            "lo": projection["stat_ranges"][stat][0],
                            "hi": projection["stat_ranges"][stat][1],
                            "expected": projection["expected_stats"][stat],
                        }
                        for stat in STAT_NAMES
                    },
                    "sum_range": projection["sum_range"],
                },
            }

        def _rotation_candidate(pair: dict) -> Optional[dict]:
            missing_stats = pair["projection"]["missing_stats"]
            if not missing_stats:
                return None
            best = None
            pair_cats = {pair["cat_a"].db_key, pair["cat_b"].db_key}
            for parent in (pair["cat_a"], pair["cat_b"]):
                for candidate in alive_cats:
                    if candidate.db_key in pair_cats:
                        continue
                    if not planner_pair_allows_breeding(parent, candidate):
                        continue
                    factors = _score_pair_cached(parent, candidate, stimulation)
                    if not factors.compatible or factors.risk > max_risk:
                        continue
                    bring_stats = [stat for stat in missing_stats if candidate.base_stats[stat] >= 7]
                    if not bring_stats:
                        continue
                    planner_bias = planner_pair_bias(parent, candidate)
                    ancestry_penalty = planner_inbreeding_penalty(parent, candidate)
                    score = (
                        len(bring_stats) * 15.0
                        + sum(candidate.base_stats[stat] for stat in bring_stats)
                        - factors.risk
                        + factors.personality_bonus * 3.0
                        + (4.0 if not get_parents(candidate) else 0.0)
                        + planner_bias
                        - ancestry_penalty
                        + factors.trait_bonus
                    )
                    record = {
                        "parent": parent,
                        "candidate": candidate,
                        "risk": factors.risk,
                        "bring_stats": bring_stats,
                        "score": score,
                    }
                    if best is None or record["score"] > best["score"]:
                        best = record
            return best

        stage_rows: list[dict] = []

        stage1_actions = []
        for idx, pair in enumerate(selected_pairs, 1):
            projection = pair["projection"]
            bp = _pair_breakpoint_analysis(pair["cat_a"], pair["cat_b"], stimulation)
            mode = _tr("perfect_planner.foundation.using", default="Using these") if pair.get("source") == "using" else _tr("perfect_planner.foundation.suggested", default="Suggested")
            stage1_actions.append({
                "action": _tr("perfect_planner.action.pair", index=idx),
                "target": f"{mode}: {_pair_name(pair)}",
                "parents": [pair["cat_a"], pair["cat_b"]],
                "mutation_summary": _mutation_payload(pair["cat_a"], pair["cat_b"]),
                "detail_projection": projection,
                "coverage_value": float(projection["seven_plus_total"]),
                "target_grid": _stage1_target_grid(pair),
                "risk": pair["risk"],
                "why": (
                    _tr(
                        "perfect_planner.stage1.why",
                        coverage=f"{projection['seven_plus_total']:.1f}",
                        stim=int(stimulation),
                        headline=bp["headline"],
                        hints=" ".join(bp["hints"][:2]),
                    )
                ),
                "children": (
                    _tr("perfect_planner.stage1.children")
                ),
                "rotate": (
                    _tr("perfect_planner.stage1.rotate")
                ),
            })

        stage_rows.append({
            "stage": _tr("perfect_planner.stage1.title"),
            "goal": (
                f"{len(selected_pairs)} pairs"
                f" | {manual_using_count} using"
                f" | {len(selected_pairs) - manual_using_count} suggested"
            ),
            "pairs": len(selected_pairs),
            "coverage": sum(pair["projection"]["seven_plus_total"] for pair in selected_pairs) / len(selected_pairs) if selected_pairs else 0.0,
            "risk": max((pair["risk"] for pair in selected_pairs), default=0.0),
            "mutation_ratio": _stage_mutation_ratio(stage1_actions),
            "details": _tr("perfect_planner.stage1.details"),
            "summary": _tr("perfect_planner.stage1.summary", count=len(selected_pairs)),
            "notes": [
                _tr("perfect_planner.stage1.note1"),
                _tr("perfect_planner.stage1.note2"),
                *plan_notes[:3],
            ],
            "actions": stage1_actions,
        })

        stage2_actions = []
        for idx, pair in enumerate(selected_pairs, 1):
            projection = pair["projection"]
            stage2_actions.append({
                "action": _tr("perfect_planner.stage2.action", index=idx),
                "target": _tr("perfect_planner.stage2.target", stats=_fmt_stats(projection["locked_stats"])),
                "parents": [pair["cat_a"], pair["cat_b"]],
                "mutation_summary": _mutation_payload(pair["cat_a"], pair["cat_b"]),
                "detail_projection": projection,
                "coverage_value": float(projection["seven_plus_total"]),
                "target_grid": _planner_pair_grid(pair["cat_a"], pair["cat_b"], projection),
                "risk": None,
                "why": _tr("perfect_planner.stage2.why"),
                "children": _tr(
                    "perfect_planner.stage2.children",
                    index=idx,
                    a=pair["cat_a"].name,
                    b=pair["cat_b"].name,
                ),
                "rotate": _tr("perfect_planner.stage2.rotate"),
            })

        stage_rows.append({
            "stage": _tr("perfect_planner.stage2.title"),
            "goal": _tr("perfect_planner.stage2.goal"),
            "pairs": len(stage2_actions),
            "coverage": sum(len(pair["projection"]["locked_stats"]) for pair in selected_pairs) / len(selected_pairs) if selected_pairs else 0.0,
            "risk": 0.0,
            "mutation_ratio": _stage_mutation_ratio(stage2_actions),
            "details": _tr("perfect_planner.stage2.details"),
            "summary": _tr("perfect_planner.stage2.summary"),
            "notes": [
                _tr("perfect_planner.stage2.note1"),
                _tr("perfect_planner.stage2.note2"),
            ],
            "actions": stage2_actions,
        })

        stage3_actions = []
        stage3_import_counts: list[float] = []
        for idx, pair in enumerate(selected_pairs, 1):
            rotation = _rotation_candidate(pair)
            missing = pair["projection"]["missing_stats"]
            if rotation is None:
                stage3_import_counts.append(0.0)
                stage3_actions.append({
                    "action": _tr("perfect_planner.stage3.action_later", index=idx),
                    "target": _tr("perfect_planner.stage3.target_missing", stats=_fmt_stats(missing)),
                    "parents": [pair["cat_a"], pair["cat_b"]],
                    "mutation_summary": _mutation_payload(pair["cat_a"], pair["cat_b"]),
                    "detail_projection": pair["projection"],
                    "coverage_value": float(pair["projection"]["seven_plus_total"]),
                    "risk": None,
                    "why": _tr("perfect_planner.stage3.why_none"),
                    "children": _tr("perfect_planner.stage3.children_none"),
                    "rotate": _tr("perfect_planner.stage3.rotate_none", stats=_fmt_stats(missing)),
                })
            else:
                source_note = (
                    _tr("perfect_planner.stage3.source.founder")
                    if not get_parents(rotation["candidate"])
                    else _tr("perfect_planner.stage3.source.existing")
                )
                rotated_projection = pair_projection(rotation["parent"], rotation["candidate"], stimulation=stimulation)
                rotated_bp = _pair_breakpoint_analysis(rotation["parent"], rotation["candidate"], stimulation)
                stage3_import_counts.append(float(len(rotation["bring_stats"])))
                stage3_actions.append({
                    "action": _tr("perfect_planner.stage3.action_rotation", index=idx),
                    "target": (
                        f"{rotation['parent'].name} ({rotation['parent'].gender_display}) x "
                        f"{rotation['candidate'].name} ({rotation['candidate'].gender_display})"
                    ),
                    "parents": [rotation["parent"], rotation["candidate"]],
                    "mutation_summary": _mutation_payload(rotation["parent"], rotation["candidate"]),
                    "detail_projection": rotated_projection,
                    "coverage_value": float(rotated_projection["seven_plus_total"]),
                    "target_grid": _planner_pair_grid(
                        rotation["parent"],
                        rotation["candidate"],
                        rotated_projection,
                    ),
                    "risk": rotation["risk"],
                    "why": (
                        _tr(
                            "perfect_planner.stage3.why_rotation",
                            source=source_note,
                            index=idx,
                            missing=_fmt_stats(missing),
                            coverage=f"{rotated_projection['seven_plus_total']:.1f}",
                            stim=int(stimulation),
                            headline=rotated_bp["headline"],
                            hints=" ".join(rotated_bp["hints"][:2]),
                        )
                    ),
                    "children": _tr("perfect_planner.stage3.children_rotation"),
                    "rotate": _tr("perfect_planner.stage3.rotate_rotation"),
                })

        stage_rows.append({
            "stage": _tr("perfect_planner.stage3.title"),
            "goal": _tr("perfect_planner.stage3.goal"),
            "pairs": len(stage3_actions),
            "coverage": sum(stage3_import_counts) / max(1, len(stage3_import_counts)),
            "risk": max(
                [float(action["risk"]) for action in stage3_actions if action["risk"] is not None] or [0.0]
            ),
            "mutation_ratio": _stage_mutation_ratio(stage3_actions),
            "details": _tr("perfect_planner.stage3.details"),
            "summary": _tr("perfect_planner.stage3.summary"),
            "notes": [
                _tr("perfect_planner.stage3.note1"),
                _tr("perfect_planner.stage3.note2"),
            ],
            "actions": stage3_actions,
        })

        stage4_actions = []
        for idx, pair in enumerate(selected_pairs, 1):
            missing = pair["projection"]["missing_stats"]
            if missing:
                stage4_actions.append({
                    "action": _tr("perfect_planner.stage4.action_finish", index=idx),
                    "target": _tr("perfect_planner.stage4.target_finish", stats=_fmt_stats(missing)),
                    "parents": [pair["cat_a"], pair["cat_b"]],
                    "mutation_summary": _mutation_payload(pair["cat_a"], pair["cat_b"]),
                    "detail_projection": pair["projection"],
                    "coverage_value": float(pair["projection"]["seven_plus_total"]),
                    "risk": pair["risk"],
                    "why": _tr("perfect_planner.stage4.why_finish"),
                    "children": _tr("perfect_planner.stage4.children_finish"),
                    "rotate": _tr("perfect_planner.stage4.rotate_finish"),
                })
            else:
                stage4_actions.append({
                    "action": _tr("perfect_planner.stage4.action_maintain", index=idx),
                    "target": _tr("perfect_planner.stage4.target_maintain"),
                    "parents": [pair["cat_a"], pair["cat_b"]],
                    "mutation_summary": _mutation_payload(pair["cat_a"], pair["cat_b"]),
                    "detail_projection": pair["projection"],
                    "coverage_value": float(pair["projection"]["seven_plus_total"]),
                    "risk": pair["risk"],
                    "why": _tr("perfect_planner.stage4.why_maintain"),
                    "children": _tr("perfect_planner.stage4.children_maintain"),
                    "rotate": _tr("perfect_planner.stage4.rotate_maintain"),
                })

        stage_rows.append({
            "stage": _tr("perfect_planner.stage4.title"),
            "goal": _tr("perfect_planner.stage4.goal"),
            "pairs": len(stage4_actions),
            "coverage": sum(len(pair["projection"]["reachable_stats"]) for pair in selected_pairs) / len(selected_pairs) if selected_pairs else 0.0,
            "risk": max((pair["risk"] for pair in selected_pairs), default=0.0),
            "mutation_ratio": _stage_mutation_ratio(stage4_actions),
            "details": _tr("perfect_planner.stage4.details"),
            "summary": _tr("perfect_planner.stage4.summary"),
            "notes": [
                _tr("perfect_planner.stage4.note1"),
                _tr("perfect_planner.stage4.note2"),
            ],
            "actions": stage4_actions,
        })

        self._table.setRowCount(0)
        self._details_pane.show_stage(None)

        for row_idx, stage in enumerate(stage_rows):
            self._table.insertRow(row_idx)
            stage_item = QTableWidgetItem(stage["stage"])
            stage_item.setData(Qt.UserRole, stage)
            stage_item.setTextAlignment(Qt.AlignCenter)

            goal_item = QTableWidgetItem(stage["goal"])
            pair_item = QTableWidgetItem(str(stage["pairs"]))
            pair_item.setTextAlignment(Qt.AlignCenter)

            coverage_value = float(stage["coverage"])
            coverage_item = QTableWidgetItem(f"{coverage_value:.1f}/7")
            coverage_item.setTextAlignment(Qt.AlignCenter)
            if coverage_value >= 6.0:
                coverage_item.setForeground(QBrush(QColor(98, 194, 135)))
            elif coverage_value >= 4.5:
                coverage_item.setForeground(QBrush(QColor(216, 181, 106)))
            else:
                coverage_item.setForeground(QBrush(QColor(190, 145, 40)))

            risk_value = float(stage["risk"])
            risk_item = QTableWidgetItem(f"{risk_value:.0f}%")
            risk_item.setTextAlignment(Qt.AlignCenter)
            if risk_value >= 20:
                risk_item.setForeground(QBrush(QColor(217, 119, 119)))
            elif risk_value > 0:
                risk_item.setForeground(QBrush(QColor(216, 181, 106)))
            else:
                risk_item.setForeground(QBrush(QColor(98, 194, 135)))

            details_item = QTableWidgetItem(stage["details"])
            mutation_ratio = float(stage.get("mutation_ratio", 0.0))
            if abs(mutation_ratio) > 1e-6:
                mutation_color = _planner_trait_color(mutation_ratio)
                mutation_color.setAlpha(85)
                stage_item.setBackground(QBrush(mutation_color))

            self._table.setItem(row_idx, 0, stage_item)
            self._table.setItem(row_idx, 1, goal_item)
            self._table.setItem(row_idx, 2, pair_item)
            self._table.setItem(row_idx, 3, coverage_item)
            self._table.setItem(row_idx, 4, risk_item)
            self._table.setItem(row_idx, 5, details_item)

        if excluded_cats:
            row_idx = self._table.rowCount()
            self._table.insertRow(row_idx)
            stage_item = QTableWidgetItem(_tr("perfect_planner.stage.excluded"))
            stage_item.setTextAlignment(Qt.AlignCenter)
            stage_item.setForeground(QBrush(QColor(170, 120, 120)))
            stage_item.setData(Qt.UserRole, {
                "stage": _tr("perfect_planner.stage.excluded"),
                "excluded_cat_rows": [
                    {
                        "name": f"{cat.name} ({cat.gender_display})",
                        "tags": list(_cat_tags(cat)),
                        "stats": dict(cat.base_stats),
                        "sum": _cat_base_sum(cat),
                        "traits": {
                            "aggression": _trait_label_from_value("aggression", cat.aggression) or "unknown",
                            "libido": _trait_label_from_value("libido", cat.libido) or "unknown",
                            "inbredness": _trait_label_from_value("inbredness", cat.inbredness) or "unknown",
                        },
                    }
                    for cat in excluded_cats
                ],
            })
            details_item = QTableWidgetItem(_tr("perfect_planner.excluded.details"))
            dash_pair = QTableWidgetItem("—"); dash_pair.setTextAlignment(Qt.AlignCenter)
            dash_cov = QTableWidgetItem("—"); dash_cov.setTextAlignment(Qt.AlignCenter)
            dash_risk = QTableWidgetItem("—"); dash_risk.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row_idx, 0, stage_item)
            self._table.setItem(row_idx, 1, QTableWidgetItem(_tr("perfect_planner.excluded.count", count=len(excluded_cats))))
            self._table.setItem(row_idx, 2, dash_pair)
            self._table.setItem(row_idx, 3, dash_cov)
            self._table.setItem(row_idx, 4, dash_risk)
            self._table.setItem(row_idx, 5, details_item)

        # Build cat locator data from all cats involved in the plan
        locator_cats: dict[int, dict] = {}  # keyed by db_key to deduplicate
        room_order_counter = 0
        tracker_rows_by_pair_index = {row["pair_index"]: row for row in tracker_rows}
        for idx, pair in enumerate(selected_pairs):
            pair_label = f"Pair {idx + 1}"
            cat_a, cat_b = pair["cat_a"], pair["cat_b"]
            row_info = tracker_rows_by_pair_index.get(idx + 1, {})
            room_a = cat_a.room_display or cat_a.status or "?"
            room_b = cat_b.room_display or cat_b.status or "?"
            # Pair needs to move if the two cats aren't already in the same room together
            pair_needs_move = (cat_a.status != "In House" or cat_b.status != "In House"
                               or room_a != room_b)
            base_order = float(room_order_counter)
            for cat in (cat_a, cat_b):
                if cat.db_key not in locator_cats:
                    current = cat.room_display or cat.status or "?"
                    current_room_key = cat.room if cat.room in ROOM_DISPLAY else _room_key_from_display(cat.room_display)
                    locator_cats[cat.db_key] = {
                        "name": cat.name,
                        "gender_display": cat.gender_display,
                        "db_key": cat.db_key, "tags": list(_cat_tags(cat)),
                        "has_lover": bool(getattr(cat, "lovers", None)),
                        "age": cat.age if cat.age is not None else cat.db_key,
                        "current_room": current,
                        "current_room_key": current_room_key,
                        "assigned_room": pair_label,
                        "room_order": base_order,
                        "needs_move": pair_needs_move,
                    }
            for child_idx, child in enumerate(row_info.get("known_offspring", []), 1):
                if child.db_key in locator_cats:
                    continue
                current = child.room_display or child.status or "?"
                current_room_key = child.room if child.room in ROOM_DISPLAY else _room_key_from_display(child.room_display)
                locator_cats[child.db_key] = {
                    "name": child.name,
                    "gender_display": child.gender_display,
                    "db_key": child.db_key,
                    "has_lover": bool(getattr(child, "lovers", None)),
                    "tags": list(_cat_tags(child)),
                    "age": child.age if child.age is not None else child.db_key,
                    "current_room": current,
                    "current_room_key": current_room_key,
                    "assigned_room": f"{pair_label} offspring",
                    "room_order": base_order + 0.2 + (child_idx * 0.01),
                    "needs_move": child.status != "In House",
                }

            rotation = _rotation_candidate(pair)
            if rotation is not None:
                cat = rotation["candidate"]
                if cat.db_key not in locator_cats:
                    current = cat.room_display or cat.status or "?"
                    current_room_key = cat.room if cat.room in ROOM_DISPLAY else _room_key_from_display(cat.room_display)
                    locator_cats[cat.db_key] = {
                        "name": cat.name,
                        "gender_display": cat.gender_display,
                        "db_key": cat.db_key, "tags": list(_cat_tags(cat)),
                        "has_lover": bool(getattr(cat, "lovers", None)),
                        "age": cat.age if cat.age is not None else cat.db_key,
                        "current_room": current,
                        "current_room_key": current_room_key,
                        "assigned_room": f"Rotation {idx + 1}",
                        "room_order": base_order + 0.4,
                        "needs_move": cat.status != "In House",
                    }
            room_order_counter += 1
        self._cat_locator.show_assignments(list(locator_cats.values()))

        if excluded_cats:
            self._summary.setText(
                _tr(
                    "perfect_planner.status.planned_with_excluded",
                    pairs=len(selected_pairs),
                    alive=len(alive_cats),
                    excluded=len(excluded_cats),
                ) + f" · {'SA' if use_sa else 'greedy'}"
            )
        else:
            self._summary.setText(
                _tr("perfect_planner.status.planned", pairs=len(selected_pairs), alive=len(alive_cats))
                + f" · {'SA' if use_sa else 'greedy'}"
            )

        if stage_rows:
            self._selected_stage_row = min(max(int(getattr(self, "_selected_stage_row", 0) or 0), 0), len(stage_rows) - 1)
            self._table.selectRow(self._selected_stage_row)
            self._show_stage_row(self._selected_stage_row, context_note=self._pending_stage_context)
        else:
            self._selected_stage_row = 0

        if table_sorting_was_enabled:
            self._table.setSortingEnabled(True)
            if had_sort_indicator and sort_column >= 0:
                self._table.sortItems(sort_column, sort_order)
            else:
                self._table.sortItems(0, Qt.AscendingOrder)


class CalibrationView(QWidget):
    """
    In-app calibration editor for parser-sensitive fields.
    Edits are saved to <save>.calibration.json and applied to app logic.
    """
    calibrationChanged = Signal()

    # Sort order for combo columns (lower = first when ascending)
    _GENDER_SORT    = {"": 0, "male": 1, "female": 2, "?": 3}
    _SEXUALITY_SORT = {"": 0, "straight": 1, "bi": 2, "gay": 3}
    _TRAIT_SORT     = {"": 0, "not": 1, "slightly": 2, "moderately": 3, "highly": 4, "extremely": 5}

    COL_NAME = 0
    COL_STATUS = 1
    COL_TOKEN = 2
    COL_TOKEN_FIELDS = 3
    COL_PARSED_G = 4
    COL_OVR_G = 5
    COL_DEFAULT_SEXUALITY = 6
    COL_OVR_SEXUALITY = 7
    COL_PARSED_AGE = 8
    COL_OVR_AGE = 9
    COL_PARSED_AGG = 10
    COL_OVR_AGG = 11
    COL_PARSED_LIB = 12
    COL_OVR_LIB = 13
    COL_PARSED_INB = 14
    COL_CALC_INB = 15
    COL_OVR_INB = 16
    COL_OVR_STR = 17
    COL_OVR_DEX = 18
    COL_OVR_CON = 19
    COL_OVR_INT = 20
    COL_OVR_SPD = 21
    COL_OVR_CHA = 22
    COL_OVR_LCK = 23

    class _AgeNumericDelegate(QStyledItemDelegate):
        def createEditor(self, parent, option, index):
            editor = QLineEdit(parent)
            # Allow blank (no override) or a non-negative number with up to 3 decimals.
            validator = QRegularExpressionValidator(
                QRegularExpression(r"^$|^\d+(?:\.\d{0,3})?$"),
                editor,
            )
            editor.setValidator(validator)
            return editor

    class _StatDelegate(QStyledItemDelegate):
        def createEditor(self, parent, option, index):
            editor = QLineEdit(parent)
            # Allow blank or integer 0-20
            validator = QRegularExpressionValidator(
                QRegularExpression(r"^$|^([0-9]|1[0-9]|20)$"),
                editor,
            )
            editor.setValidator(validator)
            return editor

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 10px; font-size:11px; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
            "QComboBox { background:#1a1a32; color:#ddd; border:1px solid #2a2a4a; padding:2px 6px; }"
            "QComboBox QAbstractItemView { background:#101023; color:#ddd; selection-background-color:#252545; }"
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; }"
            "QHeaderView::section { background:#151532; color:#7d8bb0; border:none; padding:4px; font-weight:bold; }"
        )
        self._save_path: Optional[str] = None
        self._cats: list[Cat] = []
        self._row_cat: list[Cat] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self._title_label = QLabel()
        self._title_label.setStyleSheet("color:#ddd; font-size:18px; font-weight:bold;")
        root.addWidget(self._title_label)

        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet("color:#8d8da8; font-size:11px;")
        root.addWidget(self._desc_label)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self._search_label = QLabel()
        self._search_label.setStyleSheet("color:#888; font-size:11px;")
        filter_row.addWidget(self._search_label)
        self._search_input = QLineEdit()
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setStyleSheet(
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
        )
        self._search_input.textChanged.connect(self._apply_search_filter)
        filter_row.addWidget(self._search_input, 1)
        root.addLayout(filter_row)

        actions = QHBoxLayout()
        self._save_btn = QPushButton()
        self._reload_btn = QPushButton()
        self._export_btn = QPushButton()
        self._import_btn = QPushButton()
        self._clear_overrides_btn = QPushButton()
        self._clear_overrides_btn.setStyleSheet(
            "QPushButton { background:#3a2a2a; color:#e0a0a0; border:1px solid #5a3a3a; "
            "border-radius:4px; padding:6px 10px; font-size:11px; }"
            "QPushButton:hover { background:#4a3a3a; color:#ffb0b0; }"
        )
        self._status = QLabel("")
        self._status.setStyleSheet("color:#8d8da8; font-size:11px;")
        actions.addWidget(self._save_btn)
        actions.addWidget(self._reload_btn)
        actions.addWidget(self._export_btn)
        actions.addWidget(self._import_btn)
        actions.addWidget(self._clear_overrides_btn)
        actions.addSpacing(16)

        self._bulk_label = QLabel()
        self._bulk_label.setStyleSheet("color:#888; font-size:11px;")
        actions.addWidget(self._bulk_label)

        self._bulk_sexuality_combo = QComboBox()
        self._bulk_sexuality_combo.setFixedWidth(100)
        self._bulk_sexuality_combo.setStyleSheet(
            "QComboBox { background:#1a1a32; color:#ddd; border:1px solid #2a2a4a; padding:2px 6px; }"
            "QComboBox QAbstractItemView { background:#101023; color:#ddd; selection-background-color:#252545; }"
        )
        actions.addWidget(self._bulk_sexuality_combo)

        self._bulk_apply_btn = QPushButton()
        self._bulk_apply_btn.setStyleSheet(
            "QPushButton { background:#2a3a2a; color:#aaa; border:1px solid #3a5a3a; "
            "border-radius:4px; padding:4px 10px; font-size:10px; }"
            "QPushButton:hover { background:#3a4a3a; color:#ddd; }"
        )
        self._bulk_apply_btn.clicked.connect(self._on_bulk_apply_sexuality)
        actions.addWidget(self._bulk_apply_btn)

        self._deselect_btn = QPushButton(_tr("calibration.deselect_all", default="Deselect All"))
        self._deselect_btn.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#888; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:4px 10px; font-size:10px; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        actions.addWidget(self._deselect_btn)

        actions.addStretch()
        actions.addWidget(self._status)
        root.addLayout(actions)

        self._table = QTableWidget(0, 24)
        self._table.setIconSize(QSize(60, 20))
        self._table.setHorizontalHeaderLabels([
            "Name", "Status", "Gender\nToken", "Pre-G\nU32s", "Parsed\nG", "Override\nG",
            "Default\nSexuality", "Sexuality",
            "Parsed\nAge", "Override\nAge",
            "Parsed\nAgg", "Override\nAgg",
            "Parsed\nLibido", "Override\nLibido",
            "Parsed\nInbr", "Calc\nInbr", "Override\nInbr",
            "STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK",
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Allow Ctrl-click for disjoint row picks and Shift-click for ranges.
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        self._table.setItemDelegateForColumn(self.COL_OVR_AGE, self._AgeNumericDelegate(self._table))
        for stat_col in (self.COL_OVR_STR, self.COL_OVR_DEX, self.COL_OVR_CON,
                         self.COL_OVR_INT, self.COL_OVR_SPD, self.COL_OVR_CHA, self.COL_OVR_LCK):
            self._table.setItemDelegateForColumn(stat_col, self._StatDelegate(self._table))
        hh = self._table.horizontalHeader()
        hh.setMinimumSectionSize(40)
        hh.setDefaultAlignment(Qt.AlignCenter)
        hh.setMinimumHeight(36)
        hh.setSectionResizeMode(self.COL_NAME, QHeaderView.Interactive)
        self._table.setColumnWidth(self.COL_NAME, 140)
        hh.setSectionResizeMode(self.COL_STATUS, QHeaderView.Interactive)
        self._table.setColumnWidth(self.COL_STATUS, 92)
        hh.setSectionResizeMode(self.COL_TOKEN, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_TOKEN_FIELDS, QHeaderView.ResizeToContents)
        for col in (self.COL_PARSED_G, self.COL_OVR_G):
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
            self._table.setColumnWidth(col, 68)
        hh.setSectionResizeMode(self.COL_DEFAULT_SEXUALITY, QHeaderView.Interactive)
        self._table.setColumnWidth(self.COL_DEFAULT_SEXUALITY, 80)
        hh.setSectionResizeMode(self.COL_OVR_SEXUALITY, QHeaderView.Interactive)
        self._table.setColumnWidth(self.COL_OVR_SEXUALITY, 80)
        for col in (
            self.COL_PARSED_AGE, self.COL_OVR_AGE,
            self.COL_PARSED_AGG, self.COL_OVR_AGG,
            self.COL_PARSED_LIB, self.COL_OVR_LIB,
            self.COL_PARSED_INB, self.COL_CALC_INB, self.COL_OVR_INB,
        ):
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
            self._table.setColumnWidth(col, 76)
        for col in (self.COL_OVR_AGG, self.COL_OVR_LIB, self.COL_OVR_INB):
            self._table.setColumnWidth(col, 110)
        for stat_col in (self.COL_OVR_STR, self.COL_OVR_DEX, self.COL_OVR_CON,
                         self.COL_OVR_INT, self.COL_OVR_SPD, self.COL_OVR_CHA, self.COL_OVR_LCK):
            hh.setSectionResizeMode(stat_col, QHeaderView.Interactive)
            self._table.setColumnWidth(stat_col, 50)
        self._table.setSortingEnabled(True)
        root.addWidget(self._table, 1)

        self.retranslate_ui()
        self._save_btn.clicked.connect(self._save_clicked)
        self._reload_btn.clicked.connect(self._reload_clicked)
        self._export_btn.clicked.connect(self._export_clicked)
        self._import_btn.clicked.connect(self._import_clicked)
        self._clear_overrides_btn.clicked.connect(self._clear_overrides_clicked)
        self._deselect_btn.clicked.connect(self._table.clearSelection)

    def retranslate_ui(self):
        self._title_label.setText(_tr("calibration.title"))
        self._desc_label.setText(_tr("calibration.description"))
        self._save_btn.setText(_tr("calibration.save"))
        self._reload_btn.setText(_tr("calibration.reload"))
        self._export_btn.setText(_tr("calibration.export"))
        self._import_btn.setText(_tr("calibration.import"))
        self._clear_overrides_btn.setText(_tr("calibration.clear_overrides", default="Clear Overrides"))
        self._deselect_btn.setText(_tr("calibration.deselect_all", default="Deselect All"))
        self._bulk_label.setText(_tr("calibration.bulk_edit_selected"))
        self._search_label.setText(_tr("calibration.search"))
        self._search_input.setPlaceholderText(_tr("calibration.search_placeholder"))
        current_value = self._bulk_sexuality_combo.currentData()
        self._bulk_sexuality_combo.blockSignals(True)
        self._bulk_sexuality_combo.clear()
        self._bulk_sexuality_combo.addItem(_tr("calibration.sexuality.clear", default="— clear —"), "")
        self._bulk_sexuality_combo.addItem(_tr("calibration.sexuality.straight"), "straight")
        self._bulk_sexuality_combo.addItem(_tr("calibration.sexuality.gay"), "gay")
        self._bulk_sexuality_combo.addItem(_tr("calibration.sexuality.bi"), "bi")
        index = self._bulk_sexuality_combo.findData(current_value)
        if index >= 0:
            self._bulk_sexuality_combo.setCurrentIndex(index)
        self._bulk_sexuality_combo.blockSignals(False)
        self._bulk_apply_btn.setText(_tr("calibration.apply_sexuality"))
        self._table.setHorizontalHeaderLabels([
            _tr("calibration.table.name"),
            _tr("calibration.table.status"),
            _tr("calibration.table.gender_token"),
            _tr("calibration.table.pre_gender_u32"),
            _tr("calibration.table.parsed_gender"),
            _tr("calibration.table.override_gender"),
            _tr("calibration.table.default_sexuality"),
            _tr("calibration.table.sexuality"),
            _tr("calibration.table.parsed_age"),
            _tr("calibration.table.override_age"),
            _tr("calibration.table.parsed_agg"),
            _tr("calibration.table.override_agg"),
            _tr("calibration.table.parsed_libido"),
            _tr("calibration.table.override_libido"),
            _tr("calibration.table.parsed_inbr"),
            _tr("calibration.table.calc_inbr", default="Calc\nInbr"),
            _tr("calibration.table.override_inbr"),
            "STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK",
        ])
        if self._save_path and self._cats:
            self.set_context(self._save_path, self._cats)
        _enforce_min_font_in_widget_tree(self)

    @staticmethod
    def _fmt(v) -> str:
        if v is None:
            return ""
        try:
            return f"{float(v):.3f}".rstrip("0").rstrip(".")
        except Exception:
            return str(v)

    @staticmethod
    def _readonly_item(text: str) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        return it

    @staticmethod
    def _fmt_gender_token_fields(cat: Cat) -> str:
        vals = getattr(cat, "gender_token_fields", None)
        if not vals:
            return ""
        return ", ".join(str(int(v)) for v in vals)

    @staticmethod
    def _editable_item(text: str) -> QTableWidgetItem:
        return QTableWidgetItem(text)

    @staticmethod
    def _get_text_item(table: QTableWidget, row: int, col: int) -> str:
        w = table.cellWidget(row, col)
        if isinstance(w, QComboBox):
            return w.currentText().strip()
        it = table.item(row, col)
        return (it.text().strip() if it is not None else "")

    @staticmethod
    def _gender_combo(value: str) -> QComboBox:
        combo = QComboBox()
        combo.addItems(["", "male", "female", "?"])
        idx = combo.findText((value or "").strip().lower(), Qt.MatchFixedString)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        return combo

    @staticmethod
    def _make_sort_item(sort_key: int) -> "_SortKeyItem":
        item = _SortKeyItem()
        item.setData(Qt.UserRole, sort_key)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    @staticmethod
    def _sexuality_combo(value: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem("", "")
        combo.addItem(_tr("calibration.sexuality.bi"), "bi")
        combo.addItem(_tr("calibration.sexuality.gay"), "gay")
        combo.addItem(_tr("calibration.sexuality.straight"), "straight")
        idx = combo.findData((value or "").strip().lower(), Qt.UserRole, Qt.MatchFixedString)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        return combo

    @staticmethod
    def _trait_combo(options: tuple[str, ...], value: str) -> QComboBox:
        combo = QComboBox()
        combo.addItems([""] + list(options))
        idx = combo.findText((value or "").strip().lower(), Qt.MatchFixedString)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        return combo

    @staticmethod
    def _get_optional_float(table: QTableWidget, row: int, col: int):
        txt = CalibrationView._get_text_item(table, row, col)
        if txt == "":
            return None
        try:
            return float(txt)
        except Exception:
            return None

    def set_context(self, save_path: str, cats: list[Cat]):
        self._save_path = save_path
        self._cats = sorted([c for c in cats if c.status != "Gone"], key=lambda c: (c.name or "").lower())
        self._row_cat = []

        data = _load_calibration_data(save_path)
        overrides = data.get("overrides", {}) if isinstance(data, dict) else {}
        if not isinstance(overrides, dict):
            overrides = {}

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._cats))
        for row, cat in enumerate(self._cats):
            self._row_cat.append(cat)
            uid = (cat.unique_id or "").strip().lower()
            ov = overrides.get(uid) if isinstance(overrides.get(uid), dict) else {}

            name_item = self._readonly_item(cat.name or "?")
            name_item.setData(Qt.UserRole, cat)
            icon = _make_tag_icon(_cat_tags(cat), dot_size=10, spacing=3)
            if not icon.isNull():
                name_item.setIcon(icon)
            self._table.setItem(row, self.COL_NAME, name_item)
            self._table.setItem(row, self.COL_STATUS, self._readonly_item(cat.status))
            self._table.setItem(row, self.COL_TOKEN, self._readonly_item(getattr(cat, "gender_token", "") or ""))
            self._table.setItem(row, self.COL_TOKEN_FIELDS, self._readonly_item(self._fmt_gender_token_fields(cat)))
            self._table.setItem(row, self.COL_PARSED_G, self._readonly_item((getattr(cat, "parsed_gender", cat.gender) or "?")))
            g_combo = self._gender_combo(str(ov.get("gender", "") or ""))
            g_sort = self._make_sort_item(self._GENDER_SORT.get((ov.get("gender") or "").lower(), 0))
            self._table.setCellWidget(row, self.COL_OVR_G, g_combo)
            self._table.setItem(row, self.COL_OVR_G, g_sort)
            g_combo.currentIndexChanged.connect(lambda _, c=g_combo, it=g_sort: it.setData(Qt.UserRole, self._GENDER_SORT.get(c.currentText().lower(), 0)))

            self._table.setItem(row, self.COL_DEFAULT_SEXUALITY, self._readonly_item(getattr(cat, "parsed_sexuality", "straight")))
            sex_val = str(ov.get("sexuality", "") or "")
            sex_combo = self._sexuality_combo(sex_val)
            sex_sort = self._make_sort_item(self._SEXUALITY_SORT.get(sex_val, 0))
            self._table.setCellWidget(row, self.COL_OVR_SEXUALITY, sex_combo)
            self._table.setItem(row, self.COL_OVR_SEXUALITY, sex_sort)
            sex_combo.currentIndexChanged.connect(lambda _, c=sex_combo, it=sex_sort: it.setData(Qt.UserRole, self._SEXUALITY_SORT.get(c.currentData() or "", 0)))

            self._table.setItem(row, self.COL_PARSED_AGE, self._readonly_item(self._fmt(getattr(cat, "parsed_age", None))))
            self._table.setItem(row, self.COL_OVR_AGE, self._editable_item(self._fmt(ov.get("age"))))
            self._table.setItem(row, self.COL_PARSED_AGG, self._readonly_item(self._fmt(getattr(cat, "parsed_aggression", None))))
            agg_val = _trait_label_from_value("aggression", ov.get("aggression"))
            agg_combo = self._trait_combo(_CALIBRATION_TRAIT_OPTIONS["aggression"], agg_val)
            agg_sort = self._make_sort_item(self._TRAIT_SORT.get(agg_val, 0))
            self._table.setCellWidget(row, self.COL_OVR_AGG, agg_combo)
            self._table.setItem(row, self.COL_OVR_AGG, agg_sort)
            agg_combo.currentIndexChanged.connect(lambda _, c=agg_combo, it=agg_sort: it.setData(Qt.UserRole, self._TRAIT_SORT.get(c.currentText(), 0)))

            self._table.setItem(row, self.COL_PARSED_LIB, self._readonly_item(self._fmt(getattr(cat, "parsed_libido", None))))
            lib_val = _trait_label_from_value("libido", ov.get("libido"))
            lib_combo = self._trait_combo(_CALIBRATION_TRAIT_OPTIONS["libido"], lib_val)
            lib_sort = self._make_sort_item(self._TRAIT_SORT.get(lib_val, 0))
            self._table.setCellWidget(row, self.COL_OVR_LIB, lib_combo)
            self._table.setItem(row, self.COL_OVR_LIB, lib_sort)
            lib_combo.currentIndexChanged.connect(lambda _, c=lib_combo, it=lib_sort: it.setData(Qt.UserRole, self._TRAIT_SORT.get(c.currentText(), 0)))

            self._table.setItem(row, self.COL_PARSED_INB, self._readonly_item(self._fmt(getattr(cat, "parsed_inbredness", None))))
            # Computed COI from ancestry (set by CatTableModel.load)
            calc_inb = cat.inbredness if cat.inbredness != cat.parsed_inbredness else None
            calc_label = _trait_label_from_value("inbredness", calc_inb) if calc_inb is not None else ""
            calc_text = f"{calc_inb:.3f} ({calc_label})" if calc_inb is not None else "—"
            self._table.setItem(row, self.COL_CALC_INB, self._readonly_item(calc_text))
            inb_val = _trait_label_from_value("inbredness", ov.get("inbredness"))
            inb_combo = self._trait_combo(_CALIBRATION_TRAIT_OPTIONS["inbredness"], inb_val)
            inb_sort = self._make_sort_item(self._TRAIT_SORT.get(inb_val, 0))
            self._table.setCellWidget(row, self.COL_OVR_INB, inb_combo)
            self._table.setItem(row, self.COL_OVR_INB, inb_sort)
            inb_combo.currentIndexChanged.connect(lambda _, c=inb_combo, it=inb_sort: it.setData(Qt.UserRole, self._TRAIT_SORT.get(c.currentText(), 0)))

            # Add base stats override columns
            for i, stat_name in enumerate(STAT_NAMES):
                stat_col = self.COL_OVR_STR + i
                override_val = ov.get("base_stats", {}).get(stat_name, "")
                current_val = cat.base_stats.get(stat_name, 0)
                # Show current value in background, allow override
                item = self._editable_item(str(override_val) if override_val != "" else "")
                item.setToolTip(f"Current: {current_val}")
                self._table.setItem(row, stat_col, item)

        self._table.setSortingEnabled(True)
        self._status.setText(_tr("calibration.status.alive_cats", count=len(self._cats)))
        self._apply_search_filter()

    def _apply_search_filter(self, text: Optional[str] = None):
        needle = (text if text is not None else self._search_input.text()).strip().lower()
        for row in range(self._table.rowCount()):
            if not needle:
                self._table.setRowHidden(row, False)
                continue
            fields = [
                self._get_text_item(self._table, row, self.COL_NAME),
                self._get_text_item(self._table, row, self.COL_STATUS),
                self._get_text_item(self._table, row, self.COL_TOKEN),
                self._get_text_item(self._table, row, self.COL_TOKEN_FIELDS),
                self._get_text_item(self._table, row, self.COL_PARSED_G),
                self._get_text_item(self._table, row, self.COL_OVR_G),
                self._get_text_item(self._table, row, self.COL_DEFAULT_SEXUALITY),
                self._get_text_item(self._table, row, self.COL_OVR_SEXUALITY),
            ]
            match = any(needle in (field or "").lower() for field in fields)
            self._table.setRowHidden(row, not match)

    def _reload_clicked(self):
        if not self._save_path:
            self._status.setText(_tr("calibration.status.no_save_loaded"))
            return
        self.set_context(self._save_path, self._cats)
        self._status.setText(_tr("calibration.status.reloaded"))

    def _collect_calibration_data(self) -> dict:
        overrides: dict[str, dict] = {}
        for row in range(self._table.rowCount()):
            name_item = self._table.item(row, self.COL_NAME)
            cat = name_item.data(Qt.UserRole) if name_item else None
            if cat is None:
                continue
            uid = (cat.unique_id or "").strip().lower()
            if not uid:
                continue

            g = _normalize_override_gender(self._get_text_item(self._table, row, self.COL_OVR_G))
            age = self._get_optional_float(self._table, row, self.COL_OVR_AGE)
            agg = _normalize_trait_override("aggression", self._get_text_item(self._table, row, self.COL_OVR_AGG))
            lib = _normalize_trait_override("libido", self._get_text_item(self._table, row, self.COL_OVR_LIB))
            inb = _normalize_trait_override("inbredness", self._get_text_item(self._table, row, self.COL_OVR_INB))
            sexuality_widget = self._table.cellWidget(row, self.COL_OVR_SEXUALITY)
            sexuality_raw = sexuality_widget.currentData() if isinstance(sexuality_widget, QComboBox) else ""
            sexuality = sexuality_raw if sexuality_raw in ("bi", "gay", "straight") else ""

            # Collect base stats overrides
            base_stats = {}
            for i, stat_name in enumerate(STAT_NAMES):
                stat_col = self.COL_OVR_STR + i
                txt = self._get_text_item(self._table, row, stat_col).strip()
                if txt:
                    try:
                        val = int(txt)
                        if 0 <= val <= 20:
                            base_stats[stat_name] = val
                    except ValueError:
                        pass

            if g or age is not None or agg or lib or inb or sexuality or base_stats:
                ov = {"name": cat.name}
                if g:
                    ov["gender"] = g
                if age is not None:
                    ov["age"] = age
                if agg:
                    ov["aggression"] = agg
                if lib:
                    ov["libido"] = lib
                if inb:
                    ov["inbredness"] = inb
                if sexuality:
                    ov["sexuality"] = sexuality
                if base_stats:
                    ov["base_stats"] = base_stats
                overrides[uid] = ov

        return {
            "version": 1,
            "overrides": overrides,
            "gender_token_map": _learn_gender_token_map(self._cats, overrides),
        }

    def _save_clicked(self):
        if not self._save_path:
            self._status.setText(_tr("calibration.status.no_save_loaded"))
            return

        data = self._collect_calibration_data()
        overrides = data.get("overrides", {}) if isinstance(data, dict) else {}
        if not _save_calibration_data(self._save_path, data):
            self._status.setText(_tr("calibration.status.save_failed"))
            return

        explicit, token_applied, _ = _apply_calibration_data(data, self._cats)
        self._status.setText(
            _tr(
                "calibration.status.saved",
                overrides=len(overrides),
                applied=explicit,
                hints=len(data["gender_token_map"]),
                token=token_applied,
            )
        )
        self.calibrationChanged.emit()

    def _export_clicked(self):
        if not self._save_path:
            self._status.setText(_tr("calibration.status.no_save_loaded"))
            return
        default_path = _calibration_path(self._save_path)
        path, _ = QFileDialog.getSaveFileName(
            self,
            _tr("calibration.dialog.export.title"),
            default_path,
            _tr("calibration.dialog.filter"),
        )
        if not path:
            return
        data = self._collect_calibration_data()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=True)
            self._status.setText(_tr("calibration.status.exported", name=os.path.basename(path)))
        except Exception:
            self._status.setText(_tr("calibration.status.export_failed"))

    def _import_clicked(self):
        if not self._save_path:
            self._status.setText(_tr("calibration.status.no_save_loaded"))
            return
        start = os.path.dirname(_calibration_path(self._save_path))
        path, _ = QFileDialog.getOpenFileName(
            self,
            _tr("calibration.dialog.import.title"),
            start,
            _tr("calibration.dialog.filter"),
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            self._status.setText(_tr("calibration.status.read_failed"))
            return
        if not isinstance(data, dict):
            self._status.setText(_tr("calibration.status.invalid_format"))
            return
        overrides = data.get("overrides", {})
        if not isinstance(overrides, dict):
            overrides = {}
        token_map = data.get("gender_token_map", {})
        if not isinstance(token_map, dict):
            token_map = {}
        normalized = {
            "version": int(data.get("version", 1) or 1),
            "overrides": overrides,
            "gender_token_map": token_map or _learn_gender_token_map(self._cats, overrides),
        }
        if not _save_calibration_data(self._save_path, normalized):
            self._status.setText(_tr("calibration.status.import_failed"))
            return
        explicit, token_applied, _ = _apply_calibration_data(normalized, self._cats)
        self.set_context(self._save_path, self._cats)
        self._status.setText(
            _tr("calibration.status.imported", applied=explicit, token=token_applied, name=os.path.basename(path))
        )
        self.calibrationChanged.emit()

    def _clear_overrides_clicked(self):
        """Clear all manual calibration overrides for all cats."""
        if not self._cats:
            self._status.setText(_tr("calibration.status.no_save_loaded"))
            return

        reply = QMessageBox.question(
            self,
            _tr("calibration.confirm_clear_title", default="Clear All Overrides?"),
            _tr(
                "calibration.confirm_clear_message",
                default="This will clear all manual calibration overrides (age, aggression, libido, inbreeding, stats, sexuality) for all cats. This cannot be undone until you reload. Continue?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Wipe persisted overrides so set_context reloads clean
        if self._save_path:
            cal_data = _load_calibration_data(self._save_path)
            cal_data["overrides"] = {}
            _save_calibration_data(self._save_path, cal_data)

        # Reset cat attributes to parsed values
        for cat in self._cats:
            cat.age = cat.parsed_age
            cat.aggression = cat.parsed_aggression
            cat.libido = cat.parsed_libido
            cat.inbredness = cat.parsed_inbredness
            cat.base_stats = dict(cat.parsed_stats) if cat.parsed_stats else {}
            cat.sexuality = cat.parsed_sexuality

        # Refresh the UI
        self.set_context(self._save_path, self._cats)
        self._status.setText(_tr("calibration.status.overrides_cleared"))
        self.calibrationChanged.emit()

    def _on_bulk_apply_sexuality(self):
        """Apply sexuality to all selected rows."""
        selected_rows = sorted(set(idx.row() for idx in self._table.selectedIndexes()))
        if not selected_rows:
            self._status.setText(_tr("calibration.status.select_rows"))
            return

        sexuality = str(self._bulk_sexuality_combo.currentData() or "")
        sm = self._table.selectionModel()
        sm.blockSignals(True)
        for row in selected_rows:
            widget = self._table.cellWidget(row, self.COL_OVR_SEXUALITY)
            if isinstance(widget, QComboBox):
                widget.blockSignals(True)
                idx = widget.findData(sexuality)
                widget.setCurrentIndex(idx if idx >= 0 else 0)
                widget.blockSignals(False)
        sm.blockSignals(False)

        self._save_clicked()
        sexuality_label = _tr("calibration.sexuality.clear", default="— clear —") if not sexuality else _tr(f"calibration.sexuality.{sexuality}")
        self._status.setText(
            _tr(
                "calibration.status.applied",
                sexuality=sexuality_label,
                count=len(selected_rows),
            )
        )


# ── Mutation & Disorder Breeding Planner ──────────────────────────────────────

def _planner_trait_color(ratio: float) -> QColor:
    """Return a tint color for mutation-planner trait coverage."""
    ratio = max(-1.0, min(1.0, float(ratio)))
    neutral = QColor(29, 29, 44)
    positive_low = QColor(214, 163, 69)
    positive_high = QColor(82, 185, 146)
    negative = QColor(177, 84, 94)
    if ratio > 0:
        warm = _blend_qcolor(positive_low, positive_high, min(ratio, 1.0))
        return _blend_qcolor(neutral, warm, 0.28 + 0.58 * min(ratio, 1.0))
    if ratio < 0:
        return _blend_qcolor(neutral, negative, 0.36 + 0.54 * min(abs(ratio), 1.0))
    return neutral


def _planner_trait_style(ratio: float, *, alpha: int = 150) -> str:
    color = _planner_trait_color(ratio)
    color.setAlpha(max(0, min(255, int(alpha))))
    border = QColor(color).lighter(135)
    border.setAlpha(max(0, min(255, int(alpha + 40))))
    return (
        f"background-color: rgba({color.red()},{color.green()},{color.blue()},{color.alpha()});"
        f"color:#fff; border:1px solid rgba({border.red()},{border.green()},{border.blue()},{border.alpha()});"
        "border-radius:3px; padding:1px 4px;"
    )


def _planner_trait_tooltip(summary: dict, *, label: str = "Mutation planner") -> str:
    if not summary:
        return ""

    score = float(summary.get("score", 0.0))
    matches = list(summary.get("matches", []) or [])
    penalties = list(summary.get("penalties", []) or [])
    parts = [f"{label}: {score:+.1f}"]
    if matches:
        parts.append("Matches: " + ", ".join(matches[:4]) + ("..." if len(matches) > 4 else ""))
    if penalties:
        parts.append("Penalties: " + ", ".join(penalties[:4]) + ("..." if len(penalties) > 4 else ""))
    return "\n".join(parts)


def _planner_trait_summary_for_cat(cat: 'Cat', traits: Sequence[dict]) -> dict:
    positive_score = 0.0
    negative_score = 0.0
    max_score = 0.0
    matches: list[str] = []
    penalties: list[str] = []

    for trait in traits:
        category = str(trait.get("category", "")).strip()
        key = str(trait.get("key", "")).strip().lower()
        if not category or not key:
            continue

        weight = float(trait.get("weight", 0) or 0)
        if weight == 0:
            continue

        max_score += abs(weight)
        if not _cat_has_trait(cat, category, key):
            continue

        display = _planner_trait_display_name(str(trait.get("display") or key))
        if weight > 0:
            matches.append(display)
            positive_score += weight
        else:
            penalties.append(display)
            negative_score += abs(weight)

    net_score = positive_score - negative_score
    ratio = net_score / max(1.0, max_score)
    return {
        "score": net_score,
        "ratio": ratio,
        "positive": positive_score,
        "negative": negative_score,
        "matches": matches,
        "penalties": penalties,
        "max": max_score,
    }


def _planner_trait_summary_for_pair(cat_a: 'Cat', cat_b: 'Cat', traits: Sequence[dict]) -> dict:
    score = 0.0
    max_score = 0.0
    matches: list[str] = []
    penalties: list[str] = []

    for trait in traits:
        category = str(trait.get("category", "")).strip()
        key = str(trait.get("key", "")).strip().lower()
        if not category or not key:
            continue

        weight = float(trait.get("weight", 0) or 0)
        if weight == 0:
            continue

        scale = weight / 10.0
        max_score += abs(scale) * 7.5

        a_has = _cat_has_trait(cat_a, category, key)
        b_has = _cat_has_trait(cat_b, category, key)
        if not (a_has or b_has):
            continue

        display = _planner_trait_display_name(str(trait.get("display") or key))
        if weight > 0:
            matches.append(display)
        else:
            penalties.append(display)

        score += scale * 5.0
        if a_has and b_has:
            score += scale * 2.5

    ratio = score / max(1.0, max_score)
    return {
        "score": score,
        "ratio": ratio,
        "matches": matches,
        "penalties": penalties,
        "max": max_score,
    }


class MutationDisorderPlannerView(QWidget):
    """View for planning breeding around specific mutations, disorders, and passives."""

    traitsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; }"
            "QHeaderView::section { background:#151532; color:#7d8bb0; border:none; padding:4px; font-weight:bold; }"
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a; "
            "border-radius:4px; padding:6px 12px; font-size:11px; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
        )
        self._cats: list[Cat] = []
        self._alive_cats: list[Cat] = []
        self._selected_pair: list[Cat] = []
        self._selected_traits: list[dict] = []  # [{category, key, display, weight}]
        self._active_trait_data: tuple[str, str] | None = None
        self._browse_trait_datas: list[tuple[str, str]] = []
        self._trait_catalog: list[dict] = []
        self._navigate_to_cat_callback = None
        self._save_path: Optional[str] = None
        self._session_state: dict = _load_planner_state_value("mutation_planner_state", {})
        self._restoring_session_state = False
        self._suppress_traits_changed = False
        self._syncing_trait_selection = False
        self._build_ui()

    def _notify_traits_changed(self):
        if getattr(self, "_suppress_traits_changed", False):
            return
        self.traitsChanged.emit()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(4)

        # Header
        header = QHBoxLayout()
        self._title = QLabel(_tr("mutation_planner.title"))
        self._title.setStyleSheet("color:#ddd; font-size:18px; font-weight:bold;")
        header.addWidget(self._title)
        header.addStretch()
        root.addLayout(header)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(6)
        self._room_label = QLabel(_tr("mutation_planner.room"))
        self._room_combo = QComboBox()
        self._room_combo.setFixedWidth(200)
        self._room_combo.setStyleSheet(
            "QComboBox { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
        )
        self._room_combo.currentIndexChanged.connect(self._refresh_table)
        self._room_combo.currentIndexChanged.connect(lambda _: self._save_session_state())
        controls.addStretch()
        self._pair_label = QLabel(_tr("mutation_planner.pair_hint"))
        self._pair_label.setStyleSheet("color:#666; font-size:11px;")
        controls.addWidget(self._pair_label)
        root.addLayout(controls)

        # Target trait row
        trait_row = QHBoxLayout()
        trait_row.setSpacing(6)
        self._target_trait_label = QLabel(_tr("mutation_planner.target_trait"))
        trait_row.addWidget(self._target_trait_label)
        self._trait_search = QLineEdit()
        self._trait_search.setPlaceholderText(_tr("mutation_planner.search_placeholder"))
        self._trait_search.setFixedWidth(160)
        self._trait_search.setClearButtonEnabled(True)
        self._trait_search.setStyleSheet(
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
        )
        self._trait_search.textChanged.connect(self._on_trait_search_changed)
        self._trait_search.textChanged.connect(lambda _: self._save_session_state())
        trait_row.addWidget(self._trait_search)
        self._trait_combo = QComboBox()
        self._trait_combo.setFixedWidth(300)
        self._trait_combo.setStyleSheet(
            "QComboBox { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
        )
        self._trait_combo.currentIndexChanged.connect(self._on_target_trait_changed)
        self._trait_combo.currentIndexChanged.connect(lambda _: self._save_session_state())
        trait_row.addWidget(self._trait_combo)
        self._trait_combo.setVisible(False)
        self._stimulation_label = QLabel(_tr("mutation_planner.stimulation"))
        trait_row.addWidget(self._stimulation_label)
        self._stim_spin = QSpinBox()
        self._stim_spin.setRange(0, 100)
        self._stim_spin.setValue(10)
        self._stim_spin.setFixedWidth(60)
        self._stim_spin.setStyleSheet(
            "QSpinBox { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px; }"
        )
        self._stim_spin.valueChanged.connect(self._on_stim_changed)
        self._stim_spin.valueChanged.connect(lambda _: self._save_session_state())
        trait_row.addWidget(self._stim_spin)
        # "Add" button to add selected trait to the multi-select list
        self._deselect_traits_btn = QPushButton(_tr("mutation_planner.deselect_traits", default="Deselect"))
        self._deselect_traits_btn.setFixedWidth(90)
        self._deselect_traits_btn.setStyleSheet(
            "QPushButton { background:#2a1a1a; color:#c88; border:1px solid #4a2a2a; "
            "border-radius:4px; padding:4px 8px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#3a2a2a; }"
        )
        self._deselect_traits_btn.clicked.connect(self._on_deselect_traits)
        trait_row.addWidget(self._deselect_traits_btn)
        self._add_trait_btn = QPushButton(_tr("mutation_planner.add_trait", default="Add Traits"))
        self._add_trait_btn.setFixedWidth(180)
        self._add_trait_btn.setStyleSheet(
            "QPushButton { background:#1f5f4a; color:#f2f7f3; border:1px solid #3f8f72; "
            "border-radius:4px; padding:4px 8px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#26735a; }"
        )
        self._add_trait_btn.clicked.connect(self._on_add_trait)
        trait_row.addWidget(self._add_trait_btn)
        self._add_trait_btn.setVisible(True)
        # Master list of (display_text, user_data) for filtering
        self._trait_items_master: list[tuple[str, object]] = []
        self._trait_info_label = QLabel("")
        self._trait_info_label.setStyleSheet("color:#666; font-size:11px;")
        trait_row.addWidget(self._trait_info_label)
        self._trait_info_label.setVisible(False)
        trait_row.addStretch()
        root.addLayout(trait_row)

        # Main splitter: trait browser left, cat list + outcome panel right
        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("mutation_planner_main_splitter")
        splitter.setStyleSheet("QSplitter::handle { background:#26264a; width:3px; }")
        self._splitter = splitter

        # Left: trait browser
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        trait_detail = QFrame()
        trait_detail.setStyleSheet("QFrame { background:#0e0e20; border:1px solid #26264a; border-radius:4px; }")
        trait_detail_layout = QVBoxLayout(trait_detail)
        trait_detail_layout.setContentsMargins(8, 6, 8, 6)
        trait_detail_layout.setSpacing(3)
        self._trait_detail_title = QLabel(_tr("mutation_planner.target_trait"))
        self._trait_detail_title.setStyleSheet("color:#8fb8a0; font-size:12px; font-weight:bold;")
        trait_detail_layout.addWidget(self._trait_detail_title)
        self._trait_detail_meta = QLabel("")
        self._trait_detail_meta.setStyleSheet("color:#bbb; font-size:11px;")
        self._trait_detail_meta.setWordWrap(True)
        trait_detail_layout.addWidget(self._trait_detail_meta)
        self._trait_detail_desc = QLabel(_tr("mutation_planner.no_traits_selected"))
        self._trait_detail_desc.setStyleSheet("color:#888; font-size:11px;")
        self._trait_detail_desc.setWordWrap(True)
        trait_detail_layout.addWidget(self._trait_detail_desc)
        left_layout.addWidget(trait_detail)
        trait_detail.setVisible(False)

        self._trait_table = QTableWidget(0, 4)
        self._trait_table.setHorizontalHeaderLabels([
            "Trait",
            "Type",
            "Cats",
            "Description",
        ])
        self._trait_table.verticalHeader().setVisible(False)
        self._trait_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._trait_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._trait_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._trait_table.setSortingEnabled(True)
        self._trait_table.setAlternatingRowColors(True)
        thh = self._trait_table.horizontalHeader()
        thh.setSectionResizeMode(0, QHeaderView.Interactive)
        thh.setSectionResizeMode(1, QHeaderView.Interactive)
        thh.setSectionResizeMode(2, QHeaderView.Interactive)
        thh.setSectionResizeMode(3, QHeaderView.Stretch)
        self._trait_table.setColumnWidth(0, 150)
        self._trait_table.setColumnWidth(1, 90)
        self._trait_table.setColumnWidth(2, 55)
        self._trait_table.sortByColumn(1, Qt.AscendingOrder)
        self._trait_table.selectionModel().selectionChanged.connect(self._on_trait_table_selection_changed)
        left_layout.addWidget(self._trait_table)
        splitter.addWidget(left)

        # Right: room selector header + vertical splitter with cat list (top),
        # selected traits (middle), outcome (bottom)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        right_header = QHBoxLayout()
        right_header.setSpacing(6)
        right_header.addWidget(self._room_label)
        right_header.addWidget(self._room_combo)
        right_header.addStretch()
        right_layout.addLayout(right_header)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setObjectName("mutation_planner_right_splitter")
        right_splitter.setStyleSheet("QSplitter::handle { background:#26264a; height:3px; }")
        self._right_splitter = right_splitter

        # -- Cat table --
        self._cat_table = QTableWidget(0, 7)
        self._cat_table.setIconSize(QSize(60, 20))
        self._cat_table.setHorizontalHeaderLabels([
            _tr("mutation_planner.table.name"),
            _tr("mutation_planner.table.gender"),
            _tr("mutation_planner.table.age"),
            _tr("mutation_planner.table.sum"),
            _tr("mutation_planner.table.mutations"),
            _tr("mutation_planner.table.passives_disorders"),
            _tr("mutation_planner.table.abilities"),
        ])
        self._cat_table.verticalHeader().setVisible(False)
        self._cat_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._cat_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._cat_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._cat_table.setSortingEnabled(True)
        self._cat_table.setAlternatingRowColors(True)
        hh = self._cat_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.Stretch)
        hh.setSectionResizeMode(6, QHeaderView.Stretch)
        self._cat_table.setColumnWidth(0, 130)
        self._cat_table.setColumnWidth(1, 50)
        self._cat_table.setColumnWidth(2, 40)
        self._cat_table.setColumnWidth(3, 50)
        self._cat_table.sortByColumn(0, Qt.AscendingOrder)
        self._cat_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        right_splitter.addWidget(self._cat_table)

        # -- Selected traits panel --
        traits_panel = QWidget()
        self._traits_panel = traits_panel
        traits_panel.setStyleSheet("QWidget { background:#0e0e20; }")
        traits_panel_layout = QVBoxLayout(traits_panel)
        traits_panel_layout.setContentsMargins(6, 4, 6, 4)
        traits_panel_layout.setSpacing(3)
        traits_header = QHBoxLayout()
        traits_header.setContentsMargins(0, 0, 0, 0)
        self._traits_title = QLabel(_tr("mutation_planner.selected_traits"))
        self._traits_title.setStyleSheet("color:#8fb8a0; font-size:12px; font-weight:bold;")
        traits_header.addWidget(self._traits_title)
        traits_header.addStretch()
        self._clear_traits_btn = QPushButton(_tr("mutation_planner.clear_all"))
        self._clear_traits_btn.setFixedHeight(22)
        self._clear_traits_btn.setStyleSheet(
            "QPushButton { background:#2a1a1a; color:#c88; border:1px solid #4a2a2a; "
            "border-radius:3px; padding:2px 8px; font-size:10px; }"
            "QPushButton:hover { background:#3a2a2a; }"
        )
        self._clear_traits_btn.clicked.connect(self._on_clear_all_traits)
        traits_header.addWidget(self._clear_traits_btn)
        self._find_pairs_btn = QPushButton(_tr("mutation_planner.find_best_pairs"))
        self._find_pairs_btn.setFixedHeight(22)
        self._find_pairs_btn.setStyleSheet(
            "QPushButton { background:#1f5f4a; color:#f2f7f3; border:1px solid #3f8f72; "
            "border-radius:3px; padding:2px 8px; font-size:10px; font-weight:bold; }"
            "QPushButton:hover { background:#26735a; }"
        )
        self._find_pairs_btn.clicked.connect(self._on_find_best_pairs)
        traits_header.addWidget(self._find_pairs_btn)
        traits_panel_layout.addLayout(traits_header)
        # Scroll area for trait rows
        self._traits_list_widget = QWidget()
        self._traits_list_layout = QVBoxLayout(self._traits_list_widget)
        self._traits_list_layout.setContentsMargins(0, 0, 0, 0)
        self._traits_list_layout.setSpacing(2)
        self._traits_list_layout.addStretch()
        traits_scroll = QScrollArea()
        traits_scroll.setWidgetResizable(True)
        traits_scroll.setFrameShape(QFrame.NoFrame)
        traits_scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        traits_scroll.setWidget(self._traits_list_widget)
        traits_scroll.setMaximumHeight(200)
        traits_panel_layout.addWidget(traits_scroll)
        self._traits_empty_label = QLabel(_tr("mutation_planner.no_traits_selected"))
        self._traits_empty_label.setStyleSheet("color:#555; font-size:10px;")
        self._traits_empty_label.setWordWrap(True)
        traits_panel_layout.addWidget(self._traits_empty_label)
        right_splitter.addWidget(traits_panel)

        # -- Outcome panel --
        self._outcome_scroll = QScrollArea()
        self._outcome_scroll.setWidgetResizable(True)
        self._outcome_scroll.setFrameShape(QFrame.NoFrame)
        self._outcome_scroll.setStyleSheet("QScrollArea { border:none; background:#0a0a18; }")
        self._outcome_widget = QWidget()
        self._outcome_layout = QVBoxLayout(self._outcome_widget)
        self._outcome_layout.setContentsMargins(12, 8, 12, 8)
        self._outcome_layout.setSpacing(6)
        self._outcome_placeholder = QLabel(_tr("mutation_planner.outcome.placeholder_initial"))
        self._outcome_placeholder.setStyleSheet("color:#555; font-size:12px;")
        self._outcome_placeholder.setWordWrap(True)
        self._outcome_layout.addWidget(self._outcome_placeholder)
        self._outcome_layout.addStretch()
        self._outcome_scroll.setWidget(self._outcome_widget)
        right_splitter.addWidget(self._outcome_scroll)

        right_splitter.setSizes([260, 180, 360])
        right_layout.addWidget(right_splitter, 1)
        splitter.addWidget(right)

        splitter.setSizes([500, 500])
        root.addWidget(splitter, 1)
        self.retranslate_ui()

    def retranslate_ui(self):
        self._title.setText(_tr("mutation_planner.title"))
        self._room_label.setText(_tr("mutation_planner.room"))
        self._stimulation_label.setText(_tr("mutation_planner.stimulation"))
        self._target_trait_label.setText(_tr("mutation_planner.target_trait"))
        self._trait_search.setPlaceholderText(_tr("mutation_planner.search_placeholder"))
        self._deselect_traits_btn.setText(_tr("mutation_planner.deselect_traits", default="Deselect"))
        self._add_trait_btn.setText(_tr("mutation_planner.add_trait", default="Add Traits"))
        self._traits_title.setText(_tr("mutation_planner.selected_traits"))
        self._clear_traits_btn.setText(_tr("mutation_planner.clear_all"))
        self._find_pairs_btn.setText(_tr("mutation_planner.find_best_pairs"))
        self._traits_empty_label.setText(_tr("mutation_planner.no_traits_selected"))
        if self._active_trait_data:
            self._update_trait_detail_panel(self._active_trait_data)
        else:
            self._trait_detail_title.setText(_tr("mutation_planner.target_trait"))
            self._trait_detail_meta.setText(_tr("mutation_planner.no_traits_selected"))
            self._trait_detail_desc.setText(_tr("mutation_planner.no_traits_selected"))
        if len(self._selected_pair) < 2:
            self._pair_label.setText(_tr("mutation_planner.pair_hint"))
            self._pair_label.setStyleSheet("color:#666; font-size:11px;")
        if hasattr(self, "_trait_table"):
            self._trait_table.setHorizontalHeaderLabels([
                "Trait",
                "Type",
                "Cats",
                "Description",
            ])
        self._cat_table.setHorizontalHeaderLabels([
            _tr("mutation_planner.table.name"),
            _tr("mutation_planner.table.gender"),
            _tr("mutation_planner.table.age"),
            _tr("mutation_planner.table.sum"),
            _tr("mutation_planner.table.mutations"),
            _tr("mutation_planner.table.passives_disorders"),
            _tr("mutation_planner.table.abilities"),
        ])

    def set_cats(self, cats: list[Cat]):
        self._cats = cats
        self._alive_cats = [cat for cat in cats if cat.status != "Gone"]
        self._selected_pair.clear()
        self._populate_room_filter()
        self._populate_trait_combo()
        self._refresh_table()
        self._restore_session_state()

    def set_navigate_to_cat_callback(self, callback):
        self._navigate_to_cat_callback = callback

    def save_session_state(self):
        self._save_session_state()

    def set_save_path(self, save_path: Optional[str], *, refresh_existing: bool = True, notify: bool = True):
        self._save_path = save_path
        if refresh_existing and self._cats:
            self.set_cats(self._cats)
            return
        self._suppress_traits_changed = not notify
        try:
            self._restore_session_state()
        finally:
            self._suppress_traits_changed = False

    def _populate_room_filter(self):
        self._room_combo.blockSignals(True)
        self._room_combo.clear()
        self._room_combo.addItem(_tr("mutation_planner.all_cats"), "")
        rooms: dict[str, str] = {}
        for cat in self._alive_cats:
            if not cat.room or cat.room == "Adventure":
                continue
            if cat.room not in rooms:
                rooms[cat.room] = ROOM_DISPLAY.get(cat.room, cat.room)
        for raw, display in sorted(rooms.items(), key=lambda kv: kv[1]):
            self._room_combo.addItem(display, raw)
        self._room_combo.blockSignals(False)

    def _build_trait_catalog(self):
        """Collect every visible trait across the current cats with counts and details."""
        catalog: dict[tuple[str, str], dict] = {}
        category_order = {
            "mutation": 0,
            "defect": 1,
            "passive": 2,
            "disorder": 3,
            "ability": 4,
        }

        for cat in self._alive_cats:
            def _add_trait(category: str, raw_key: str, display: str, tip: str):
                key = str(raw_key or "").strip().lower()
                if not key:
                    return
                entry = catalog.setdefault((category, key), {
                    "category": category,
                    "key": key,
                    "display": display,
                    "tip": tip,
                    "cats": set(),
                    "order": category_order.get(category, 99),
                })
                if not entry.get("display"):
                    entry["display"] = display
                if tip and not entry.get("tip"):
                    entry["tip"] = tip
                entry["cats"].add(_cat_uid(cat) or str(id(cat)))

            for text, tip in getattr(cat, "mutation_chip_items", []):
                display = _mutation_display_name(text)
                mid_match = re.search(r'\(ID\s+(-?\d+)\)', tip)
                key = f"{text}|{mid_match.group(1)}" if mid_match else text
                _add_trait("mutation", key, display, tip)

            for text, tip in getattr(cat, "defect_chip_items", []):
                display = _mutation_display_name(text)
                mid_match = re.search(r'\(ID\s+(-?\d+)\)', tip)
                key = f"{text}|{mid_match.group(1)}" if mid_match else text
                _add_trait("defect", key, display, tip)

            for p in (cat.passive_abilities or []):
                display = _mutation_display_name(p)
                _add_trait("passive", p, display, _ability_tip(p))

            for d in (cat.disorders or []):
                display = _mutation_display_name(d)
                _add_trait("disorder", d, display, _ability_tip(d))

            for a in (cat.abilities or []):
                display = _mutation_display_name(a)
                _add_trait("ability", a, display, _ability_tip(a))

        rows: list[dict] = []
        for entry in catalog.values():
            tip = str(entry.get("tip") or "")
            detail = _trait_visible_detail(tip)
            rows.append({
                "category": entry["category"],
                "key": entry["key"],
                "display": entry["display"],
                "tip": tip,
                "cats": len(entry["cats"]),
                "stats": _trait_selector_summary(tip),
                "desc": detail,
                "kind": _trait_display_kind(entry["category"]),
                "order": entry["order"],
            })

        # Disambiguate mutation/defect variants that share the same display name
        from collections import Counter  # noqa: local import for one-time use
        display_counts: Counter = Counter(
            (row["category"], row["display"])
            for row in rows
            if row["category"] in ("mutation", "defect")
        )
        for row in rows:
            if row["category"] in ("mutation", "defect"):
                if display_counts.get((row["category"], row["display"]), 0) > 1 and row["stats"]:
                    row["display"] = f"{row['display']} ({row['stats']})"

        self._trait_catalog = sorted(rows, key=lambda row: (row["order"], row["display"].lower()))

    def _populate_trait_table(self, search: str = "", restore_data=None):
        if not hasattr(self, "_trait_table"):
            return

        needle = search.strip().lower()
        selected_row = -1
        self._trait_table.blockSignals(True)
        self._trait_table.setSortingEnabled(False)
        self._trait_table.setRowCount(0)

        for row_data in self._trait_catalog:
            display_text = _trait_selector_label(row_data["category"], row_data["display"], row_data["tip"])
            if needle:
                hay = " ".join([
                    row_data["display"],
                    row_data["kind"],
                    str(row_data["cats"]),
                    row_data["desc"],
                    row_data["tip"],
                    display_text,
                ]).lower()
                if needle not in hay:
                    continue

            row = self._trait_table.rowCount()
            self._trait_table.insertRow(row)

            display_item = QTableWidgetItem(row_data["display"])
            display_item.setData(Qt.UserRole, (row_data["category"], row_data["key"]))
            display_item.setToolTip(row_data["desc"] or row_data["display"])
            self._trait_table.setItem(row, 0, display_item)

            kind_item = _SortByUserRoleItem(row_data["kind"])
            kind_item.setData(Qt.UserRole, row_data["order"])
            kind_item.setTextAlignment(Qt.AlignCenter)
            self._trait_table.setItem(row, 1, kind_item)

            cats_item = _SortByUserRoleItem(str(row_data["cats"]))
            cats_item.setData(Qt.UserRole, row_data["cats"])
            cats_item.setTextAlignment(Qt.AlignCenter)
            self._trait_table.setItem(row, 2, cats_item)

            desc_text = row_data["desc"] or ""
            desc_item = QTableWidgetItem(desc_text)
            if desc_text:
                desc_item.setToolTip(desc_text)
            self._trait_table.setItem(row, 3, desc_item)

            if restore_data is not None and (row_data["category"], row_data["key"]) == restore_data:
                selected_row = row

        self._trait_table.setSortingEnabled(True)
        self._trait_table.blockSignals(False)
        if selected_row >= 0:
            self._trait_table.selectRow(selected_row)

    def _populate_trait_combo(self):
        prev = self._trait_combo.currentData()
        self._build_trait_catalog()
        self._trait_items_master = [
            (
                _trait_selector_label(row["category"], row["display"], row["tip"]),
                (row["category"], row["key"]),
                row["tip"],
            )
            for row in self._trait_catalog
        ]
        self._apply_trait_filter(self._trait_search.text(), prev)

    def _on_trait_search_changed(self, text: str):
        prev = self._trait_combo.currentData()
        self._apply_trait_filter(text, prev)
        self._save_session_state()

    def _apply_trait_filter(self, search: str, restore_data=None):
        self._trait_combo.blockSignals(True)
        self._trait_combo.clear()
        self._trait_combo.addItem(_tr("mutation_planner.none_trait"), None)

        needle = search.strip().lower()
        last_category = None
        for display_text, user_data, tooltip_text in self._trait_items_master:
            if needle:
                hay = " ".join([display_text, tooltip_text or "", " ".join(map(str, user_data or ())) ]).lower()
                if needle not in hay:
                    continue
            # Insert category separator when category changes
            category = user_data[0] if isinstance(user_data, tuple) else None
            if category != last_category:
                if last_category is not None:
                    self._trait_combo.insertSeparator(self._trait_combo.count())
                last_category = category
            self._trait_combo.addItem(display_text, user_data)
            if tooltip_text:
                tooltip = str(tooltip_text).strip()
                if re.fullmatch(r"[A-Z0-9_]+(?:_DESC)?", tooltip):
                    tooltip = display_text
                if not tooltip:
                    tooltip = display_text
                self._trait_combo.setItemData(self._trait_combo.count() - 1, tooltip, Qt.ToolTipRole)

        # Restore previous selection if still present
        if restore_data is not None:
            for i in range(self._trait_combo.count()):
                if self._trait_combo.itemData(i) == restore_data:
                    self._trait_combo.setCurrentIndex(i)
                    break
        self._trait_combo.blockSignals(False)

        if hasattr(self, "_trait_table"):
            self._populate_trait_table(search, restore_data)

    def _activate_trait_filter(self, trait_data: tuple[str, str] | None, *, source: str = "combo"):
        if self._restoring_session_state:
            return
        self._active_trait_data = trait_data if isinstance(trait_data, tuple) else None
        self._browse_trait_datas = [self._active_trait_data] if self._active_trait_data is not None else []

        # Keep the combo, trait table, and cat list aligned without recursive signal churn.
        if source != "combo":
            self._trait_combo.blockSignals(True)
            if self._active_trait_data is None:
                self._trait_combo.setCurrentIndex(0)
            else:
                for i in range(self._trait_combo.count()):
                    if self._trait_combo.itemData(i) == self._active_trait_data:
                        self._trait_combo.setCurrentIndex(i)
                        break
            self._trait_combo.blockSignals(False)

        if source != "trait_table" and hasattr(self, "_trait_table"):
            self._trait_table.blockSignals(True)
            if self._active_trait_data is None:
                self._trait_table.clearSelection()
            else:
                for row in range(self._trait_table.rowCount()):
                    item = self._trait_table.item(row, 0)
                    if item is not None and item.data(Qt.UserRole) == self._active_trait_data:
                        self._trait_table.selectRow(row)
                        break
            self._trait_table.blockSignals(False)

        self._cat_table.blockSignals(True)
        self._cat_table.clearSelection()
        self._cat_table.blockSignals(False)
        self._selected_pair.clear()
        self._pair_label.setText(_tr("mutation_planner.pair_hint"))
        self._pair_label.setStyleSheet("color:#666; font-size:11px;")
        self._update_trait_detail_panel(self._active_trait_data)
        self._clear_outcome_panel()
        self._refresh_table()

    def _update_trait_detail_panel(self, trait_data: tuple[str, str] | None):
        if not hasattr(self, "_trait_detail_meta"):
            return
        if trait_data is None:
            self._trait_detail_title.setText(_tr("mutation_planner.target_trait"))
            self._trait_detail_meta.setText(_tr("mutation_planner.no_traits_selected"))
            self._trait_detail_desc.setText(_tr("mutation_planner.no_traits_selected"))
            self._trait_info_label.setText("")
            self._trait_info_label.setStyleSheet("color:#666; font-size:11px;")
            return

        category, key = trait_data
        row_data = next((row for row in self._trait_catalog if row["category"] == category and row["key"] == key), None)
        if row_data is None:
            self._trait_detail_title.setText(_tr("mutation_planner.target_trait"))
            self._trait_detail_meta.setText("")
            self._trait_detail_desc.setText("")
            self._trait_info_label.setText("")
            return

        title = _trait_selector_label(row_data["category"], row_data["display"], row_data["tip"])
        self._trait_detail_title.setText(title)
        meta_bits = [row_data["kind"], _tr("mutation_planner.trait_info.carriers_found", count=row_data["cats"])]
        if row_data["stats"]:
            meta_bits.append(row_data["stats"])
        self._trait_detail_meta.setText("  ".join(meta_bits))
        desc = row_data["desc"] or _tr("mutation_planner.no_description", default="No description available")
        self._trait_detail_desc.setText(desc)
        self._trait_info_label.setText(_tr("mutation_planner.trait_info.carriers_found", count=row_data["cats"]))
        self._trait_info_label.setStyleSheet("color:#8fb8a0; font-size:11px;")

    def _on_target_trait_changed(self):
        data = self._trait_combo.currentData()
        if data is None:
            self._activate_trait_filter(None, source="combo")
            if len(self._selected_pair) == 2:
                self._update_outcome_panel(self._selected_pair[0], self._selected_pair[1])
            else:
                self._clear_outcome_panel()
            self._save_session_state()
            return
        self._cat_table.clearSelection()
        self._activate_trait_filter(data, source="combo")
        self._save_session_state()

    def _on_trait_table_selection_changed(self):
        if self._restoring_session_state or self._syncing_trait_selection or not hasattr(self, "_trait_table"):
            return
        trait_datas = self._selected_trait_datas_from_table()
        self._browse_trait_datas = list(trait_datas)
        self._active_trait_data = trait_datas[-1] if trait_datas else None
        self._update_trait_detail_panel(self._active_trait_data)
        self._selected_pair.clear()
        self._pair_label.setText(_tr("mutation_planner.pair_hint"))
        self._pair_label.setStyleSheet("color:#666; font-size:11px;")
        self._clear_outcome_panel()
        self._refresh_table()
        self._save_session_state()

    # ── Multi-select trait management ──

    def _selected_trait_datas_from_table(self) -> list[tuple[str, str]]:
        if not hasattr(self, "_trait_table"):
            return []
        datas: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        rows = sorted(set(idx.row() for idx in self._trait_table.selectionModel().selectedRows()))
        for row in rows:
            item = self._trait_table.item(row, 0)
            if item is None:
                continue
            data = item.data(Qt.UserRole)
            if isinstance(data, tuple) and len(data) == 2 and data not in seen:
                seen.add(data)
                datas.append((str(data[0]), str(data[1])))
        return datas

    def _sync_trait_table_selection(self, trait_datas: list[tuple[str, str]]):
        if not hasattr(self, "_trait_table"):
            return
        table = self._trait_table
        sel_model = table.selectionModel()
        if sel_model is None:
            return
        wanted = {tuple(d) for d in trait_datas}
        table.blockSignals(True)
        sel_model.blockSignals(True)
        try:
            table.clearSelection()
            if not wanted:
                return
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if item is None:
                    continue
                data = item.data(Qt.UserRole)
                if isinstance(data, tuple) and tuple(data) in wanted:
                    table.selectRow(row)
        finally:
            sel_model.blockSignals(False)
            table.blockSignals(False)

    def _set_selected_traits_from_datas(
        self,
        trait_datas: list[tuple[str, str]],
        *,
        sync_table: bool,
        clear_combo: bool,
    ):
        trait_lookup = {(row["category"], row["key"]): row for row in self._trait_catalog}
        existing_weights = {
            (trait["category"], trait["key"]): int(trait.get("weight", 5))
            for trait in self._selected_traits
        }
        new_traits: list[dict] = []
        for category, key in trait_datas:
            row_data = trait_lookup.get((category, key))
            if row_data is None:
                continue
            new_traits.append({
                "category": category,
                "key": key,
                "display": row_data["display"],
                "weight": existing_weights.get((category, key), 5),
            })

        self._selected_traits = new_traits
        self._selected_pair.clear()
        self._pair_label.setText(_tr("mutation_planner.pair_hint"))
        self._pair_label.setStyleSheet("color:#666; font-size:11px;")
        self._active_trait_data = trait_datas[-1] if trait_datas else None
        self._cat_table.blockSignals(True)
        self._cat_table.clearSelection()
        self._cat_table.blockSignals(False)

        if clear_combo and hasattr(self, "_trait_combo"):
            self._trait_combo.blockSignals(True)
            self._trait_combo.setCurrentIndex(0)
            self._trait_combo.blockSignals(False)

        self._rebuild_traits_list()
        self._clear_outcome_panel()
        self._refresh_table()
        self._save_session_state()
        self._notify_traits_changed()

    def _on_add_trait(self):
        """Add the currently selected left-table traits to the selected list."""
        trait_datas = self._selected_trait_datas_from_table()
        if not trait_datas:
            return
        combined = [(trait["category"], trait["key"]) for trait in self._selected_traits]
        for data in trait_datas:
            if data not in combined:
                combined.append(data)
        self._set_selected_traits_from_datas(combined, sync_table=False, clear_combo=True)

    def _on_clear_all_traits(self):
        self._selected_traits.clear()
        self._browse_trait_datas = []
        if hasattr(self, "_trait_table"):
            self._trait_table.blockSignals(True)
            self._trait_table.clearSelection()
            self._trait_table.blockSignals(False)
        self._cat_table.blockSignals(True)
        self._cat_table.clearSelection()
        self._cat_table.blockSignals(False)
        if hasattr(self, "_trait_combo"):
            self._trait_combo.blockSignals(True)
            self._trait_combo.setCurrentIndex(0)
            self._trait_combo.blockSignals(False)
        self._active_trait_data = None
        self._selected_pair.clear()
        self._pair_label.setText(_tr("mutation_planner.pair_hint"))
        self._pair_label.setStyleSheet("color:#666; font-size:11px;")
        self._rebuild_traits_list()
        self._clear_outcome_panel()
        self._refresh_table()
        self._save_session_state()
        self._notify_traits_changed()

    def _on_deselect_traits(self):
        if hasattr(self, "_trait_table"):
            self._trait_table.blockSignals(True)
            self._trait_table.clearSelection()
            self._trait_table.blockSignals(False)
        if hasattr(self, "_trait_combo"):
            self._trait_combo.blockSignals(True)
            self._trait_combo.setCurrentIndex(0)
            self._trait_combo.blockSignals(False)
        self._browse_trait_datas = []
        self._active_trait_data = None
        self._selected_pair.clear()
        self._pair_label.setText(_tr("mutation_planner.pair_hint"))
        self._pair_label.setStyleSheet("color:#666; font-size:11px;")
        self._update_trait_detail_panel(None)
        self._clear_outcome_panel()
        self._refresh_table()
        self._save_session_state()

    def _on_remove_trait(self, index: int):
        if 0 <= index < len(self._selected_traits):
            self._selected_traits.pop(index)
            self._set_selected_traits_from_datas(
                [(trait["category"], trait["key"]) for trait in self._selected_traits],
                sync_table=False,
                clear_combo=True,
            )

    def _on_trait_weight_changed(self, index: int, value: int):
        if 0 <= index < len(self._selected_traits):
            self._selected_traits[index]["weight"] = value
            self._save_session_state()
            self._notify_traits_changed()

    def _rebuild_traits_list(self):
        """Rebuild the selected traits list UI."""
        layout = self._traits_list_layout
        # Clear all widgets except the stretch at the end
        while layout.count() > 1:
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._traits_empty_label.setVisible(len(self._selected_traits) == 0)

        for i, trait in enumerate(self._selected_traits):
            row = QWidget()
            row.setStyleSheet("QWidget { background:#151530; border-radius:3px; }")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 2, 4, 2)
            row_layout.setSpacing(6)

            lbl = QToolButton()
            lbl.setText(trait["display"])
            lbl.setToolButtonStyle(Qt.ToolButtonTextOnly)
            lbl.setAutoRaise(True)
            lbl.setCursor(Qt.PointingHandCursor)
            lbl.setStyleSheet("QToolButton { color:#ccc; font-size:10px; border:none; background:transparent; text-align:left; }")
            lbl.clicked.connect(lambda _checked=False, t=trait: self._activate_trait_filter((t["category"], t["key"]), source="selected_trait"))
            row_layout.addWidget(lbl, 1)

            wt_label = QLabel(_tr("mutation_planner.weight_short"))
            wt_label.setStyleSheet("color:#888; font-size:10px;")
            row_layout.addWidget(wt_label)

            spin = QSpinBox()
            spin.setRange(-10, 10)
            spin.setValue(trait["weight"])
            spin.setFixedWidth(45)

            def _spin_style(v):
                if v < 0:
                    return ("QSpinBox { background:#0d0d1c; color:#c86060; border:1px solid #2a2a4a;"
                            " border-radius:3px; padding:1px; font-size:10px; }")
                return ("QSpinBox { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
                        " border-radius:3px; padding:1px; font-size:10px; }")

            spin.setStyleSheet(_spin_style(trait["weight"]))
            idx = i  # capture for lambda
            spin.valueChanged.connect(lambda v, ii=idx, s=spin: (
                self._on_trait_weight_changed(ii, v),
                s.setStyleSheet(
                    "QSpinBox { background:#0d0d1c; color:#c86060; border:1px solid #2a2a4a;"
                    " border-radius:3px; padding:1px; font-size:10px; }" if v < 0
                    else "QSpinBox { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
                    " border-radius:3px; padding:1px; font-size:10px; }"
                )
            ))
            row_layout.addWidget(spin)

            remove_btn = QPushButton(_tr("mutation_planner.remove_trait"))
            remove_btn.setFixedSize(20, 20)
            remove_btn.setStyleSheet(
                "QPushButton { background:#2a1a1a; color:#c88; border:none; "
                "border-radius:3px; font-size:10px; font-weight:bold; }"
                "QPushButton:hover { background:#3a2a2a; }"
            )
            remove_btn.clicked.connect(lambda _, ii=idx: self._on_remove_trait(ii))
            row_layout.addWidget(remove_btn)

            layout.insertWidget(layout.count() - 1, row)  # insert before stretch

    def _on_find_best_pairs(self):
        """Find the best breeding pairs to cover all selected traits."""
        if not self._selected_traits:
            return
        self._cat_table.clearSelection()
        self._selected_pair.clear()
        self._active_trait_data = None
        self._pair_label.setText(_tr("mutation_planner.pair_hint"))
        self._pair_label.setStyleSheet("color:#666; font-size:11px;")
        self._trait_combo.blockSignals(True)
        self._trait_combo.setCurrentIndex(0)
        self._trait_combo.blockSignals(False)
        if hasattr(self, "_trait_table"):
            self._trait_table.clearSelection()
        self._update_trait_detail_panel(None)
        self._trait_info_label.setText("")
        self._refresh_table()
        self._update_multi_trait_plan()
        self._save_session_state()

    def _update_multi_trait_plan(self):
        """Show breeding plan for multiple selected traits with weights."""
        stim = self._stim_spin.value()
        traits = self._selected_traits

        # Get all alive cats, excluding blacklisted
        alive = [c for c in self._alive_cats if not c.is_blacklisted]

        # Score each cat: how many of the selected traits does it carry?
        def _cat_score(cat):
            return sum(t["weight"] for t in traits if _cat_has_trait(cat, t["category"], t["key"]))

        # Generate all candidate pairs via can_breed (respects sexuality overrides)
        candidate_pairs = []
        for i, a in enumerate(alive):
            for b in alive[i + 1:]:
                ok, _ = can_breed(a, b)
                if ok:
                    candidate_pairs.append((a, b))

        max_possible = sum(t["weight"] for t in traits if t["weight"] > 0)
        # With both-parents bonus: max is weight * 1.5 per positive trait
        max_score_with_bonus = max_possible * 1.5

        scored_pairs: list[tuple] = []
        for a, b in candidate_pairs:
            score = 0.0
            covered = []      # positive-weight traits covered by at least one parent
            uncovered = []    # positive-weight traits not covered
            penalized = []    # negative-weight traits carried by at least one parent
            for t in traits:
                a_has = _cat_has_trait(a, t["category"], t["key"])
                b_has = _cat_has_trait(b, t["category"], t["key"])
                w = t["weight"]
                if w < 0:
                    if a_has or b_has:
                        score += w  # penalty
                        if a_has and b_has:
                            score += w * 0.5  # extra penalty if both carry it
                        penalized.append(t)
                else:
                    if a_has or b_has:
                        score += w
                        if a_has and b_has:
                            score += w * 0.5  # bonus for both carriers
                        covered.append(t)
                    else:
                        uncovered.append(t)
            if covered:  # only show pairs that cover at least one positive trait
                pair_risk = risk_percent(a, b)
                scored_pairs.append((score, a, b, covered, uncovered, penalized, pair_risk))

        scored_pairs.sort(key=lambda x: (-x[0], x[6]))  # best score, lowest birth-defect risk

        # Build outcome panel
        layout = self._outcome_layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        layout.addWidget(self._sec_label(
            _tr("mutation_planner.multi_trait.title", count=len(traits), max=max_possible)
        ))

        if not scored_pairs:
            layout.addWidget(self._info_label(_tr("mutation_planner.multi_trait.no_pairs")))
            layout.addStretch()
            return

        # Check if any pair covers all positive traits
        pos_traits = [t for t in traits if t["weight"] > 0]
        best_score = scored_pairs[0][0]
        full_coverage = [p for p in scored_pairs if not p[4]]  # no uncovered positive traits

        if full_coverage:
            layout.addWidget(self._info_label(
                f"{len(full_coverage)} pair(s) can cover ALL positive traits."
            ))
        else:
            best_covered = len(scored_pairs[0][3])
            layout.addWidget(
                self._info_label(
                    _tr("mutation_planner.multi_trait.best_coverage", total=len(pos_traits), covered=best_covered)
                )
            )

        # Show top pairs (limit to 20)
        layout.addWidget(self._sec_label(_tr("mutation_planner.multi_trait.best_pairs")))
        show_pairs = scored_pairs[:20]

        pair_table = QTableWidget(len(show_pairs), 6)
        pair_table.setHorizontalHeaderLabels([
            _tr("mutation_planner.multi_trait.table.parent_a"),
            _tr("mutation_planner.multi_trait.table.parent_b"),
            _tr("mutation_planner.multi_trait.table.score"),
            _tr("mutation_planner.multi_trait.table.coverage"),
            _tr("mutation_planner.multi_trait.table.uncovered"),
            _tr("mutation_planner.multi_trait.table.inbreeding"),
        ])
        pair_table.verticalHeader().setVisible(False)
        pair_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        pair_table.setSelectionMode(QAbstractItemView.SingleSelection)
        pair_table.setMaximumHeight(min(30 + len(show_pairs) * 26, 500))
        pair_table.setStyleSheet(
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; font-size:11px; }"
        )
        phh = pair_table.horizontalHeader()
        phh.setSectionResizeMode(0, QHeaderView.Stretch)
        phh.setSectionResizeMode(1, QHeaderView.Stretch)
        phh.setSectionResizeMode(2, QHeaderView.Interactive)
        phh.setSectionResizeMode(3, QHeaderView.Stretch)
        phh.setSectionResizeMode(4, QHeaderView.Stretch)
        phh.setSectionResizeMode(5, QHeaderView.Interactive)
        pair_table.setColumnWidth(2, 55)
        pair_table.setColumnWidth(5, 70)
        pair_table.cellClicked.connect(self._on_pair_table_clicked)
        pair_table.setMouseTracking(True)
        pair_table.cellEntered.connect(lambda r, c: pair_table.setCursor(
            Qt.PointingHandCursor if c in (0, 1) else Qt.ArrowCursor
        ))

        for row, (score, a, b, covered, uncovered, penalized, pair_risk) in enumerate(show_pairs):
            a_item = QTableWidgetItem(f"{a.name} ({a.gender_display})")
            a_item.setData(Qt.UserRole, a.db_key)
            a_icon = _make_tag_icon(_cat_tags(a), dot_size=14, spacing=4)
            if not a_icon.isNull():
                a_item.setIcon(a_icon)
            a_item.setForeground(QColor("#5b9bd5"))
            a_item.setToolTip(_tr("mutation_planner.tooltip.jump_to_cat"))
            pair_table.setItem(row, 0, a_item)

            b_item = QTableWidgetItem(f"{b.name} ({b.gender_display})")
            b_item.setData(Qt.UserRole, b.db_key)
            b_icon = _make_tag_icon(_cat_tags(b), dot_size=14, spacing=4)
            if not b_icon.isNull():
                b_item.setIcon(b_icon)
            b_item.setForeground(QColor("#5b9bd5"))
            b_item.setToolTip(_tr("mutation_planner.tooltip.jump_to_cat"))
            pair_table.setItem(row, 1, b_item)

            score_item = QTableWidgetItem(f"{score:.0f}/{max_possible}")
            score_item.setTextAlignment(Qt.AlignCenter)
            if score >= max_possible:
                score_item.setForeground(QColor("#8fb8a0"))
            elif score < 0:
                score_item.setForeground(QColor("#cc6666"))
            pair_table.setItem(row, 2, score_item)

            cov_names = ", ".join(t["display"].split("] ")[-1] for t in covered)
            pair_table.setItem(row, 3, QTableWidgetItem(cov_names))

            # Build uncovered + penalized cell
            parts = []
            if uncovered:
                parts.append(", ".join(t["display"].split("] ")[-1] for t in uncovered))
            if penalized:
                parts.append("\u26a0 " + ", ".join(t["display"].split("] ")[-1] for t in penalized))
            if parts:
                unc_item = QTableWidgetItem(" | ".join(parts))
                unc_item.setForeground(QColor("#cc8833") if penalized else QColor("#cc6666"))
                pair_table.setItem(row, 4, unc_item)
            else:
                full_item = QTableWidgetItem(_tr("mutation_planner.multi_trait.all_covered"))
                full_item.setForeground(QColor("#8fb8a0"))
                pair_table.setItem(row, 4, full_item)

            risk_pct = int(round(pair_risk))
            inbred_item = QTableWidgetItem(f"{risk_pct}%")
            inbred_item.setTextAlignment(Qt.AlignCenter)
            if risk_pct >= 100:
                inbred_item.setForeground(QColor("#d97777"))
            elif risk_pct >= 50:
                inbred_item.setForeground(QColor("#d8b56a"))
            elif risk_pct >= 20:
                inbred_item.setForeground(QColor("#8fc9e6"))
            pair_table.setItem(row, 5, inbred_item)

        layout.addWidget(pair_table)

        # Per-trait carrier summary
        layout.addWidget(self._sec_label(_tr("mutation_planner.multi_trait.carrier_summary")))
        for t in traits:
            carriers = [c for c in alive if _cat_has_trait(c, t["category"], t["key"])]
            trait_short = t["display"].split("] ")[-1]
            w = t["weight"]
            if w < 0:
                prefix = "\u26a0 "
                color = "#cc8833" if carriers else "#888"
            else:
                prefix = ""
                color = "#8fb8a0" if carriers else "#cc6666"
            lbl = self._info_label(
                f"  {prefix}{trait_short} (wt {w}): {len(carriers)} carrier(s)"
                + (f" -- {', '.join(c.name for c in carriers[:8])}" if carriers else " -- NONE")
            )
            lbl.setStyleSheet(f"color:{color}; font-size:11px;")
            layout.addWidget(lbl)

        layout.addStretch()

    def _on_pair_table_clicked(self, row: int, col: int):
        """Navigate to a cat in the Alive Cats view when its name is clicked."""
        if col not in (0, 1):
            return
        table = self.sender()
        item = table.item(row, col)
        if item is None:
            return
        db_key = item.data(Qt.UserRole)
        if db_key is not None and self._navigate_to_cat_callback is not None:
            self._navigate_to_cat_callback(db_key)

    def get_selected_traits(self) -> list[dict]:
        """Return current selected traits with weights (for export to room optimizer)."""
        source = self._selected_traits
        if not source:
            source = self._session_state.get("selected_traits", [])

        normalized: list[dict] = []
        if isinstance(source, list):
            for trait in source:
                if not isinstance(trait, dict):
                    continue
                category = str(trait.get("category") or "").strip()
                key = str(trait.get("key") or "").strip().lower()
                if not category or not key:
                    continue
                display = str(trait.get("display") or "").strip() or key
                try:
                    weight = int(trait.get("weight", 5))
                except (TypeError, ValueError):
                    weight = 5
                normalized.append({
                    "category": category,
                    "key": key,
                    "display": display,
                    "weight": weight,
                })
        return normalized

    def _session_state_payload(self) -> dict:
        state = dict(self._session_state) if isinstance(self._session_state, dict) else {}
        selected_pair_uids = [_cat_uid(cat) for cat in self._selected_pair if _cat_uid(cat)]
        current_trait = self._trait_combo.currentData()
        state.update({
            "room": self._room_combo.currentData() or "",
            "stim": int(self._stim_spin.value()),
            "search": self._trait_search.text(),
            "trait_data": list(current_trait) if isinstance(current_trait, tuple) else None,
            "selected_traits": [dict(t) for t in self._selected_traits],
            "selected_pair_uids": selected_pair_uids if len(selected_pair_uids) == 2 else [],
            "last_mode": state.get("last_mode", "none"),
        })
        if state["selected_traits"]:
            state["last_mode"] = "multi"
        elif state["selected_pair_uids"]:
            state["last_mode"] = "pair"
        elif state["trait_data"] is not None:
            state["last_mode"] = "single"
        return state

    def _save_session_state(self):
        if getattr(self, "_restoring_session_state", False):
            return
        self._session_state = self._session_state_payload()
        _save_planner_state_value("mutation_planner_state", self._session_state, self._save_path)

    def _restore_session_state(self):
        state = _load_planner_state_value("mutation_planner_state", {}, self._save_path)
        if not isinstance(state, dict):
            state = {}
        self._session_state = state
        self._restoring_session_state = True
        try:
            room_value = str(state.get("room", "") or "")
            idx = self._room_combo.findData(room_value)
            self._room_combo.setCurrentIndex(idx if idx >= 0 else 0)

            self._stim_spin.setValue(int(state.get("stim", 10) or 10))

            selected_traits = state.get("selected_traits", [])
            restored_traits: list[dict] = []
            if isinstance(selected_traits, list):
                for trait in selected_traits:
                    if not isinstance(trait, dict):
                        continue
                    category = str(trait.get("category") or "").strip()
                    key = str(trait.get("key") or "").strip().lower()
                    display = str(trait.get("display") or "").strip() or key
                    try:
                        weight = int(trait.get("weight", 5))
                    except (TypeError, ValueError):
                        weight = 5
                    if category and key:
                        restored_traits.append({
                            "category": category,
                            "key": key,
                            "display": display,
                            "weight": weight,
                        })
            self._selected_traits = restored_traits
            self._rebuild_traits_list()

            trait_data = state.get("trait_data")
            if isinstance(trait_data, (list, tuple)) and len(trait_data) == 2:
                restored_trait = (str(trait_data[0]), str(trait_data[1]).strip().lower())
                for i in range(self._trait_combo.count()):
                    if self._trait_combo.itemData(i) == restored_trait:
                        self._trait_combo.setCurrentIndex(i)
                        break

            pair_uids = state.get("selected_pair_uids", [])
            if isinstance(pair_uids, list) and len(pair_uids) == 2:
                uid_map = {_cat_uid(cat): cat for cat in self._cats}
                pair_cats = [uid_map.get(str(uid).strip().lower()) for uid in pair_uids]
                if all(pair_cats):
                    self._selected_pair = [pair_cats[0], pair_cats[1]]
        finally:
            self._restoring_session_state = False

        current_trait = self._trait_combo.currentData()
        if isinstance(current_trait, tuple):
            self._activate_trait_filter(current_trait, source="combo")
        else:
            self._clear_outcome_panel()
        self._notify_traits_changed()

    def reset_to_defaults(self):
        """Restore the mutation planner to its default room, search, and trait state."""
        self._session_state = {}
        self._restoring_session_state = True
        try:
            if self._room_combo.count():
                self._room_combo.setCurrentIndex(0)
            self._stim_spin.setValue(10)
            self._trait_search.setText("")
            self._selected_traits.clear()
            self._selected_pair.clear()
            self._active_trait_data = None
            self._browse_trait_datas = []
            self._pair_label.setText(_tr("mutation_planner.pair_hint"))
            self._pair_label.setStyleSheet("color:#666; font-size:11px;")
            if self._trait_combo.count():
                self._trait_combo.setCurrentIndex(0)
            self._cat_table.clearSelection()
            if hasattr(self, "_trait_table"):
                self._trait_table.clearSelection()
            self._update_trait_detail_panel(None)
            self._clear_outcome_panel()
            if hasattr(self, "_splitter"):
                self._splitter.setSizes([500, 500])
            if hasattr(self, "_right_splitter"):
                self._right_splitter.setSizes([260, 180, 360])
        finally:
            self._restoring_session_state = False
        self.retranslate_ui()
        self._refresh_table()
        self._notify_traits_changed()
        self._save_session_state()

    def _update_trait_plan(self, trait_data: tuple):
        """Show breeding plan for the selected target trait (single-trait mode)."""
        category, trait_key = trait_data
        stim = self._stim_spin.value()

        # Find all alive cats that have this trait, excluding blacklisted
        carriers: list[Cat] = []
        for cat in self._cats:
            if cat.status == "Gone" or cat.is_blacklisted:
                continue
            if _cat_has_trait(cat, category, trait_key):
                carriers.append(cat)

        # Display name for the trait
        trait_display = self._trait_combo.currentText()
        self._trait_info_label.setText(_tr("mutation_planner.trait_info.carriers_found", count=len(carriers)))
        self._trait_info_label.setStyleSheet(
            f"color:{'#8fb8a0' if carriers else '#cc6666'}; font-size:11px;"
        )

        # Clear and rebuild outcome panel
        layout = self._outcome_layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not carriers:
            layout.addWidget(self._info_label(_tr("mutation_planner.single_trait.no_carriers")))
            layout.addStretch()
            return

        carrier_table = QTableWidget(len(carriers), 4)
        carrier_table.setHorizontalHeaderLabels([
            _tr("mutation_planner.table.name"),
            _tr("mutation_planner.table.gender"),
            _tr("mutation_planner.table.age"),
            _tr("mutation_planner.table.room"),
        ])
        carrier_table.verticalHeader().setVisible(False)
        carrier_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        carrier_table.setSelectionMode(QAbstractItemView.NoSelection)
        carrier_table.setMaximumHeight(min(30 + len(carriers) * 26, 250))
        carrier_table.setStyleSheet(
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; font-size:11px; }"
        )
        chh = carrier_table.horizontalHeader()
        chh.setSectionResizeMode(0, QHeaderView.Stretch)
        chh.setSectionResizeMode(1, QHeaderView.Interactive)
        chh.setSectionResizeMode(2, QHeaderView.Interactive)
        chh.setSectionResizeMode(3, QHeaderView.Stretch)
        carrier_table.setColumnWidth(1, 50)
        carrier_table.setColumnWidth(2, 40)
        for row, cat in enumerate(carriers):
            carrier_table.setItem(row, 0, QTableWidgetItem(cat.name))
            g_item = QTableWidgetItem(cat.gender_display if hasattr(cat, 'gender_display') else cat.gender)
            g_item.setTextAlignment(Qt.AlignCenter)
            carrier_table.setItem(row, 1, g_item)
            a_item = QTableWidgetItem(str(cat.age) if cat.age is not None else "-")
            a_item.setTextAlignment(Qt.AlignCenter)
            carrier_table.setItem(row, 2, a_item)
            room_name = ROOM_DISPLAY.get(cat.room, cat.room) if cat.room else "-"
            carrier_table.setItem(row, 3, QTableWidgetItem(room_name))
        layout.addWidget(carrier_table)

        # ── Inheritance mechanics ──
        layout.addWidget(self._sec_label(_tr("mutation_planner.single_trait.inheritance")))
        if category == "mutation":
            favor_weight = _stimulation_inheritance_weight(stim)
            layout.addWidget(self._info_label(
                _tr("mutation_planner.single_trait.mutation_help", favor=f"{favor_weight*100:.1f}", stim=stim)
            ))
        elif category == "passive":
            passive_chance = 0.05 + 0.01 * stim
            layout.addWidget(self._info_label(
                _tr("mutation_planner.single_trait.passive_help", chance=f"{min(passive_chance, 1.0)*100:.1f}", stim=stim)
            ))
        elif category == "ability":
            spell_chance = 0.2 + 0.025 * stim
            layout.addWidget(self._info_label(
                _tr("mutation_planner.single_trait.ability_help", chance=f"{min(spell_chance, 1.0)*100:.1f}", stim=stim)
            ))

        # ── Recommended pairs ──
        layout.addWidget(self._sec_label(_tr("mutation_planner.single_trait.recommended_pairs")))

        males = [c for c in carriers if c.gender and c.gender.upper() in ("M", "MALE")]
        females = [c for c in carriers if c.gender and c.gender.upper() in ("F", "FEMALE")]
        non_carriers = [c for c in self._cats if c.status != "Gone" and not c.is_blacklisted and c not in carriers]
        nc_males = [c for c in non_carriers if c.gender and c.gender.upper() in ("M", "MALE")]
        nc_females = [c for c in non_carriers if c.gender and c.gender.upper() in ("F", "FEMALE")]

        pairs: list[tuple[Cat, Cat, str]] = []  # (cat_a, cat_b, note)

        # Best: carrier x carrier (opposite gender)
        for m in males:
            for f in females:
                if m is f:
                    continue
                pair_risk = risk_percent(m, f)
                note = _tr("mutation_planner.single_trait.note.both_carriers")
                if pair_risk >= 20:
                    note += f" (birth defect risk {int(round(pair_risk))}%)"
                pairs.append((m, f, note))

        # Good: carrier x non-carrier (opposite gender)
        if len(pairs) < 10:
            for carrier in carriers:
                pool = nc_females if carrier.gender and carrier.gender.upper() in ("M", "MALE") else nc_males
                for partner in pool[:5]:  # limit to avoid huge lists
                    pairs.append((carrier, partner, _tr("mutation_planner.single_trait.note.one_carrier")))
                    if len(pairs) >= 15:
                        break
                if len(pairs) >= 15:
                    break

        if not pairs:
            if len(carriers) == 1:
                layout.addWidget(self._info_label(_tr("mutation_planner.single_trait.only_one_carrier", name=carriers[0].name)))
            else:
                layout.addWidget(self._info_label(_tr("mutation_planner.single_trait.no_pairs")))
        else:
            pair_table = QTableWidget(len(pairs), 4)
            pair_table.setHorizontalHeaderLabels([
                _tr("mutation_planner.multi_trait.table.parent_a"),
                _tr("mutation_planner.multi_trait.table.parent_b"),
                _tr("mutation_planner.single_trait.table.note"),
                _tr("mutation_planner.multi_trait.table.inbreeding"),
            ])
            pair_table.verticalHeader().setVisible(False)
            pair_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            pair_table.setSelectionMode(QAbstractItemView.NoSelection)
            pair_table.setMaximumHeight(min(30 + len(pairs) * 26, 400))
            pair_table.setStyleSheet(
                "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; font-size:11px; }"
            )
            phh = pair_table.horizontalHeader()
            phh.setSectionResizeMode(0, QHeaderView.Stretch)
            phh.setSectionResizeMode(1, QHeaderView.Stretch)
            phh.setSectionResizeMode(2, QHeaderView.Stretch)
            phh.setSectionResizeMode(3, QHeaderView.Interactive)
            pair_table.setColumnWidth(3, 80)
            for row, (ca, cb, note) in enumerate(pairs):
                pair_table.setItem(row, 0, QTableWidgetItem(ca.name))
                pair_table.setItem(row, 1, QTableWidgetItem(cb.name))
                pair_table.setItem(row, 2, QTableWidgetItem(note))
                pair_risk = risk_percent(ca, cb)
                risk_pct = int(round(pair_risk))
                inbred_item = QTableWidgetItem(f"{risk_pct}%")
                inbred_item.setTextAlignment(Qt.AlignCenter)
                if risk_pct >= 100:
                    inbred_item.setForeground(QColor("#d97777"))
                elif risk_pct >= 50:
                    inbred_item.setForeground(QColor("#d8b56a"))
                elif risk_pct >= 20:
                    inbred_item.setForeground(QColor("#8fc9e6"))
                pair_table.setItem(row, 3, inbred_item)
            layout.addWidget(pair_table)

        layout.addStretch()

    def _filtered_cats(self) -> list[Cat]:
        room_filter = self._room_combo.currentData() or ""
        trait_filters = list(self._browse_trait_datas)
        result = []
        for cat in self._alive_cats:
            if room_filter and cat.room != room_filter:
                continue
            if trait_filters and not any(_cat_has_trait(cat, category, trait_key) for category, trait_key in trait_filters):
                continue
            result.append(cat)
        return result

    def _refresh_table(self):
        self._cat_table.setSortingEnabled(False)
        cats = self._filtered_cats()
        self._cat_table.setRowCount(len(cats))
        for row, cat in enumerate(cats):
            name_item = QTableWidgetItem(cat.name)
            name_item.setData(Qt.UserRole, id(cat))
            icon = _make_tag_icon(_cat_tags(cat), dot_size=10, spacing=3)
            if not icon.isNull():
                name_item.setIcon(icon)
            self._cat_table.setItem(row, 0, name_item)

            gender_item = QTableWidgetItem(cat.gender_display if hasattr(cat, 'gender_display') else cat.gender)
            gender_item.setTextAlignment(Qt.AlignCenter)
            self._cat_table.setItem(row, 1, gender_item)

            age_item = _SortByUserRoleItem(str(cat.age) if cat.age is not None else "—")
            age_item.setData(Qt.UserRole, cat.age if cat.age is not None else -1)
            age_item.setTextAlignment(Qt.AlignCenter)
            self._cat_table.setItem(row, 2, age_item)

            stat_sum = sum(cat.base_stats.values()) if cat.base_stats else 0
            sum_item = _SortByUserRoleItem(str(stat_sum))
            sum_item.setData(Qt.UserRole, stat_sum)
            sum_item.setTextAlignment(Qt.AlignCenter)
            self._cat_table.setItem(row, 3, sum_item)

            muts = ", ".join(_mutation_display_name(m) for m in cat.mutations) if cat.mutations else "—"
            self._cat_table.setItem(row, 4, QTableWidgetItem(muts))

            passives = ", ".join(_mutation_display_name(p) for p in cat.passive_abilities) if cat.passive_abilities else "—"
            self._cat_table.setItem(row, 5, QTableWidgetItem(passives))

            abils = ", ".join(_mutation_display_name(a) for a in cat.abilities) if cat.abilities else "—"
            self._cat_table.setItem(row, 6, QTableWidgetItem(abils))
        self._cat_table.setSortingEnabled(True)

    def _on_stim_changed(self):
        if len(self._selected_pair) == 2:
            self._update_outcome_panel(self._selected_pair[0], self._selected_pair[1])
        elif self._active_trait_data is not None:
            self._update_trait_detail_panel(self._active_trait_data)
        self._save_session_state()

    def _on_selection_changed(self):
        rows = sorted(set(idx.row() for idx in self._cat_table.selectionModel().selectedRows()))
        cats_by_id = {id(c): c for c in self._cats}
        selected: list[Cat] = []
        for r in rows:
            item = self._cat_table.item(r, 0)
            if item is None:
                continue
            cat_id = item.data(Qt.UserRole)
            cat = cats_by_id.get(cat_id)
            if cat is not None:
                selected.append(cat)

        if len(selected) == 2:
            self._selected_pair = selected
            self._pair_label.setText(f"Pair: {selected[0].name} \u00d7 {selected[1].name}")
            self._pair_label.setStyleSheet("color:#8fb8a0; font-size:11px; font-weight:bold;")
            self._update_outcome_panel(selected[0], selected[1])
            self._session_state["last_mode"] = "pair"
            self._save_session_state()
        elif len(selected) == 1:
            self._selected_pair = selected
            self._pair_label.setText(_tr("mutation_planner.selected_one", name=selected[0].name))
            self._pair_label.setStyleSheet("color:#aa8; font-size:11px;")
            self._clear_outcome_panel()
            self._save_session_state()
        else:
            self._selected_pair.clear()
            self._pair_label.setText(_tr("mutation_planner.pair_hint"))
            self._pair_label.setStyleSheet("color:#666; font-size:11px;")
            self._clear_outcome_panel()
            self._save_session_state()

    def _clear_outcome_panel(self):
        layout = self._outcome_layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._outcome_placeholder = QLabel(_tr("mutation_planner.outcome.placeholder_pair"))
        self._outcome_placeholder.setStyleSheet("color:#555; font-size:12px;")
        self._outcome_placeholder.setWordWrap(True)
        layout.addWidget(self._outcome_placeholder)
        layout.addStretch()

    def _sec_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#7d8bb0; font-size:13px; font-weight:bold; padding:4px 0 2px 0;")
        return lbl

    def _info_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#bbb; font-size:11px;")
        lbl.setWordWrap(True)
        return lbl

    def _update_outcome_panel(self, cat_a: Cat, cat_b: Cat):
        layout = self._outcome_layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        stim = self._stim_spin.value()
        favor_weight = _stimulation_inheritance_weight(stim)

        # ── Header ──
        layout.addWidget(self._sec_label(
            f"{cat_a.name} \u00d7 {cat_b.name}"
        ))

        # ── Top summary strip: stats table + pair context ──
        stat_table = QTableWidget(7, 4)
        stat_table.setHorizontalHeaderLabels([
            _tr("mutation_planner.pair.table.stat"),
            cat_a.name,
            cat_b.name,
            _tr("mutation_planner.pair.table.offspring_likely"),
        ])
        stat_table.verticalHeader().setVisible(False)
        stat_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        stat_table.setSelectionMode(QAbstractItemView.NoSelection)
        stat_table.setMaximumHeight(30 + 7 * 26)
        stat_table.setStyleSheet(
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; font-size:11px; }"
        )
        shh = stat_table.horizontalHeader()
        shh.setSectionResizeMode(0, QHeaderView.Interactive)
        shh.setSectionResizeMode(1, QHeaderView.Interactive)
        shh.setSectionResizeMode(2, QHeaderView.Interactive)
        shh.setSectionResizeMode(3, QHeaderView.Stretch)
        stat_table.setColumnWidth(0, 40)
        stat_table.setColumnWidth(1, 60)
        stat_table.setColumnWidth(2, 60)

        for row, stat_name in enumerate(STAT_NAMES):
            a_val = cat_a.base_stats.get(stat_name, 0)
            b_val = cat_b.base_stats.get(stat_name, 0)
            if a_val == b_val:
                likely = f"{a_val} (same)"
            elif a_val > b_val:
                likely = f"{a_val} ({favor_weight*100:.0f}%) or {b_val} ({(1-favor_weight)*100:.0f}%)"
            else:
                likely = f"{b_val} ({favor_weight*100:.0f}%) or {a_val} ({(1-favor_weight)*100:.0f}%)"

            stat_table.setItem(row, 0, QTableWidgetItem(stat_name))
            a_item = QTableWidgetItem(str(a_val))
            a_item.setTextAlignment(Qt.AlignCenter)
            stat_table.setItem(row, 1, a_item)
            b_item = QTableWidgetItem(str(b_val))
            b_item.setTextAlignment(Qt.AlignCenter)
            stat_table.setItem(row, 2, b_item)
            stat_table.setItem(row, 3, QTableWidgetItem(likely))

        stat_table.setToolTip(
            _tr("mutation_planner.pair.stat_summary", favor=f"{favor_weight*100:.1f}", stim=stim)
        )

        pair_context = QFrame()
        pair_context.setStyleSheet("QFrame { background:#0e0e20; border:1px solid #26264a; border-radius:4px; }")
        pair_context_layout = QVBoxLayout(pair_context)
        pair_context_layout.setContentsMargins(10, 8, 10, 8)
        pair_context_layout.setSpacing(4)

        pair_context_layout.addWidget(self._sec_label(_tr("mutation_planner.pair.partners", default="Partners")))
        pair_context_layout.addWidget(self._info_label(
            f"Partner A: {cat_a.name} ({cat_a.gender_display})\n"
            f"Partner B: {cat_b.name} ({cat_b.gender_display})"
        ))
        pair_context_layout.addWidget(self._sec_label(
            _tr("mutation_planner.pair.offspring_side", default="Likely offspring")
        ))
        pair_context_layout.addWidget(self._info_label(
            _tr("mutation_planner.pair.stat_summary", favor=f"{favor_weight*100:.1f}", stim=stim)
        ))

        top_strip = QWidget()
        top_strip_layout = QHBoxLayout(top_strip)
        top_strip_layout.setContentsMargins(0, 0, 0, 0)
        top_strip_layout.setSpacing(10)
        top_strip_layout.addWidget(stat_table, 2)
        top_strip_layout.addWidget(pair_context, 1)
        layout.addWidget(top_strip)

        # ── Disorder Inheritance ──
        layout.addWidget(self._sec_label(_tr("mutation_planner.pair.disorder_inheritance")))
        layout.addWidget(self._info_label(
            _tr("mutation_planner.pair.disorder_summary")
        ))

        a_disorders = cat_a.disorders or []
        b_disorders = cat_b.disorders or []

        disorder_rows: list[str] = []
        seen = set()
        for disorder in a_disorders:
            name = _mutation_display_name(disorder)
            key = disorder.lower()
            if key not in seen:
                seen.add(key)
                # Check if other parent also has it
                b_has = any(other.lower() == key for other in b_disorders)
                if b_has:
                    pct = 1.0 - (0.85 * 0.85)  # both parents: ~27.75%
                    disorder_rows.append(f"  {name}: {pct*100:.1f}% (both parents)")
                else:
                    disorder_rows.append(f"  {name}: 15% (from {cat_a.name})")
        for disorder in b_disorders:
            key = disorder.lower()
            if key not in seen:
                seen.add(key)
                name = _mutation_display_name(disorder)
                disorder_rows.append(f"  {name}: 15% (from {cat_b.name})")

        if disorder_rows:
            layout.addWidget(self._info_label("\n".join(disorder_rows)))
        else:
            layout.addWidget(self._info_label(_tr("mutation_planner.pair.no_disorders")))

        # Birth defect risk breakdown
        coi = kinship_coi(cat_a, cat_b)
        disorder_ch, part_defect_ch, combined_ch = _malady_breakdown(coi)
        inbred_note = ""
        if cat_a.inbredness is None and cat_b.inbredness is None:
            inbred_note = _tr("mutation_planner.pair.inbred_note_unknown")
        layout.addWidget(self._info_label(
            _tr(
                "mutation_planner.pair.risk_breakdown",
                disorder=f"{disorder_ch*100:.1f}",
                part=f"{part_defect_ch*100:.1f}",
                combined=f"{combined_ch*100:.1f}",
                note=inbred_note,
            )
        ))

        note_lbl = QLabel(_tr("mutation_planner.pair.note"))
        note_lbl.setStyleSheet("color:#665; font-size:10px; font-style:italic;")
        note_lbl.setWordWrap(True)
        layout.addWidget(note_lbl)
        # ── Visual Mutation Inheritance ──
        layout.addWidget(self._sec_label(_tr("mutation_planner.pair.visual_mutation_inheritance")))
        layout.addWidget(self._info_label(
            _tr("mutation_planner.pair.visual_summary", stim=stim, favor=f"{favor_weight*100:.1f}")
        ))

        # Group mutations by group_key
        a_by_group: dict[str, list[dict]] = {}
        for entry in (cat_a.visual_mutation_entries or []):
            gk = entry.get("group_key", "")
            a_by_group.setdefault(gk, []).append(entry)
        b_by_group: dict[str, list[dict]] = {}
        for entry in (cat_b.visual_mutation_entries or []):
            gk = entry.get("group_key", "")
            b_by_group.setdefault(gk, []).append(entry)

        all_groups = sorted(set(list(a_by_group.keys()) + list(b_by_group.keys())))
        if all_groups:
            mut_table = QTableWidget(len(all_groups), 4)
            mut_table.setHorizontalHeaderLabels([
                _tr("mutation_planner.pair.table.body_part"),
                cat_a.name,
                cat_b.name,
                _tr("mutation_planner.pair.table.odds"),
            ])
            mut_table.verticalHeader().setVisible(False)
            mut_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            mut_table.setSelectionMode(QAbstractItemView.NoSelection)
            mut_table.setMaximumHeight(min(30 + len(all_groups) * 26, 300))
            mut_table.setStyleSheet(
                "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; font-size:11px; }"
            )
            mhh = mut_table.horizontalHeader()
            mhh.setSectionResizeMode(0, QHeaderView.Interactive)
            mhh.setSectionResizeMode(1, QHeaderView.Stretch)
            mhh.setSectionResizeMode(2, QHeaderView.Stretch)
            mhh.setSectionResizeMode(3, QHeaderView.Interactive)
            mut_table.setColumnWidth(0, 100)
            mut_table.setColumnWidth(3, 120)

            for row, gk in enumerate(all_groups):
                a_entries = a_by_group.get(gk, [])
                b_entries = b_by_group.get(gk, [])
                part_label = a_entries[0].get("part_label", gk) if a_entries else (
                    b_entries[0].get("part_label", gk) if b_entries else gk
                )
                a_names = ", ".join(e.get("name", "?") for e in a_entries) or _tr("mutation_planner.pair.base")
                b_names = ", ".join(e.get("name", "?") for e in b_entries) or _tr("mutation_planner.pair.base")

                a_has_mutation = bool(a_entries)
                b_has_mutation = bool(b_entries)

                if a_has_mutation and b_has_mutation:
                    if a_names == b_names:
                        odds_text = _tr("mutation_planner.pair.odds.same_mutation")
                    else:
                        odds_text = _tr("mutation_planner.pair.odds.split", a=cat_a.name, b=cat_b.name)
                elif a_has_mutation:
                    odds_text = _tr("mutation_planner.pair.odds.mutated", name=cat_a.name, chance=f"{favor_weight*100:.0f}")
                elif b_has_mutation:
                    odds_text = _tr("mutation_planner.pair.odds.mutated", name=cat_b.name, chance=f"{favor_weight*100:.0f}")
                else:
                    odds_text = _tr("mutation_planner.pair.odds.none")

                mut_table.setItem(row, 0, QTableWidgetItem(part_label))
                mut_table.setItem(row, 1, QTableWidgetItem(a_names))
                mut_table.setItem(row, 2, QTableWidgetItem(b_names))
                mut_table.setItem(row, 3, QTableWidgetItem(odds_text))

            layout.addWidget(mut_table)
        else:
            layout.addWidget(self._info_label(_tr("mutation_planner.pair.no_visual_mutations")))

        # ── Passive Inheritance ──
        layout.addWidget(self._sec_label(_tr("mutation_planner.pair.passive_ability_inheritance")))
        passive_chance = 0.05 + 0.01 * stim
        spell_chance = 0.2 + 0.025 * stim
        layout.addWidget(self._info_label(
            _tr(
                "mutation_planner.pair.passive_spell_summary",
                passive=f"{min(passive_chance, 1.0)*100:.1f}",
                spell=f"{min(spell_chance, 1.0)*100:.1f}",
            )
        ))

        a_passives = list(getattr(cat_a, "passive_abilities", []) or [])
        b_passives = list(getattr(cat_b, "passive_abilities", []) or [])
        if a_passives or b_passives:
            chips, share_a, share_b = _inheritance_candidates(
                a_passives, b_passives, stim, _mutation_display_name,
            )
            passive_lines = []
            for label, tip in chips:
                passive_lines.append(f"  {label}")
            if passive_lines:
                layout.addWidget(self._info_label(
                    _tr("mutation_planner.pair.passive_weighted_prefix") +
                    "\n" +
                    "\n".join(passive_lines)
                ))

        if cat_a.abilities or cat_b.abilities:
            spell_chips, _, _ = _inheritance_candidates(
                cat_a.abilities or [], cat_b.abilities or [],
                stim, _mutation_display_name,
            )
            spell_lines = []
            for label, tip in spell_chips:
                spell_lines.append(f"  {label}")
            if spell_lines:
                layout.addWidget(self._info_label(
                    _tr("mutation_planner.pair.spell_weighted_prefix") +
                    "\n" +
                    "\n".join(spell_lines)
                ))

        # ── Lineage Info ──
        layout.addWidget(self._sec_label(_tr("mutation_planner.pair.lineage")))
        lineage_lines = []
        for label, cat in [(cat_a.name, cat_a), (cat_b.name, cat_b)]:
            pa_name = cat.parent_a.name if cat.parent_a else _tr("common.unknown", default="Unknown")
            pb_name = cat.parent_b.name if cat.parent_b else _tr("common.unknown", default="Unknown")
            inbred_str = f"{cat.inbredness:.2f}" if cat.inbredness is not None else "?"
            lineage_lines.append(f"{label}: parents = {pa_name} \u00d7 {pb_name}, inbreeding = {inbred_str}")

            # Show grandparent disorders if available
            for gp_label, gp in [("  GP", cat.parent_a), ("  GP", cat.parent_b)]:
                if gp is not None and gp.passive_abilities:
                    gp_passives = ", ".join(_mutation_display_name(p) for p in gp.passive_abilities)
                    lineage_lines.append(f"    {gp.name} passives: {gp_passives}")

        layout.addWidget(self._info_label("\n".join(lineage_lines)))

        layout.addStretch()


class FurnitureView(QWidget):
    """Dedicated view for furniture placement and current room stat totals."""

    _WHOLE_HOME_KEY = "__whole_home__"

    _ROOM_ORDER = {
        "Attic": 0,
        "Floor2_Small": 1,
        "Floor2_Large": 2,
        "Floor1_Large": 3,
        "Floor1_Small": 4,
    }

    _STAT_ACCENTS = {
        "Appeal": "#d8b25e",
        "Comfort": "#68c7cf",
        "Stimulation": "#8f8fff",
        "Health": "#6fb07a",
        "Evolution": "#d96fb4",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QWidget { background:#0a0a18; }"
            "QLabel { color:#bbb; }"
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
            "QTableWidget { background:#101023; color:#ddd; border:1px solid #26264a; }"
            "QHeaderView::section { background:#151532; color:#7d8bb0; border:none; padding:4px; font-weight:bold; }"
            "QTextBrowser { background:#0d0d1c; color:#ddd; border:1px solid #26264a; border-radius:6px; padding:10px; }"
            "QFrame#furnitureStatCard { background:#111124; border:1px solid #26264a; border-radius:8px; }"
            "QLabel#furnitureStatTitle { color:#9ca6c7; font-size:10px; font-weight:bold; }"
            "QLabel#furnitureStatValue { color:#f3f3ff; font-size:18px; font-weight:bold; }"
        )
        self._cats: list[Cat] = []
        self._furniture: list[FurnitureItem] = []
        self._furniture_by_room: dict[str, list[FurnitureItem]] = {}
        self._furniture_data: dict[str, FurnitureDefinition] = {}
        self._room_summaries: list[FurnitureRoomSummary] = []
        self._available_rooms: list[str] = list(self._ROOM_ORDER.keys())
        self._house_raw = {key: 0.0 for key in FURNITURE_ROOM_STAT_KEYS}
        self._house_effective = {key: 0.0 for key in FURNITURE_ROOM_STAT_KEYS}
        self._session_state: dict = _load_ui_state("furniture_state")
        self._restoring_session_state = False
        self._layout_splitter_restore_pending = False
        self._pending_layout_splitter_sizes: Optional[list[int]] = None
        self._splitter_restore_pending = False
        self._pending_splitter_sizes: Optional[list[int]] = None
        self._selected_room_key = ""
        self._suppress_selection_changed = False
        self._pinned_item_keys: set[int] = set()
        self._pinned_only = False
        self._table_sort_column: Optional[int] = None
        self._table_sort_order = Qt.AscendingOrder
        self._item_table_sort_column: Optional[int] = None
        self._item_table_sort_order = Qt.AscendingOrder
        self._layout_splitter: Optional[QSplitter] = None
        self._splitter: Optional[QSplitter] = None
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        self._title = QLabel()
        self._title.setStyleSheet("color:#ddd; font-size:18px; font-weight:bold;")
        self._subtitle = QLabel()
        self._subtitle.setStyleSheet("color:#666; font-size:11px;")
        self._subtitle.setWordWrap(True)
        self._subtitle.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self._title)
        header.addStretch()
        header.addWidget(self._subtitle, 1)
        root.addLayout(header)

        cards = QHBoxLayout()
        cards.setSpacing(8)
        self._card_title_labels: dict[str, QLabel] = {}
        self._card_value_labels: dict[str, QLabel] = {}
        self._card_note_labels: dict[str, QLabel] = {}
        for stat in FURNITURE_ROOM_STAT_KEYS:
            accent = self._STAT_ACCENTS[stat]
            card = QFrame()
            card.setObjectName("furnitureStatCard")
            card.setStyleSheet(f"QFrame#furnitureStatCard {{ border-color:{accent}; }}")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(2)

            title = QLabel()
            title.setObjectName("furnitureStatTitle")
            title.setStyleSheet(f"QLabel#furnitureStatTitle {{ color:{accent}; }}")
            value = QLabel("0")
            value.setObjectName("furnitureStatValue")
            note = QLabel("")
            note.setStyleSheet("color:#8d8da8; font-size:10px;")
            note.setWordWrap(True)

            card_layout.addWidget(title)
            card_layout.addWidget(value)
            card_layout.addWidget(note)
            cards.addWidget(card, 1)

            self._card_title_labels[stat] = title
            self._card_value_labels[stat] = value
            self._card_note_labels[stat] = note
        root.addLayout(cards)

        self._note = QLabel(
            _tr(
                "furniture.note.comfort_penalty",
                default="Comfort includes the -1 per cat above 4 room penalty.",
            )
        )
        self._note.setStyleSheet("color:#8d8da8; font-size:11px;")
        self._note.setWordWrap(True)
        root.addWidget(self._note)

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setStyleSheet("QSplitter::handle { background:#1e1e38; }")
        self._layout_splitter = content_splitter

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background:#1e1e38; }")

        self._table = QTableWidget(0, 11)
        self._table.setIconSize(QSize(60, 20))
        self._table.setHorizontalHeaderLabels([
            _tr("furniture.table.order", default="#"),
            _tr("furniture.table.room", default="Room"),
            _tr("furniture.table.pieces", default="Pieces"),
            _tr("furniture.table.cats", default="Cats"),
            _tr("furniture.table.appeal", default="APP"),
            _tr("furniture.table.comfort_raw", default="COMF Raw"),
            _tr("furniture.table.crowd", default="Crowd"),
            _tr("furniture.table.comfort", default="COMF"),
            _tr("furniture.table.stimulation", default="STIM"),
            _tr("furniture.table.health", default="HEA"),
            _tr("furniture.table.mutation", default="MUT"),
        ])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(False)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        hh = self._table.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setSectionsMovable(True)
        hh.setSortIndicatorShown(False)
        hh.sectionClicked.connect(self._on_table_header_clicked)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        for col in (2, 3):
            hh.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        for col in (4, 5, 6, 7, 8, 9, 10):
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
        for col, width in {
            0: 32, 1: 118, 2: 52, 3: 42, 4: 60, 5: 74, 6: 54, 7: 72, 8: 72, 9: 58, 10: 66,
        }.items():
            self._table.setColumnWidth(col, width)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setFrameShape(QFrame.NoFrame)
        self._browser.setStyleSheet(
            "QTextBrowser { background:#0d0d1c; color:#ddd; border:1px solid #26264a; border-radius:6px; padding:10px; }"
            "QTextBrowser h2 { color:#f0f0ff; margin-top: 4px; margin-bottom: 8px; }"
            "QTextBrowser h3 { color:#c9d6ff; margin-top: 12px; margin-bottom: 4px; }"
            "QTextBrowser table { border-collapse: collapse; margin-top: 4px; margin-bottom: 8px; }"
            "QTextBrowser td { padding: 2px 8px 2px 0; vertical-align: top; }"
            "QTextBrowser ul { margin-left: 18px; }"
            "QTextBrowser li { margin-bottom: 4px; }"
            "QTextBrowser .muted { color:#8d8da8; }"
        )

        splitter.addWidget(self._table)
        splitter.addWidget(self._browser)
        # Bias the default layout toward the detail pane so more of the lower
        # window is visible before the user starts dragging the splitter.
        splitter.setSizes([300, 420])
        splitter.splitterMoved.connect(lambda *_: self._save_session_state())
        self._splitter = splitter
        right_layout.addWidget(splitter, 1)

        item_panel = QWidget()
        item_panel_layout = QVBoxLayout(item_panel)
        item_panel_layout.setContentsMargins(0, 0, 0, 0)
        item_panel_layout.setSpacing(8)

        self._item_title = QLabel()
        self._item_title.setStyleSheet("color:#ddd; font-size:18px; font-weight:bold;")
        self._item_subtitle = QLabel()
        self._item_subtitle.setStyleSheet("color:#8d8da8; font-size:11px;")
        self._item_subtitle.setWordWrap(True)
        item_panel_layout.addWidget(self._item_title)
        item_panel_layout.addWidget(self._item_subtitle)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._search_label = QLabel()
        self._search_label.setStyleSheet("color:#888; font-size:11px;")
        search_row.addWidget(self._search_label)
        self._search = QLineEdit()
        self._search.setClearButtonEnabled(True)
        self._search.setPlaceholderText(
            _tr("furniture.search.placeholder", default="Search furniture items…")
        )
        self._search.setStyleSheet(
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:4px 8px; }"
        )
        self._search.textChanged.connect(self._refresh_current_item_table)
        self._search.textChanged.connect(lambda _: self._save_session_state())
        search_row.addWidget(self._search, 1)
        self._pin_toggle_btn = QPushButton(_tr("bulk.toggle_pin", default="Toggle Pin"))
        self._pin_toggle_btn.setMinimumWidth(92)
        self._pin_toggle_btn.setStyleSheet(
            "QPushButton { background:#2a3a2a; color:#c8dcc8; border:1px solid #4a6a4a;"
            " border-radius:4px; padding:4px 10px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#3a4a3a; }"
            "QPushButton:pressed { background:#1e2e1e; }"
        )
        self._pin_toggle_btn.clicked.connect(self._toggle_selected_item_pins)
        search_row.addWidget(self._pin_toggle_btn)
        self._pin_only_check = QToolButton()
        self._pin_only_check.setCheckable(True)
        self._pin_only_check.setCursor(Qt.PointingHandCursor)
        self._pin_only_check.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._pin_only_check.setIconSize(QSize(16, 16))
        self._pin_only_check.setFixedSize(28, 24)
        self._pin_only_check.setStyleSheet(
            "QToolButton { background:#1a1a32; color:#888; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:2px; }"
            "QToolButton:hover { background:#222244; }"
            "QToolButton:checked { background:#2a2a5a; border-color:#4a4a8a; }"
        )
        self._pin_only_check.toggled.connect(self._on_pin_only_changed)
        self._pin_only_check.toggled.connect(lambda _: self._save_session_state())
        self._pin_only_check.setIcon(_make_pin_icon(True, 16))
        search_row.addWidget(self._pin_only_check)
        item_panel_layout.addLayout(search_row)

        self._item_table = QTableWidget(0, 9)
        self._item_table.setIconSize(QSize(60, 20))
        self._item_table.setHorizontalHeaderLabels([
            _tr("furniture.item.table.id", default="#"),
            _tr("furniture.item.table.pin", default="Pin"),
            _tr("furniture.item.table.item", default="Item"),
            _tr("furniture.item.table.appeal", default="APP"),
            _tr("furniture.item.table.comfort", default="COMF"),
            _tr("furniture.item.table.stim", default="STIM"),
            _tr("furniture.item.table.health", default="HEA"),
            _tr("furniture.item.table.mutation", default="MUT"),
            _tr("furniture.item.table.notes", default="Notes"),
        ])
        self._item_table.verticalHeader().setVisible(False)
        self._item_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._item_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._item_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._item_table.setSortingEnabled(False)
        self._item_table.setAlternatingRowColors(True)
        self._item_table.setWordWrap(True)
        self._item_table.setStyleSheet(
            "QTableWidget { background:#0d0d1c; color:#ddd; border:1px solid #26264a; border-radius:6px; }"
            "QHeaderView::section { background:#151532; color:#7d8bb0; border:none; padding:4px; font-weight:bold; }"
        )
        item_header = self._item_table.horizontalHeader()
        item_header.setSectionsMovable(False)
        item_header.setSortIndicatorShown(False)
        item_header.sectionClicked.connect(self._on_item_table_header_clicked)
        item_header.setStretchLastSection(False)
        for col in range(9):
            item_header.setSectionResizeMode(col, QHeaderView.Interactive)
        self._item_table.itemClicked.connect(self._on_item_table_item_clicked)
        self._item_table.setColumnWidth(0, 32)
        self._item_table.setColumnWidth(1, 34)
        self._item_table.setColumnWidth(2, 140)
        self._item_table.setColumnWidth(3, 46)
        self._item_table.setColumnWidth(4, 46)
        self._item_table.setColumnWidth(5, 46)
        self._item_table.setColumnWidth(6, 46)
        self._item_table.setColumnWidth(7, 46)
        self._item_table.setColumnWidth(8, 124)
        item_panel_layout.addWidget(self._item_table, 1)

        content_splitter.addWidget(item_panel)
        content_splitter.addWidget(right_panel)
        # Keep the default split closer to center so the item list and details
        # share the view more evenly on first open.
        content_splitter.setSizes([640, 700])
        content_splitter.splitterMoved.connect(lambda *_: self._save_session_state())
        root.addWidget(content_splitter, 1)

        _enforce_min_font_in_widget_tree(self)
        self.retranslate_ui()
        self._browser.setHtml(self._build_empty_html())
        self._clear_item_table()

    def set_context(self, cats: list[Cat], furniture: list[FurnitureItem], furniture_data: dict[str, FurnitureDefinition] | None = None, available_rooms: list[str] | None = None):
        self._cats = cats or []
        self._furniture = furniture or []
        self._furniture_data = furniture_data or {}
        self._furniture_by_room = {}
        for item in self._furniture:
            self._furniture_by_room.setdefault(item.room or "", []).append(item)
        if available_rooms:
            allowed = {room for room in self._ROOM_ORDER.keys() if room in set(available_rooms)}
            self._available_rooms = [room for room in self._ROOM_ORDER.keys() if room in allowed]
        else:
            self._available_rooms = list(self._ROOM_ORDER.keys())
        self._build_room_summaries()
        self._refresh_table()
        self._restore_session_state()

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_layout_splitter_restore()
        self._schedule_splitter_restore()

    def hideEvent(self, event):
        self._save_session_state()
        super().hideEvent(event)

    def retranslate_ui(self):
        self._title.setText(_tr("furniture.title", default="Furniture"))
        self._search_label.setText(_tr("furniture.search.label", default="Search:"))
        self._search.setPlaceholderText(_tr("furniture.search.placeholder", default="Search furniture items…"))
        self._pin_toggle_btn.setText(_tr("bulk.toggle_pin", default="Toggle Pin"))
        self._pin_toggle_btn.setToolTip(_tr("bulk.toggle_pin.tooltip", default="Toggle pin for selected furniture items"))
        self._pin_only_check.setToolTip(_tr("furniture.pin_only.tooltip", default="Show only pinned items in the current room."))
        self._pin_only_check.setIcon(_make_pin_icon(True, 16))
        self._table.setHorizontalHeaderLabels([
            _tr("furniture.table.order", default="#"),
            _tr("furniture.table.room", default="Room"),
            _tr("furniture.table.pieces", default="Pieces"),
            _tr("furniture.table.cats", default="Cats"),
            _tr("furniture.table.appeal", default="APP"),
            _tr("furniture.table.comfort_raw", default="COMF Raw"),
            _tr("furniture.table.crowd", default="Crowd"),
            _tr("furniture.table.comfort", default="COMF"),
            _tr("furniture.table.stimulation", default="STIM"),
            _tr("furniture.table.health", default="HEA"),
            _tr("furniture.table.mutation", default="MUT"),
        ])
        for stat in FURNITURE_ROOM_STAT_KEYS:
            self._card_title_labels[stat].setText(
                _tr(f"furniture.stat.{stat.lower()}", default=FURNITURE_ROOM_STAT_LABELS[stat])
            )
        self._refresh_cards()
        self._refresh_table()

    def save_session_state(self):
        self._save_session_state()

    def _save_session_state(self):
        if self._restoring_session_state:
            return
        layout_splitter_sizes = list(self._layout_splitter.sizes()) if self._layout_splitter is not None else []
        splitter_sizes = list(self._splitter.sizes()) if self._splitter is not None else []
        item_header_state = ""
        if self._item_table is not None:
            try:
                item_header_state = self._item_table.horizontalHeader().saveState().toBase64().data().decode("ascii")
            except Exception:
                item_header_state = ""
        _save_ui_state("furniture_state", {
            "selected_room": self._selected_room_key,
            "search": self._search.text().strip(),
            "layout_splitter_sizes": layout_splitter_sizes,
            "splitter_sizes": splitter_sizes,
            "item_header_state": item_header_state,
            "pinned_item_keys": sorted(self._pinned_item_keys),
            "pinned_only": self._pinned_only,
            "table_sort_column": self._table_sort_column,
            "table_sort_order": int(self._table_sort_order.value),
            "item_table_sort_column": self._item_table_sort_column,
            "item_table_sort_order": int(self._item_table_sort_order.value),
        })

    def _on_pin_only_changed(self, checked: bool):
        self._pinned_only = bool(checked)
        self._pin_only_check.setIcon(_make_pin_icon(True, 16))
        self._refresh_current_item_table()

    def _refresh_current_item_table(self, selected_item_keys: list[int] | None = None):
        selected = self._table.selectedRanges()
        if not selected:
            self._clear_item_table()
            return
        row = selected[0].topRow()
        item = self._table.item(row, 0)
        if item is None:
            return
        data = item.data(Qt.UserRole + 1)
        if not isinstance(data, dict):
            return
        summary = data.get("summary")
        if not isinstance(summary, FurnitureRoomSummary):
            return
        self._build_item_table(summary, selected_item_keys=selected_item_keys)

    def _capture_item_table_view_state(self) -> dict[str, int]:
        if self._item_table is None:
            return {}
        return {
            "vscroll": int(self._item_table.verticalScrollBar().value()),
            "hscroll": int(self._item_table.horizontalScrollBar().value()),
        }

    def _capture_item_table_selection_keys(self) -> list[int]:
        if self._item_table is None or self._item_table.selectionModel() is None:
            return []
        keys: list[int] = []
        for idx in self._item_table.selectionModel().selectedRows():
            item = self._item_table.item(idx.row(), 1)
            if item is None:
                continue
            key_value = item.data(Qt.UserRole + 1)
            if isinstance(key_value, int):
                keys.append(key_value)
        return keys

    def _restore_item_table_selection(self, keys: list[int]):
        if self._item_table is None or not keys:
            return
        selection_model = self._item_table.selectionModel()
        if selection_model is None:
            return
        key_set = set(keys)
        first = True
        for row in range(self._item_table.rowCount()):
            item = self._item_table.item(row, 1)
            if item is None:
                continue
            key_value = item.data(Qt.UserRole + 1)
            if not isinstance(key_value, int) or key_value not in key_set:
                continue
            flags = QItemSelectionModel.SelectionFlag.Rows
            if first:
                flags |= QItemSelectionModel.SelectionFlag.ClearAndSelect
                first = False
            else:
                flags |= QItemSelectionModel.SelectionFlag.Select
            selection_model.select(self._item_table.model().index(row, 0), flags)
        if first:
            selection_model.clearSelection()

    def _restore_item_table_view_state(self, state: dict[str, int]):
        if self._item_table is None or not state:
            return
        try:
            self._item_table.horizontalScrollBar().setValue(int(state.get("hscroll", 0)))
        except Exception:
            pass
        try:
            self._item_table.verticalScrollBar().setValue(int(state.get("vscroll", 0)))
        except Exception:
            pass

    def _toggle_item_pin(self, item_key: int):
        scroll_state = self._capture_item_table_view_state()
        if item_key in self._pinned_item_keys:
            self._pinned_item_keys.remove(item_key)
        else:
            self._pinned_item_keys.add(item_key)
        self._refresh_current_item_table()
        self._restore_item_table_view_state(scroll_state)

    def _toggle_selected_item_pins(self):
        selection = self._capture_item_table_selection_keys()
        if not selection:
            current_row = self._item_table.currentRow() if self._item_table is not None else -1
            if current_row >= 0:
                item = self._item_table.item(current_row, 1)
                if item is not None:
                    key_value = item.data(Qt.UserRole + 1)
                    if isinstance(key_value, int):
                        selection = [key_value]
        if not selection:
            return
        scroll_state = self._capture_item_table_view_state()
        for key in selection:
            if key in self._pinned_item_keys:
                self._pinned_item_keys.remove(key)
            else:
                self._pinned_item_keys.add(key)
        self._refresh_current_item_table(selected_item_keys=selection)
        self._restore_item_table_view_state(scroll_state)

    def _on_item_table_item_clicked(self, item: QTableWidgetItem):
        if item.column() != 1:
            return
        key_value = item.data(Qt.UserRole + 1)
        if isinstance(key_value, int):
            self._toggle_item_pin(key_value)

    def _apply_table_sort(self, column: int, order: Qt.SortOrder):
        self._table_sort_column = column
        self._table_sort_order = order
        header = self._table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(column, order)
        self._table.sortItems(column, order)

    def _on_table_header_clicked(self, column: int):
        order = Qt.AscendingOrder
        if self._table_sort_column == column:
            order = Qt.DescendingOrder if self._table_sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        self._apply_table_sort(column, order)
        self._save_session_state()

    def _apply_item_table_sort(self, column: int, order: Qt.SortOrder):
        scroll_state = self._capture_item_table_view_state()
        self._item_table_sort_column = column
        self._item_table_sort_order = order
        header = self._item_table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(column, order)
        self._item_table.sortItems(column, order)
        self._restore_item_table_view_state(scroll_state)

    def _on_item_table_header_clicked(self, column: int):
        order = Qt.AscendingOrder
        if self._item_table_sort_column == column:
            order = Qt.DescendingOrder if self._item_table_sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        self._apply_item_table_sort(column, order)
        self._save_session_state()

    def _schedule_layout_splitter_restore(self):
        if self._layout_splitter is None or self._pending_layout_splitter_sizes is None or self._layout_splitter_restore_pending:
            return
        self._layout_splitter_restore_pending = True
        QTimer.singleShot(0, self._apply_pending_layout_splitter_sizes)

    def _apply_pending_layout_splitter_sizes(self):
        self._layout_splitter_restore_pending = False
        if self._layout_splitter is None or self._pending_layout_splitter_sizes is None:
            return
        if not self.isVisible() or self._layout_splitter.width() <= 0 or self._layout_splitter.height() <= 0:
            self._schedule_layout_splitter_restore()
            return
        self._restoring_session_state = True
        try:
            self._layout_splitter.setSizes(self._pending_layout_splitter_sizes)
        finally:
            self._restoring_session_state = False
        self._pending_layout_splitter_sizes = None
        self._save_session_state()

    def _schedule_splitter_restore(self):
        if self._splitter is None or self._pending_splitter_sizes is None or self._splitter_restore_pending:
            return
        self._splitter_restore_pending = True
        QTimer.singleShot(0, self._apply_pending_splitter_sizes)

    def _apply_pending_splitter_sizes(self):
        self._splitter_restore_pending = False
        if self._splitter is None or self._pending_splitter_sizes is None:
            return
        if not self.isVisible() or self._splitter.width() <= 0 or self._splitter.height() <= 0:
            self._schedule_splitter_restore()
            return
        self._restoring_session_state = True
        try:
            self._splitter.setSizes(self._pending_splitter_sizes)
        finally:
            self._restoring_session_state = False
        self._pending_splitter_sizes = None
        self._save_session_state()

    def _restore_session_state(self):
        state = self._session_state
        self._restoring_session_state = True
        try:
            search = str(state.get("search", "") or "")
            if search != self._search.text():
                self._search.blockSignals(True)
                self._search.setText(search)
                self._search.blockSignals(False)
            self._selected_room_key = str(state.get("selected_room", "") or "")
            layout_splitter_sizes = state.get("layout_splitter_sizes", [])
            if isinstance(layout_splitter_sizes, list) and len(layout_splitter_sizes) == 2:
                self._pending_layout_splitter_sizes = [
                    max(10, int(layout_splitter_sizes[0] or 0)),
                    max(10, int(layout_splitter_sizes[1] or 0)),
                ]
                self._schedule_layout_splitter_restore()
            splitter_sizes = state.get("splitter_sizes", [])
            if isinstance(splitter_sizes, list) and len(splitter_sizes) == 2:
                self._pending_splitter_sizes = [
                    max(10, int(splitter_sizes[0] or 0)),
                    max(10, int(splitter_sizes[1] or 0)),
                ]
                self._schedule_splitter_restore()
            pinned_item_keys = state.get("pinned_item_keys", [])
            if isinstance(pinned_item_keys, list):
                pinned_keys: set[int] = set()
                for key in pinned_item_keys:
                    try:
                        pinned_keys.add(int(key))
                    except (TypeError, ValueError):
                        continue
                self._pinned_item_keys = pinned_keys
            self._pinned_only = bool(state.get("pinned_only", False))
            if hasattr(self, "_pin_only_check"):
                self._pin_only_check.blockSignals(True)
                self._pin_only_check.setChecked(self._pinned_only)
                self._pin_only_check.blockSignals(False)
                self._pin_only_check.setIcon(_make_pin_icon(True, 16))
            table_sort_column = state.get("table_sort_column")
            if isinstance(table_sort_column, int):
                self._table_sort_column = table_sort_column
                self._table_sort_order = Qt.SortOrder(int(state.get("table_sort_order", int(Qt.AscendingOrder.value))))
            item_table_sort_column = state.get("item_table_sort_column")
            if isinstance(item_table_sort_column, int):
                self._item_table_sort_column = item_table_sort_column
                self._item_table_sort_order = Qt.SortOrder(int(state.get("item_table_sort_order", int(Qt.AscendingOrder.value))))
        finally:
            self._restoring_session_state = False
        item_header_state = state.get("item_header_state", "")
        if isinstance(item_header_state, str) and item_header_state:
            try:
                self._item_table.horizontalHeader().restoreState(QByteArray.fromBase64(item_header_state.encode("ascii")))
            except Exception:
                pass
        self._refresh_current_item_table()

    def reset_to_defaults(self):
        """Restore the furniture view to its default search and splitter state."""
        self._session_state = {}
        self._restoring_session_state = True
        try:
            self._pending_layout_splitter_sizes = None
            self._pending_splitter_sizes = None
            self._search.setText("")
            self._pinned_only = False
            if hasattr(self, "_pin_only_check"):
                self._pin_only_check.blockSignals(True)
                self._pin_only_check.setChecked(False)
                self._pin_only_check.blockSignals(False)
                self._pin_only_check.setIcon(_make_pin_icon(True, 16))
            self._selected_room_key = ""
            if self._layout_splitter is not None:
                self._layout_splitter.setSizes([640, 700])
            if self._splitter is not None:
                self._splitter.setSizes([420, 300])
        finally:
            self._restoring_session_state = False
        self.retranslate_ui()
        self._refresh_table()
        self._save_session_state()

    @staticmethod
    def _fmt(value: float) -> str:
        number = float(value)
        if number == 0:
            return "0"
        if number.is_integer():
            return f"{int(number):+d}"
        return f"{number:+.1f}".rstrip("0").rstrip(".")

    @staticmethod
    def _stat_brush(value: float) -> QBrush:
        if value > 0:
            return QBrush(QColor(98, 194, 135))
        if value < 0:
            return QBrush(QColor(216, 120, 120))
        return QBrush(QColor(160, 160, 175))

    def _room_sort_key(self, room: str):
        if room == self._WHOLE_HOME_KEY:
            return (0, "")
        if room in self._ROOM_ORDER:
            return (self._ROOM_ORDER[room] + 1, room)
        if not room:
            return (7, "")
        return (50, room.lower())

    def _room_label(self, room: str) -> str:
        if room == self._WHOLE_HOME_KEY:
            return _tr("furniture.room.whole_home", default="Whole Home")
        if not room:
            return _tr("furniture.room.unplaced", default="Unplaced")
        return ROOM_DISPLAY.get(room, room)

    def _room_order_number(self, room: str) -> int:
        if room == self._WHOLE_HOME_KEY:
            return 1
        if not room:
            return 7
        order = self._ROOM_ORDER.get(room)
        if order is None:
            return 50
        return order + 2

    def _room_note(self, summary: FurnitureRoomSummary) -> str:
        if summary.room == self._WHOLE_HOME_KEY:
            return _tr(
                "furniture.detail.whole_home_note",
                default="Aggregated from all placed rooms. Unplaced items are excluded.",
            )
        if not summary.room:
            return _tr(
                "furniture.detail.unplaced_note",
                default="Unplaced items do not contribute to room stats until they are assigned to a room.",
            )
        return _tr(
            "furniture.detail.room_note",
            default="Comfort is reduced by one for every cat above four in the room.",
        )

    def _clear_item_table(self):
        self._item_title.setText(_tr("furniture.items.title", default="Furniture Items"))
        self._item_subtitle.setText(_tr("furniture.items.empty", default="Select a room to inspect the actual furniture items in that room."))
        self._item_table.setRowCount(0)

    def _item_notes(self, effects: dict[str, float]) -> str:
        notes: list[str] = []
        for key, value in sorted(effects.items(), key=lambda kv: kv[0].lower()):
            if key in FURNITURE_ROOM_STAT_KEYS or not value:
                continue
            note_value = "" if key.lower().startswith("special") and float(value) == 1.0 else f" {self._fmt(value)}"
            notes.append(f"{key}{note_value}")
        return ", ".join(notes)

    def _build_room_summaries(self):
        allowed_rooms = set(self._available_rooms or self._ROOM_ORDER.keys())
        furniture_by_room = {
            room: items
            for room, items in self._furniture_by_room.items()
            if not room or room in allowed_rooms
        }
        summaries = build_furniture_room_summaries(
            furniture_by_room,
            self._furniture_data,
            self._cats,
            room_order=self._available_rooms or self._ROOM_ORDER.keys(),
        )
        summaries.sort(key=lambda s: self._room_sort_key(s.room))
        placed_summaries = [summary for summary in summaries if summary.room]
        whole_home_items = [item for summary in placed_summaries for item in summary.items]
        whole_home_raw = {key: 0.0 for key in FURNITURE_ROOM_STAT_KEYS}
        whole_home_effective = {key: 0.0 for key in FURNITURE_ROOM_STAT_KEYS}
        whole_home_all: dict[str, float] = {}
        whole_home_cat_count = 0
        whole_home_crowd_penalty = 0
        whole_home_dead_bodies = 0
        for summary in placed_summaries:
            whole_home_cat_count += summary.cat_count
            whole_home_crowd_penalty += summary.crowd_penalty
            whole_home_dead_bodies += summary.dead_body_penalty
            for key in FURNITURE_ROOM_STAT_KEYS:
                whole_home_raw[key] += summary.raw_effects.get(key, 0.0)
                whole_home_effective[key] += summary.effective_effects.get(key, 0.0)
            for key, value in summary.all_effects.items():
                whole_home_all[key] = whole_home_all.get(key, 0.0) + value

        whole_home_summary = FurnitureRoomSummary(
            room=self._WHOLE_HOME_KEY,
            cat_count=whole_home_cat_count,
            furniture_count=len(whole_home_items),
            items=tuple(whole_home_items),
            raw_effects=whole_home_raw,
            effective_effects=whole_home_effective,
            all_effects=whole_home_all,
            crowd_penalty=whole_home_crowd_penalty,
            dead_body_penalty=whole_home_dead_bodies,
        )
        placed_summaries = [summary for summary in summaries if summary.room]
        unplaced_summaries = [summary for summary in summaries if not summary.room]
        self._room_summaries = [whole_home_summary, *placed_summaries, *unplaced_summaries]

        for key in FURNITURE_ROOM_STAT_KEYS:
            self._house_raw[key] = 0.0
            self._house_effective[key] = 0.0
        for summary in summaries:
            if not summary.room:
                continue
            for key in FURNITURE_ROOM_STAT_KEYS:
                self._house_raw[key] += summary.raw_effects.get(key, 0.0)
                self._house_effective[key] += summary.effective_effects.get(key, 0.0)

    def _refresh_cards(self):
        values = {
            "Appeal": self._house_raw.get("Appeal", 0.0),
            "Comfort": self._house_effective.get("Comfort", 0.0),
            "Stimulation": self._house_raw.get("Stimulation", 0.0),
            "Health": self._house_effective.get("Health", 0.0),
            "Evolution": self._house_raw.get("Evolution", 0.0),
        }
        notes = {
            "Appeal": _tr("furniture.card.appeal_note", default="House-wide furniture appeal."),
            "Comfort": _tr("furniture.card.comfort_note", default="After room crowding penalties."),
            "Stimulation": _tr("furniture.card.stimulation_note", default="Affects inherited item quality."),
            "Health": _tr("furniture.card.health_note", default="After dead-body penalties."),
            "Evolution": _tr("furniture.card.mutation_note", default="Mutation chance total."),
        }
        for stat in FURNITURE_ROOM_STAT_KEYS:
            self._card_value_labels[stat].setText(self._fmt(values.get(stat, 0.0)))
            self._card_note_labels[stat].setText(notes[stat])

    def _refresh_table(self):
        self._refresh_cards()
        self._table.setSortingEnabled(False)
        visible = list(self._room_summaries)

        self._table.setRowCount(len(visible))
        for row, summary in enumerate(visible):
            room_number = self._room_order_number(summary.room)
            room_label = self._room_label(summary.room)
            row_items = [
                _SortByUserRoleItem(str(room_number)),
                _SortByUserRoleItem(room_label),
                _SortByUserRoleItem(str(summary.furniture_count)),
                _SortByUserRoleItem(str(summary.cat_count)),
                _SortByUserRoleItem(self._fmt(summary.raw_effects.get("Appeal", 0.0))),
                _SortByUserRoleItem(self._fmt(summary.raw_effects.get("Comfort", 0.0))),
                _SortByUserRoleItem(self._fmt(-summary.crowd_penalty if summary.crowd_penalty else 0.0)),
                _SortByUserRoleItem(self._fmt(summary.effective_effects.get("Comfort", 0.0))),
                _SortByUserRoleItem(self._fmt(summary.raw_effects.get("Stimulation", 0.0))),
                _SortByUserRoleItem(self._fmt(summary.effective_effects.get("Health", 0.0))),
                _SortByUserRoleItem(self._fmt(summary.raw_effects.get("Evolution", 0.0))),
            ]
            user_roles = [
                room_number,
                self._room_sort_key(summary.room),
                summary.furniture_count,
                summary.cat_count,
                summary.raw_effects.get("Appeal", 0.0),
                summary.raw_effects.get("Comfort", 0.0),
                -summary.crowd_penalty if summary.crowd_penalty else 0.0,
                summary.effective_effects.get("Comfort", 0.0),
                summary.raw_effects.get("Stimulation", 0.0),
                summary.effective_effects.get("Health", 0.0),
                summary.raw_effects.get("Evolution", 0.0),
            ]
            for col, item in enumerate(row_items):
                item.setData(Qt.UserRole, user_roles[col])
                item.setData(Qt.UserRole + 1, {
                    "room": summary.room,
                    "room_display": room_label,
                    "summary": summary,
                })
                if summary.room == self._WHOLE_HOME_KEY:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if col >= 4:
                    item.setForeground(self._stat_brush(float(user_roles[col])))
                if col == 1 and not summary.room:
                    item.setForeground(QBrush(QColor(160, 160, 175)))
                self._table.setItem(row, col, item)

        if self._table.rowCount() == 0:
            self._browser.setHtml(self._build_empty_html())
            self._clear_item_table()
        else:
            if self._table_sort_column is not None:
                self._apply_table_sort(self._table_sort_column, self._table_sort_order)
            target_room = self._selected_room_key or self._WHOLE_HOME_KEY
            selected_row = None
            selected_summary = None
            for row in range(self._table.rowCount()):
                item = self._table.item(row, 0)
                data = item.data(Qt.UserRole + 1) if item is not None else None
                if isinstance(data, dict) and data.get("room") == target_room:
                    selected_row = row
                    summary = data.get("summary")
                    if isinstance(summary, FurnitureRoomSummary):
                        selected_summary = summary
                    break
            if selected_row is None:
                selected_row = 0
                item = self._table.item(selected_row, 0)
                data = item.data(Qt.UserRole + 1) if item is not None else None
                if isinstance(data, dict):
                    summary = data.get("summary")
                    if isinstance(summary, FurnitureRoomSummary):
                        selected_summary = summary
            self._suppress_selection_changed = True
            try:
                self._table.selectRow(selected_row)
            finally:
                self._suppress_selection_changed = False
            if isinstance(selected_summary, FurnitureRoomSummary):
                self._selected_room_key = selected_summary.room
                self._browser.setHtml(self._build_room_html(selected_summary))
                self._build_item_table(selected_summary)

        self._subtitle.setText(
            _tr(
                "furniture.subtitle",
                default="{rooms} rooms | {items} pieces | {unplaced} unplaced",
                rooms=len([room for room in self._available_rooms if room]),
                items=len(self._furniture),
                unplaced=len(self._furniture_by_room.get("", [])),
            )
        )

    def _on_selection_changed(self):
        if self._suppress_selection_changed:
            return
        selected = self._table.selectedRanges()
        if not selected:
            self._selected_room_key = ""
            self._browser.setHtml(self._build_empty_html())
            self._clear_item_table()
            self._save_session_state()
            return

        row = selected[0].topRow()
        item = self._table.item(row, 0)
        if item is None:
            return
        data = item.data(Qt.UserRole + 1)
        if not isinstance(data, dict):
            return
        summary = data.get("summary")
        if not isinstance(summary, FurnitureRoomSummary):
            return
        self._selected_room_key = str(data.get("room", "") or "")
        self._browser.setHtml(self._build_room_html(summary))
        self._build_item_table(summary)
        self._save_session_state()

    def _build_empty_html(self) -> str:
        return """
        <html>
          <body style="font-family:Segoe UI, Arial, sans-serif; line-height:1.45;">
            <h2>Furniture</h2>
            <p class="muted">Load a save with furniture to inspect room stats.</p>
          </body>
        </html>
        """

    def _effect_spans(self, effects: dict[str, float]) -> str:
        if not effects:
            return '<span class="muted">No stat effects</span>'
        parts: list[str] = []
        for key in FURNITURE_ROOM_STAT_KEYS:
            value = effects.get(key, 0.0)
            if not value:
                continue
            label = FURNITURE_ROOM_STAT_LABELS[key]
            parts.append(
                f'<span style="color:{self._STAT_ACCENTS[key]}; font-weight:bold;">'
                f'{html.escape(label)} {self._fmt(value)}</span>'
            )
        for key, value in sorted(effects.items(), key=lambda kv: kv[0].lower()):
            if key in FURNITURE_ROOM_STAT_KEYS or not value:
                continue
            parts.append(
                f'<span style="color:#a8a8bd;">{html.escape(key)} {self._fmt(value)}</span>'
            )
        return ", ".join(parts)

    def _build_item_table(self, summary: FurnitureRoomSummary, selected_item_keys: list[int] | None = None):
        scroll_state = self._capture_item_table_view_state()
        selected_keys = list(selected_item_keys) if selected_item_keys is not None else self._capture_item_table_selection_keys()
        title = self._room_label(summary.room)
        subtitle = self._room_note(summary)
        self._item_title.setText(title)
        self._item_subtitle.setText(
            f"{subtitle}  Items: {summary.furniture_count}  Cats: {summary.cat_count}"
        )

        items = sorted(
            summary.items,
            key=lambda item: (
                self._room_label(item.room or "").lower(),
                self._furniture_data.get(item.item_name).display_name.lower()
                if self._furniture_data.get(item.item_name)
                else item.item_name.lower(),
                int(item.key),
            ),
        )

        query = self._search.text().strip().lower()
        if query:
            filtered_items = []
            for item in items:
                definition = self._furniture_data.get(item.item_name)
                haystack = " ".join([
                    str(item.key).lower(),
                    item.item_name.lower(),
                    self._room_label(item.room or "").lower(),
                    (definition.display_name.lower() if definition is not None else ""),
                    (definition.description.lower() if definition is not None and definition.description else ""),
                    (self._item_notes(definition.effects).lower() if definition is not None and definition.effects else ""),
                ])
                if query in haystack:
                    filtered_items.append(item)
            items = filtered_items

        if self._pinned_only:
            items = [item for item in items if int(item.key) in self._pinned_item_keys]

        self._item_table.setSortingEnabled(False)
        self._item_table.setRowCount(len(items))
        self._item_table.setHorizontalHeaderLabels([
            _tr("furniture.item.table.id", default="#"),
            _tr("furniture.item.table.pin", default="Pin"),
            _tr("furniture.item.table.item", default="Item"),
            _tr("furniture.item.table.appeal", default="APP"),
            _tr("furniture.item.table.comfort", default="COMF"),
            _tr("furniture.item.table.stim", default="STIM"),
            _tr("furniture.item.table.health", default="HEA"),
            _tr("furniture.item.table.mutation", default="MUT"),
            _tr("furniture.item.table.notes", default="Notes"),
        ])
        stat_keys = {
            3: "Appeal",
            4: "Comfort",
            5: "Stimulation",
            6: "Health",
            7: "Evolution",
        }

        for row, item in enumerate(items):
            definition = self._furniture_data.get(item.item_name)
            display = definition.display_name if definition is not None else item.item_name.replace("_", " ").title()
            desc = definition.description if definition is not None else ""
            effects = definition.effects if definition is not None else {}
            pinned = int(item.key) in self._pinned_item_keys
            values = [
                (str(item.key), item.key),
                ("", 1 if pinned else 0),
                (display, display.lower()),
                self._sort_stat_cell(effects.get("Appeal", 0.0)),
                self._sort_stat_cell(effects.get("Comfort", 0.0)),
                self._sort_stat_cell(effects.get("Stimulation", 0.0)),
                self._sort_stat_cell(effects.get("Health", 0.0)),
                self._sort_stat_cell(effects.get("Evolution", 0.0)),
                (self._item_notes(effects) or "—", self._item_notes(effects).lower() if self._item_notes(effects) else ""),
            ]
            for col, (value, sort_key) in enumerate(values):
                cell = _SortByUserRoleItem(value)
                cell.setData(Qt.UserRole, sort_key)
                if col == 1:
                    cell.setData(Qt.UserRole + 1, int(item.key))
                    cell.setTextAlignment(Qt.AlignCenter)
                    cell.setIcon(_make_pin_icon(pinned, 16))
                    if pinned:
                        cell.setForeground(QBrush(QColor(216, 182, 106)))
                if col == 0:
                    cell.setTextAlignment(Qt.AlignCenter)
                if col in stat_keys and value not in ("—", ""):
                    cell.setForeground(self._stat_brush(float(effects.get(stat_keys[col], 0.0))))
                cell.setToolTip("\n".join(part for part in [display, desc, item.item_name, self._room_label(item.room or "")] if part))
                self._item_table.setItem(row, col, cell)

        if self._item_table_sort_column is not None:
            self._apply_item_table_sort(self._item_table_sort_column, self._item_table_sort_order)
        else:
            self._restore_item_table_view_state(scroll_state)
        self._restore_item_table_selection(selected_keys)

    @staticmethod
    def _sort_stat_cell(value: float) -> tuple[str, tuple[int, float]]:
        number = float(value or 0.0)
        if number == 0.0:
            return ("—", (1, 0.0))
        return (FurnitureView._fmt(number), (0, -number))

    def _build_room_html(self, summary: FurnitureRoomSummary) -> str:
        title = self._room_label(summary.room)
        note = self._room_note(summary)

        rows = []
        for key in FURNITURE_ROOM_STAT_KEYS:
            raw = summary.raw_effects.get(key, 0.0)
            effective = summary.effective_effects.get(key, 0.0)
            current = effective if key in ("Comfort", "Health") else raw
            rows.append(
                "<tr>"
                f"<td style='color:{self._STAT_ACCENTS[key]}; font-weight:bold;'>{html.escape(FURNITURE_ROOM_STAT_LABELS[key])}</td>"
                f"<td>{html.escape(self._fmt(raw))}</td>"
                f"<td>{html.escape(self._fmt(current))}</td>"
                "</tr>"
            )

        stats_html = "".join(rows)

        return f"""
        <html>
          <body style="font-family:Segoe UI, Arial, sans-serif; line-height:1.45;">
            <h2>{html.escape(title)}</h2>
            <p class="muted">{html.escape(note)}</p>
            <p>
              <strong>Cats:</strong> {summary.cat_count}
              &nbsp;&nbsp; <strong>Pieces:</strong> {summary.furniture_count}
              &nbsp;&nbsp; <strong>Crowd penalty:</strong> -{summary.crowd_penalty}
            </p>
            <table>
              <tr>
                <td></td>
                <td class="muted"><strong>Raw</strong></td>
                <td class="muted"><strong>Current</strong></td>
              </tr>
              {stats_html}
            </table>
            <p class="muted">The actual item list is shown in the left pane.</p>
          </body>
        </html>
        """


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    @staticmethod
    def _set_bulk_toggle_label(btn: QPushButton, label: str, enabled: bool):
        btn.setText(_tr("bulk.label_template", label=label, state=_tr("common.on" if enabled else "common.off")))

    @staticmethod
    def _style_room_action_button(btn: QPushButton, background: str, border: str, hover_background: str, width: int = 110):
        btn.setCheckable(False)
        btn.setMinimumWidth(width)
        btn.setStyleSheet(
            "QPushButton { "
            f"background:{background}; color:#f1f1f1; border:1px solid {border}; "
            "border-radius:4px; padding:4px 10px; font-size:11px; font-weight:bold; }"
            f"QPushButton:hover {{ background:{hover_background}; }}"
            "QPushButton:pressed { background:#1a1a1a; }"
        )

    def _set_room_action_button_texts(self):
        self._room_must_breed_btn.setText(_tr("bulk.toggle_must_breed"))
        self._room_must_breed_btn.setToolTip(_tr("bulk.toggle_must_breed.tooltip"))
        self._room_breeding_block_btn.setText(_tr("bulk.toggle_breeding_block"))
        self._room_breeding_block_btn.setToolTip(_tr("bulk.toggle_breeding_block.tooltip"))
        self._room_pin_btn.setText(_tr("bulk.toggle_pin", default="Toggle Pin"))
        self._room_pin_btn.setToolTip(_tr("bulk.toggle_pin.tooltip", default="Toggle pin for selected cats"))

    def _room_view_target_cats(self, room_key=None) -> list[Cat]:
        if room_key in (None, "__all__"):
            return self._selected_cats()
        return self._visible_filtered_cats()

    def _active_room_key(self):
        if self._active_btn is not None:
            for key, btn in self._room_btns.items():
                if btn is self._active_btn:
                    return key
        return None

    def _toggle_room_view_boolean(self, attr: str, room_key=None) -> int:
        cats = self._room_view_target_cats(room_key)
        mw_status = self.statusBar()
        if not cats:
            if room_key in (None, "__all__"):
                mw_status.showMessage("Select cats first, then click a room action.")
            else:
                mw_status.showMessage("No cats in the current room view needed a change.")
            return 0

        current = [bool(getattr(cat, attr, False)) for cat in cats]
        target_state = not all(current)
        changed = 0
        for cat in cats:
            if attr == "is_pinned":
                if cat.is_pinned == target_state:
                    continue
                cat.is_pinned = target_state
                changed += 1
                continue
            if attr == "must_breed":
                if cat.must_breed == target_state:
                    continue
                cat.must_breed = target_state
                if target_state:
                    cat.is_blacklisted = False
                changed += 1
                continue
            if attr == "is_blacklisted":
                if cat.is_blacklisted == target_state and (not target_state or not cat.must_breed):
                    continue
                cat.is_blacklisted = target_state
                if target_state:
                    cat.must_breed = False
                changed += 1

        if changed == 0:
            mw_status.showMessage("No cats in view needed a change.")
            return 0
        self._emit_bulk_toggle_refresh()
        return changed

    def _toggle_room_must_breed(self, room_key=None):
        changed = self._toggle_room_view_boolean("must_breed", room_key)
        if changed:
            self.statusBar().showMessage(_tr("bulk.status.toggled_must_breed", default="Toggled must breed for {count} selected cats", count=changed))

    def _toggle_room_breeding_block(self, room_key=None):
        changed = self._toggle_room_view_boolean("is_blacklisted", room_key)
        if changed:
            self.statusBar().showMessage(_tr("bulk.status.toggled_breeding_block", default="Toggled breeding block for {count} selected cats", count=changed))

    def _toggle_room_pin(self, room_key=None):
        changed = self._toggle_room_view_boolean("is_pinned", room_key)
        if changed:
            self.statusBar().showMessage(_tr("bulk.status.toggled_pin", default="Toggled pin for {count} selected cats", count=changed))

    def __init__(self, initial_save: Optional[str] = None, use_saved_default: bool = True):
        super().__init__()
        _set_current_language(_saved_language())
        _refresh_localized_constants()
        self.setWindowTitle(_tr("app.title"))
        self.resize(1440, 900)

        self._current_save = None
        self._cats: list[Cat] = []
        self._furniture = []
        self._furniture_by_room = {}
        self._room_summaries: dict[str, FurnitureRoomSummary] = {}
        self._available_house_rooms: list[str] = list(ROOM_KEYS)
        self._furniture_data: dict[str, FurnitureDefinition] = dict(_FURNITURE_DATA)
        self._room_btns: dict = {}
        self._active_btn = None
        self._show_lineage: bool = False
        self._pedigree_coi_memos: dict[tuple[int, int], float] = {}
        self._tree_view: Optional[FamilyTreeBrowserView] = None
        self._safe_breeding_view: Optional[SafeBreedingView] = None
        self._breeding_partners_view: Optional[BreedingPartnersView] = None
        self._room_optimizer_view: Optional[RoomOptimizerView] = None
        self._perfect_planner_view: Optional[PerfectCatPlannerView] = None
        self._calibration_view: Optional[CalibrationView] = None
        self._furniture_view: Optional[FurnitureView] = None
        self._breeding_cache: Optional[BreedingCache] = None
        self._cache_worker: Optional[BreedingCacheWorker] = None
        self._save_load_worker: Optional[SaveLoadWorker] = None
        self._quick_refresh_worker: Optional[QuickRoomRefreshWorker] = None
        self._prev_parent_keys: dict[int, tuple] = {}
        self._zoom_percent: int = 100
        self._font_size_offset: int = 0   # pt offset applied on top of zoom
        self._base_font: QFont = QApplication.instance().font()
        self._base_sidebar_width = 190
        self._base_header_height = 46
        self._base_search_width = 180
        self._base_col_widths = {
            COL_NAME: 160,
            COL_GEN: _W_GEN,
            COL_STAT: _W_STATUS,
            COL_BL: 34,
            COL_MB: 34,
            COL_PIN: 34,
            COL_SUM: 38,
            COL_ABIL: 180,
            COL_MUTS: 155,
            COL_RELNS: _W_RELNS,
            COL_REL: _W_REL,
            COL_AGE: 34,
            COL_AGG: _W_TRAIT_NARROW,
            COL_LIB: _W_TRAIT_NARROW,
            COL_INBRD: _W_TRAIT_NARROW,
            COL_SEXUALITY: _W_TRAIT,
            **{c: _W_STAT for c in STAT_COLS},
        }

        self._build_ui()
        self._build_menu()
        self._apply_zoom()

        # Progress bar for breeding cache computation
        self._cache_progress = QProgressBar()
        self._cache_progress.setFixedWidth(200)
        self._cache_progress.setFixedHeight(16)
        self._cache_progress.setTextVisible(True)
        self._cache_progress.setFormat(_tr("loading.cache.computing"))
        self._cache_progress.setStyleSheet(
            "QProgressBar { background:#1a1a32; border:1px solid #2a2a4a; border-radius:4px; color:#aaa; font-size:10px; }"
            "QProgressBar::chunk { background:#3f8f72; border-radius:3px; }"
        )
        self._cache_progress.hide()
        self.statusBar().addPermanentWidget(self._cache_progress)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)

        # Use initial_save if provided; otherwise only auto-load the saved default when allowed.
        save_to_load = initial_save if initial_save else (_saved_default_save() if use_saved_default else None)
        if save_to_load:
            # Defer load_save to after the window is shown so the UI appears instantly.
            QTimer.singleShot(0, lambda: self.load_save(save_to_load))

    # ── Menu ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        self.menuBar().clear()
        fm = self.menuBar().addMenu(_tr("menu.file"))

        oa = QAction(_tr("menu.file.open_save"), self)
        oa.setShortcut("Ctrl+O")
        oa.triggered.connect(self._open_file)
        fm.addAction(oa)

        # Recent Saves submenu
        self._recent_saves_menu = fm.addMenu(_tr("menu.file.recent_saves"))
        self._recent_save_actions: list[QAction] = []
        self._refresh_recent_save_actions()

        fm.addSeparator()

        # Default Save submenu
        self._default_save_menu = fm.addMenu(_tr("menu.file.default_save"))
        self._set_default_save_action = QAction(_tr("menu.file.default_save.set_current"), self)
        self._set_default_save_action.triggered.connect(self._set_current_as_default)
        self._set_default_save_action.setEnabled(False)
        self._default_save_menu.addAction(self._set_default_save_action)

        self._clear_default_save_action = QAction(_tr("menu.file.default_save.clear"), self)
        self._clear_default_save_action.triggered.connect(self._clear_default_save)
        self._clear_default_save_action.setEnabled(False)
        self._default_save_menu.addAction(self._clear_default_save_action)

        fm.addSeparator()

        ra = QAction(_tr("menu.file.reload"), self)
        ra.setShortcut("F5")
        ra.triggered.connect(self._reload)
        fm.addAction(ra)

        recalc = QAction(_tr("menu.file.recalculate_breeding_data"), self)
        recalc.setShortcut("Ctrl+F5")
        recalc.setToolTip(_tr("menu.file.recalculate_breeding_data.tooltip"))
        recalc.triggered.connect(lambda: self._start_breeding_cache(self._cats, force_full=True) if self._cats else None)
        fm.addAction(recalc)

        clear_cache = QAction(_tr("menu.file.clear_breeding_cache"), self)
        clear_cache.setToolTip(_tr("menu.file.clear_breeding_cache.tooltip"))
        clear_cache.triggered.connect(self._clear_breeding_cache)
        fm.addAction(clear_cache)

        fm.addSeparator()

        export_action = QAction(_tr("menu.file.export_cats", default="Export Cats…"), self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_cats)
        fm.addAction(export_action)

        fm.addSeparator()

        exit_action = QAction(_tr("menu.file.exit"), self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        fm.addAction(exit_action)

        sm = self.menuBar().addMenu(_tr("menu.settings"))
        locations_action = QAction(_tr("menu.settings.locations"), self)
        locations_action.triggered.connect(self._open_locations_dialog)
        sm.addAction(locations_action)

        self._thresholds_action = QAction(_tr("menu.settings.thresholds", default="Donation / Exceptional Thresholds…"), self)
        self._thresholds_action.triggered.connect(self._open_threshold_preferences_dialog)
        sm.addAction(self._thresholds_action)

        self._optimizer_search_settings_action = QAction(
            _tr("menu.settings.optimizer_search_settings", default="Optimizer Search Settings…"),
            self,
        )
        self._optimizer_search_settings_action.triggered.connect(self._open_optimizer_search_settings_dialog)
        sm.addAction(self._optimizer_search_settings_action)

        sm.addSeparator()
        self._language_menu = sm.addMenu(_tr("language.menu"))
        self._language_group = QActionGroup(self)
        self._language_group.setExclusive(True)
        for language in _SUPPORTED_LANGUAGES:
            action = QAction(_language_label(language), self)
            action.setCheckable(True)
            action.setChecked(language == _current_language())
            action.triggered.connect(lambda checked=False, lang=language: self._change_language(lang))
            self._language_group.addAction(action)
            self._language_menu.addAction(action)

        sm.addSeparator()
        self._lineage_action = QAction(_tr("menu.settings.show_lineage"), self)
        self._lineage_action.setCheckable(True)
        self._lineage_action.setChecked(self._show_lineage)
        self._lineage_action.triggered.connect(self._toggle_lineage)
        sm.addAction(self._lineage_action)

        sm.addSeparator()
        self._room_optimizer_auto_recalc_action = QAction(_tr("menu.settings.room_optimizer_auto_recalc", default="Auto Recalculate Room Optimizer"), self)
        self._room_optimizer_auto_recalc_action.setCheckable(True)
        self._room_optimizer_auto_recalc_action.setChecked(_saved_room_optimizer_auto_recalc())
        self._room_optimizer_auto_recalc_action.toggled.connect(self._toggle_room_optimizer_auto_recalc)
        sm.addAction(self._room_optimizer_auto_recalc_action)

        sm.addSeparator()
        zoom_in = QAction(_tr("menu.settings.zoom_in"), self)
        zoom_in_keys = QKeySequence.keyBindings(QKeySequence.StandardKey.ZoomIn)
        if not zoom_in_keys:
            zoom_in_keys = []
        for seq in (QKeySequence("Ctrl+="), QKeySequence("Ctrl++")):
            if seq not in zoom_in_keys:
                zoom_in_keys.append(seq)
        zoom_in.setShortcuts(zoom_in_keys)
        zoom_in.triggered.connect(lambda: self._change_zoom(+1))
        sm.addAction(zoom_in)

        zoom_out = QAction(_tr("menu.settings.zoom_out"), self)
        zoom_out_keys = QKeySequence.keyBindings(QKeySequence.StandardKey.ZoomOut)
        if not zoom_out_keys:
            zoom_out_keys = []
        if QKeySequence("Ctrl+-") not in zoom_out_keys:
            zoom_out_keys.append(QKeySequence("Ctrl+-"))
        zoom_out.setShortcuts(zoom_out_keys)
        zoom_out.triggered.connect(lambda: self._change_zoom(-1))
        sm.addAction(zoom_out)

        zoom_reset = QAction(_tr("menu.settings.reset_zoom"), self)
        zoom_reset.setShortcut("Ctrl+0")
        zoom_reset.triggered.connect(self._reset_zoom)
        sm.addAction(zoom_reset)

        self._zoom_info_action = QAction("", self)
        self._zoom_info_action.setEnabled(False)
        sm.addAction(self._zoom_info_action)
        self._update_zoom_info_action()

        sm.addSeparator()
        fs_in = QAction(_tr("menu.settings.increase_font_size"), self)
        fs_in.setShortcut("Ctrl+]")
        fs_in.triggered.connect(lambda: self._change_font_size(+1))
        sm.addAction(fs_in)

        fs_out = QAction(_tr("menu.settings.decrease_font_size"), self)
        fs_out.setShortcut("Ctrl+[")
        fs_out.triggered.connect(lambda: self._change_font_size(-1))
        sm.addAction(fs_out)

        fs_reset = QAction(_tr("menu.settings.reset_font_size"), self)
        fs_reset.setShortcut("Ctrl+\\")
        fs_reset.triggered.connect(lambda: self._set_font_size_offset(0))
        sm.addAction(fs_reset)

        self._font_size_info_action = QAction("", self)
        self._font_size_info_action.setEnabled(False)
        sm.addAction(self._font_size_info_action)
        self._update_font_size_info_action()

        sm.addSeparator()
        self._reset_ui_settings_action = QAction(_tr("menu.settings.reset_ui_defaults"), self)
        self._reset_ui_settings_action.triggered.connect(self._reset_ui_settings_to_defaults)
        sm.addAction(self._reset_ui_settings_action)

    def _refresh_recent_save_actions(self):
        if not hasattr(self, "_recent_saves_menu"):
            return
        self._recent_saves_menu.clear()
        self._recent_save_actions = []

        saves = find_save_files()
        if not saves:
            action = QAction(_tr("menu.file.no_saves_found", path=_save_root_dir()), self)
            action.setEnabled(False)
            self._recent_saves_menu.addAction(action)
            self._recent_save_actions.append(action)
            return

        for path in saves[:10]:
            action = QAction(os.path.basename(path), self)
            action.setToolTip(path)
            action.triggered.connect(lambda _, p=path: self.load_save(p))
            self._recent_saves_menu.addAction(action)
            self._recent_save_actions.append(action)

    def _open_locations_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(_tr("dialog.locations.title"))
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        game_title = QLabel(_tr("dialog.locations.game_install"))
        game_title.setStyleSheet(_NAME_STYLE)
        game_path_label = QLabel()
        game_path_label.setWordWrap(True)
        game_path_label.setStyleSheet(_META_STYLE)

        save_title = QLabel(_tr("dialog.locations.save_root"))
        save_title.setStyleSheet(_NAME_STYLE)
        save_path_label = QLabel()
        save_path_label.setWordWrap(True)
        save_path_label.setStyleSheet(_META_STYLE)

        note_label = QLabel(_tr("dialog.locations.note", path=APPDATA_SAVE_DIR))
        note_label.setWordWrap(True)
        note_label.setStyleSheet(_META_STYLE)

        def _refresh_labels():
            game_path_label.setText(_GPAK_PATH or _tr("common.not_found"))
            save_path_label.setText(_save_root_dir())

        def _choose_game_dir():
            start_dir = os.path.dirname(_GPAK_PATH) if _GPAK_PATH else (
                r"C:\Program Files (x86)\Steam\steamapps\common\Mewgenics"
                if os.path.isdir(r"C:\Program Files (x86)\Steam\steamapps\common\Mewgenics")
                else (
                    r"C:\Program Files\Steam\steamapps\common\Mewgenics"
                    if os.path.isdir(r"C:\Program Files\Steam\steamapps\common\Mewgenics")
                    else str(Path.home())
                )
            )
            chosen_dir = QFileDialog.getExistingDirectory(
                dlg,
                _tr("dialog.locations.select_game_folder"),
                start_dir,
            )
            if not chosen_dir:
                return
            gpak_path = os.path.join(chosen_dir, "resources.gpak")
            if not os.path.exists(gpak_path):
                QMessageBox.warning(
                    dlg,
                    _tr("dialog.locations.resources_not_found.title"),
                    _tr("dialog.locations.resources_not_found.body"),
                )
                return
            _set_gpak_path(gpak_path)
            _refresh_labels()
            if self._current_save:
                self.load_save(self._current_save)
            self.statusBar().showMessage(_tr("status.using_game_data", path=gpak_path))

        def _choose_save_dir():
            chosen_dir = QFileDialog.getExistingDirectory(
                dlg,
                _tr("dialog.locations.select_save_root"),
                _save_root_dir(),
            )
            if not chosen_dir:
                return
            _set_save_dir(chosen_dir)
            _refresh_labels()
            self._refresh_recent_save_actions()
            self.statusBar().showMessage(_tr("status.using_save_root", path=chosen_dir))

        game_btn = QPushButton(_tr("dialog.locations.change_game_folder"))
        game_btn.clicked.connect(_choose_game_dir)
        save_btn = QPushButton(_tr("dialog.locations.change_save_root"))
        save_btn.clicked.connect(_choose_save_dir)

        layout.addWidget(game_title)
        layout.addWidget(game_path_label)
        layout.addWidget(game_btn)
        layout.addSpacing(8)
        layout.addWidget(save_title)
        layout.addWidget(save_path_label)
        layout.addWidget(save_btn)
        layout.addSpacing(8)
        layout.addWidget(note_label)

        close_btn = QPushButton(_tr("common.close"))
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

        _refresh_labels()
        dlg.resize(640, 260)
        dlg.exec()

    def _open_threshold_preferences_dialog(self):
        dlg = ThresholdPreferencesDialog(self, _load_threshold_preferences(), self._cats)
        if dlg.exec() != QDialog.Accepted:
            return
        prefs = dlg.preferences()
        _save_threshold_preferences(prefs)
        self._refresh_threshold_runtime(self._cats)
        room_key = None
        if self._active_btn is not None:
            for key, btn in self._room_btns.items():
                if btn is self._active_btn:
                    room_key = key
                    break
        self._refresh_threshold_sensitive_ui(room_key)
        self.statusBar().showMessage(
            _tr("status.thresholds_saved", default="Threshold preferences saved")
        )

    def _open_optimizer_search_settings_dialog(self):
        dlg = SharedOptimizerSearchSettingsDialog(self, _load_optimizer_search_settings())
        if dlg.exec() != QDialog.Accepted:
            return
        settings = dlg.preferences()
        _save_optimizer_search_settings(settings)
        self.statusBar().showMessage(
            _tr("status.optimizer_search_settings_saved", default="Optimizer search settings saved")
        )

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        rl = QHBoxLayout(central)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        hs = QSplitter(Qt.Horizontal)
        hs.setObjectName("main_window_sidebar_splitter")
        self._sidebar_splitter = hs
        rl.addWidget(hs)
        hs.addWidget(self._build_sidebar())
        hs.addWidget(self._build_content())
        hs.setStretchFactor(0, 0)
        hs.setStretchFactor(1, 1)
        hs.setSizes([190, 1250])
        _enforce_min_font_in_widget_tree(central)
        # Snapshot all stylesheet font sizes before any offset is applied,
        # so _apply_font_offset_to_tree always scales from the true originals.
        _apply_font_offset_to_tree(central, 0)
        _bind_splitter_persistence(self)

    # ── Sidebar ────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        w  = QWidget()
        self._sidebar = w
        w.setFixedWidth(self._base_sidebar_width)
        w.setStyleSheet("background:#14142a;")
        vb = QVBoxLayout(w)
        vb.setContentsMargins(8, 14, 8, 12)
        vb.setSpacing(2)

        def sl(text):
            l = QLabel(text)
            l.setStyleSheet("color:#444; font-size:10px; font-weight:bold;"
                            " letter-spacing:1px; padding:8px 4px 4px 4px;")
            return l

        self._filters_section_label = sl(_tr("sidebar.section.filters"))
        vb.addWidget(self._filters_section_label)
        self._btn_everyone = _sidebar_btn(_tr("sidebar.button.all_cats"))
        self._btn_everyone.clicked.connect(
            lambda: self._filter("__all__", self._btn_everyone))
        vb.addWidget(self._btn_everyone)
        self._room_btns["__all__"] = self._btn_everyone

        self._btn_all = _sidebar_btn(_tr("sidebar.button.alive_cats"))
        self._btn_all.setChecked(True)
        self._active_btn = self._btn_all
        self._btn_all.clicked.connect(lambda: self._filter(None, self._btn_all))
        vb.addWidget(self._btn_all)
        self._room_btns[None] = self._btn_all

        self._btn_exceptional = _sidebar_btn("")
        self._btn_exceptional.setToolTip("")
        self._btn_exceptional.clicked.connect(
            lambda: self._filter("__exceptional__", self._btn_exceptional)
        )
        vb.addWidget(self._btn_exceptional)
        self._room_btns["__exceptional__"] = self._btn_exceptional

        self._btn_donation = _sidebar_btn("")
        self._btn_donation.setToolTip("")
        self._btn_donation.clicked.connect(
            lambda: self._filter("__donation__", self._btn_donation)
        )
        vb.addWidget(self._btn_donation)
        self._room_btns["__donation__"] = self._btn_donation

        vb.addWidget(_hsep())
        self._breeding_section_label = sl(_tr("sidebar.section.breeding"))
        vb.addWidget(self._breeding_section_label)
        self._btn_room_optimizer = _sidebar_btn(_tr("sidebar.button.room_optimizer"))
        self._btn_room_optimizer.clicked.connect(self._open_room_optimizer)
        vb.addWidget(self._btn_room_optimizer)
        self._btn_perfect_planner = _sidebar_btn(_tr("sidebar.button.perfect_7_planner"))
        self._btn_perfect_planner.clicked.connect(self._open_perfect_planner_view)
        vb.addWidget(self._btn_perfect_planner)
        self._btn_mutation_planner = _sidebar_btn(_tr("sidebar.button.mutation_planner"))
        self._btn_mutation_planner.clicked.connect(self._open_mutation_planner_view)
        vb.addWidget(self._btn_mutation_planner)
        self._btn_safe_breeding_view = _sidebar_btn(_tr("sidebar.button.safe_breeding"))
        self._btn_safe_breeding_view.clicked.connect(self._open_safe_breeding_view)
        vb.addWidget(self._btn_safe_breeding_view)
        self._btn_breeding_partners_view = _sidebar_btn(_tr("sidebar.button.breeding_partners"))
        self._btn_breeding_partners_view.clicked.connect(self._open_breeding_partners_view)
        vb.addWidget(self._btn_breeding_partners_view)

        vb.addWidget(_hsep())
        self._info_section_label = sl(_tr("sidebar.section.info"))
        vb.addWidget(self._info_section_label)
        self._btn_tree_view = _sidebar_btn(_tr("sidebar.button.family_tree_view"))
        self._btn_tree_view.clicked.connect(self._open_tree_browser)
        vb.addWidget(self._btn_tree_view)
        self._btn_furniture_view = _sidebar_btn(_tr("sidebar.button.furniture", default="Furniture"))
        self._btn_furniture_view.clicked.connect(self._open_furniture_view)
        vb.addWidget(self._btn_furniture_view)
        self._btn_calibration = _sidebar_btn(_tr("sidebar.button.calibration"))
        self._btn_calibration.clicked.connect(self._open_calibration_view)
        vb.addWidget(self._btn_calibration)

        vb.addWidget(_hsep())
        self._rooms_section_label = sl(_tr("sidebar.section.rooms"))
        vb.addWidget(self._rooms_section_label)
        self._rooms_vb = QVBoxLayout(); self._rooms_vb.setSpacing(2)
        vb.addLayout(self._rooms_vb)
        vb.addWidget(_hsep())

        self._other_section_label = sl(_tr("sidebar.section.other"))
        vb.addWidget(self._other_section_label)
        self._btn_adventure = _sidebar_btn(_tr("sidebar.button.on_adventure"))
        self._btn_gone      = _sidebar_btn(_tr("sidebar.button.gone"))
        self._btn_adventure.clicked.connect(
            lambda: self._filter("__adventure__", self._btn_adventure))
        self._btn_gone.clicked.connect(
            lambda: self._filter("__gone__", self._btn_gone))
        vb.addWidget(self._btn_adventure)
        vb.addWidget(self._btn_gone)
        self._room_btns["__adventure__"] = self._btn_adventure
        self._room_btns["__gone__"]      = self._btn_gone

        vb.addStretch()

        self._version_lbl = QLabel(f"v{APP_VERSION}")
        self._version_lbl.setStyleSheet("color:#666; font-size:10px; padding:0 4px 2px 4px;")
        self._version_lbl.setToolTip(f"Application version: {APP_VERSION}")
        vb.addWidget(self._version_lbl)

        self._save_lbl = QLabel(_tr("sidebar.no_save_loaded"))
        self._save_lbl.setStyleSheet("color:#444; font-size:10px;")
        self._save_lbl.setWordWrap(True)
        vb.addWidget(self._save_lbl)

        self._reload_btn = QPushButton(_tr("sidebar.button.reload"))
        self._reload_btn.setStyleSheet("QPushButton { color:#888; background:#1a1a32;"
                         " border:1px solid #2a2a4a; padding:7px;"
                         " border-radius:4px; font-size:11px; }"
                         "QPushButton:hover { background:#222244; }")
        self._reload_btn.clicked.connect(self._reload)
        vb.addWidget(self._reload_btn)
        self._refresh_filter_button_counts()
        return w

    def _rebuild_room_buttons(self, cats: list[Cat]):
        while self._rooms_vb.count():
            item = self._rooms_vb.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        _ROOM_ORDER = {
            "Attic": 0,
            "Floor2_Large": 1, "Floor2_Small": 2,
            "Floor1_Large": 3, "Floor1_Small": 4,
        }
        rooms = sorted(
            {c.room for c in cats if c.status == "In House" and c.room},
            key=lambda r: _ROOM_ORDER.get(r, 99),
        )
        for room in rooms:
            count = sum(1 for c in cats if c.room == room)
            display = ROOM_DISPLAY.get(room, room)
            btn = _sidebar_btn(f"{display}  ({count})")
            btn.clicked.connect(lambda _, r=room, b=btn: self._filter(r, b))
            self._rooms_vb.addWidget(btn)
            self._room_btns[room] = btn

    def _refresh_filter_button_counts(self):
        total = len(self._cats)
        alive = sum(1 for c in self._cats if c.status != "Gone")
        exceptional = sum(1 for c in self._cats if c.status != "Gone" and _is_exceptional_breeder(c))
        donation = sum(1 for c in self._cats if c.status != "Gone" and _is_donation_candidate(c))
        adv = sum(1 for c in self._cats if c.status == "Adventure")
        gone = sum(1 for c in self._cats if c.status == "Gone")

        self._btn_everyone.setText(f"{_tr('sidebar.button.all_cats')}  ({total})" if total else _tr("sidebar.button.all_cats"))
        self._btn_all.setText(f"{_tr('sidebar.button.alive_cats')}  ({alive})" if total else _tr("sidebar.button.alive_cats"))
        self._btn_exceptional.setText(f"{_tr('sidebar.button.exceptional')}  ({exceptional})")
        self._btn_donation.setText(f"{_tr('sidebar.button.donation_candidates')}  ({donation})")
        self._btn_adventure.setText(f"{_tr('sidebar.button.on_adventure')}  ({adv})" if total else _tr("sidebar.button.on_adventure"))
        self._btn_gone.setText(f"{_tr('sidebar.button.gone')}  ({gone})" if total else _tr("sidebar.button.gone"))
        self._btn_room_optimizer.setText(_tr("sidebar.button.room_optimizer"))
        self._btn_perfect_planner.setText(_tr("sidebar.button.perfect_7_planner"))
        self._btn_mutation_planner.setText(_tr("sidebar.button.mutation_planner"))
        self._btn_safe_breeding_view.setText(_tr("sidebar.button.safe_breeding"))
        self._btn_breeding_partners_view.setText(_tr("sidebar.button.breeding_partners"))
        self._btn_tree_view.setText(_tr("sidebar.button.family_tree_view"))
        self._btn_calibration.setText(_tr("sidebar.button.calibration"))
        self._btn_furniture_view.setText(_tr("sidebar.button.furniture", default="Furniture"))
        self._update_threshold_button_copy()

    def _update_threshold_button_copy(self):
        if not hasattr(self, "_btn_exceptional") or not hasattr(self, "_btn_donation"):
            return
        summary = _current_threshold_summary(self._cats)
        exceptional = summary["exceptional"]
        donation = summary["donation"]
        top_stat = summary["top_stat"]
        avg_sum = summary["avg_sum"]
        base_exceptional = summary["base_exceptional"]
        base_donation = summary["base_donation"]
        adaptive = summary["adaptive_enabled"]
        if adaptive:
            self._btn_exceptional.setToolTip(
                "Exceptional breeders follow the living-cat average curve: "
                f"base {base_exceptional}, reference avg {summary['adaptive_reference_avg_sum']:.1f}, "
                f"curve {summary['adaptive_curve_strength']:.2f}, current avg {avg_sum:.1f} -> {exceptional}."
            )
            self._btn_donation.setToolTip(
                "Donation candidates follow the living-cat average curve: "
                f"base {base_donation}, reference avg {summary['adaptive_reference_avg_sum']:.1f}, "
                f"curve {summary['adaptive_curve_strength']:.2f}, current avg {avg_sum:.1f} -> {donation}, "
                f"top stat cap {top_stat}."
            )
        else:
            self._btn_exceptional.setToolTip(
                f"Exceptional breeders: base stat sum >= {exceptional}."
            )
            self._btn_donation.setToolTip(
                "Donation candidates use documented heuristics: "
                f"base stat sum <= {donation}, "
                f"top stat <= {top_stat}, and/or high aggression."
            )

    def _refresh_threshold_runtime(self, cats: list[Cat] | None = None):
        _apply_threshold_preferences(_load_threshold_preferences(), cats if cats is not None else self._cats)

    def _refresh_threshold_sensitive_ui(self, room_key=None):
        if hasattr(self, "_proxy_model"):
            self._proxy_model.invalidate()
        self._refresh_filter_button_counts()
        self._refresh_bulk_view_buttons(room_key)
        self._update_count()

    def _sync_room_config_views(self):
        if self._room_optimizer_view is None or self._perfect_planner_view is None:
            return
        self._perfect_planner_view.sync_from_room_config(
            self._room_optimizer_view.get_room_config(),
            available_rooms=self._room_optimizer_view.get_available_rooms(),
        )

    def _retranslate_ui(self):
        current_room_key = next((key for key, btn in self._room_btns.items() if btn is self._active_btn), None)
        _refresh_localized_constants()
        self._build_menu()
        self._filters_section_label.setText(_tr("sidebar.section.filters"))
        self._breeding_section_label.setText(_tr("sidebar.section.breeding"))
        self._info_section_label.setText(_tr("sidebar.section.info"))
        self._rooms_section_label.setText(_tr("sidebar.section.rooms"))
        self._other_section_label.setText(_tr("sidebar.section.other"))
        self._reload_btn.setText(_tr("sidebar.button.reload"))
        self._save_lbl.setText(os.path.basename(self._current_save) if self._current_save else _tr("sidebar.no_save_loaded"))
        self._search.setPlaceholderText(_tr("header.search_placeholder"))
        self._loading_label.setText(_tr("loading.save_file"))
        self._cache_progress.setFormat(_tr("loading.cache.computing"))
        self._refresh_filter_button_counts()
        self._rebuild_room_buttons(self._cats)
        if current_room_key in self._room_btns:
            self._active_btn = self._room_btns[current_room_key]
            self._active_btn.setChecked(True)
        self._update_header(current_room_key)
        self._update_count()
        self._refresh_bulk_view_buttons()
        if hasattr(self, "_source_model") and self._source_model is not None:
            self._source_model.headerDataChanged.emit(Qt.Horizontal, 0, len(COLUMNS) - 1)
        if self._safe_breeding_view is not None:
            self._safe_breeding_view.retranslate_ui()
        if self._breeding_partners_view is not None:
            self._breeding_partners_view.retranslate_ui()
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.retranslate_ui()
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.retranslate_ui()
        if hasattr(self, "_mutation_planner_view") and self._mutation_planner_view is not None:
            self._mutation_planner_view.retranslate_ui()
        if self._calibration_view is not None:
            self._calibration_view.retranslate_ui()
        if self._furniture_view is not None:
            self._furniture_view.retranslate_ui()
        if hasattr(self, "_thresholds_action"):
            self._thresholds_action.setText(_tr("menu.settings.thresholds", default="Donation / Exceptional Thresholds…"))
        if hasattr(self, "_optimizer_search_settings_action"):
            self._optimizer_search_settings_action.setText(
                _tr("menu.settings.optimizer_search_settings", default="Optimizer Search Settings…")
            )
        if hasattr(self, "_reset_ui_settings_action"):
            self._reset_ui_settings_action.setText(_tr("menu.settings.reset_ui_defaults"))
        if hasattr(self, "_room_optimizer_auto_recalc_action"):
            self._room_optimizer_auto_recalc_action.setText(_tr("menu.settings.room_optimizer_auto_recalc", default="Auto Recalculate Room Optimizer"))

    def _change_language(self, language: str):
        if language not in _SUPPORTED_LANGUAGES or language == _current_language():
            return
        _set_saved_language(language)
        _set_current_language(language)
        self._retranslate_ui()
        current_title = _language_label(language)
        self.setWindowTitle(_tr("app.title_with_save", name=os.path.basename(self._current_save)) if self._current_save else _tr("app.title"))
        self.statusBar().showMessage(_tr("status.language_changed", language=current_title))

    # ── Content ────────────────────────────────────────────────────────────

    def _build_content(self) -> QWidget:
        w  = QWidget()
        vb = QVBoxLayout(w)
        vb.setContentsMargins(0, 0, 0, 0)
        vb.setSpacing(0)

        # Header
        hdr = QWidget()
        self._header = hdr
        hdr.setStyleSheet("background:#16213e; border-bottom:1px solid #1e1e38;")
        hdr.setFixedHeight(self._base_header_height)
        hb = QHBoxLayout(hdr); hb.setContentsMargins(14, 0, 14, 0)
        self._header_lbl = QLabel(_tr("header.filter.all_cats"))
        self._header_lbl.setStyleSheet("color:#eee; font-size:15px; font-weight:bold;")
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color:#555; font-size:12px; padding-left:8px;")
        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet("color:#4a7a9a; font-size:11px;")
        self._bulk_blacklist_btn = QPushButton()
        self._bulk_blacklist_btn.setCheckable(True)
        self._bulk_blacklist_btn.setMinimumWidth(130)
        self._bulk_blacklist_btn.setStyleSheet(
            "QPushButton { background:#5a2d22; color:#f1dfda; border:1px solid #8b4c3e;"
            " border-radius:4px; padding:4px 10px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#6c382a; }"
            "QPushButton:pressed { background:#4c241b; }"
            "QPushButton:checked { background:#7a3626; border:1px solid #b35b48; }"
        )
        self._set_bulk_toggle_label(self._bulk_blacklist_btn, _tr("bulk.breeding_block"), False)
        self._bulk_blacklist_btn.clicked.connect(self._toggle_blacklist_filtered_cats)
        self._bulk_must_breed_btn = QPushButton()
        self._bulk_must_breed_btn.setCheckable(True)
        self._bulk_must_breed_btn.setMinimumWidth(110)
        self._bulk_must_breed_btn.setStyleSheet(
            "QPushButton { background:#3b355f; color:#ece8fb; border:1px solid #5d58a0;"
            " border-radius:4px; padding:4px 10px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#49417a; }"
            "QPushButton:pressed { background:#312c4f; }"
            "QPushButton:checked { background:#514890; border:1px solid #7d73c7; }"
        )
        self._set_bulk_toggle_label(self._bulk_must_breed_btn, _tr("bulk.must_breed"), False)
        self._bulk_must_breed_btn.clicked.connect(self._toggle_must_breed_filtered_cats)
        bulk_container = QWidget()
        self._bulk_actions_layout = QHBoxLayout(bulk_container)
        self._bulk_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._bulk_actions_layout.setSpacing(8)
        self._bulk_pin_btn = QPushButton()
        self._bulk_pin_btn.setCheckable(True)
        self._bulk_pin_btn.setMinimumWidth(90)
        self._bulk_pin_btn.setStyleSheet(
            "QPushButton { background:#2a3a2a; color:#c8dcc8; border:1px solid #4a6a4a;"
            " border-radius:4px; padding:4px 10px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#3a4a3a; }"
            "QPushButton:pressed { background:#1e2e1e; }"
            "QPushButton:checked { background:#3a5a3a; border:1px solid #5a8a5a; }")
        self._set_bulk_toggle_label(self._bulk_pin_btn, _tr("bulk.pin", default="Pin"), False)
        self._bulk_pin_btn.clicked.connect(self._toggle_pin_filtered_cats)
        self._bulk_actions_layout.addWidget(self._bulk_must_breed_btn)
        self._bulk_actions_layout.addWidget(self._bulk_blacklist_btn)
        self._bulk_actions_layout.addWidget(self._bulk_pin_btn)

        self._room_actions_box = QWidget()
        room_actions = QHBoxLayout(self._room_actions_box)
        room_actions.setContentsMargins(0, 0, 0, 0)
        room_actions.setSpacing(8)

        self._room_must_breed_btn = QPushButton()
        self._style_room_action_button(self._room_must_breed_btn, "#3b355f", "#5d58a0", "#49417a")
        self._room_must_breed_btn.clicked.connect(lambda: self._toggle_room_must_breed(self._active_room_key()))
        room_actions.addWidget(self._room_must_breed_btn)

        self._room_breeding_block_btn = QPushButton()
        self._style_room_action_button(self._room_breeding_block_btn, "#5a2d22", "#8b4c3e", "#6c382a")
        self._room_breeding_block_btn.clicked.connect(lambda: self._toggle_room_breeding_block(self._active_room_key()))
        room_actions.addWidget(self._room_breeding_block_btn)

        self._room_pin_btn = QPushButton()
        self._style_room_action_button(self._room_pin_btn, "#2a3a2a", "#4a6a4a", "#3a4a3a", width=90)
        self._room_pin_btn.clicked.connect(lambda: self._toggle_room_pin(self._active_room_key()))
        room_actions.addWidget(self._room_pin_btn)

        room_actions.addStretch()
        self._set_room_action_button_texts()
        self._search = QLineEdit()
        self._search.setPlaceholderText(_tr("header.search_placeholder"))
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(self._base_search_width)
        self._search.setStyleSheet(
            "QLineEdit { background:#0d0d1c; color:#ccc; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:3px 8px; font-size:12px; }"
            "QLineEdit:focus { border-color:#3a3a7a; }")
        self._pin_toggle = QPushButton(_tr("header.pin_toggle", default="📌"))
        self._pin_toggle.setCheckable(True)
        self._pin_toggle.setToolTip(_tr("header.pin_toggle_tooltip", default="Show only pinned cats"))
        self._pin_toggle.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#888; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:3px 8px; font-size:12px; min-width:28px; }"
            "QPushButton:hover { background:#222244; }"
            "QPushButton:checked { background:#2a2a5a; color:#eee; border-color:#4a4a8a; }")
        self._pin_toggle.toggled.connect(self._on_pin_toggle)

        self._tags_btn = QPushButton("Tags")
        self._tags_btn.setToolTip("Apply tags to selected cats")
        self._tags_btn.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:3px 10px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
            "QPushButton::menu-indicator { image:none; }")
        self._tags_btn.clicked.connect(self._show_tags_menu)

        hb.addWidget(self._header_lbl)
        hb.addWidget(self._count_lbl)
        hb.addStretch()
        hb.addWidget(self._room_actions_box)
        hb.addSpacing(8)
        hb.addWidget(bulk_container)
        hb.addSpacing(10)
        hb.addWidget(self._tags_btn)
        hb.addSpacing(4)
        hb.addWidget(self._pin_toggle)
        hb.addSpacing(4)
        hb.addWidget(self._search)
        hb.addSpacing(12)
        hb.addWidget(self._summary_lbl)
        vb.addWidget(hdr)

        # Vertical splitter: table on top, detail panel on bottom (user-resizable)
        vs = QSplitter(Qt.Vertical)
        vs.setObjectName("main_window_detail_splitter")
        vs.setHandleWidth(4)
        vs.setStyleSheet("QSplitter::handle:vertical { background:#1e1e38; }")
        self._detail_splitter = vs
        self._table_view_container = vs
        vb.addWidget(vs)

        # Table
        self._source_model = CatTableModel()
        self._source_model.blacklistChanged.connect(self._on_blacklist_changed)
        self._proxy_model  = RoomFilterModel()
        self._proxy_model.setSourceModel(self._source_model)
        self._proxy_model.modelReset.connect(self._update_count)
        self._proxy_model.rowsInserted.connect(self._update_count)
        self._proxy_model.rowsRemoved.connect(self._update_count)

        self._table = QTableView()
        self._table.setModel(self._proxy_model)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(COL_NAME, Qt.AscendingOrder)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        # Checkbox columns are toggled explicitly in _on_table_clicked.
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hh = self._table.horizontalHeader()
        hh.setStretchLastSection(False)  # we control stretch manually

        # Name: interactive so the user can resize it; not Stretch so it
        # doesn't eat the blank space that should sit at the right edge.
        hh.setSectionResizeMode(COL_NAME, QHeaderView.Interactive)
        self._table.setColumnWidth(COL_NAME, self._base_col_widths[COL_NAME])
        self._name_tag_delegate = NameTagDelegate(self._table)
        self._table.setItemDelegateForColumn(COL_NAME, self._name_tag_delegate)

        # Room: size to content so it adapts to room name length
        hh.setSectionResizeMode(COL_ROOM, QHeaderView.ResizeToContents)

        # Narrow columns keep today's defaults but can now be widened for translated text.
        for col, width in [
            (COL_GEN, _W_GEN),
            (COL_STAT, _W_STATUS),
            (COL_BL, 34),
            (COL_MB, 34),
            (COL_PIN, 34),
            (COL_SUM, 38),
            (COL_AGG, _W_TRAIT_NARROW),
            (COL_LIB, _W_TRAIT_NARROW),
            (COL_INBRD, _W_TRAIT_NARROW),
            (COL_SEXUALITY, _W_TRAIT),
        ] + [(c, _W_STAT) for c in STAT_COLS]:
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
            self._table.setColumnWidth(col, width)

        # Abilities: interactive — user drags to taste
        hh.setSectionResizeMode(COL_ABIL, QHeaderView.Interactive)
        self._table.setColumnWidth(COL_ABIL, self._base_col_widths[COL_ABIL])

        # Mutations: interactive
        hh.setSectionResizeMode(COL_MUTS, QHeaderView.Interactive)
        self._table.setColumnWidth(COL_MUTS, self._base_col_widths[COL_MUTS])

        # Relations: interactive
        hh.setSectionResizeMode(COL_RELNS, QHeaderView.Interactive)
        self._table.setColumnWidth(COL_RELNS, self._base_col_widths[COL_RELNS])

        # Narrow auxiliary columns keep their defaults but can be widened manually.
        hh.setSectionResizeMode(COL_REL, QHeaderView.Interactive)
        self._table.setColumnWidth(COL_REL, self._base_col_widths[COL_REL])

        hh.setSectionResizeMode(COL_AGE, QHeaderView.Interactive)
        self._table.setColumnWidth(COL_AGE, self._base_col_widths[COL_AGE])

        hh.setSectionResizeMode(COL_GEN_DEPTH, QHeaderView.Interactive)
        self._table.setColumnWidth(COL_GEN_DEPTH, _W_GEN)
        self._table.setColumnHidden(COL_GEN_DEPTH, True)

        # Source: Stretch — absorbs blank space, hidden by default (behind lineage toggle)
        hh.setSectionResizeMode(COL_SRC, QHeaderView.Stretch)
        self._table.setColumnHidden(COL_SRC, True)

        self._table.setStyleSheet("""
            QTableView {
                background:#0d0d1c; alternate-background-color:#131326;
                color:#ddd; border:none; font-size:12px;
                selection-background-color:#1e3060;
            }
            QTableView::item { padding:3px 4px; }
            QTableView::item:selected { color:#fff; }
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
        """)

        self._table.selectionModel().selectionChanged.connect(self._on_selection)
        self._table.clicked.connect(self._on_table_clicked)
        self._search.textChanged.connect(self._proxy_model.set_name_filter)
        self._search.textChanged.connect(self._update_count)
        self._search.textChanged.connect(lambda _: self._refresh_bulk_view_buttons())
        vs.addWidget(self._table)

        # Detail panel
        self._detail = CatDetailPanel()
        vs.addWidget(self._detail)
        vs.setStretchFactor(0, 1)
        vs.setStretchFactor(1, 0)

        # Family tree view lives in the same main container and is swapped in/out
        # via left sidebar "VIEW" buttons.
        self._tree_view = FamilyTreeBrowserView(self)
        self._tree_view.hide()
        vb.addWidget(self._tree_view, 1)
        self._safe_breeding_view = SafeBreedingView(self)
        self._safe_breeding_view.hide()
        vb.addWidget(self._safe_breeding_view, 1)
        self._breeding_partners_view = BreedingPartnersView(self)
        self._breeding_partners_view.set_navigate_to_cat_callback(self._navigate_to_cat_by_name)
        self._breeding_partners_view.hide()
        vb.addWidget(self._breeding_partners_view, 1)
        self._room_optimizer_view = RoomOptimizerView(self)
        self._room_optimizer_view.hide()
        vb.addWidget(self._room_optimizer_view, 1)
        self._perfect_planner_view = PerfectCatPlannerView(self)
        self._perfect_planner_view.hide()
        vb.addWidget(self._perfect_planner_view, 1)
        self._calibration_view = CalibrationView(self)
        self._calibration_view.calibrationChanged.connect(self._on_calibration_changed)
        self._calibration_view.hide()
        vb.addWidget(self._calibration_view, 1)
        self._mutation_planner_view = MutationDisorderPlannerView(self)
        self._mutation_planner_view.hide()
        vb.addWidget(self._mutation_planner_view, 1)
        self._furniture_view = FurnitureView(self)
        self._furniture_view.hide()
        vb.addWidget(self._furniture_view, 1)
        # Wire planner to optimizer so traits can be imported
        self._room_optimizer_view.set_planner_view(self._mutation_planner_view)
        self._perfect_planner_view.set_mutation_planner_view(self._mutation_planner_view)
        self._room_optimizer_view.room_priority_panel.configChanged.connect(self._sync_room_config_views)
        # Allow cat locator tables to navigate to cat in Alive Cats view
        self._mutation_planner_view.set_navigate_to_cat_callback(self._navigate_to_cat)
        self._room_optimizer_view.cat_locator.set_navigate_to_cat_callback(self._navigate_to_cat)
        self._perfect_planner_view.cat_locator.set_navigate_to_cat_callback(self._navigate_to_cat)
        self._perfect_planner_view.offspring_tracker.set_navigate_to_cat_callback(self._navigate_to_cat)

        # Loading overlay — shown during background save parse, dismissed before UI population
        self._loading_overlay = QWidget(w)
        self._loading_overlay.setStyleSheet("background:#0a0a18;")
        lo_vb = QVBoxLayout(self._loading_overlay)
        lo_vb.setAlignment(Qt.AlignCenter)
        self._loading_label = QLabel(_tr("loading.save_file"))
        self._loading_label.setStyleSheet("color:#aaa; font-size:15px; font-weight:bold;")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_bar = QProgressBar()
        self._loading_bar.setFixedWidth(320)
        self._loading_bar.setFixedHeight(16)
        self._loading_bar.setRange(0, 0)  # indeterminate pulse
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setStyleSheet(
            "QProgressBar { background:#1a1a32; border:1px solid #2a2a4a; border-radius:4px; }"
            "QProgressBar::chunk { background:#3f8f72; border-radius:3px; }"
        )
        lo_vb.addWidget(self._loading_label)
        lo_vb.addSpacing(10)
        lo_vb.addWidget(self._loading_bar, 0, Qt.AlignCenter)
        self._loading_overlay.hide()

        return w

    # ── Selection → detail ────────────────────────────────────────────────

    def _on_selection(self):
        rows = list({
            self._proxy_model.mapToSource(idx).row()
            for idx in self._table.selectionModel().selectedRows()
        })
        cats = [c for r in rows[:2] if (c := self._source_model.cat_at(r)) is not None]
        if len(cats) == 2 and _is_hater_pair(cats[0], cats[1]):
            cats = cats[:1]
        was_collapsed = self._detail.maximumHeight() == 0
        self._detail.show_cats(cats)
        if cats and was_collapsed:
            total   = self._detail_splitter.height()
            panel_h = 200 if len(cats) == 1 else 300
            self._detail_splitter.setSizes([max(10, total - panel_h), panel_h])

        # Highlight compatibility: dim incompatible cats when 1 is selected
        focus = cats[0] if len(cats) == 1 else None
        self._source_model.set_focus_cat(focus)
        if self._tree_view is not None and self._tree_view.isVisible() and focus is not None:
            self._tree_view.select_cat(focus)
        if self._safe_breeding_view is not None and self._safe_breeding_view.isVisible() and focus is not None:
            self._safe_breeding_view.select_cat(focus)

    def _on_table_clicked(self, proxy_index: QModelIndex):
        if not proxy_index.isValid() or proxy_index.column() not in (COL_BL, COL_MB, COL_PIN):
            return
        src_index = self._proxy_model.mapToSource(proxy_index)
        if not src_index.isValid():
            return
        current = self._source_model.data(src_index, Qt.CheckStateRole)
        next_state = Qt.Unchecked if current == Qt.Checked else Qt.Checked
        if self._source_model.setData(src_index, next_state, Qt.CheckStateRole):
            self._on_selection()

    # ── Filtering ──────────────────────────────────────────────────────────

    def _filter(self, room_key, btn: QPushButton):
        if not getattr(self, "_save_view_disabled", False):
            _save_current_view("table")
        self._show_table_view()
        if self._active_btn and self._active_btn is not btn:
            self._active_btn.setChecked(False)
        btn.setChecked(True)
        self._active_btn = btn
        self._proxy_model.set_room(room_key)

        # Set multi-column sort for donation candidates and exceptional breeders
        if room_key in ("__donation__", "__exceptional__"):
            self._proxy_model.set_sort_columns([
                (COL_ROOM, Qt.AscendingOrder),
                (COL_AGE, Qt.AscendingOrder),
                (COL_NAME, Qt.AscendingOrder),
            ])
        else:
            self._proxy_model.set_sort_columns([])

        self._refresh_bulk_view_buttons(room_key)
        self._update_header(room_key)
        self._update_count()
        self._detail.show_cats([])
        self._source_model.set_focus_cat(None)

    def _visible_filtered_cats(self) -> list[Cat]:
        cats: list[Cat] = []
        for row in range(self._proxy_model.rowCount()):
            src_idx = self._proxy_model.mapToSource(self._proxy_model.index(row, 0))
            if not src_idx.isValid():
                continue
            cat = self._source_model.cat_at(src_idx.row())
            if cat is not None:
                cats.append(cat)
        return cats

    def _selected_cats(self) -> list[Cat]:
        cats: list[Cat] = []
        for idx in self._table.selectionModel().selectedRows():
            src_idx = self._proxy_model.mapToSource(idx)
            if not src_idx.isValid():
                continue
            cat = self._source_model.cat_at(src_idx.row())
            if cat is not None:
                cats.append(cat)
        return cats

    def _refresh_bulk_view_buttons(self, room_key=None):
        if room_key is None and self._active_btn is not None:
            for key, btn in self._room_btns.items():
                if btn is self._active_btn:
                    room_key = key
                    break
        room_visible = room_key in (None, "__all__") or room_key in ROOM_DISPLAY
        bulk_visible = room_key in ("__donation__", "__exceptional__")
        donation_view = room_key == "__donation__"
        exceptional_view = room_key == "__exceptional__"
        alive_view = room_key is None
        if hasattr(self, "_bulk_actions_layout"):
            while self._bulk_actions_layout.count():
                item = self._bulk_actions_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            if bulk_visible and donation_view:
                self._bulk_actions_layout.addWidget(self._bulk_blacklist_btn)
                self._bulk_actions_layout.addWidget(self._bulk_must_breed_btn)
            elif bulk_visible:
                self._bulk_actions_layout.addWidget(self._bulk_must_breed_btn)
                self._bulk_actions_layout.addWidget(self._bulk_blacklist_btn)
            if bulk_visible:
                self._bulk_actions_layout.addWidget(self._bulk_pin_btn)
        if hasattr(self, "_bulk_blacklist_btn"):
            self._bulk_blacklist_btn.setVisible(bulk_visible)
        if hasattr(self, "_bulk_must_breed_btn"):
            self._bulk_must_breed_btn.setVisible(bulk_visible)
        if hasattr(self, "_bulk_pin_btn"):
            self._bulk_pin_btn.setVisible(bulk_visible)
        if hasattr(self, "_room_actions_box"):
            self._room_actions_box.setVisible(room_visible)
        if not (bulk_visible or room_visible):
            return
        if room_visible:
            self._set_room_action_button_texts()
            return
        if alive_view:
            self._bulk_blacklist_btn.blockSignals(True)
            try:
                self._bulk_blacklist_btn.setCheckable(False)
                self._bulk_blacklist_btn.setText(_tr("bulk.toggle_breeding_block"))
                self._bulk_blacklist_btn.setEnabled(True)
                self._bulk_blacklist_btn.setToolTip(_tr("bulk.toggle_breeding_block.tooltip"))
            finally:
                self._bulk_blacklist_btn.blockSignals(False)
            self._bulk_must_breed_btn.blockSignals(True)
            try:
                self._bulk_must_breed_btn.setCheckable(False)
                self._bulk_must_breed_btn.setText(_tr("bulk.toggle_must_breed"))
                self._bulk_must_breed_btn.setEnabled(True)
                self._bulk_must_breed_btn.setToolTip(_tr("bulk.toggle_must_breed.tooltip"))
            finally:
                self._bulk_must_breed_btn.blockSignals(False)
            self._bulk_pin_btn.blockSignals(True)
            try:
                self._bulk_pin_btn.setCheckable(False)
                self._bulk_pin_btn.setText(_tr("bulk.toggle_pin", default="Toggle Pin"))
                self._bulk_pin_btn.setEnabled(True)
                self._bulk_pin_btn.setToolTip(_tr("bulk.toggle_pin.tooltip", default="Toggle pin for selected cats"))
            finally:
                self._bulk_pin_btn.blockSignals(False)
            return
        cats = self._visible_filtered_cats()
        all_blocked = bool(cats) and all(cat.is_blacklisted for cat in cats)
        all_must_breed = bool(cats) and all(cat.must_breed for cat in cats)
        self._bulk_blacklist_btn.setCheckable(True)
        self._bulk_blacklist_btn.blockSignals(True)
        if exceptional_view:
            any_blocked = any(cat.is_blacklisted for cat in cats)
            self._bulk_blacklist_btn.setChecked(False)
            self._bulk_blacklist_btn.setEnabled(any_blocked)
            self._bulk_blacklist_btn.setText(_tr("bulk.clear_breeding_block"))
            self._bulk_blacklist_btn.setToolTip(_tr("bulk.clear_breeding_block.tooltip"))
        else:
            self._bulk_blacklist_btn.setChecked(all_blocked)
            self._bulk_blacklist_btn.setEnabled(True)
            self._set_bulk_toggle_label(self._bulk_blacklist_btn, _tr("bulk.breeding_block"), all_blocked)
            self._bulk_blacklist_btn.setToolTip("")
        self._bulk_blacklist_btn.blockSignals(False)
        self._bulk_must_breed_btn.setCheckable(True)
        self._bulk_must_breed_btn.blockSignals(True)
        if donation_view:
            any_must_breed = any(cat.must_breed for cat in cats)
            self._bulk_must_breed_btn.setChecked(False)
            self._bulk_must_breed_btn.setEnabled(any_must_breed)
            self._bulk_must_breed_btn.setText(_tr("bulk.clear_must_breed"))
            self._bulk_must_breed_btn.setToolTip(_tr("bulk.clear_must_breed.tooltip"))
        else:
            self._bulk_must_breed_btn.setChecked(all_must_breed)
            self._bulk_must_breed_btn.setEnabled(True)
            self._set_bulk_toggle_label(self._bulk_must_breed_btn, _tr("bulk.must_breed"), all_must_breed)
            self._bulk_must_breed_btn.setToolTip("")
        self._bulk_must_breed_btn.blockSignals(False)
        all_pinned = bool(cats) and all(cat.is_pinned for cat in cats)
        self._bulk_pin_btn.setCheckable(True)
        self._bulk_pin_btn.blockSignals(True)
        self._bulk_pin_btn.setChecked(all_pinned)
        self._bulk_pin_btn.setEnabled(True)
        self._set_bulk_toggle_label(self._bulk_pin_btn, _tr("bulk.pin", default="Pin"), all_pinned)
        self._bulk_pin_btn.setToolTip("")
        self._bulk_pin_btn.blockSignals(False)

    def _toggle_blacklist_filtered_cats(self):
        room_key = None
        if self._active_btn is not None:
            for key, btn in self._room_btns.items():
                if btn is self._active_btn:
                    room_key = key
                    break
        alive_view = room_key is None
        exceptional_view = room_key == "__exceptional__"
        if alive_view:
            cats = self._selected_cats()
            if not cats:
                self.statusBar().showMessage(_tr("bulk.status.select_toggle_breeding_block", default="Select cats first, then click Toggle Breeding Block"))
                return
            changed = 0
            for cat in cats:
                cat.is_blacklisted = not cat.is_blacklisted
                if cat.is_blacklisted:
                    cat.must_breed = False
                changed += 1
            self._emit_bulk_toggle_refresh()
            self.statusBar().showMessage(_tr("bulk.status.toggled_breeding_block", default="Toggled breeding block for {count} selected cats", count=changed))
            return
        target_state = False if exceptional_view else self._bulk_blacklist_btn.isChecked()
        changed = 0
        for cat in self._visible_filtered_cats():
            if cat.is_blacklisted == target_state and (not target_state or not cat.must_breed):
                continue
            cat.is_blacklisted = target_state
            if target_state:
                cat.must_breed = False
            changed += 1
        self._refresh_bulk_view_buttons()
        if changed == 0:
            self.statusBar().showMessage(_tr("bulk.status.no_breeding_block_change", default="No cats in view needed a breeding-block change"))
            return
        self._emit_bulk_toggle_refresh()
        if exceptional_view:
            self.statusBar().showMessage(_tr("bulk.status.cleared_breeding_block_exceptional", default="Cleared breeding block for {count} cats in the current exceptional view", count=changed))
        else:
            state_text = _tr("common.on", default="on") if target_state else _tr("common.off", default="off")
            self.statusBar().showMessage(_tr("bulk.status.turned_breeding_block", default="Turned breeding block {state} for {count} cats in the current view", state=state_text, count=changed))

    def _toggle_must_breed_filtered_cats(self):
        room_key = None
        if self._active_btn is not None:
            for key, btn in self._room_btns.items():
                if btn is self._active_btn:
                    room_key = key
                    break
        alive_view = room_key is None
        donation_view = room_key == "__donation__"
        if alive_view:
            cats = self._selected_cats()
            if not cats:
                self.statusBar().showMessage(_tr("bulk.status.select_toggle_must_breed", default="Select cats first, then click Toggle Must Breed"))
                return
            changed = 0
            for cat in cats:
                cat.must_breed = not cat.must_breed
                if cat.must_breed:
                    cat.is_blacklisted = False
                changed += 1
            self._emit_bulk_toggle_refresh()
            self.statusBar().showMessage(_tr("bulk.status.toggled_must_breed", default="Toggled must breed for {count} selected cats", count=changed))
            return
        target_state = False if donation_view else self._bulk_must_breed_btn.isChecked()
        changed = 0
        for cat in self._visible_filtered_cats():
            if cat.must_breed == target_state and (not target_state or not cat.is_blacklisted):
                continue
            cat.must_breed = target_state
            if target_state:
                cat.is_blacklisted = False
            changed += 1
        self._refresh_bulk_view_buttons()
        if changed == 0:
            self.statusBar().showMessage(_tr("bulk.status.no_must_breed_change", default="No cats in view needed a must-breed change"))
            return
        self._emit_bulk_toggle_refresh()
        if donation_view:
            self.statusBar().showMessage(_tr("bulk.status.cleared_must_breed_donation", default="Cleared Must Breed for {count} cats in the current donation-candidates view", count=changed))
        else:
            state_text = _tr("common.on", default="on") if target_state else _tr("common.off", default="off")
            self.statusBar().showMessage(_tr("bulk.status.turned_must_breed", default="Turned must breed {state} for {count} cats in the current view", state=state_text, count=changed))

    def _toggle_pin_filtered_cats(self):
        room_key = None
        if self._active_btn is not None:
            for key, btn in self._room_btns.items():
                if btn is self._active_btn:
                    room_key = key
                    break
        alive_view = room_key is None
        if alive_view:
            cats = self._selected_cats()
            if not cats:
                self.statusBar().showMessage(_tr("bulk.status.select_toggle_pin", default="Select cats first, then click Toggle Pin"))
                return
            changed = 0
            for cat in cats:
                cat.is_pinned = not cat.is_pinned
                changed += 1
            self._emit_bulk_toggle_refresh()
            self.statusBar().showMessage(_tr("bulk.status.toggled_pin", default="Toggled pin for {count} selected cats", count=changed))
            return
        target_state = self._bulk_pin_btn.isChecked()
        changed = 0
        for cat in self._visible_filtered_cats():
            if cat.is_pinned == target_state:
                continue
            cat.is_pinned = target_state
            changed += 1
        self._refresh_bulk_view_buttons()
        if changed == 0:
            self.statusBar().showMessage(_tr("bulk.status.no_pin_change", default="No cats in view needed a pin change"))
            return
        self._emit_bulk_toggle_refresh()
        state_text = _tr("common.on", default="on") if target_state else _tr("common.off", default="off")
        self.statusBar().showMessage(_tr("bulk.status.turned_pin", default="Turned pin {state} for {count} cats in the current view", state=state_text, count=changed))

    def _emit_bulk_toggle_refresh(self):
        if self._source_model.rowCount() == 0:
            return
        top_left = self._source_model.index(0, COL_BL)
        bottom_right = self._source_model.index(max(0, self._source_model.rowCount() - 1), COL_PIN)
        self._source_model.dataChanged.emit(
            top_left,
            bottom_right,
            [Qt.DisplayRole, Qt.CheckStateRole, Qt.ToolTipRole],
        )
        self._proxy_model.invalidate()
        self._source_model.blacklistChanged.emit()
        self._update_count()
        self._refresh_bulk_view_buttons()

    def _blacklist_filtered_cats(self):
        changed = 0
        for row in range(self._proxy_model.rowCount()):
            proxy_idx = self._proxy_model.index(row, COL_BL)
            if not proxy_idx.isValid():
                continue
            src_idx = self._proxy_model.mapToSource(proxy_idx)
            if not src_idx.isValid():
                continue
            cat = self._source_model.cat_at(src_idx.row())
            if cat is None or cat.is_blacklisted:
                continue
            cat.is_blacklisted = True
            changed += 1
        if changed == 0:
            self.statusBar().showMessage(_tr("bulk.status.no_additional_blacklist", default="No additional cats in view were added to the breeding blacklist"))
            return

        top_left = self._source_model.index(0, COL_BL)
        bottom_right = self._source_model.index(max(0, self._source_model.rowCount() - 1), COL_BL)
        self._source_model.dataChanged.emit(
            top_left,
            bottom_right,
            [Qt.DisplayRole, Qt.CheckStateRole, Qt.ToolTipRole],
        )
        self._source_model.blacklistChanged.emit()
        self._update_count()
        self.statusBar().showMessage(_tr("bulk.status.excluded_donation", default="Excluded {count} cats in the current donation-candidates view from breeding", count=changed))

    def _clear_must_breed_filtered_cats(self):
        changed = 0
        for row in range(self._proxy_model.rowCount()):
            proxy_idx = self._proxy_model.index(row, COL_MB)
            if not proxy_idx.isValid():
                continue
            src_idx = self._proxy_model.mapToSource(proxy_idx)
            if not src_idx.isValid():
                continue
            cat = self._source_model.cat_at(src_idx.row())
            if cat is None or not cat.must_breed:
                continue
            cat.must_breed = False
            changed += 1
        if changed == 0:
            self.statusBar().showMessage("No cats in view had Must Breed set")
            return

        top_left = self._source_model.index(0, COL_MB)
        bottom_right = self._source_model.index(max(0, self._source_model.rowCount() - 1), COL_MB)
        self._source_model.dataChanged.emit(
            top_left,
            bottom_right,
            [Qt.DisplayRole, Qt.CheckStateRole, Qt.ToolTipRole],
        )
        self._source_model.blacklistChanged.emit()
        self._update_count()
        self.statusBar().showMessage(f"Cleared Must Breed for {changed} cats in the current donation-candidates view")

    def _show_table_view(self):
        if hasattr(self, "_tree_view") and self._tree_view is not None:
            self._tree_view.hide()
        if hasattr(self, "_safe_breeding_view") and self._safe_breeding_view is not None:
            self._safe_breeding_view.hide()
        if hasattr(self, "_breeding_partners_view") and self._breeding_partners_view is not None:
            self._breeding_partners_view.hide()
        if hasattr(self, "_room_optimizer_view") and self._room_optimizer_view is not None:
            self._room_optimizer_view.hide()
        if hasattr(self, "_perfect_planner_view") and self._perfect_planner_view is not None:
            self._perfect_planner_view.hide()
        if hasattr(self, "_calibration_view") and self._calibration_view is not None:
            self._calibration_view.hide()
        if hasattr(self, "_mutation_planner_view") and self._mutation_planner_view is not None:
            self._mutation_planner_view.hide()
        if hasattr(self, "_furniture_view") and self._furniture_view is not None:
            self._furniture_view.hide()
        if hasattr(self, "_header"):
            self._header.show()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.show()
        if hasattr(self, "_btn_tree_view"):
            self._btn_tree_view.setChecked(False)
        if hasattr(self, "_btn_safe_breeding_view"):
            self._btn_safe_breeding_view.setChecked(False)
        if hasattr(self, "_btn_breeding_partners_view"):
            self._btn_breeding_partners_view.setChecked(False)
        if hasattr(self, "_btn_room_optimizer"):
            self._btn_room_optimizer.setChecked(False)
        if hasattr(self, "_btn_perfect_planner"):
            self._btn_perfect_planner.setChecked(False)
        if hasattr(self, "_btn_calibration"):
            self._btn_calibration.setChecked(False)
        if hasattr(self, "_btn_mutation_planner"):
            self._btn_mutation_planner.setChecked(False)
        if hasattr(self, "_btn_furniture_view"):
            self._btn_furniture_view.setChecked(False)

    def _show_tree_view(self):
        if self._active_btn is not None:
            self._active_btn.setChecked(False)
        self._active_btn = None
        if hasattr(self, "_header"):
            self._header.hide()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.hide()
        if hasattr(self, "_safe_breeding_view") and self._safe_breeding_view is not None:
            self._safe_breeding_view.hide()
        if hasattr(self, "_breeding_partners_view") and self._breeding_partners_view is not None:
            self._breeding_partners_view.hide()
        if hasattr(self, "_room_optimizer_view") and self._room_optimizer_view is not None:
            self._room_optimizer_view.hide()
        if hasattr(self, "_perfect_planner_view") and self._perfect_planner_view is not None:
            self._perfect_planner_view.hide()
        if hasattr(self, "_calibration_view") and self._calibration_view is not None:
            self._calibration_view.hide()
        if hasattr(self, "_mutation_planner_view") and self._mutation_planner_view is not None:
            self._mutation_planner_view.hide()
        if hasattr(self, "_furniture_view") and self._furniture_view is not None:
            self._furniture_view.hide()
        if self._tree_view is not None:
            self._tree_view.set_cats(self._cats)
            self._tree_view.show()
        if hasattr(self, "_btn_tree_view"):
            self._btn_tree_view.setChecked(True)
        if hasattr(self, "_btn_safe_breeding_view"):
            self._btn_safe_breeding_view.setChecked(False)
        if hasattr(self, "_btn_breeding_partners_view"):
            self._btn_breeding_partners_view.setChecked(False)
        if hasattr(self, "_btn_room_optimizer"):
            self._btn_room_optimizer.setChecked(False)
        if hasattr(self, "_btn_perfect_planner"):
            self._btn_perfect_planner.setChecked(False)
        if hasattr(self, "_btn_calibration"):
            self._btn_calibration.setChecked(False)
        if hasattr(self, "_btn_mutation_planner"):
            self._btn_mutation_planner.setChecked(False)
        if hasattr(self, "_btn_furniture_view"):
            self._btn_furniture_view.setChecked(False)

    def _show_safe_breeding_view(self):
        if self._active_btn is not None:
            self._active_btn.setChecked(False)
        self._active_btn = None
        if hasattr(self, "_header"):
            self._header.hide()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.hide()
        if hasattr(self, "_tree_view") and self._tree_view is not None:
            self._tree_view.hide()
        if hasattr(self, "_breeding_partners_view") and self._breeding_partners_view is not None:
            self._breeding_partners_view.hide()
        if hasattr(self, "_room_optimizer_view") and self._room_optimizer_view is not None:
            self._room_optimizer_view.hide()
        if hasattr(self, "_perfect_planner_view") and self._perfect_planner_view is not None:
            self._perfect_planner_view.hide()
        if hasattr(self, "_calibration_view") and self._calibration_view is not None:
            self._calibration_view.hide()
        if hasattr(self, "_mutation_planner_view") and self._mutation_planner_view is not None:
            self._mutation_planner_view.hide()
        if hasattr(self, "_furniture_view") and self._furniture_view is not None:
            self._furniture_view.hide()
        if self._safe_breeding_view is not None:
            self._safe_breeding_view.set_cats(self._cats)
            self._safe_breeding_view.show()
        if hasattr(self, "_btn_tree_view"):
            self._btn_tree_view.setChecked(False)
        if hasattr(self, "_btn_safe_breeding_view"):
            self._btn_safe_breeding_view.setChecked(True)
        if hasattr(self, "_btn_breeding_partners_view"):
            self._btn_breeding_partners_view.setChecked(False)
        if hasattr(self, "_btn_room_optimizer"):
            self._btn_room_optimizer.setChecked(False)
        if hasattr(self, "_btn_perfect_planner"):
            self._btn_perfect_planner.setChecked(False)
        if hasattr(self, "_btn_calibration"):
            self._btn_calibration.setChecked(False)
        if hasattr(self, "_btn_mutation_planner"):
            self._btn_mutation_planner.setChecked(False)
        if hasattr(self, "_btn_furniture_view"):
            self._btn_furniture_view.setChecked(False)

    def _show_breeding_partners_view(self):
        if self._active_btn is not None:
            self._active_btn.setChecked(False)
        self._active_btn = None
        if hasattr(self, "_header"):
            self._header.hide()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.hide()
        if hasattr(self, "_tree_view") and self._tree_view is not None:
            self._tree_view.hide()
        if hasattr(self, "_safe_breeding_view") and self._safe_breeding_view is not None:
            self._safe_breeding_view.hide()
        if hasattr(self, "_room_optimizer_view") and self._room_optimizer_view is not None:
            self._room_optimizer_view.hide()
        if hasattr(self, "_calibration_view") and self._calibration_view is not None:
            self._calibration_view.hide()
        if hasattr(self, "_mutation_planner_view") and self._mutation_planner_view is not None:
            self._mutation_planner_view.hide()
        if hasattr(self, "_perfect_planner_view") and self._perfect_planner_view is not None:
            self._perfect_planner_view.hide()
        if hasattr(self, "_furniture_view") and self._furniture_view is not None:
            self._furniture_view.hide()
        if self._breeding_partners_view is not None:
            self._breeding_partners_view.set_cats(self._cats)
            self._breeding_partners_view.show()
        if hasattr(self, "_btn_tree_view"):
            self._btn_tree_view.setChecked(False)
        if hasattr(self, "_btn_safe_breeding_view"):
            self._btn_safe_breeding_view.setChecked(False)
        if hasattr(self, "_btn_breeding_partners_view"):
            self._btn_breeding_partners_view.setChecked(True)
        if hasattr(self, "_btn_room_optimizer"):
            self._btn_room_optimizer.setChecked(False)
        if hasattr(self, "_btn_perfect_planner"):
            self._btn_perfect_planner.setChecked(False)
        if hasattr(self, "_btn_calibration"):
            self._btn_calibration.setChecked(False)
        if hasattr(self, "_btn_mutation_planner"):
            self._btn_mutation_planner.setChecked(False)
        if hasattr(self, "_btn_furniture_view"):
            self._btn_furniture_view.setChecked(False)

    def _show_room_optimizer_view(self):
        if self._active_btn is not None:
            self._active_btn.setChecked(False)
        self._active_btn = None
        if hasattr(self, "_header"):
            self._header.hide()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.hide()
        if hasattr(self, "_tree_view") and self._tree_view is not None:
            self._tree_view.hide()
        if hasattr(self, "_safe_breeding_view") and self._safe_breeding_view is not None:
            self._safe_breeding_view.hide()
        if hasattr(self, "_breeding_partners_view") and self._breeding_partners_view is not None:
            self._breeding_partners_view.hide()
        if hasattr(self, "_calibration_view") and self._calibration_view is not None:
            self._calibration_view.hide()
        if hasattr(self, "_perfect_planner_view") and self._perfect_planner_view is not None:
            self._perfect_planner_view.hide()
        if hasattr(self, "_mutation_planner_view") and self._mutation_planner_view is not None:
            self._mutation_planner_view.hide()
        if hasattr(self, "_furniture_view") and self._furniture_view is not None:
            self._furniture_view.hide()
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.set_cats(self._cats)
            self._room_optimizer_view.show()
        if hasattr(self, "_btn_tree_view"):
            self._btn_tree_view.setChecked(False)
        if hasattr(self, "_btn_safe_breeding_view"):
            self._btn_safe_breeding_view.setChecked(False)
        if hasattr(self, "_btn_breeding_partners_view"):
            self._btn_breeding_partners_view.setChecked(False)
        if hasattr(self, "_btn_room_optimizer"):
            self._btn_room_optimizer.setChecked(True)
        if hasattr(self, "_btn_perfect_planner"):
            self._btn_perfect_planner.setChecked(False)
        if hasattr(self, "_btn_calibration"):
            self._btn_calibration.setChecked(False)
        if hasattr(self, "_btn_mutation_planner"):
            self._btn_mutation_planner.setChecked(False)
        if hasattr(self, "_btn_furniture_view"):
            self._btn_furniture_view.setChecked(False)

    def _show_perfect_planner_view(self):
        if self._active_btn is not None:
            self._active_btn.setChecked(False)
        self._active_btn = None
        if hasattr(self, "_header"):
            self._header.hide()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.hide()
        if hasattr(self, "_tree_view") and self._tree_view is not None:
            self._tree_view.hide()
        if hasattr(self, "_safe_breeding_view") and self._safe_breeding_view is not None:
            self._safe_breeding_view.hide()
        if hasattr(self, "_breeding_partners_view") and self._breeding_partners_view is not None:
            self._breeding_partners_view.hide()
        if hasattr(self, "_room_optimizer_view") and self._room_optimizer_view is not None:
            self._room_optimizer_view.hide()
        if hasattr(self, "_calibration_view") and self._calibration_view is not None:
            self._calibration_view.hide()
        if hasattr(self, "_mutation_planner_view") and self._mutation_planner_view is not None:
            self._mutation_planner_view.hide()
        if hasattr(self, "_furniture_view") and self._furniture_view is not None:
            self._furniture_view.hide()
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.set_cats(self._cats)
            self._perfect_planner_view.show()
        if hasattr(self, "_btn_tree_view"):
            self._btn_tree_view.setChecked(False)
        if hasattr(self, "_btn_safe_breeding_view"):
            self._btn_safe_breeding_view.setChecked(False)
        if hasattr(self, "_btn_breeding_partners_view"):
            self._btn_breeding_partners_view.setChecked(False)
        if hasattr(self, "_btn_room_optimizer"):
            self._btn_room_optimizer.setChecked(False)
        if hasattr(self, "_btn_perfect_planner"):
            self._btn_perfect_planner.setChecked(True)
        if hasattr(self, "_btn_calibration"):
            self._btn_calibration.setChecked(False)
        if hasattr(self, "_btn_mutation_planner"):
            self._btn_mutation_planner.setChecked(False)
        if hasattr(self, "_btn_furniture_view"):
            self._btn_furniture_view.setChecked(False)

    def _show_calibration_view(self):
        if self._active_btn is not None:
            self._active_btn.setChecked(False)
        self._active_btn = None
        if hasattr(self, "_header"):
            self._header.hide()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.hide()
        if hasattr(self, "_tree_view") and self._tree_view is not None:
            self._tree_view.hide()
        if hasattr(self, "_safe_breeding_view") and self._safe_breeding_view is not None:
            self._safe_breeding_view.hide()
        if hasattr(self, "_breeding_partners_view") and self._breeding_partners_view is not None:
            self._breeding_partners_view.hide()
        if hasattr(self, "_room_optimizer_view") and self._room_optimizer_view is not None:
            self._room_optimizer_view.hide()
        if hasattr(self, "_perfect_planner_view") and self._perfect_planner_view is not None:
            self._perfect_planner_view.hide()
        if hasattr(self, "_furniture_view") and self._furniture_view is not None:
            self._furniture_view.hide()
        if self._calibration_view is not None:
            if self._current_save:
                self._calibration_view.set_context(self._current_save, self._cats)
            self._calibration_view.show()
        if hasattr(self, "_btn_tree_view"):
            self._btn_tree_view.setChecked(False)
        if hasattr(self, "_btn_safe_breeding_view"):
            self._btn_safe_breeding_view.setChecked(False)
        if hasattr(self, "_btn_breeding_partners_view"):
            self._btn_breeding_partners_view.setChecked(False)
        if hasattr(self, "_btn_room_optimizer"):
            self._btn_room_optimizer.setChecked(False)
        if hasattr(self, "_btn_perfect_planner"):
            self._btn_perfect_planner.setChecked(False)
        if hasattr(self, "_btn_calibration"):
            self._btn_calibration.setChecked(True)
        if hasattr(self, "_btn_mutation_planner"):
            self._btn_mutation_planner.setChecked(False)
        if hasattr(self, "_btn_furniture_view"):
            self._btn_furniture_view.setChecked(False)
        if hasattr(self, "_mutation_planner_view") and self._mutation_planner_view is not None:
            self._mutation_planner_view.hide()

    def _show_mutation_planner_view(self):
        if self._active_btn is not None:
            self._active_btn.setChecked(False)
        self._active_btn = None
        if hasattr(self, "_header"):
            self._header.hide()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.hide()
        if hasattr(self, "_tree_view") and self._tree_view is not None:
            self._tree_view.hide()
        if hasattr(self, "_safe_breeding_view") and self._safe_breeding_view is not None:
            self._safe_breeding_view.hide()
        if hasattr(self, "_breeding_partners_view") and self._breeding_partners_view is not None:
            self._breeding_partners_view.hide()
        if hasattr(self, "_room_optimizer_view") and self._room_optimizer_view is not None:
            self._room_optimizer_view.hide()
        if hasattr(self, "_perfect_planner_view") and self._perfect_planner_view is not None:
            self._perfect_planner_view.hide()
        if hasattr(self, "_calibration_view") and self._calibration_view is not None:
            self._calibration_view.hide()
        if hasattr(self, "_furniture_view") and self._furniture_view is not None:
            self._furniture_view.hide()
        if self._mutation_planner_view is not None:
            self._mutation_planner_view.set_cats(self._cats)
            self._mutation_planner_view.show()
        if hasattr(self, "_btn_tree_view"):
            self._btn_tree_view.setChecked(False)
        if hasattr(self, "_btn_safe_breeding_view"):
            self._btn_safe_breeding_view.setChecked(False)
        if hasattr(self, "_btn_breeding_partners_view"):
            self._btn_breeding_partners_view.setChecked(False)
        if hasattr(self, "_btn_room_optimizer"):
            self._btn_room_optimizer.setChecked(False)
        if hasattr(self, "_btn_perfect_planner"):
            self._btn_perfect_planner.setChecked(False)
        if hasattr(self, "_btn_calibration"):
            self._btn_calibration.setChecked(False)
        if hasattr(self, "_btn_mutation_planner"):
            self._btn_mutation_planner.setChecked(True)
        if hasattr(self, "_btn_furniture_view"):
            self._btn_furniture_view.setChecked(False)

    def _show_furniture_view(self):
        if self._active_btn is not None:
            self._active_btn.setChecked(False)
        self._active_btn = None
        if hasattr(self, "_header"):
            self._header.hide()
        if hasattr(self, "_table_view_container"):
            self._table_view_container.hide()
        if hasattr(self, "_tree_view") and self._tree_view is not None:
            self._tree_view.hide()
        if hasattr(self, "_safe_breeding_view") and self._safe_breeding_view is not None:
            self._safe_breeding_view.hide()
        if hasattr(self, "_breeding_partners_view") and self._breeding_partners_view is not None:
            self._breeding_partners_view.hide()
        if hasattr(self, "_room_optimizer_view") and self._room_optimizer_view is not None:
            self._room_optimizer_view.hide()
        if hasattr(self, "_perfect_planner_view") and self._perfect_planner_view is not None:
            self._perfect_planner_view.hide()
        if hasattr(self, "_calibration_view") and self._calibration_view is not None:
            self._calibration_view.hide()
        if hasattr(self, "_mutation_planner_view") and self._mutation_planner_view is not None:
            self._mutation_planner_view.hide()
        if self._furniture_view is not None:
            if self._current_save:
                self._furniture_view.set_context(self._cats, self._furniture, self._furniture_data, available_rooms=self._available_house_rooms)
            self._furniture_view.show()
        if hasattr(self, "_btn_tree_view"):
            self._btn_tree_view.setChecked(False)
        if hasattr(self, "_btn_safe_breeding_view"):
            self._btn_safe_breeding_view.setChecked(False)
        if hasattr(self, "_btn_breeding_partners_view"):
            self._btn_breeding_partners_view.setChecked(False)
        if hasattr(self, "_btn_room_optimizer"):
            self._btn_room_optimizer.setChecked(False)
        if hasattr(self, "_btn_perfect_planner"):
            self._btn_perfect_planner.setChecked(False)
        if hasattr(self, "_btn_calibration"):
            self._btn_calibration.setChecked(False)
        if hasattr(self, "_btn_mutation_planner"):
            self._btn_mutation_planner.setChecked(False)
        if hasattr(self, "_btn_furniture_view"):
            self._btn_furniture_view.setChecked(True)

    def _navigate_to_cat(self, db_key: int):
        """Switch to Alive Cats view and select the given cat by db_key."""
        self._filter(None, self._btn_all)
        for row in range(self._proxy_model.rowCount()):
            src_idx = self._proxy_model.mapToSource(self._proxy_model.index(row, 0))
            cat = self._source_model.cat_at(src_idx.row())
            if cat is not None and cat.db_key == db_key:
                self._table.scrollTo(self._proxy_model.index(row, 0))
                self._table.selectRow(row)
                return
        # Not found in Alive filter — try All Cats
        self._filter("__all__", self._btn_everyone)
        for row in range(self._proxy_model.rowCount()):
            src_idx = self._proxy_model.mapToSource(self._proxy_model.index(row, 0))
            cat = self._source_model.cat_at(src_idx.row())
            if cat is not None and cat.db_key == db_key:
                self._table.scrollTo(self._proxy_model.index(row, 0))
                self._table.selectRow(row)
                return

    def _navigate_to_cat_by_name(self, cat_name_formatted: str):
        """Navigate to a cat by its formatted name (e.g. 'Fluffy (Female)')."""
        cat_name = cat_name_formatted.split(" (")[0] if " (" in cat_name_formatted else cat_name_formatted
        cat_name = cat_name.replace(" \u2665", "")
        for cat in self._cats:
            if cat.name == cat_name:
                self._navigate_to_cat(cat.db_key)
                return

    def _update_header(self, room_key):
        if room_key == "__all__":
            self._header_lbl.setText(_tr("header.filter.all_cats"))
        elif room_key is None:
            self._header_lbl.setText(_tr("header.filter.alive"))
        elif room_key == "__exceptional__":
            self._header_lbl.setText(_tr("header.filter.exceptional"))
        elif room_key == "__donation__":
            self._header_lbl.setText(_tr("header.filter.donation"))
        elif room_key == "__gone__":
            self._header_lbl.setText(_tr("header.filter.gone"))
        elif room_key == "__adventure__":
            self._header_lbl.setText(_tr("header.filter.adventure"))
        else:
            self._header_lbl.setText(ROOM_DISPLAY.get(room_key, room_key))

    def _current_room_key(self):
        if self._active_btn is None:
            return None
        for key, btn in self._room_btns.items():
            if btn is self._active_btn:
                return key
        return None

    def _update_count(self):
        visible = self._proxy_model.rowCount()
        total   = self._source_model.rowCount()
        room_key = self._current_room_key()
        if room_key in ("__exceptional__", "__donation__"):
            summary = _current_threshold_summary(self._cats)
            if room_key == "__exceptional__":
                self._count_lbl.setText(
                    _tr(
                        "header.count_exceptional",
                        visible=visible,
                        total=total,
                        threshold=summary["exceptional"],
                    )
                )
            else:
                self._count_lbl.setText(
                    _tr(
                        "header.count_donation",
                        visible=visible,
                        total=total,
                        threshold=summary["donation"],
                    )
                )
        else:
            self._count_lbl.setText(_tr("header.count", visible=visible, total=total))

        placed = sum(1 for c in self._cats if c.status == "In House")
        adv    = sum(1 for c in self._cats if c.status == "Adventure")
        gone   = sum(1 for c in self._cats if c.status == "Gone")
        self._summary_lbl.setText(_tr("header.summary", placed=placed, adv=adv, gone=gone))

    def _on_pin_toggle(self, checked: bool):
        self._proxy_model.set_pinned_only(checked)
        self._update_count()

    def _show_tags_menu(self):
        """Show dropdown menu to apply/remove tags on selected cats."""
        selected_cats = self._get_selected_cats()
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#1a1a32; color:#ddd; border:1px solid #2a2a4a; padding:4px; }"
            "QMenu::item { padding:4px 16px; }"
            "QMenu::item:selected { background:#252545; }"
            "QMenu::separator { height:1px; background:#2a2a4a; margin:4px 8px; }"
        )

        if not _TAG_DEFS:
            no_tags = menu.addAction("No tags defined — open Manage Tags")
            no_tags.triggered.connect(self._open_tag_manager)
        else:
            header = menu.addAction("Apply Tags")
            header.setEnabled(False)
            menu.addSeparator()

            if not selected_cats:
                hint = menu.addAction("Select cats first, then apply tags")
                hint.setEnabled(False)
                menu.addSeparator()

            for td in _TAG_DEFS:
                tid = td["id"]
                label = td["name"] if td["name"] else ""
                # Show check if ALL selected cats have this tag
                all_have = bool(selected_cats) and all(tid in _cat_tags(c) for c in selected_cats)
                action = menu.addAction(f"  \u25CF  {label}")
                action.setCheckable(True)
                action.setChecked(all_have)
                # Color the dot via rich icon
                pix = QPixmap(12, 12)
                pix.fill(Qt.transparent)
                p = QPainter(pix)
                p.setRenderHint(QPainter.Antialiasing)
                p.setBrush(QBrush(QColor(td["color"])))
                p.setPen(Qt.NoPen)
                p.drawEllipse(1, 1, 10, 10)
                p.end()
                action.setIcon(QIcon(pix))
                action.triggered.connect(
                    lambda checked, tag_id=tid: self._apply_tag_to_selection(tag_id, checked)
                )

            menu.addSeparator()
            clear_action = menu.addAction("Clear all tags from selection")
            clear_action.setEnabled(bool(selected_cats))
            clear_action.triggered.connect(self._clear_tags_from_selection)

            # ── Filter section ──
            menu.addSeparator()
            filter_label = menu.addAction("Show only:")
            filter_label.setEnabled(False)

            current_filter = self._proxy_model.tag_filter
            show_all = menu.addAction("All cats")
            show_all.setCheckable(True)
            show_all.setChecked(not current_filter)
            show_all.triggered.connect(self._clear_tag_filter)

            for td in _TAG_DEFS:
                tid = td["id"]
                label = td["name"] if td["name"] else "\u25CF"
                is_active = tid in current_filter
                pix = QPixmap(12, 12)
                pix.fill(Qt.transparent)
                p = QPainter(pix)
                p.setRenderHint(QPainter.Antialiasing)
                p.setBrush(QBrush(QColor(td["color"])))
                p.setPen(Qt.NoPen)
                p.drawEllipse(1, 1, 10, 10)
                p.end()
                check_mark = "\u2713 " if is_active else "  "
                fa = menu.addAction(QIcon(pix), f"{check_mark}{label}")
                fa.setCheckable(True)
                fa.setChecked(is_active)
                fa.triggered.connect(
                    lambda checked, tag_id=tid: self._toggle_tag_filter(tag_id, checked)
                )

        menu.addSeparator()
        manage = menu.addAction("Manage Tags\u2026")
        manage.triggered.connect(self._open_tag_manager)

        menu.exec(self._tags_btn.mapToGlobal(
            self._tags_btn.rect().bottomLeft()))

    def _get_selected_cats(self) -> list:
        """Get currently selected cats from the main table."""
        rows = set()
        for idx in self._table.selectionModel().selectedRows():
            src = self._proxy_model.mapToSource(idx)
            rows.add(src.row())
        return [c for r in rows if (c := self._source_model.cat_at(r)) is not None]

    def _apply_tag_to_selection(self, tag_id: str, add: bool):
        """Add or remove a tag from all selected cats."""
        cats = self._get_selected_cats()
        if not cats:
            return
        _TAG_ICON_CACHE.clear()
        _TAG_PIX_CACHE.clear()
        for c in cats:
            current = list(getattr(c, 'tags', None) or [])
            if add and tag_id not in current:
                current.append(tag_id)
            elif not add and tag_id in current:
                current.remove(tag_id)
            c.tags = current
        # Refresh name column for affected rows
        for row in range(self._source_model.rowCount()):
            cat = self._source_model.cat_at(row)
            if cat in cats:
                idx = self._source_model.index(row, COL_NAME)
                self._source_model.dataChanged.emit(idx, idx, [Qt.DisplayRole])
        if self._current_save:
            _save_tags(self._current_save, self._cats)
        if self._detail and self._detail.current_cats:
            self._detail.show_cats(self._detail.current_cats)

    def _clear_tags_from_selection(self):
        """Remove all tags from selected cats."""
        cats = self._get_selected_cats()
        if not cats:
            return
        _TAG_ICON_CACHE.clear()
        _TAG_PIX_CACHE.clear()
        for c in cats:
            c.tags = []
        for row in range(self._source_model.rowCount()):
            cat = self._source_model.cat_at(row)
            if cat in cats:
                idx = self._source_model.index(row, COL_NAME)
                self._source_model.dataChanged.emit(idx, idx, [Qt.DisplayRole])
        if self._current_save:
            _save_tags(self._current_save, self._cats)
        if self._detail and self._detail.current_cats:
            self._detail.show_cats(self._detail.current_cats)

    def _tag_filtered_cats(self) -> list:
        """Return cats filtered by the active tag filter, or all cats if no filter."""
        f = self._proxy_model.tag_filter
        if not f:
            return self._cats
        return [c for c in self._cats if set(_cat_tags(c)) & f]

    def _toggle_tag_filter(self, tag_id: str, checked: bool):
        """Toggle a single tag in the filter set."""
        f = set(self._proxy_model.tag_filter)
        if checked:
            f.add(tag_id)
        else:
            f.discard(tag_id)
        self._proxy_model.set_tag_filter(f)
        self._update_count()
        self._refresh_views_for_tag_filter()
        # Visual indicator on the Tags button when filtering
        if f:
            self._tags_btn.setStyleSheet(
                "QPushButton { background:#2a3a2a; color:#8c8; border:1px solid #4a6a4a;"
                " border-radius:4px; padding:3px 10px; font-size:11px; font-weight:bold; }"
                "QPushButton:hover { background:#3a5a3a; color:#afa; }"
                "QPushButton::menu-indicator { image:none; }")
        else:
            self._tags_btn.setStyleSheet(
                "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a;"
                " border-radius:4px; padding:3px 10px; font-size:11px; font-weight:bold; }"
                "QPushButton:hover { background:#252545; color:#ddd; }"
                "QPushButton::menu-indicator { image:none; }")

    def _refresh_views_for_tag_filter(self):
        """Push tag-filtered cat list to secondary views."""
        filtered = self._tag_filtered_cats()
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.set_cats(filtered)
        if self._safe_breeding_view is not None:
            self._safe_breeding_view.set_cats(filtered)
        if self._breeding_partners_view is not None:
            self._breeding_partners_view.set_cats(filtered)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.set_cats(filtered)

    def _clear_tag_filter(self):
        """Remove all tag filters."""
        self._proxy_model.set_tag_filter(set())
        self._update_count()
        self._refresh_views_for_tag_filter()
        self._tags_btn.setStyleSheet(
            "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a;"
            " border-radius:4px; padding:3px 10px; font-size:11px; font-weight:bold; }"
            "QPushButton:hover { background:#252545; color:#ddd; }"
            "QPushButton::menu-indicator { image:none; }")

    def _open_tag_manager(self):
        dlg = TagManagerDialog(self)
        dlg.exec()
        _TAG_ICON_CACHE.clear()
        _TAG_PIX_CACHE.clear()
        # Repaint table without invalidating selection
        self._table.viewport().update()
        if self._detail and self._detail.current_cats:
            self._detail.show_cats(self._detail.current_cats)
        if self._current_save:
            _save_tags(self._current_save, self._cats)

    def _on_blacklist_changed(self):
        if self._current_save:
            _save_blacklist(self._current_save, self._cats)
            _save_must_breed(self._current_save, self._cats)
            _save_pinned(self._current_save, self._cats)
            _save_tags(self._current_save, self._cats)
        self._refresh_bulk_view_buttons()
        if self._safe_breeding_view is not None:
            self._safe_breeding_view.set_cats(self._cats)
        if self._breeding_partners_view is not None:
            self._breeding_partners_view.set_cats(self._cats)
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.set_cats(self._cats)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.set_cats(self._cats)

    def _on_calibration_changed(self):
        if not self._current_save:
            return
        cal_explicit, cal_token, cal_rows = _apply_calibration(self._current_save, self._cats)
        self._source_model.load(self._cats)
        self._refresh_filter_button_counts()
        if self._safe_breeding_view is not None:
            self._safe_breeding_view.set_cats(self._cats)
        if self._breeding_partners_view is not None:
            self._breeding_partners_view.set_cats(self._cats)
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.set_cats(self._cats)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.set_cats(self._cats)
        if self._calibration_view is not None and self._calibration_view.isVisible():
            self._calibration_view.set_context(self._current_save, self._cats)
        self._update_count()
        self.statusBar().showMessage(
            _tr("status.calibration_applied", default="Calibration applied ({explicit} explicit, {token} token from {rows} rows)", explicit=cal_explicit, token=cal_token, rows=cal_rows)
        )

    # ── Breeding cache ──────────────────────────────────────────────────

    @staticmethod
    def _cache_cat_fingerprint(cat: 'Cat') -> tuple:
        """Tuple of every field that affects cache computation (not room/display)."""
        return _breeding_cache_fingerprint(cat)

    def _only_display_changed(self, new_cats: list['Cat']) -> bool:
        """Return True if self._cats and new_cats differ only in display fields (e.g. room)."""
        if not self._cats:
            return False
        old_fps = {c.db_key: self._cache_cat_fingerprint(c) for c in self._cats}
        new_fps = {c.db_key: self._cache_cat_fingerprint(c) for c in new_cats}
        return old_fps == new_fps

    def _start_breeding_cache(self, cats: list[Cat], force_full: bool = False):
        """Kick off background computation of the breeding cache."""
        # Fast path: skip rebuild when only display fields (e.g. room) changed
        if (not force_full
                and self._breeding_cache is not None
                and self._breeding_cache.ready
                and self._only_display_changed(cats)):
            # Refresh cat object references so views see updated rooms
            self._breeding_cache._cats_by_key = {
                c.db_key: c for c in cats if c.status != "Gone"
            }
            # Keep _prev_parent_keys current for the next reload's incremental check
            self._prev_parent_keys = {
                c.db_key: (
                    c.parent_a.db_key if c.parent_a is not None else None,
                    c.parent_b.db_key if c.parent_b is not None else None,
                )
                for c in cats
            }
            return

        # Cancel any in-progress worker
        if self._cache_worker is not None:
            worker = self._cache_worker
            self._cache_worker = None
            worker.quit()
            if not worker.wait(500):
                worker.terminate()
                worker.wait(100)

        # Snapshot parent keys before clearing old cache (for incremental update)
        prev_cache = self._breeding_cache if not force_full else None
        prev_parent_keys = dict(self._prev_parent_keys) if hasattr(self, "_prev_parent_keys") and not force_full else {}

        # Record current parent keys for next reload
        self._prev_parent_keys = {
            c.db_key: (
                c.parent_a.db_key if c.parent_a is not None else None,
                c.parent_b.db_key if c.parent_b is not None else None,
            )
            for c in cats
        }

        self._breeding_cache = None
        self._cache_progress.setValue(0)
        self._cache_progress.show()

        # Try loading pairwise data from disk (skip if force_full)
        existing = None
        save_path = self._current_save or ""
        save_signature = _breeding_save_signature(cats)
        pedigree_coi_memos = getattr(self, "_pedigree_coi_memos", {})
        if not force_full and save_path:
            existing = BreedingCache.load_from_disk(save_path, save_signature)
            if existing is not None:
                self._cache_progress.setFormat(_tr("loading.cache.loading_cached"))
            elif prev_cache is not None:
                self._cache_progress.setFormat(_tr("loading.cache.updating"))
            else:
                self._cache_progress.setFormat(_tr("loading.cache.computing"))
        else:
            self._cache_progress.setFormat(_tr("loading.cache.computing"))

        worker = BreedingCacheWorker(
            cats, save_path=save_path, existing_pairwise=existing,
            prev_cache=prev_cache, prev_parent_keys=prev_parent_keys,
            save_signature=save_signature,
            pedigree_coi_memos=pedigree_coi_memos,
            parent=self,
        )
        worker.progress.connect(self._on_cache_progress)
        worker.phase1_ready.connect(self._on_phase1_ready)
        worker.finished_cache.connect(self._on_cache_ready)
        worker.finished.connect(lambda: self._cache_progress.hide())
        self._cache_worker = worker
        worker.start()

    def _on_cache_progress(self, current: int, total: int):
        self._cache_progress.setMaximum(total)
        self._cache_progress.setValue(current)

    def _clear_breeding_cache(self):
        """Delete the on-disk breeding cache for the current save file."""
        if not self._current_save:
            self.statusBar().showMessage(_tr("status.no_save_loaded_clear"))
            return
        cp = _breeding_cache_path(self._current_save)
        if os.path.exists(cp):
            try:
                os.remove(cp)
                self.statusBar().showMessage(_tr("status.cache_cleared"))
            except OSError as e:
                self.statusBar().showMessage(_tr("status.cache_delete_failed", default="Could not delete cache: {error}", error=e))
        else:
            self.statusBar().showMessage(_tr("status.cache_missing"))

    def _on_phase1_ready(self, cache: BreedingCache):
        """Ancestry computed — push to table and Safe Breeding so they're usable immediately."""
        self._breeding_cache = cache
        self._source_model.set_breeding_cache(cache)
        if self._safe_breeding_view is not None:
            self._safe_breeding_view.set_cache(cache)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.set_cache(cache)
        self._cache_progress.setFormat(_tr("loading.cache.pair_risks"))

    def _on_cache_ready(self, cache: BreedingCache):
        self._breeding_cache = cache
        self._cache_worker = None
        self._cache_progress.hide()
        # Push completed cache (now includes pairwise risk) to all views
        self._source_model.set_breeding_cache(cache)
        if self._safe_breeding_view is not None:
            self._safe_breeding_view.set_cache(cache)
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.set_cache(cache)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.set_cache(cache)
        self.statusBar().showMessage(
            self.statusBar().currentMessage() + _tr("status.cache_ready_suffix", default="  |  Breeding cache ready")
        )

    # ── Loading ────────────────────────────────────────────────────────────

    def load_save(self, path: str, force_full_breeding_cache: bool = False):
        previous_save = self._current_save
        fresh_save = True
        if previous_save:
            fresh_save = os.path.normcase(os.path.abspath(previous_save)) != os.path.normcase(os.path.abspath(path))
        if fresh_save:
            self._breeding_cache = None
            self._prev_parent_keys = {}
        self._current_save = path
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.set_save_path(path, refresh_existing=False)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.set_save_path(path, refresh_existing=False)
        if self._mutation_planner_view is not None:
            self._mutation_planner_view.set_save_path(path, refresh_existing=False, notify=False)
            if self._room_optimizer_view is not None:
                self._room_optimizer_view.on_planner_traits_changed()
            if self._perfect_planner_view is not None:
                self._perfect_planner_view.sync_mutation_traits()
                self._perfect_planner_view.sync_mutation_import_button_state()
        if self._watcher.files():
            self._watcher.removePaths(self._watcher.files())
        self._watcher.addPath(path)

        # Cancel any in-progress load
        if self._save_load_worker is not None:
            worker = self._save_load_worker
            self._save_load_worker = None
            worker.quit()
            if not worker.wait(500):
                worker.terminate()
                worker.wait(100)
        if self._cache_worker is not None:
            worker = self._cache_worker
            self._cache_worker = None
            worker.quit()
            if not worker.wait(500):
                worker.terminate()
                worker.wait(100)

        # Show overlay while parsing (background thread — main thread stays responsive for repaint)
        name = os.path.basename(path)
        self._loading_label.setText(_tr("loading.save_named", name=name))
        overlay = self._loading_overlay
        parent = overlay.parentWidget()
        if parent:
            overlay.setGeometry(0, 0, parent.width(), parent.height())
        overlay.raise_()
        overlay.show()

        worker = SaveLoadWorker(path, parent=self)
        worker.finished_load.connect(
            lambda result, force=force_full_breeding_cache: self._on_save_loaded(result, force)
        )
        self._save_load_worker = worker
        worker.start()

    def _on_save_loaded(self, result: dict, force_full_breeding_cache: bool = False):
        self._save_load_worker = None
        # Dismiss overlay immediately — UI work below is fast (model.load is O(n), no ancestry)
        self._loading_overlay.hide()
        self._save_view_disabled = True
        try:
            cats = result["cats"]
            errors = result["errors"]
            unlocked_house_rooms = result.get("unlocked_house_rooms", [])
            furniture = result.get("furniture", [])
            furniture_by_room = result.get("furniture_by_room", {})
            applied_overrides = result["applied_overrides"]
            override_rows = result["override_rows"]
            cal_explicit = result["cal_explicit"]
            cal_token = result["cal_token"]
            cal_rows = result["cal_rows"]
            self._pedigree_coi_memos = dict(result.get("pedigree_coi_memos", {}))

            self._cats = cats
            self._furniture = furniture
            self._furniture_by_room = furniture_by_room
            self._furniture_data = dict(_FURNITURE_DATA)
            self._available_house_rooms = [room for room in ROOM_KEYS if room in set(unlocked_house_rooms)] or list(ROOM_KEYS)
            self._room_summaries = {
                summary.room: summary
                for summary in build_furniture_room_summaries(
                    self._furniture_by_room,
                    self._furniture_data,
                    self._cats,
                    room_order=self._available_house_rooms,
                )
                if summary.room in self._available_house_rooms or not summary.room
            }
            self._source_model.set_breeding_cache(None)
            if self._safe_breeding_view is not None:
                self._safe_breeding_view.set_cache(None)
            if self._breeding_partners_view is not None:
                self._breeding_partners_view.set_cache(None)
            if self._room_optimizer_view is not None:
                self._room_optimizer_view.set_cache(None)
            if self._perfect_planner_view is not None:
                self._perfect_planner_view.set_cache(None)
            self._refresh_threshold_runtime(cats)
            self._source_model.load(cats)
            self._rebuild_room_buttons(cats)
            self._refresh_filter_button_counts()
            self._filter(None, self._btn_all)
            if self._room_optimizer_view is not None:
                self._room_optimizer_view.set_available_rooms(self._available_house_rooms)
                self._room_optimizer_view.set_room_summaries(self._room_summaries)
            if self._furniture_view is not None:
                self._furniture_view.set_context(self._cats, self._furniture, self._furniture_data, available_rooms=self._available_house_rooms)
            # Only push cats to currently visible views immediately.
            # Hidden views call set_cats themselves when shown via _show_* methods.
            if self._tree_view is not None and self._tree_view.isVisible():
                self._tree_view.set_cats(cats)
            if self._safe_breeding_view is not None and self._safe_breeding_view.isVisible():
                self._safe_breeding_view.set_cats(cats)
            if self._breeding_partners_view is not None and self._breeding_partners_view.isVisible():
                self._breeding_partners_view.set_cats(cats)
            if self._room_optimizer_view is not None and self._room_optimizer_view.isVisible():
                self._room_optimizer_view.set_cats(cats)
            if self._perfect_planner_view is not None and self._perfect_planner_view.isVisible():
                self._perfect_planner_view.set_cats(cats)
            if self._calibration_view is not None and self._calibration_view.isVisible():
                self._calibration_view.set_context(self._current_save, cats)
            name = os.path.basename(self._current_save)
            self._save_lbl.setText(name)
            self.setWindowTitle(_tr("app.title_with_save", name=name))

            msg = _tr("status.save_loaded", default="Loaded {count} cats from {name}", count=len(cats), name=name)
            if errors:
                msg += _tr("status.save_loaded.parse_errors_suffix", default="  ({count} parse errors)", count=len(errors))
            if applied_overrides:
                msg += _tr("status.save_loaded.gender_overrides_suffix", default="  ({applied}/{rows} gender overrides)", applied=applied_overrides, rows=override_rows)
            if cal_rows:
                msg += _tr("status.save_loaded.calibration_suffix", default="  (calibration: {explicit} explicit, {token} token)", explicit=cal_explicit, token=cal_token)
            self.statusBar().showMessage(msg)

            # Start background breeding cache computation
            self._start_breeding_cache(cats, force_full=force_full_breeding_cache)

            # Update default save menu items
            self._update_default_save_menu()
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            self.statusBar().showMessage(_tr("status.save_load_failed", default="Error loading save: {error}", error=e))
        finally:
            self._save_view_disabled = False
            self._restore_current_view()

    def _update_default_save_menu(self):
        """Update the enabled state of default save menu items."""
        has_save = self._current_save is not None
        default_save = _saved_default_save()
        is_current_default = has_save and default_save == self._current_save

        self._set_default_save_action.setEnabled(has_save and not is_current_default)
        self._clear_default_save_action.setEnabled(has_save and is_current_default)

    def _set_current_as_default(self):
        """Set the current save file as the default."""
        if self._current_save:
            _set_default_save(self._current_save)
            name = os.path.basename(self._current_save)
            self.statusBar().showMessage(_tr("status.default_save_set", default="Default save set to: {name}", name=name))
            self._update_default_save_menu()

    def _clear_default_save(self):
        """Clear the default save setting."""
        _set_default_save(None)
        self.statusBar().showMessage(_tr("status.default_save_cleared", default="Default save cleared"))
        self._update_default_save_menu()

    def _flush_persistent_view_state(self):
        """Persist planner-style view state before the app shuts down."""
        if self._room_optimizer_view is not None:
            self._room_optimizer_view.save_session_state()
            _save_room_priority_config(self._room_optimizer_view.get_room_config(), self._room_optimizer_view.save_path)
        if self._perfect_planner_view is not None:
            self._perfect_planner_view.save_session_state()
        if self._mutation_planner_view is not None:
            self._mutation_planner_view.save_session_state()
        if self._furniture_view is not None:
            self._furniture_view.save_session_state()

    def closeEvent(self, event):
        self._flush_persistent_view_state()
        super().closeEvent(event)

    def _reset_ui_settings_to_defaults(self):
        """Reset pane sizes and planner inputs without touching save-file data."""
        confirm = QMessageBox.question(
            self,
            _tr("menu.settings.reset_ui_defaults.title"),
            _tr("menu.settings.reset_ui_defaults.body"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        for view in (
            self._room_optimizer_view,
            self._perfect_planner_view,
            self._furniture_view,
            self._mutation_planner_view,
        ):
            if view is not None and hasattr(view, "reset_to_defaults"):
                view.reset_to_defaults()

        _set_room_optimizer_auto_recalc(False)
        _save_optimizer_search_settings(_OPTIMIZER_SEARCH_DEFAULTS)
        if hasattr(self, "_room_optimizer_auto_recalc_action"):
            self._room_optimizer_auto_recalc_action.blockSignals(True)
            self._room_optimizer_auto_recalc_action.setChecked(False)
            self._room_optimizer_auto_recalc_action.blockSignals(False)
        if self._room_optimizer_view is not None and hasattr(self._room_optimizer_view, "set_auto_recalculate"):
            self._room_optimizer_view.set_auto_recalculate(False)

        if hasattr(self, "_detail_splitter") and self._detail_splitter is not None:
            total = max(20, self._detail_splitter.height())
            detail_h = min(240, max(10, total - 10))
            self._detail_splitter.setSizes([max(10, total - detail_h), detail_h])
            _save_splitter_state(self._detail_splitter)

        if hasattr(self, "_sidebar_splitter") and self._sidebar_splitter is not None:
            total = max(20, self._sidebar_splitter.width())
            sidebar_w = min(self._base_sidebar_width, max(10, total - 10))
            self._sidebar_splitter.setSizes([sidebar_w, max(10, total - sidebar_w)])
            _save_splitter_state(self._sidebar_splitter)

        self.statusBar().showMessage(
            _tr("status.ui_settings_reset", default="UI settings reset to defaults")
        )

    def _toggle_room_optimizer_auto_recalc(self, checked: bool):
        _set_room_optimizer_auto_recalc(bool(checked))
        if self._room_optimizer_view is not None and hasattr(self._room_optimizer_view, "set_auto_recalculate"):
            self._room_optimizer_view.set_auto_recalculate(bool(checked))

    def _toggle_lineage(self, checked: bool):
        self._show_lineage = checked
        for col in (COL_GEN_DEPTH, COL_SRC):
            self._table.setColumnHidden(col, not checked)
        self._source_model.set_show_lineage(checked)
        self._detail.set_show_lineage(checked)
        self._on_selection()   # refresh detail panel with updated flag

    def _open_file(self):
        saves   = find_save_files()
        start   = os.path.dirname(saves[0]) if saves else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self,
            _tr("dialog.open_save.title"),
            start,
            _tr("dialog.open_save.filter"),
        )
        if path:
            self.load_save(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_loading_overlay") and self._loading_overlay.isVisible():
            parent = self._loading_overlay.parentWidget()
            if parent:
                self._loading_overlay.setGeometry(0, 0, parent.width(), parent.height())

    def _export_cats(self):
        if not self._cats:
            QMessageBox.information(self, _tr("export.title", default="Export"), _tr("export.no_save", default="No save loaded."))
            return

        base = os.path.splitext(self._current_save)[0] if self._current_save else "cats"
        path, _ = QFileDialog.getSaveFileName(
            self, _tr("export.dialog_title", default="Export Cats"),
            base,
            "CSV (*.csv);;Excel (*.xlsx)"
        )
        if not path:
            return

        base_stat_headers  = ["Base " + s for s in STAT_NAMES]
        actual_stat_headers = ["Actual " + s for s in STAT_NAMES]
        headers = (
            ["Name", "Status", "Room", "Age", "Gender", "Sexuality", "Generation"]
            + base_stat_headers + ["Base Sum"]
            + actual_stat_headers + ["Actual Sum"]
            + ["Abilities", "Mutations", "Aggression", "Libido", "Inbreeding",
               "Pinned", "Blacklisted", "Must Breed", "Parent A", "Parent B"]
        )

        def _trait(val, field):
            if val is None:
                return ""
            return _trait_label_from_value(field, val)

        rows = []
        for cat in self._cats:
            base_vals   = [cat.base_stats.get(s, 0) for s in STAT_NAMES]
            actual_vals = [cat.total_stats.get(s, 0) for s in STAT_NAMES]
            row = (
                [
                    cat.name,
                    cat.status or "",
                    cat.room_display,
                    str(cat.age) if cat.age is not None else "",
                    cat.gender or "",
                    cat.sexuality or "",
                    str(cat.generation),
                ]
                + [str(v) for v in base_vals] + [str(sum(base_vals))]
                + [str(v) for v in actual_vals] + [str(sum(actual_vals))]
                + [
                    "; ".join(cat.abilities or []),
                    "; ".join(cat.mutations or []),
                    _trait(cat.aggression, "aggression"),
                    _trait(cat.libido, "libido"),
                    _trait(cat.inbredness, "inbredness"),
                    "Yes" if getattr(cat, "is_pinned", False) else "No",
                    "Yes" if getattr(cat, "is_blacklisted", False) else "No",
                    "Yes" if getattr(cat, "must_breed", False) else "No",
                    cat.parent_a.name if cat.parent_a else "",
                    cat.parent_b.name if cat.parent_b else "",
                ]
            )
            rows.append(row)

        ext = os.path.splitext(path)[1].lower()

        if ext == ".xlsx":
            try:
                import openpyxl
                from openpyxl.styles import Font
            except ImportError:
                QMessageBox.critical(self, _tr("export.title", default="Export"), "openpyxl is not installed. Install it with: pip install openpyxl")
                return
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Cats"
            ws.append(headers)
            for cell in ws[1]:
                cell.font = Font(bold=True)
            for row in rows:
                ws.append(row)
            wb.save(path)
        else:
            if not path.lower().endswith(".csv"):
                path += ".csv"
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)

        QMessageBox.information(self, _tr("export.title", default="Export"), f"Exported {len(rows)} cats to:\n{path}")

    def _reload(self):
        if self._current_save:
            self.load_save(self._current_save)

    def _on_file_changed(self, path: str):
        if path != self._current_save:
            return
        # If cats are already loaded and no full reload is running, try the fast path.
        if self._cats and self._save_load_worker is None:
            self._start_quick_room_refresh()
        else:
            self._reload()

    def _start_quick_room_refresh(self):
        if self._quick_refresh_worker is not None:
            self._quick_refresh_worker.quit()
            self._quick_refresh_worker.wait(200)
            self._quick_refresh_worker = None
        expected = {c.db_key for c in self._cats}
        w = QuickRoomRefreshWorker(self._current_save, expected, parent=self)
        w.room_patch.connect(self._on_room_patch)
        w.needs_full_reload.connect(self._reload)
        self._quick_refresh_worker = w
        w.start()

    def _on_room_patch(self, patch: dict):
        self._quick_refresh_worker = None
        for cat in self._cats:
            entry = patch.get(cat.db_key)
            if entry is not None:
                cat.room, cat.status = entry
        # Lightweight repaint — no model rebuild, no ancestry recompute
        self._source_model.layoutChanged.emit()
        self._rebuild_room_buttons(self._cats)
        self._refresh_filter_button_counts()
        if self._furniture_view is not None:
            self._furniture_view.set_context(self._cats, self._furniture, self._furniture_data, available_rooms=self._available_house_rooms)
        if self._tree_view is not None and self._tree_view.isVisible():
            self._tree_view.set_cats(self._cats)
        if self._safe_breeding_view is not None and self._safe_breeding_view.isVisible():
            self._safe_breeding_view.set_cats(self._cats)
        if self._breeding_partners_view is not None and self._breeding_partners_view.isVisible():
            self._breeding_partners_view.set_cats(self._cats)
        if self._room_optimizer_view is not None and self._room_optimizer_view.isVisible():
            self._room_optimizer_view.set_cats(self._cats)
        if self._perfect_planner_view is not None and self._perfect_planner_view.isVisible():
            self._perfect_planner_view.set_cats(self._cats)
        if self._calibration_view is not None and self._calibration_view.isVisible():
            self._calibration_view.set_context(self._current_save, self._cats)
        self.statusBar().showMessage(_tr("status.rooms_refreshed", default="Room locations updated."))

    def _open_tree_browser(self):
        _save_current_view("tree")
        self._show_tree_view()
        rows = list({
            self._proxy_model.mapToSource(idx).row()
            for idx in self._table.selectionModel().selectedRows()
        })
        cats = [c for r in rows[:1] if (c := self._source_model.cat_at(r)) is not None]
        if cats and self._tree_view is not None:
            self._tree_view.select_cat(cats[0])

    def _open_safe_breeding_view(self):
        _save_current_view("safe_breeding")
        self._show_safe_breeding_view()
        rows = list({
            self._proxy_model.mapToSource(idx).row()
            for idx in self._table.selectionModel().selectedRows()
        })
        cats = [c for r in rows[:1] if (c := self._source_model.cat_at(r)) is not None]
        if cats and self._safe_breeding_view is not None:
            self._safe_breeding_view.select_cat(cats[0])

    def _open_breeding_partners_view(self):
        _save_current_view("breeding_partners")
        self._show_breeding_partners_view()

    def _open_room_optimizer(self):
        _save_current_view("room_optimizer")
        self._show_room_optimizer_view()

    def _open_perfect_planner_view(self):
        _save_current_view("perfect_planner")
        self._show_perfect_planner_view()

    def _open_calibration_view(self):
        _save_current_view("calibration")
        self._show_calibration_view()

    def _open_mutation_planner_view(self):
        _save_current_view("mutation_planner")
        self._show_mutation_planner_view()

    def _open_furniture_view(self):
        _save_current_view("furniture")
        self._show_furniture_view()

    def _restore_current_view(self):
        """Restore the last-used view after a save is loaded."""
        view = _load_current_view()
        _restore_map = {
            "tree":               self._show_tree_view,
            "safe_breeding":      self._show_safe_breeding_view,
            "breeding_partners":  self._show_breeding_partners_view,
            "room_optimizer":     self._show_room_optimizer_view,
            "perfect_planner":    self._show_perfect_planner_view,
            "calibration":        self._show_calibration_view,
            "mutation_planner":   self._show_mutation_planner_view,
            "furniture":          self._show_furniture_view,
        }
        fn = _restore_map.get(view)
        if fn:
            fn()

    # ── UI zoom ───────────────────────────────────────────────────────────

    def _scaled(self, value: int) -> int:
        return max(1, round(value * (self._zoom_percent / 100.0)))

    def _update_zoom_info_action(self):
        if hasattr(self, "_zoom_info_action"):
            self._zoom_info_action.setText(_tr("menu.settings.zoom_info", percent=self._zoom_percent))

    def _set_zoom(self, percent: int):
        clamped = max(_ZOOM_MIN, min(_ZOOM_MAX, int(percent)))
        if clamped == self._zoom_percent:
            return
        self._zoom_percent = clamped
        self._apply_zoom()
        self._update_zoom_info_action()
        self.statusBar().showMessage(_tr("status.zoom_changed", default="UI zoom set to {percent}%", percent=self._zoom_percent))

    def _change_zoom(self, direction: int):
        self._set_zoom(self._zoom_percent + (direction * _ZOOM_STEP))

    def _reset_zoom(self):
        self._set_zoom(100)

    def _change_font_size(self, direction: int):
        self._set_font_size_offset(self._font_size_offset + direction)

    def _set_font_size_offset(self, offset: int):
        clamped = max(-6, min(12, offset))
        if clamped == self._font_size_offset:
            return
        self._font_size_offset = clamped
        self._apply_zoom()
        self._update_font_size_info_action()
        label = _font_size_offset_label(clamped)
        self.statusBar().showMessage(_tr("status.font_size_offset", default="Font size offset: {label}", label=label))

    def _update_font_size_info_action(self):
        if hasattr(self, "_font_size_info_action"):
            off = self._font_size_offset
            label = _font_size_offset_label(off)
            self._font_size_info_action.setText(_tr("menu.settings.font_size_info", label=label))

    def _apply_zoom(self):
        app = QApplication.instance()
        font = QFont(self._base_font)
        base_pt = self._base_font.pointSizeF()
        if base_pt > 0:
            zoomed_pt = base_pt * (self._zoom_percent / 100.0) + self._font_size_offset
            font.setPointSizeF(max(_ACCESSIBILITY_MIN_FONT_PT, zoomed_pt))
        elif self._base_font.pixelSize() > 0:
            font.setPixelSize(max(_ACCESSIBILITY_MIN_FONT_PX, self._scaled(self._base_font.pixelSize()) + self._font_size_offset))
        app.setFont(font)

        if hasattr(self, "_sidebar"):
            self._sidebar.setFixedWidth(self._scaled(self._base_sidebar_width))
        if hasattr(self, "_header"):
            self._header.setFixedHeight(self._scaled(self._base_header_height))
        if hasattr(self, "_search"):
            self._search.setFixedWidth(self._scaled(self._base_search_width))
        if hasattr(self, "_table"):
            for col, width in self._base_col_widths.items():
                self._table.setColumnWidth(col, self._scaled(width))
            self._table.verticalHeader().setDefaultSectionSize(self._scaled(24))

        # Scale all hardcoded stylesheet font-size values across the whole window.
        # 1pt ≈ 1.33px; round to nearest integer pixel.
        offset_px = round(self._font_size_offset * 1.333)
        _apply_font_offset_to_tree(self, offset_px)


def _ensure_gpak_path_interactive(parent: Optional[QWidget] = None):
    if _GPAK_PATH:
        return

    if os.path.isdir(r"C:\Program Files (x86)\Steam\steamapps\common\Mewgenics"):
        start_dir = r"C:\Program Files (x86)\Steam\steamapps\common\Mewgenics"
    elif os.path.isdir(r"C:\Program Files\Steam\steamapps\common\Mewgenics"):
        start_dir = r"C:\Program Files\Steam\steamapps\common\Mewgenics"
    elif os.path.isdir(r"D:\Games\Mewgenics"):
        start_dir = r"D:\Games\Mewgenics"
    else:
        start_dir = str(Path.home())
    chosen_dir = QFileDialog.getExistingDirectory(
        parent,
        "Select Mewgenics Install Folder",
        start_dir,
    )
    if not chosen_dir:
        return

    gpak_path = os.path.join(chosen_dir, "resources.gpak")
    if os.path.exists(gpak_path):
        _set_gpak_path(gpak_path)
        return

    QMessageBox.warning(
        parent,
        "resources.gpak not found",
        "The selected folder does not contain resources.gpak. "
        "Choose the Mewgenics install directory that contains that file.",
    )



def main():
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],
    )
    logger.info("Mewgenics Breeding Manager %s starting", APP_VERSION)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(13,  13,  28))
    pal.setColor(QPalette.WindowText,      QColor(220, 220, 230))
    pal.setColor(QPalette.Base,            QColor(18,  18,  36))
    pal.setColor(QPalette.AlternateBase,   QColor(20,  20,  40))
    pal.setColor(QPalette.Text,            QColor(220, 220, 230))
    pal.setColor(QPalette.Button,          QColor(22,  22,  46))
    pal.setColor(QPalette.ButtonText,      QColor(200, 200, 210))
    pal.setColor(QPalette.Highlight,       QColor(30,  48, 100))
    pal.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.ToolTipBase,     QColor(20,  20,  40))
    pal.setColor(QPalette.ToolTipText,     QColor(220, 220, 230))
    app.setPalette(pal)

    # Keep Qt initialized before showing dialogs on some Linux setups.
    from PySide6 import QtWidgets
    QtWidgets.QMessageBox()

    if not _GPAK_PATH:
        QMessageBox.information(
            None,
            "Locate Mewgenics",
            "Ability and mutation descriptions need the game's resources.gpak.\n"
            "Select your Mewgenics install folder to enable them.",
        )
        _ensure_gpak_path_interactive()

    # Open directly only when a valid default save exists; otherwise always show the save selector.
    default_save = _saved_default_save()
    initial_save: Optional[str] = default_save if default_save and os.path.isfile(default_save) else None

    if initial_save is None:
        saves = find_save_files()
        dlg = SaveSelectorDialog(saves)
        if dlg.exec() == QDialog.Accepted:
            initial_save = dlg.selected_path
        else:
            return 0

    win = MainWindow(initial_save=initial_save, use_saved_default=False)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
