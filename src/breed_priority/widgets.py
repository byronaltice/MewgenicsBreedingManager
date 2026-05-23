"""Breed Priority — shared reusable UI widgets.

Widgets in this module are used across multiple breed_priority sub-modules
and are kept here to avoid circular imports.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

from .theme import (
    CLR_DESIRABLE, CLR_UNDESIRABLE,
    CLR_TEXT_CONTENT_UNSCORED, CLR_TEXT_CONTENT_SECONDARY,
    CLR_SURFACE_APP_ALT, CLR_SURFACE_SEPARATOR,
)


class _WeightSpin(QWidget):
    """Compact value editor with visible ▲/▼ buttons."""
    valueChanged = Signal(float)

    _BTN_STYLE = (
        "QPushButton { color:#ccc; background:#3a3a60; border:1px solid #4a4a80;"
        " font-size:8px; padding:0; }"
        "QPushButton:hover { background:#5050a0; }"
        "QPushButton:pressed { background:#6060c0; }"
    )
    _LBL_BASE = (
        f"background:{CLR_SURFACE_APP_ALT};"
        f" border:1px solid {CLR_SURFACE_SEPARATOR}; border-right:none;"
    )

    def __init__(self, value: float, min_val=-50.0, max_val=50.0, step=0.5):
        super().__init__()
        self._value = float(value)
        self._min   = min_val
        self._max   = max_val
        self._step  = step

        hb = QHBoxLayout(self)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(2)

        self._lbl = QLabel(self._fmt(self._value))
        self._lbl.setFixedWidth(36)
        self._lbl.setAlignment(Qt.AlignCenter)
        _f = self._lbl.font()
        _f.setPointSize(8)
        self._lbl.setFont(_f)
        self._update_color()

        btn_col_1 = QWidget()
        bv1 = QVBoxLayout(btn_col_1)
        bv1.setContentsMargins(0, 0, 0, 0)
        bv1.setSpacing(0)

        up = QPushButton("▲")
        up.setFixedSize(18, 11)
        up.setStyleSheet(self._BTN_STYLE)
        up.clicked.connect(self._inc)

        dn = QPushButton("▼")
        dn.setFixedSize(18, 11)
        dn.setStyleSheet(self._BTN_STYLE)
        dn.clicked.connect(self._dec)

        up5 = QPushButton("▲")
        up5.setFixedSize(18, 11)
        up5.setStyleSheet(self._BTN_STYLE)
        up5.clicked.connect(self._inc5)

        dn5 = QPushButton("▼")
        dn5.setFixedSize(18, 11)
        dn5.setStyleSheet(self._BTN_STYLE)
        dn5.clicked.connect(self._dec5)
        bv1.addWidget(up)
        bv1.addWidget(dn)
        btn_col_5 = QWidget()
        bv5 = QVBoxLayout(btn_col_5)
        bv5.setContentsMargins(0, 0, 0, 0)
        bv5.setSpacing(0)
        bv5.addWidget(up5)
        bv5.addWidget(dn5)
        hb.addWidget(btn_col_1)
        hb.addWidget(self._lbl)
        hb.addSpacing(2)
        hb.addWidget(btn_col_5)

    @staticmethod
    def _fmt(v: float) -> str:
        return f"{v:+.1f}"

    def _update_color(self):
        if self._value > 0:
            clr = CLR_DESIRABLE
        elif self._value < 0:
            clr = CLR_UNDESIRABLE
        else:
            clr = CLR_TEXT_CONTENT_UNSCORED
        self._lbl.setStyleSheet(f"color:{clr}; {self._LBL_BASE}")

    def _set(self, val: float):
        val = round(max(self._min, min(self._max, val)) / self._step) * self._step
        if val != self._value:
            self._value = val
            self._lbl.setText(self._fmt(val))
            self._update_color()
            if not self.signalsBlocked():
                self.valueChanged.emit(val)

    def _inc(self): self._set(self._value + self._step)
    def _dec(self): self._set(self._value - self._step)
    def _inc5(self): self._set(self._value + 5.0)
    def _dec5(self): self._set(self._value - 5.0)

    def value(self) -> float:
        return self._value

    def setValue(self, val: float):
        self._value = float(val)
        self._lbl.setText(self._fmt(self._value))
        self._update_color()


class _IntParamSpin(_WeightSpin):
    """Integer-only variant of _WeightSpin — shows plain integers, no +/- sign.

    Used for parameters like stat_7_threshold that are natural counts (1–20).
    """

    def _update_color(self):
        self._lbl.setStyleSheet(f"color:{CLR_TEXT_CONTENT_SECONDARY}; {self._LBL_BASE}")

    def __init__(self, value: int, min_val=1, max_val=20, step=1):
        super().__init__(float(value), float(min_val), float(max_val), float(step))
        self._lbl.setText(self._fmt(self._value))

    @staticmethod
    def _fmt(v: float) -> str:
        return str(int(round(v)))

    def _set(self, val: float):
        val = float(max(self._min, min(self._max, round(val))))
        if val != self._value:
            self._value = val
            self._lbl.setText(self._fmt(val))
            if not self.signalsBlocked():
                self.valueChanged.emit(val)

    def setValue(self, val: float):
        self._value = float(round(val))
        self._lbl.setText(self._fmt(self._value))
