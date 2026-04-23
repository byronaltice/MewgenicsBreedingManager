"""Class list widgets for the Party Builder UI."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QWidget

from .constants import CLASS_BAR_MAX_WIDTH, CLASS_COUNT_BADGE_SIZE, CLASS_ROW_MIN_HEIGHT
from .styles import class_count_badge_stylesheet, class_label_stylesheet, class_row_frame_stylesheet


class ClassListWidget(QListWidget):
    classHovered = Signal(str)
    hoverCleared = Signal()
    classClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.NoSelection)
        self.setMouseTracking(True)
        self.setSpacing(6)
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)
        self._hovered_class_name: str | None = None

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.viewport():
            if event.type() == QEvent.MouseMove:
                self._update_hovered_class_name(self.itemAt(event.pos()))
            elif event.type() == QEvent.MouseButtonPress:
                self._emit_pressed_class_name(self.itemAt(event.pos()))
            elif event.type() == QEvent.Leave:
                self._update_hovered_class_name(None)
        return super().eventFilter(watched, event)

    def leaveEvent(self, event):  # noqa: N802
        self._update_hovered_class_name(None)
        super().leaveEvent(event)

    def _update_hovered_class_name(self, hovered_item: QListWidgetItem | None) -> None:
        hovered_class_name = hovered_item.data(Qt.UserRole) if hovered_item else None
        if hovered_class_name == self._hovered_class_name:
            return
        self._hovered_class_name = hovered_class_name
        if hovered_class_name:
            self.classHovered.emit(hovered_class_name)
        else:
            self.hoverCleared.emit()

    def _emit_pressed_class_name(self, pressed_item: QListWidgetItem | None) -> None:
        class_name = pressed_item.data(Qt.UserRole) if pressed_item else None
        if class_name:
            self.classClicked.emit(class_name)


class ClassRowWidget(QWidget):
    def __init__(self, class_name: str, parent=None):
        super().__init__(parent)
        self._class_name = class_name
        self._label = QLabel(class_name)
        self._count_badge = QLabel("")
        self._bar_frame = QFrame()
        self._build_ui()

    def _build_ui(self) -> None:
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._bar_frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._count_badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch(1)

        self._bar_frame.setMaximumWidth(CLASS_BAR_MAX_WIDTH)
        self._bar_frame.setMinimumWidth(CLASS_BAR_MAX_WIDTH)
        self._bar_frame.setMinimumHeight(CLASS_ROW_MIN_HEIGHT)
        self._bar_frame.setStyleSheet(class_row_frame_stylesheet(self._class_name))

        bar_layout = QHBoxLayout(self._bar_frame)
        bar_layout.setContentsMargins(12, 4, 12, 4)
        bar_layout.addWidget(self._label)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(class_label_stylesheet(self._class_name))

        layout.addWidget(self._bar_frame)

        self._count_badge.setFixedSize(CLASS_COUNT_BADGE_SIZE, CLASS_COUNT_BADGE_SIZE)
        self._count_badge.setAlignment(Qt.AlignCenter)
        self._count_badge.setStyleSheet(class_count_badge_stylesheet())
        layout.addWidget(self._count_badge)
        layout.addStretch(1)

        self.set_selected_count(0)

    def set_selected_count(self, selected_count: int) -> None:
        self._count_badge.setText(str(selected_count) if selected_count > 0 else "")
        self._count_badge.setVisible(selected_count > 0)


def class_row_size_hint() -> QSize:
    probe_widget = QWidget()
    probe_layout = QHBoxLayout(probe_widget)
    probe_layout.setContentsMargins(0, 0, 0, 0)
    probe_layout.addStretch(1)
    probe_frame = QFrame()
    probe_frame.setMaximumWidth(CLASS_BAR_MAX_WIDTH)
    probe_frame.setMinimumWidth(CLASS_BAR_MAX_WIDTH)
    probe_frame.setMinimumHeight(CLASS_ROW_MIN_HEIGHT)
    probe_layout.addWidget(probe_frame)
    probe_layout.addStretch(1)
    return probe_widget.sizeHint()
