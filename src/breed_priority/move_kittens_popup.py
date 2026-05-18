"""Move Kittens popup — lets the user bulk-assign all kittens to one room.

Opens from the Breed Priority toolbar. Displays a room dropdown and a live
preview of how many kittens will move vs. how many are already in the target
room. On accept, exposes `.selected_room_key` for the caller to dispatch.
"""

from __future__ import annotations

from save_parser import ROOM_KEYS, ROOM_DISPLAY

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
)
from PySide6.QtCore import Qt

from .theme import CLR_SURFACE_APP_MAIN, CLR_TEXT_CONTENT_SECONDARY
from .constants import (
    _MOVE_KITTENS_TITLE,
    _MOVE_KITTENS_PROMPT,
    _MOVE_KITTENS_PREVIEW_FMT,
    _MOVE_KITTENS_CONFIRM,
)

# Sentinel value used as the first (placeholder) combo entry.
_NO_SELECTION_INDEX = 0
_PLACEHOLDER_LABEL  = "— select a room —"

_POPUP_STYLESHEET = (
    f"QDialog {{ background:{CLR_SURFACE_APP_MAIN}; }}"
    f"QLabel  {{ color:{CLR_TEXT_CONTENT_SECONDARY}; font-size:12px;"
    f"           background:transparent; border:none; }}"
    "QComboBox { background:#14142e; color:#8899bb; border:1px solid #2a2a55;"
    "  border-radius:4px; padding:3px 8px; font-size:12px; }"
    "QComboBox::drop-down { border:none; }"
    "QComboBox QAbstractItemView { background:#14142e; color:#aabbcc;"
    "  selection-background-color:#1c1c3a; }"
    "QPushButton { background:#14142e; color:#8899bb; border:1px solid #2a2a55;"
    "  border-radius:4px; padding:5px 18px; font-size:12px; }"
    "QPushButton:hover { background:#1c1c3a; color:#ccd; border-color:#4444aa; }"
    "QPushButton#confirm { background:#0e2030; color:#88aadd; border-color:#2244aa; }"
    "QPushButton#confirm:hover { background:#122840; color:#aaccff; border-color:#3366cc; }"
    "QPushButton#confirm:disabled { background:#0a1520; color:#445566; border-color:#1a2a44; }"
)


class MoveKittensPopup(QDialog):
    """Small dark-themed dialog: pick a room, preview kitten move counts, confirm.

    Attributes:
        selected_room_key: Set on accept; the chosen room key from ROOM_KEYS.
    """

    def __init__(self, parent, kittens: list, room_keys: tuple, room_display: dict):
        super().__init__(parent)
        self._kittens    = kittens
        self._room_keys  = room_keys
        self._room_display = room_display

        self.selected_room_key: str | None = None

        self.setWindowTitle(_MOVE_KITTENS_TITLE)
        self.setModal(True)
        self.setStyleSheet(_POPUP_STYLESHEET)

        self._build_ui()
        self._refresh_preview()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        vb = QVBoxLayout(self)
        vb.setContentsMargins(24, 20, 24, 16)
        vb.setSpacing(12)

        prompt = QLabel(_MOVE_KITTENS_PROMPT)
        prompt.setWordWrap(True)
        vb.addWidget(prompt)

        self._combo = QComboBox()
        self._combo.addItem(_PLACEHOLDER_LABEL, userData=None)
        for key in self._room_keys:
            self._combo.addItem(self._room_display[key], userData=key)
        self._combo.currentIndexChanged.connect(self._refresh_preview)
        vb.addWidget(self._combo)

        self._preview_label = QLabel("")
        self._preview_label.setWordWrap(True)
        vb.addWidget(self._preview_label)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self._confirm_btn = QPushButton(_MOVE_KITTENS_CONFIRM)
        self._confirm_btn.setObjectName("confirm")
        self._confirm_btn.setDefault(True)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._on_confirm)
        btns.addWidget(cancel_btn)
        btns.addSpacing(8)
        btns.addWidget(self._confirm_btn)
        vb.addLayout(btns)

        self.setMinimumWidth(360)

    # ── Event handlers ────────────────────────────────────────────────────────

    def _refresh_preview(self) -> None:
        """Update the preview label and Confirm button state based on current selection."""
        room_key = self._combo.currentData()
        if room_key is None:
            self._preview_label.setText("")
            self._confirm_btn.setEnabled(False)
            return

        already_count = sum(
            1 for c in self._kittens
            if getattr(c, "room", None) == room_key
        )
        moves_count = len(self._kittens) - already_count

        self._preview_label.setText(
            _MOVE_KITTENS_PREVIEW_FMT.format(moves=moves_count, already=already_count)
        )
        self._confirm_btn.setEnabled(moves_count > 0)

    def _on_confirm(self) -> None:
        self.selected_room_key = self._combo.currentData()
        self.accept()
