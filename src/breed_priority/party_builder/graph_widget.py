"""Balance graph widget for the Party Builder UI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .constants import (
    CATEGORIES,
    DEFAULT_MIN_SCORE,
    GRAPH_BOTTOM_MARGIN,
    GRAPH_LEFT_LABEL_WIDTH,
    GRAPH_MAX_BAR_WIDTH,
    GRAPH_MAX_GAP_WIDTH,
    GRAPH_MIN_GAP_WIDTH,
    GRAPH_MIN_HEIGHT,
    GRAPH_PLOT_MAX_WIDTH,
    GRAPH_SIDE_MARGIN,
    GRAPH_TOP_MARGIN,
    PREVIEW_ALPHA,
)
from .logic import class_score, party_totals
from .styles import color_for_class


class PartyGraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_party: list[str] = []
        self._preview_party: list[str] = []
        self._min_score = DEFAULT_MIN_SCORE
        self.setMinimumHeight(GRAPH_MIN_HEIGHT)

    def set_state(self, selected_party: list[str], preview_party_members: list[str], min_score: int) -> None:
        self._selected_party = list(selected_party)
        self._preview_party = list(preview_party_members)
        self._min_score = min_score
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        outer_rect = self.rect().adjusted(12, 12, -12, -12)
        painter.fillRect(self.rect(), QColor("#0c0c18"))
        if not outer_rect.isValid():
            return

        totals = party_totals(self._preview_party or self._selected_party)
        max_total = max(self._min_score, max(totals.values(), default=0))
        usable_rect = self._usable_rect(outer_rect)
        bar_width, gap, start_x, baseline_y = self._bar_layout(usable_rect)

        self._draw_threshold_line(painter, usable_rect, baseline_y, max_total)

        for index, category in enumerate(CATEGORIES):
            x = start_x + index * (bar_width + gap)
            total_value, current_bottom = self._draw_selected_stack(
                painter,
                category,
                x,
                bar_width,
                baseline_y,
                usable_rect.height(),
                max_total,
            )
            self._draw_preview_overlay(
                painter,
                category,
                x,
                bar_width,
                baseline_y,
                usable_rect.height(),
                max_total,
                total_value,
                current_bottom,
            )
            if total_value == 0:
                self._draw_empty_marker(painter, x, baseline_y, bar_width)
            self._draw_category_label(painter, category, x, bar_width, usable_rect.bottom())

        painter.end()

    def _usable_rect(self, outer_rect):
        usable_rect = outer_rect.adjusted(
            GRAPH_LEFT_LABEL_WIDTH,
            GRAPH_TOP_MARGIN,
            -GRAPH_SIDE_MARGIN,
            -GRAPH_BOTTOM_MARGIN,
        )
        if usable_rect.width() > GRAPH_PLOT_MAX_WIDTH:
            plot_offset = (usable_rect.width() - GRAPH_PLOT_MAX_WIDTH) // 2
            usable_rect = usable_rect.adjusted(plot_offset, 0, -plot_offset, 0)
        return usable_rect

    def _bar_layout(self, usable_rect):
        raw_bar_width = usable_rect.width() // len(CATEGORIES) - GRAPH_MAX_GAP_WIDTH
        bar_width = max(22, min(GRAPH_MAX_BAR_WIDTH, raw_bar_width))
        gap = GRAPH_MIN_GAP_WIDTH if len(CATEGORIES) == 1 else min(
            GRAPH_MAX_GAP_WIDTH,
            max(
                GRAPH_MIN_GAP_WIDTH,
                (usable_rect.width() - bar_width * len(CATEGORIES)) // max(1, len(CATEGORIES) - 1),
            ),
        )
        total_used = bar_width * len(CATEGORIES) + gap * max(0, len(CATEGORIES) - 1)
        start_x = usable_rect.left() + max(0, (usable_rect.width() - total_used) // 2)
        baseline_y = usable_rect.bottom()
        return bar_width, gap, start_x, baseline_y

    def _draw_threshold_line(self, painter: QPainter, usable_rect, baseline_y: int, max_total: int) -> None:
        grid_pen = QPen(QColor("#404050"))
        grid_pen.setStyle(Qt.DashLine)
        painter.setPen(grid_pen)
        threshold_y = baseline_y - int(usable_rect.height() * (self._min_score / max_total))
        painter.drawLine(usable_rect.left(), threshold_y, usable_rect.right(), threshold_y)
        painter.drawText(usable_rect.left(), threshold_y - 4, "balanced")

    def _draw_selected_stack(
        self,
        painter: QPainter,
        category: str,
        x: int,
        bar_width: int,
        baseline_y: int,
        usable_height: int,
        max_total: int,
    ) -> tuple[int, int]:
        class_values = [class_score(class_name)[category] for class_name in self._selected_party]
        class_colors = [color_for_class(class_name) for class_name in self._selected_party]
        total_value = sum(class_values)
        current_bottom = baseline_y

        for value, color in reversed(list(zip(class_values, class_colors))):
            if total_value == 0:
                continue
            slice_height = int(usable_height * (value / max_total))
            slice_rect = (x, current_bottom - slice_height, bar_width, slice_height)
            painter.fillRect(*slice_rect, color)
            painter.setPen(QPen(QColor("#0f0f12")))
            painter.drawRect(*slice_rect)
            current_bottom -= slice_height

        return total_value, current_bottom

    def _draw_preview_overlay(
        self,
        painter: QPainter,
        category: str,
        x: int,
        bar_width: int,
        baseline_y: int,
        usable_height: int,
        max_total: int,
        total_value: int,
        current_bottom: int,
    ) -> None:
        if not self._preview_party or self._preview_party == self._selected_party:
            return

        preview_class_names = self._preview_party[len(self._selected_party):]
        preview_values = [class_score(class_name)[category] for class_name in preview_class_names]
        preview_colors = [color_for_class(class_name) for class_name in preview_class_names]
        preview_total = sum(preview_values)
        preview_bottom = current_bottom
        overlay_pen = QPen(QColor(255, 255, 255, PREVIEW_ALPHA))
        overlay_pen.setWidth(2)
        painter.setPen(overlay_pen)

        for value, color in reversed(list(zip(preview_values, preview_colors))):
            if preview_total == 0:
                continue
            slice_height = int(usable_height * (value / max_total))
            slice_rect = (x, preview_bottom - slice_height, bar_width, slice_height)
            preview_brush = QBrush(QColor(color.red(), color.green(), color.blue(), PREVIEW_ALPHA))
            painter.fillRect(*slice_rect, preview_brush)
            painter.drawRect(*slice_rect)
            preview_bottom -= slice_height

        if preview_total:
            total_preview_height = int(usable_height * ((total_value + preview_total) / max_total))
            painter.setPen(QPen(QColor(255, 255, 255, PREVIEW_ALPHA)))
            painter.drawRect(x - 1, baseline_y - total_preview_height, bar_width + 2, total_preview_height)

    def _draw_empty_marker(self, painter: QPainter, x: int, baseline_y: int, bar_width: int) -> None:
        painter.setPen(QPen(QColor("#7b7b88")))
        painter.drawRect(x, baseline_y - 2, bar_width, 2)

    def _draw_category_label(self, painter: QPainter, category: str, x: int, bar_width: int, label_y: int) -> None:
        painter.setPen(QPen(QColor("#ddd")))
        painter.drawText(x, label_y + 18, bar_width, 16, Qt.AlignHCenter, category)
