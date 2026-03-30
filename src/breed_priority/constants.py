"""Breed Priority view — shared constants, styles, and column layout.

Standalone module — no imports from mewgenics_manager to avoid circular deps.
Functions and widgets live in breed_priority_helpers.py.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .color_utils import ColorUtils
from .helpers import (  # noqa: F401 — re-exported for consumers
    _room_style,
    _rarity_chip_colors, _sevens_color, _rank_colors,
    _paired_weight_colors, _sex_indicator_to_chip, _score_to_chip,
    _cat_injuries, _fit_chips, _paint_heatmap_bar,
    _LEFT_PANEL_W, _CollapseHandle, _CollapseSplitter,
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


# ── Personality trait thresholds ─────────────────────────────────────────────
# Aggression/libido are stored as 0-1 floats; the game displays them as three
# levels.  These boundaries match in-game behaviour (verified against save data).

TRAIT_LOW_THRESHOLD  = 0.3   # < this  → "low"
TRAIT_HIGH_THRESHOLD = 0.7   # >= this → "high"

# ── Scoring constants ─────────────────────────────────────────────────────────

BREED_PRIORITY_WEIGHTS = {
    "stat_7":           5.0,
    "stat_7_threshold": 7.0,   # cats with 7 in a stat before score scales down
    "stat_7_count":     2.0,   # flat bonus per stat the cat personally has at 7 (additive)
    "unique_ma_max":    2.0,
    "low_aggression":  1.0,
    "unknown_gender":  1.0,
    "high_libido":     0.5,
    "high_aggression": -1.0,
    "low_libido":      -0.5,
    "gay_pref":        0.0,   # score applied to gay cats  (positive = favour, negative = penalise)
    "bi_pref":         0.0,   # score applied to bi cats
    "no_children":     4.0,
    "many_children":   -3.0,
    "stat_sum":        4.0,
    "age_penalty":    -2.0,   # score per year of age above threshold (negative = penalise older cats)
    "age_threshold":  10.0,   # cats at or below this age receive no age penalty
    "love_interest":      1.0,   # flat bonus when a love interest is in scope
    "rivalry":           -2.0,   # flat penalty when a rival is in scope
    "love_interest_room": 0.0,   # flat bonus when a love interest is in same room
    "rivalry_room":       0.0,   # flat penalty when a rival is in same room
    "seven_sub":           0.0,   # max score for cats whose 7-stat set is dominated by others in scope
    "seven_sub_threshold": 1.0,   # 7-sub count at which full score is applied (linear ramp from 0)
}

# (key, short label) - drives the weight editor on the left panel.
# (None, None) entries render as a thin separator line between groups.
# A string label renders left-aligned.
# A tuple label (group, sub) renders with group left-aligned and sub right-aligned,
#   letting two equal-rank options like High/Low appear visually equivalent.
# Labels starting with "  └" are styled as true sub-parameters (dimmed).
# Order mirrors SCORE_COLUMNS left-to-right so the panel is easy to scan.
WEIGHT_UI_ROWS = [
    ("stat_sum",         "Stat Sum"),                   # ── Sum ──
    (None, None),
    ("age_penalty",      "Age penalty"),               # ── Age ──
    ("age_threshold",    "  └ threshold"),
    (None, None),
    ("stat_7",           "7rare"),                     # ── 7-rare / 7-cnt ──
    ("stat_7_threshold", "  └ threshold"),
    ("stat_7_count",     "7-count"),
    (None, None),
    ("seven_sub",          "7-Sub score"),               # ── 7-Sub ──
    ("seven_sub_threshold","  └ threshold"),
    (None, None),
    ("gay_pref",         ("Sex", "Gay")),            # ── Sexual ──
    ("bi_pref",          ("",       "Bi")),
    (None, None),
    ("high_libido",      ("Lib", "High")),           # ── Libido ──
    ("low_libido",       ("",       "Low")),
    (None, None),
    ("unknown_gender",   "Unknown gender"),             # ── Gender? ──
    (None, None),
    ("no_children",      "Genetic Novelty"),            # ── Gene ──
    ("many_children",    "4+ children"),               # ── 4+Ch ──
    (None, None),
    ("high_aggression",  ("Aggro", "High")),            # ── Aggro ──
    ("low_aggression",   ("",      "Low")),
    (None, None),
    ("rivalry",            ("Hate", "In Scope")),        # ── Hate ──
    ("rivalry_room",       ("",     "In Room")),
    (None, None),
    ("love_interest",      ("Love", "In Scope")),        # ── Love ──
    ("love_interest_room", ("",     "In Room")),
    (None, None),
    ("unique_ma_max",    "Trait"),                      # ── Trait ──
]

# Score table columns - some weight keys are merged into one column.
# (column header, list of weight keys whose subtotals are summed for this column)
SCORE_COLUMNS = [
    ("Sum",   ["stat_sum"]),
    ("Age",   ["age_penalty"]),
    ("7rare", ["stat_7"]),
    ("7cnt",  ["stat_7_count"]),
    ("7sub",  ["seven_sub"]),
    ("Sex",   ["gay_pref", "bi_pref"]),
    ("Lib",   ["high_libido", "low_libido"]),
    ("Gender", ["unknown_gender"]),
    ("Gene",  ["no_children"]),
    ("4+Ch",  ["many_children"]),
    ("Aggro", ["low_aggression", "high_aggression"]),
    ("💥🔭",    ["rivalry"]),
    ("💥🏠",    ["rivalry_room"]),
    ("💗🔭",    ["love_interest"]),
    ("💗🏠",    ["love_interest_room"]),
    ("Trait", ["unique_ma_max"]),
]

_NUM_PROFILES = 5   # number of profile slots

# ── Shared "selected" accent style ─────────────────────────────────────────
# Use these constants whenever something is visually "active" or "selected".
_SEL_BG     = "#0a1e18"
_SEL_FG     = "#aaddcc"
_SEL_BORDER = "#1ec8a0"
# Dim (unselected) button/label colours — bright enough to read comfortably
_DIM_FG       = "#ccccdd"
_DIM_BG       = "#1a1a26"
_DIM_HOVER_FG = "#ddddf0"
_DIM_HOVER_BG = "#222230"
_DIM_LABEL_FG = "#ccccdd"   # for labels adjacent to segmented buttons

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

# Column indices for the score table
# Name | Loc | Inj | STR DEX CON INT SPD CHA LCK | │ | Sum ... Trait | │ | Score
_SEP_HEADER      = "│"        # thin divider column header text
COL_NAME          = 0
COL_LOC           = 1
COL_INJ           = 2
_STAT_COL_NAMES   = ["STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK"]
_COL_STAT_START   = 3
_NUM_STAT_COLS    = len(_STAT_COL_NAMES)
_SCORE_COLS       = [h for h, _ in SCORE_COLUMNS]
COL_SEP1          = _COL_STAT_START + _NUM_STAT_COLS          # separator between stats and scored
_COL_SCORE_START  = COL_SEP1 + 1                              # = 11
COL_SEP2          = _COL_SCORE_START + len(SCORE_COLUMNS)     # separator before Score total
COL_SCORE         = COL_SEP2 + 1
_ALL_HEADERS      = (
    ["Name", "Loc", "Inj"]
    + _STAT_COL_NAMES
    + [_SEP_HEADER]
    + _SCORE_COLS
    + [_SEP_HEADER]
    + ["Score"]
)
_SEP_COLS         = frozenset({COL_SEP1, COL_SEP2})   # separator column indices
_SEP_WIDTH        = 2                                   # pixel width for separator columns

# Room display name → text color
_ROOM_STYLE = {
    "1F Left":  "#55bbdd",   # cyan
    "1F Right": "#ddbb55",   # gold
    "2F Left":  "#bb77ee",   # violet
    "2F Right": "#66cc77",   # green
    "Attic":    "#ee7788",   # rose
}

# (threshold, label, color) - first match wins; None threshold = catch-all
BREED_PRIORITY_TIERS = [
    (10,   "Keep",     "#f0c060"),
    ( 4,   "Good",     "#1ec8a0"),
    ( 0,   "Neutral",  "#777777"),
    (-5,   "Consider", "#e08030"),
    (None, "Cull",     "#e04040"),
]

# Index → (display label, stored value or None to remove from dict)
TRAIT_RATING_OPTIONS = [
    ("Top Priority - sole owner +20, shared +10÷n", 2),
    ("Desirable - sole owner +4, shared +2÷n",     1),
    ("Neutral - reviewed, not scored",              0),
    ("Undecided - not yet reviewed",                None),
    ("Undesirable - scored −2",                    -1),
]
TRAIT_RATING_LABELS = [label for label, _ in TRAIT_RATING_OPTIONS]
TRAIT_RATING_VALUES = [val   for _, val  in TRAIT_RATING_OPTIONS]
RATING_SHORT_LABELS = ["Top Priority", "Desirable", "Neutral", "Undecided", "Undesirable"]
# Shared palette: Top Priority, Desirable, Neutral, Undecided, Undesirable
CLR_TOP_PRIORITY = "#40d0c0"
CLR_DESIRABLE  = "#6aaa6a"
CLR_NEUTRAL    = "#b0a040"
CLR_UNDECIDED  = "#888899"
CLR_UNDESIRABLE = "#aa6a6a"

# Sexuality display glyphs — swap these if a platform lacks glyph support.
# No single standard emoji exists for the bi pride flag, so we approximate with
# the three pride colours.
_SEX_EMOJI_GAY = "🏳️‍🌈"    # rainbow pride flag
_SEX_EMOJI_BI  = "BI"        # text label for bisexual
CLR_HIGHLIGHT  = "#eee"       # cat names and shared-cat name lists
RATING_ITEM_COLORS  = [CLR_TOP_PRIORITY, CLR_DESIRABLE, CLR_NEUTRAL, CLR_UNDECIDED, CLR_UNDESIRABLE]

# ── Injury display ────────────────────────────────────────────────────────────
# Maps stat name → confirmed in-game injury name.
# Stats not in this dict fall back to the stat key itself (e.g. "STR").
INJURY_STAT_NAMES = {
    "INT": "Concussion",
    "LCK": "Jinxed",
    "CHA": "Disfigured",
}
# Abbreviated display labels for the narrow Inj column
_INJ_SHORT = {
    "Concussion": "Conc",
    "Jinxed":     "Jinx",
    "Disfigured": "Disfig",
}

# Color constants used for gradient coloring
_CLR_RED    = "#cc3333"
_CLR_YELLOW = "#b0a040"

# ── Color derivation utilities ────────────────────────────────────────────────
# Extend ColorUtils with helpers that drive the define-and-derive (d&d) pattern:
# base semantic colors are defined once; related variants (chip bgs, darker
# borders, hover accents) are computed from those bases via these functions.

_THEME_DARK = "#0c0c20"   # darkest base used as the "toward-black" blend target


# ── Text colors ──────────────────────────────────────────────────────────────
# Canonical text foreground palette for the breed-priority area.
# Primary is the brightest; all others are derived by blending toward _THEME_DARK.

CLR_TEXT_PRIMARY   = "#dddddd"   # cat names, trait names, always-visible data
CLR_TEXT_SECONDARY = ColorUtils.blend(CLR_TEXT_PRIMARY, _THEME_DARK, 0.24)   # ≈ #aaa — checkboxes, controls, input text
CLR_TEXT_UI_LABEL  = ColorUtils.blend(CLR_TEXT_PRIMARY, _THEME_DARK, 0.40)   # ≈ #8c8c8c — row labels (Stat Sum, Age Penalty)
CLR_TEXT_GROUP     = ColorUtils.blend(CLR_TEXT_PRIMARY, _THEME_DARK, 0.65)   # ≈ #555 — section headers (WEIGHTS, SCOPE, TRAIT DESIRABILITY)
CLR_TEXT_SUBLABEL  = CLR_TEXT_GROUP                                 # sub-parameter labels (└ threshold)
CLR_TEXT_COUNT     = ColorUtils.blend(CLR_TEXT_PRIMARY, _THEME_DARK, 0.72)   # ≈ #444 — count annotations, secondary info
CLR_TEXT_GRAYEDOUT = CLR_TEXT_GROUP                                 # unscored values — same tier as group labels
CLR_TEXT_MUTED     = ColorUtils.blend(CLR_TEXT_PRIMARY, _THEME_DARK, 0.80)   # ≈ #333 — very dim, inactive/off labels

# ── Background colors ────────────────────────────────────────────────────────
# Main surface hierarchy for the breed-priority area.  Each level is derived
# from CLR_BG_MAIN by blending toward a cool-purple tint so they share hue.

CLR_BG_MAIN       = "#0d0d1c"   # primary data-area background
CLR_BG_ALT        = "#131326"   # alternate row / secondary surface
CLR_BG_SCORE_AREA = "#0a0a18"   # score-table outer container
CLR_BG_PANEL      = "#14142a"   # left panel, weights area
CLR_BG_HEADER     = "#16213e"   # title bar, column headers
CLR_BG_HEADER_BDR = "#1e1e38"   # header bottom-border / subtle divider
CLR_BG_DEEP       = "#080818"   # deepest inset surfaces (lists, empty slots)

# ── Neutral surface / separator ──────────────────────────────────────────────
# Translucent-black base for non-semantic chip backgrounds, overflow indicators,
# and heatmap text pills.  Other neutral surfaces derive from the same base.

_NEUTRAL_SURFACE      = "rgba(0, 0, 0, 140)"   # translucent black for heatmap text pills
CLR_SURFACE_NEUTRAL   = "#1a1a22"               # opaque neutral chip bg (_CHIP_DIM bg)
CLR_SURFACE_SEPARATOR = "#252545"               # separator lines, spinner borders

# ── Group-label uppercase style helper ────────────────────────────────────────
# Section headers (WEIGHTS, COMPARISON SCOPE, etc.) share identical styling.
# CSS property string — append to a label's setStyleSheet() call.

_GROUP_LABEL_STYLE = (
    f"color:{CLR_TEXT_GROUP}; font-size:10px; font-weight:bold; letter-spacing:1px;"
)

# ── Gender colors ─────────────────────────────────────────────────────────────
# Canonical M / F / ? foreground colors for the breed-priority UI.
# Source: the Comparison Scope legend, which was the most prominent and
# consistent pre-refactor usage site.
# All gender chip (bg, fg) pairs derive their backgrounds via ColorUtils.derive_chip_bg.

CLR_GENDER_MALE    = "#2aaa99"
CLR_GENDER_FEMALE  = "#bb88dd"
CLR_GENDER_UNKNOWN = "#ccaa44"

_CHIP_GENDER_MALE    = (ColorUtils.derive_chip_bg(CLR_GENDER_MALE,    _THEME_DARK), CLR_GENDER_MALE)
_CHIP_GENDER_FEMALE  = (ColorUtils.derive_chip_bg(CLR_GENDER_FEMALE,  _THEME_DARK), CLR_GENDER_FEMALE)
_CHIP_GENDER_UNKNOWN = (ColorUtils.derive_chip_bg(CLR_GENDER_UNKNOWN, _THEME_DARK), CLR_GENDER_UNKNOWN)


# ── Interactive accent ────────────────────────────────────────────────────────
# CLR_INTERACTIVE is the canonical active-state accent for the breed-priority UI.
# It drives selected borders, filter-active badges, and toggle-on indicators.
# BG, border, and hover variants are derived from it so they stay visually
# coherent when the base changes.
#
# _SEL_BORDER is kept as an alias for backward compatibility.

CLR_INTERACTIVE     = _SEL_BORDER                                   # "#1ec8a0"
CLR_INTERACTIVE_BG  = ColorUtils.blend(_THEME_DARK, CLR_INTERACTIVE, 0.22)   # dark active bg
CLR_INTERACTIVE_BDR = ColorUtils.blend(_THEME_DARK, CLR_INTERACTIVE, 0.34)   # muted active border
CLR_INTERACTIVE_HOV = ColorUtils.blend(CLR_INTERACTIVE, "#8ff8e0", 0.30)     # bright hover accent


# ── Positive / negative value colors ─────────────────────────────────────────
# Canonical colors for numeric value indicators: score subscripts, weight
# breakdown highlights, age gradient endpoints, and total-score displays.
#
# CLR_VALUE_POS aliases CLR_INTERACTIVE: the teal-green accent doubles as the
# "positive / good" signal, keeping the two semantics visually unified.
# CLR_VALUE_NEG and CLR_VALUE_NEG_BG follow the same d&d pattern.
# CLR_VALUE_NEUTRAL covers zero-score and unknown-value displays.
#
# _CLR_AGE_OLD names the age-over-threshold gradient endpoint so it stays
# consistent with _CLR_RED across the codebase.

CLR_VALUE_POS     = CLR_INTERACTIVE
CLR_VALUE_POS_BG  = CLR_INTERACTIVE_BG
CLR_VALUE_NEG     = "#e04040"
CLR_VALUE_NEG_BG  = ColorUtils.blend(_THEME_DARK, CLR_VALUE_NEG, 0.15)
CLR_VALUE_NEUTRAL = "#888888"
_CLR_AGE_OLD      = _CLR_RED   # "#cc3333" — age-over-threshold gradient endpoint


# ── Interactive button styles ─────────────────────────────────────────────────
# Pre-built stylesheet strings for the four interactive button states, in two
# size classes.  All reference CLR_INTERACTIVE and its derived variants.
#
#   ACTIVE   — action button in a live/triggered state (e.g. "Filters ●")
#              Uses full CLR_INTERACTIVE border for maximum prominence.
#   ON       — toggleable button in the On position.
#              Uses muted CLR_INTERACTIVE_BDR border to distinguish from ACTIVE.
#   DIM      — inactive / unselected rest state.
#   TOGGLE_OFF — toggleable button in the Off position; visually distinct from
#              both On and disabled; hover carries a hint of CLR_INTERACTIVE to
#              signal the button is still clickable.
#
#   _LG suffix: larger padding/font for dialog-level buttons.
#   _SM suffix: smaller padding/font for compact inline row toggles.

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


# Custom data role for chip data stored on Trait column items
_CHIP_ROLE             = Qt.UserRole + 2
_SCORE_SECONDARY_ROLE  = Qt.UserRole + 3   # score string shown below value in "both" mode
_HEATMAP_ROLE          = Qt.UserRole + 4   # float 0..1 intensity for heatmap mode (sign from score)

# Chip appearance constants
_CHIP_H       = 15   # chip height px
_CHIP_PAD_X   = 5    # horizontal text padding inside chip
_CHIP_GAP     = 4    # gap between chips
_CHIP_RADIUS  = 5    # corner radius

# Chip color pairs (bg, fg) by rating
_CHIP_TOP_PRIORITY = ("#004040", "#60e8d8")   # dark teal bg,  bright teal text
_CHIP_DESIRABLE   = ("#1d4a1d", "#a0e8a0")   # dark green bg, light green text
_CHIP_UNDESIRABLE = ("#4a1d1d", "#e8a0a0")   # dark red bg,   light red text
_CHIP_NEUTRAL     = ("#3a3a10", "#d8d870")   # dark yellow bg, yellow text
_CHIP_UNDECIDED   = ("#252535", CLR_VALUE_NEUTRAL)   # dark grey bg,   grey text
_CHIP_LOVE_SCOPE  = ("#2a1a2e", "#dd88cc")   # 💌  dark purple-pink bg, pink text
_CHIP_LOVE_ROOM   = ("#1e1a2e", "#bb88ee")   # 💕  dark violet bg,       violet text
_CHIP_HATE_SCOPE  = ("#2e1a1a", "#cc4444")   # 😠  dark red bg,          red text
_CHIP_HATE_ROOM   = ("#2e1e10", "#cc7733")   # 👿  dark orange bg,       orange text
_CHIP_AGGRO_HI    = ("#3a1a1a", "#cc6666")   # dark red bg,    light red text
_CHIP_AGGRO_LO    = ("#1a2a3a", "#6699cc")   # dark blue bg,   light blue text
_CHIP_AGE_WARN    = ("#3a2010", "#cc8833")   # dark amber bg,  amber text
_CHIP_DIM         = (CLR_SURFACE_NEUTRAL, CLR_TEXT_GRAYEDOUT)   # neutral chip

# Emoji mapping for columns that show emoji chips in value/heatmap mode
_COL_EMOJI = {
    "💗🔭": "💌",   # love-scope
    "💗🏠": "💕",   # love-room
    "💥🔭": "😠",   # hate-scope
    "💥🏠": "👿",   # hate-room
}


_TRAIT_NAME_ROLE    = Qt.UserRole + 10
_TRAIT_SUMMARY_ROLE = Qt.UserRole + 11


# Separator columns are now dedicated thin columns (see _SEP_COLS) rather than painted lines
_SEP_COL_COLOR = QColor("#4a4a88")


_HEAT_POS = QColor(*ColorUtils.parse_hex(CLR_DESIRABLE),   55)   # CLR_DESIRABLE at low alpha
_HEAT_NEG = QColor(*ColorUtils.parse_hex(CLR_UNDESIRABLE), 55)   # CLR_UNDESIRABLE at low alpha
