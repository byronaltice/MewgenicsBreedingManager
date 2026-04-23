"""Current-party slot grid widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QPushButton, QVBoxLayout, QWidget

from .constants import MAX_PARTY_SIZE, PARTY_SLOT_SIZE
from .styles import empty_party_slot_stylesheet, filled_party_slot_stylesheet


class PartySlotsWidget(QWidget):
    slotClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._slot_buttons: list[QPushButton] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(12)
        grid_layout.setVerticalSpacing(12)
        layout.addLayout(grid_layout)

        for index in range(MAX_PARTY_SIZE):
            slot_button = QPushButton("")
            slot_button.setFixedSize(PARTY_SLOT_SIZE, PARTY_SLOT_SIZE)
            slot_button.setCursor(Qt.PointingHandCursor)
            slot_button.setProperty("slot_index", index)
            slot_button.clicked.connect(self._on_slot_clicked)
            self._slot_buttons.append(slot_button)
            grid_layout.addWidget(slot_button, index // 2, index % 2)

        self.set_party([])

    def _on_slot_clicked(self) -> None:
        slot_button = self.sender()
        if not isinstance(slot_button, QPushButton):
            return
        slot_index = slot_button.property("slot_index")
        class_name = slot_button.property("class_name")
        if class_name is not None and slot_index is not None:
            self.slotClicked.emit(int(slot_index))

    def set_party(self, party: list[str]) -> None:
        for index, slot_button in enumerate(self._slot_buttons):
            class_name = party[index] if index < len(party) else None
            slot_button.setProperty("class_name", class_name)
            if class_name:
                slot_button.setText(class_name)
                slot_button.setStyleSheet(filled_party_slot_stylesheet(class_name))
            else:
                slot_button.setText("")
                slot_button.setStyleSheet(empty_party_slot_stylesheet())
