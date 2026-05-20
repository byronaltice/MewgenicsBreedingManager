"""Breed Priority — delegate for the Name column.

Renders the cat's plain name plus its in-game symbol icon (if any) to
the right of the text, vertically centred in the row, with a small gap.

The icon pixmap is retrieved from ``symbols.symbol_pixmap()`` which
lazy-loads and caches each PNG.  If no icon is available the delegate
falls back to standard text rendering.
"""

from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QPainter

from .columns import _NAME_TAG_ROLE
from .theme import _SYMBOL_ICON_PX
from .symbols import symbol_pixmap

# Pixel gap between the end of the name text and the left edge of the icon.
_ICON_GAP_PX = 4


class NameWithSymbolDelegate(QStyledItemDelegate):
    """Paints the cat name then an in-game symbol icon to its right.

    Intended for installation on COL_NAME of the score table only.
    """

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        # Let Qt draw the selection / hover background via the base implementation.
        super().paint(painter, option, index)

        name_tag: str = index.data(_NAME_TAG_ROLE) or ""
        px = symbol_pixmap(name_tag) if name_tag else None

        text: str = index.data(Qt.DisplayRole) or ""
        if not text:
            return

        painter.save()

        # Honour the selection foreground color when selected.
        palette = option.palette
        if option.state & QStyle.State_Selected:
            fg = palette.highlightedText().color()
        else:
            fg = palette.text().color()

        painter.setPen(fg)

        # Text area — full rect with standard margin.
        rect: QRect = option.rect.adjusted(4, 0, -4, 0)

        if px is None:
            # No icon — draw text normally.
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        else:
            # Reserve space for the icon on the right.
            icon_size = min(_SYMBOL_ICON_PX, rect.height() - 2)
            icon_total_w = icon_size + _ICON_GAP_PX

            text_rect = rect.adjusted(0, 0, -icon_total_w, 0)
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, text)

            # Position icon immediately after the actual text (not after the column edge).
            fm = option.fontMetrics
            text_w = fm.horizontalAdvance(text)
            icon_x = rect.left() + text_w + _ICON_GAP_PX
            icon_y = rect.top() + (rect.height() - icon_size) // 2

            # Only draw if there is room.
            if icon_x + icon_size <= rect.right():
                icon_rect = QRect(icon_x, icon_y, icon_size, icon_size)
                scaled = px.scaled(
                    icon_size, icon_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                painter.drawPixmap(icon_rect.topLeft(), scaled)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        base = super().sizeHint(option, index)
        name_tag: str = index.data(_NAME_TAG_ROLE) or ""
        if name_tag and symbol_pixmap(name_tag) is not None:
            return QSize(base.width() + _SYMBOL_ICON_PX + _ICON_GAP_PX, base.height())
        return base
