"""Breed Priority — Qt stylesheet strings.

All pre-built stylesheet strings for buttons, tables, combos, and splitters.
Imports theme colors so styles update consistently with theme changes.
"""

from .theme import (
    CLR_TEXT_PRIMARY, CLR_TEXT_SECONDARY, CLR_TEXT_UI_LABEL,
    CLR_BG_MAIN, CLR_BG_ALT, CLR_BG_HEADER, CLR_BG_HEADER_BDR,
    CLR_SURFACE_SEPARATOR, CLR_SURFACE_NEUTRAL,
    CLR_INTERACTIVE, CLR_INTERACTIVE_BG, CLR_INTERACTIVE_BDR, CLR_INTERACTIVE_HOV,
    _SEL_FG, _SEL_BG, _SEL_BORDER,
    _DIM_FG, _DIM_BG, _DIM_HOVER_FG, _DIM_HOVER_BG, _DIM_LABEL_FG,
    ColorUtils,
)


# ── Splitter handle styles ────────────────────────────────────────────────────

SPLITTER_V_STYLE = (
    "QSplitter::handle:vertical {"
    " min-height:6px;"
    " background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
    " stop:0 #131326, stop:0.25 #1a1a36, stop:0.45 #2e2e58,"
    " stop:0.5 #3c3c70, stop:0.55 #2e2e58, stop:0.75 #1a1a36, stop:1 #131326);"
    " }"
    "QSplitter::handle:vertical:hover {"
    " background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
    " stop:0 #16162e, stop:0.25 #22224a, stop:0.45 #44449a,"
    " stop:0.5 #5555c0, stop:0.55 #44449a, stop:0.75 #22224a, stop:1 #16162e);"
    " }"
)
SPLITTER_H_STYLE = (
    "QSplitter::handle:horizontal {"
    " min-width:6px;"
    " background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
    " stop:0 #131326, stop:0.25 #1a1a36, stop:0.45 #2e2e58,"
    " stop:0.5 #3c3c70, stop:0.55 #2e2e58, stop:0.75 #1a1a36, stop:1 #131326);"
    " }"
    "QSplitter::handle:horizontal:hover {"
    " background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
    " stop:0 #16162e, stop:0.25 #22224a, stop:0.45 #44449a,"
    " stop:0.5 #5555c0, stop:0.55 #44449a, stop:0.75 #22224a, stop:1 #16162e);"
    " }"
)

# ── Segmented button style ────────────────────────────────────────────────────

_SEG_BTN_STYLE = """
    QPushButton {{
        color: {fg_dim}; background: {bg_dim}; border: 1px solid #333;
        padding: 1px 7px; font-size: 10px; border-radius: 0px;
    }}
    QPushButton:checked {{
        color: {sel_fg}; background: {sel_bg}; border-color: {sel_border};
    }}
    QPushButton:hover:!checked {{ color: {hover_fg}; background: {hover_bg}; }}
""".format(fg_dim=_DIM_FG, bg_dim=_DIM_BG,
           sel_fg=_SEL_FG, sel_bg=_SEL_BG, sel_border=_SEL_BORDER,
           hover_fg=_DIM_HOVER_FG, hover_bg=_DIM_HOVER_BG)

# ── Group label style ─────────────────────────────────────────────────────────

from .theme import CLR_TEXT_GROUP
_GROUP_LABEL_STYLE = (
    f"color:{CLR_TEXT_GROUP}; font-size:10px; font-weight:bold; letter-spacing:1px;"
)

# ── Interactive button styles ─────────────────────────────────────────────────

_INTERACTIVE_BTN_ACTIVE = (
    f"QPushButton {{ background:{CLR_INTERACTIVE_BG}; color:{CLR_INTERACTIVE};"
    f" border:1px solid {CLR_INTERACTIVE};"
    " border-radius:4px; padding:3px 4px; font-size:10px; font-weight:bold; }"
    f"QPushButton:hover {{ background:{CLR_INTERACTIVE_BDR}; color:{CLR_INTERACTIVE_HOV}; }}"
)
_INTERACTIVE_BTN_ON = (
    f"QPushButton {{ background:{CLR_INTERACTIVE_BG}; color:{CLR_INTERACTIVE};"
    f" border:1px solid {CLR_INTERACTIVE_BDR};"
    " border-radius:4px; padding:3px 4px; font-size:10px; font-weight:bold; }"
    f"QPushButton:hover {{ background:{CLR_INTERACTIVE_BDR}; color:{CLR_INTERACTIVE_HOV}; }}"
)
_INTERACTIVE_BTN_ON_SM = (
    f"QPushButton {{ background:{CLR_INTERACTIVE_BG}; color:{CLR_INTERACTIVE};"
    f" border:1px solid {CLR_INTERACTIVE_BDR};"
    " border-radius:2px; padding:0 2px; font-size:9px; font-weight:bold; }"
    f"QPushButton:hover {{ background:{CLR_INTERACTIVE_BDR}; }}"
)
_INTERACTIVE_BTN_LG = (
    f"QPushButton {{ color:#fff; background:{CLR_INTERACTIVE_BG};"
    f" border:1px solid {CLR_INTERACTIVE};"
    " border-radius:4px; padding:4px 14px; font-size:11px; }"
    f"QPushButton:hover {{ background:{CLR_INTERACTIVE_BDR}; }}"
)
_DIM_BTN = (
    "QPushButton { background:#1a1a32; color:#aaa; border:1px solid #2a2a4a;"
    " border-radius:4px; padding:3px 4px; font-size:10px; }"
    f"QPushButton:hover {{ background:{CLR_SURFACE_SEPARATOR}; color:{CLR_TEXT_PRIMARY}; }}"
)
_DIM_BTN_LG = (
    f"QPushButton {{ color:{CLR_TEXT_SECONDARY}; background:#1a1a32; border:1px solid #2a2a4a;"
    " border-radius:4px; padding:4px 14px; font-size:11px; }"
    f"QPushButton:hover {{ background:{CLR_SURFACE_SEPARATOR}; color:{CLR_TEXT_PRIMARY}; }}"
)
_TOGGLE_OFF_BTN = (
    "QPushButton { background:#1a1a2e; color:#555566; border:1px solid #2a2a44;"
    " border-radius:4px; padding:3px 4px; font-size:10px; }"
    f"QPushButton:hover {{ background:#222238; color:{ColorUtils.blend('#555566', CLR_INTERACTIVE, 0.35)}; }}"
)
_TOGGLE_OFF_BTN_SM = (
    "QPushButton { background:#1a1a2e; color:#555566; border:1px solid #2a2a44;"
    " border-radius:2px; padding:0 2px; font-size:9px; }"
    f"QPushButton:hover {{ background:#222238; color:{ColorUtils.blend('#555566', CLR_INTERACTIVE, 0.35)}; }}"
)

# ── Table and combo styles ────────────────────────────────────────────────────

_PRIORITY_TABLE_STYLE = f"""
    QTableWidget {{
        background:{CLR_BG_MAIN}; alternate-background-color:{CLR_BG_ALT};
        color:{CLR_TEXT_PRIMARY}; border:none; font-size:12px;
    }}
    QTableWidget::item {{
        padding:3px 4px;
        border-right:1px solid {CLR_BG_HEADER};
    }}
    QTableWidget::item:selected {{ background:#1e3060; color:#fff; }}
    QHeaderView::section {{
        background:{CLR_BG_HEADER}; color:{CLR_TEXT_UI_LABEL}; padding:5px 4px;
        border:none; border-bottom:1px solid {CLR_BG_HEADER_BDR};
        border-right:1px solid {CLR_BG_HEADER};
        font-size:11px; font-weight:bold;
    }}
    QScrollBar:vertical {{ background:{CLR_BG_MAIN}; width:10px; }}
    QScrollBar::handle:vertical {{
        background:{CLR_SURFACE_SEPARATOR}; border-radius:5px; min-height:20px;
    }}
"""

_PRIORITY_COMBO_STYLE = (
    f"QComboBox {{ background:{CLR_BG_ALT}; color:{CLR_TEXT_SECONDARY}; border:1px solid {CLR_SURFACE_SEPARATOR};"
    " padding:1px 4px; font-size:11px; }"
    "QComboBox:hover { border-color:#3a3a7a; }"
    "QComboBox::drop-down { border:none; }"
    f"QComboBox QAbstractItemView {{ background:{CLR_BG_ALT}; color:{CLR_TEXT_SECONDARY};"
    f" selection-background-color:#1e3060; border:1px solid {CLR_SURFACE_SEPARATOR}; }}"
)
