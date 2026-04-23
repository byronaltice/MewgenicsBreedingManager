"""Main Party Builder view."""

from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QListWidget, QListWidgetItem, QSplitter, QVBoxLayout, QWidget

from .class_widgets import ClassListWidget, ClassRowWidget, class_row_size_hint
from .constants import CLASS_NAMES, DEFAULT_MIN_SCORE, HINT_TEXT_STYLESHEET, MAX_PARTY_SIZE
from .graph_widget import PartyGraphWidget
from .logic import preview_party, recommendation_total_range, recommend_classes
from .party_slots_widget import PartySlotsWidget
from .recommendation_widgets import RecommendationListWidget, RecommendationRowWidget


class PartyBuilderWidget(QWidget):
    def __init__(self, parent=None, min_score: int = DEFAULT_MIN_SCORE):
        super().__init__(parent)
        self._min_score = min_score
        self._party: list[str] = []
        self._preview_class: str | None = None
        self._class_widgets: dict[str, ClassRowWidget] = {}
        self._class_row_size_hint = class_row_size_hint()
        self._build_ui()
        self._refresh_views()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        top_splitter = self._build_splitter(self._build_class_panel(), self._build_party_panel())
        root.addWidget(top_splitter, 1)

        bottom_splitter = self._build_splitter(self._build_graph_panel(), self._build_recommendations_panel())
        root.addWidget(bottom_splitter, 1)

    def _build_splitter(self, left_widget: QWidget, right_widget: QWidget) -> QSplitter:
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        return splitter

    def _build_class_panel(self) -> QWidget:
        box = QGroupBox("Classes")
        layout = QVBoxLayout(box)
        self._class_list = ClassListWidget()
        self._class_list.classClicked.connect(self._toggle_class)
        self._class_list.classHovered.connect(self._set_preview_class)
        self._class_list.hoverCleared.connect(self._clear_preview_class)
        layout.addWidget(self._class_list)

        for class_name in CLASS_NAMES:
            self._add_class_row(class_name)

        layout.addWidget(self._build_hint_label("Hover to preview. Click to add or remove."))
        return box

    def _add_class_row(self, class_name: str) -> None:
        item = QListWidgetItem("")
        item.setData(Qt.UserRole, class_name)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setSizeHint(self._class_row_size_hint)
        self._class_list.addItem(item)
        class_widget = ClassRowWidget(class_name)
        self._class_widgets[class_name] = class_widget
        self._class_list.setItemWidget(item, class_widget)

    def _build_party_panel(self) -> QWidget:
        box = QGroupBox("Current Party")
        layout = QVBoxLayout(box)
        self._slots_widget = PartySlotsWidget()
        self._slots_widget.slotClicked.connect(self._remove_party_slot)
        layout.addWidget(self._slots_widget)
        return box

    def _build_graph_panel(self) -> QWidget:
        box = QGroupBox("Attribute Balance")
        layout = QVBoxLayout(box)
        self._graph_widget = PartyGraphWidget()
        layout.addWidget(self._graph_widget, 1)
        layout.addWidget(self._build_hint_label("Solid bars show the selected party. Hovering a class previews its addition.", word_wrap=True))
        return box

    def _build_recommendations_panel(self) -> QWidget:
        box = QGroupBox("Recommendations")
        layout = QVBoxLayout(box)
        self._recommendation_list = RecommendationListWidget()
        self._recommendation_list.setSelectionMode(QListWidget.NoSelection)
        layout.addWidget(self._recommendation_list, 1)
        return box

    def _build_hint_label(self, text: str, *, word_wrap: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(word_wrap)
        label.setStyleSheet(HINT_TEXT_STYLESHEET)
        return label

    def _toggle_class(self, class_name: str) -> None:
        if len(self._party) < MAX_PARTY_SIZE:
            self._party.append(class_name)
        self._refresh_views()

    def _remove_party_slot(self, slot_index: int) -> None:
        if 0 <= slot_index < len(self._party):
            self._party.pop(slot_index)
            self._refresh_views()

    def _set_preview_class(self, class_name: str) -> None:
        if class_name == self._preview_class:
            return
        self._preview_class = class_name
        self._refresh_preview_views()

    def _clear_preview_class(self) -> None:
        if self._preview_class is None:
            return
        self._preview_class = None
        self._refresh_preview_views()

    def leaveEvent(self, event):  # noqa: N802
        self._preview_class = None
        self._refresh_preview_views()
        super().leaveEvent(event)

    def _preview_party(self) -> list[str]:
        return preview_party(self._party, self._preview_class)

    def _refresh_preview_views(self) -> None:
        preview_members = self._preview_party()
        self._slots_widget.set_party(preview_members)
        self._graph_widget.set_state(self._party, preview_members, self._min_score)

    def _refresh_views(self) -> None:
        self._refresh_class_panel()
        self._refresh_preview_views()
        self._refresh_recommendations()

    def _refresh_class_panel(self) -> None:
        selected_counts = Counter(self._party)
        for class_name, class_widget in self._class_widgets.items():
            class_widget.set_selected_count(selected_counts.get(class_name, 0))

    def _refresh_recommendations(self) -> None:
        self._recommendation_list.clear()
        recommendations = recommend_classes(self._party, min_score=self._min_score)
        min_total, max_total = recommendation_total_range(recommendations)
        for entry in recommendations:
            item = QListWidgetItem("")
            row_widget = RecommendationRowWidget(entry, min_total, max_total)
            item.setSizeHint(row_widget.sizeHint())
            self._recommendation_list.addItem(item)
            self._recommendation_list.setItemWidget(item, row_widget)

    def set_party(self, party: list[str]) -> None:
        self._party = list(party[:MAX_PARTY_SIZE])
        self._refresh_views()

    def party(self) -> list[str]:
        return list(self._party)
