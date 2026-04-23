"""Recommendation list widgets for the Party Builder UI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QLabel, QListWidget, QVBoxLayout

from .constants import (
    CATEGORIES,
    RECOMMENDATION_BAR_HEIGHT,
    RECOMMENDATION_BAR_SCALE,
    RECOMMENDATION_NAME_WIDTH,
    RECOMMENDATION_TEXT_COLOR,
    RECOMMENDATION_WHEEL_STEP,
)
from .logic import RecommendationEntry, class_score
from .styles import (
    recommendation_bar_color,
    recommendation_divider_stylesheet,
    recommendation_rating_text_stylesheet,
    recommendation_row_background,
    recommendation_row_stylesheet,
    score_label,
)


class RecommendationRowWidget(QFrame):
    def __init__(self, entry: RecommendationEntry, min_total: int, max_total: int, parent=None):
        super().__init__(parent)
        self.setObjectName("recommendationRow")
        self._title_label = QLabel(entry.class_name)
        self._title_label.setWordWrap(False)
        self._title_label.setFixedWidth(RECOMMENDATION_NAME_WIDTH)

        background_style, border_color = recommendation_row_background(entry.class_name)
        bar_fill_color = recommendation_bar_color(entry.total, min_total, max_total)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        layout.addLayout(self._build_header(entry, max_total))
        layout.addLayout(self._build_ratings_grid(entry))

        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._title_label.setStyleSheet(f"color: {RECOMMENDATION_TEXT_COLOR}; font-weight: 700;")
        self.setStyleSheet(recommendation_row_stylesheet(background_style, border_color, bar_fill_color))

    def _build_header(self, entry: RecommendationEntry, max_total: int) -> QHBoxLayout:
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        header_layout.addWidget(self._title_label)

        bar_track = QFrame()
        bar_track.setObjectName("recommendationBarTrack")
        bar_track.setFixedHeight(RECOMMENDATION_BAR_HEIGHT)

        bar_track_layout = QHBoxLayout(bar_track)
        bar_track_layout.setContentsMargins(0, 0, 0, 0)
        bar_track_layout.setSpacing(0)

        fill_ratio = 0 if max_total <= 0 else max(0.0, min(1.0, entry.total / max_total))
        fill_units = max(0, int(fill_ratio * RECOMMENDATION_BAR_SCALE))
        empty_units = max(0, RECOMMENDATION_BAR_SCALE - fill_units)

        bar_fill = QFrame()
        bar_fill.setObjectName("recommendationBarFill")
        bar_fill.setFixedHeight(RECOMMENDATION_BAR_HEIGHT)
        if fill_units > 0:
            bar_track_layout.addWidget(bar_fill, fill_units)
        else:
            bar_fill.hide()
        bar_track_layout.addStretch(max(1, empty_units))

        header_layout.addWidget(bar_track, 1)
        return header_layout

    def _build_ratings_grid(self, entry: RecommendationEntry) -> QGridLayout:
        ratings_layout = QGridLayout()
        ratings_layout.setContentsMargins(0, 0, 0, 0)
        ratings_layout.setHorizontalSpacing(12)
        ratings_layout.setVerticalSpacing(4)
        class_totals = class_score(entry.class_name)

        for index, category in enumerate(CATEGORIES):
            rating_panel = QFrame()
            rating_panel.setObjectName("ratingPanel")
            rating_panel_layout = QGridLayout(rating_panel)
            rating_panel_layout.setContentsMargins(6, 2, 6, 2)
            rating_panel_layout.setHorizontalSpacing(8)
            rating_panel_layout.setVerticalSpacing(0)
            rating_panel_layout.setColumnStretch(0, 1)
            rating_panel_layout.setColumnStretch(1, 0)
            rating_panel_layout.setColumnStretch(2, 1)

            is_active = entry.contribution.get(category, 0) > 0
            category_label = QLabel(category)
            divider_label = QLabel("|")
            value_label = QLabel(score_label(class_totals[category]))
            category_label.setAlignment(Qt.AlignCenter)
            divider_label.setAlignment(Qt.AlignCenter)
            value_label.setAlignment(Qt.AlignCenter)
            category_label.setStyleSheet(recommendation_rating_text_stylesheet(is_active))
            divider_label.setStyleSheet(recommendation_divider_stylesheet(is_active))
            value_label.setStyleSheet(recommendation_rating_text_stylesheet(is_active))

            rating_panel_layout.addWidget(category_label, 0, 0)
            rating_panel_layout.addWidget(divider_label, 0, 1)
            rating_panel_layout.addWidget(value_label, 0, 2)
            ratings_layout.addWidget(rating_panel, index // 3, index % 3)

        return ratings_layout


class RecommendationListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(RECOMMENDATION_WHEEL_STEP)

    def wheelEvent(self, event):  # noqa: N802
        angle_delta = event.angleDelta().y()
        if angle_delta:
            scroll_bar = self.verticalScrollBar()
            scroll_delta = round((angle_delta / 120) * RECOMMENDATION_WHEEL_STEP)
            scroll_bar.setValue(scroll_bar.value() - scroll_delta)
            event.accept()
            return
        super().wheelEvent(event)
