"""Color and stylesheet helpers for the Party Builder UI."""

from __future__ import annotations

from PySide6.QtGui import QColor

from .constants import (
    CLASS_COLORS,
    CLASS_COUNT_BADGE_COLOR,
    RECOMMENDATION_BAR_BORDER_COLOR,
    RECOMMENDATION_BAR_COLOR,
    RECOMMENDATION_BAR_LOW_COLOR,
    RECOMMENDATION_BAR_MID_COLOR,
    RECOMMENDATION_BAR_RADIUS,
    RECOMMENDATION_TEXT_COLOR,
    SCORE_TO_LETTER,
)


def color_for_class(class_name: str) -> QColor:
    return QColor(CLASS_COLORS.get(class_name, "#888888"))


def text_color_for(qcolor: QColor) -> str:
    return "#000" if qcolor.lightness() > 170 else "#f5f5f5"


def score_label(score: int) -> str:
    return SCORE_TO_LETTER.get(score, str(score))


def surface_style_for_class(class_name: str, *, border_color: str | None = None) -> tuple[str, str]:
    if class_name == "Jester":
        outline = border_color or "#d26bff"
        return (
            "qlineargradient("
            "x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #bf5a66, "
            "stop:0.18 #bf9651, "
            "stop:0.36 #bfb76e, "
            "stop:0.54 #5da06a, "
            "stop:0.72 #5d94bf, "
            "stop:0.9 #6f63bf, "
            "stop:1 #9a63bf"
            ")",
            outline,
        )
    class_color = color_for_class(class_name)
    return class_color.name(), border_color or class_color.darker(140).name()


def recommendation_row_background(class_name: str) -> tuple[str, str]:
    if class_name == "Jester":
        return surface_style_for_class(class_name)

    class_color = color_for_class(class_name)
    base_color = QColor("#5a5a50") if class_name == "Cleric" else QColor(class_color)
    left_color = QColor(base_color).darker(180)
    mid_color = QColor(base_color).darker(115)
    gradient_style = (
        "qlineargradient("
        "x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {left_color.name()}, "
        f"stop:0.45 {mid_color.name()}, "
        f"stop:1 {base_color.name()}"
        ")"
    )
    return gradient_style, class_color.name()


def _interpolate_color(start_color: QColor, end_color: QColor, ratio: float) -> QColor:
    clamped_ratio = max(0.0, min(1.0, ratio))
    red = round(start_color.red() + (end_color.red() - start_color.red()) * clamped_ratio)
    green = round(start_color.green() + (end_color.green() - start_color.green()) * clamped_ratio)
    blue = round(start_color.blue() + (end_color.blue() - start_color.blue()) * clamped_ratio)
    return QColor(red, green, blue)


def recommendation_bar_color(total: int, min_total: int, max_total: int) -> QColor:
    high_color = QColor(RECOMMENDATION_BAR_COLOR)
    mid_color = QColor(RECOMMENDATION_BAR_MID_COLOR)
    low_color = QColor(RECOMMENDATION_BAR_LOW_COLOR)
    if max_total <= min_total:
        return high_color
    relative_ratio = (max_total - total) / (max_total - min_total)
    if relative_ratio <= 0.5:
        return _interpolate_color(high_color, mid_color, relative_ratio / 0.5)
    return _interpolate_color(mid_color, low_color, (relative_ratio - 0.5) / 0.5)


def class_count_badge_stylesheet() -> str:
    return (
        "QLabel {"
        f"background-color: {CLASS_COUNT_BADGE_COLOR};"
        "color: #041414;"
        "border-radius: 4px;"
        "font-weight: 700;"
        "}"
    )


def class_label_stylesheet(class_name: str) -> str:
    return f"color:{text_color_for(color_for_class(class_name))}; font-weight:600;"


def class_row_frame_stylesheet(class_name: str) -> str:
    frame_color, border_color = surface_style_for_class(class_name)
    return (
        "QFrame {"
        f"background-color: {frame_color};"
        f"border: 1px solid {border_color};"
        "border-radius: 6px;"
        "}"
    )


def filled_party_slot_stylesheet(class_name: str) -> str:
    class_color = color_for_class(class_name)
    frame_color, border_color = surface_style_for_class(class_name, border_color="rgba(0, 0, 0, 0.45)")
    return (
        "QPushButton {"
        f"background-color: {frame_color};"
        f"color: {text_color_for(class_color)};"
        f"border: 1px solid {border_color};"
        "border-radius: 8px;"
        "font-weight: 600;"
        "padding: 10px;"
        "}"
        "QPushButton:hover {"
        "border: 2px solid rgba(255, 255, 255, 0.35);"
        "}"
    )


def empty_party_slot_stylesheet() -> str:
    return (
        "QPushButton {"
        "background-color: transparent;"
        "color: #7e7e88;"
        "border: 2px dashed #5c5c6c;"
        "border-radius: 8px;"
        "}"
        "QPushButton:hover {"
        "border-color: #7a7a8a;"
        "}"
    )


def recommendation_rating_text_stylesheet(is_active: bool) -> str:
    text_color = RECOMMENDATION_TEXT_COLOR if is_active else "rgba(255, 255, 255, 0.45)"
    return f"font-size: 12px; font-weight: 700; color: {text_color};"


def recommendation_divider_stylesheet(is_active: bool) -> str:
    return recommendation_rating_text_stylesheet(is_active).replace("font-weight: 700;", "font-weight: 600;")


def recommendation_row_stylesheet(background_style: str, border_color: str, bar_fill_color: QColor) -> str:
    return (
        "QFrame#recommendationRow {"
        f"background-color: {background_style};"
        f"border: 1px solid {border_color};"
        "border-radius: 8px;"
        "}"
        "QFrame#recommendationBarTrack {"
        "background-color: rgba(255, 255, 255, 0.10);"
        f"border-radius: {RECOMMENDATION_BAR_RADIUS}px;"
        "}"
        "QFrame#recommendationBarFill {"
        f"background-color: {bar_fill_color.name()};"
        f"border: 1px solid {RECOMMENDATION_BAR_BORDER_COLOR};"
        f"border-radius: {RECOMMENDATION_BAR_RADIUS}px;"
        "}"
        "QFrame#ratingPanel {"
        "background-color: rgba(0, 0, 0, 0.32);"
        "border: 1px solid rgba(255, 255, 255, 0.16);"
        "border-radius: 4px;"
        "}"
    )
