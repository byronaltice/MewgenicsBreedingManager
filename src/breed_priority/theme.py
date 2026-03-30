"""Breed Priority — color theme and chip color pairs.

All semantic colors, chip (bg, fg) pairs, and heatmap colors.
Derived colors are computed via ColorUtils so the entire theme
changes consistently when a base color is adjusted.
"""

from PySide6.QtGui import QColor

from .color_utils import ColorUtils


# ── Trait rating colors ───────────────────────────────────────────────────────

CLR_TOP_PRIORITY = "#40d0c0"
CLR_DESIRABLE    = "#6aaa6a"
CLR_NEUTRAL      = "#b0a040"
CLR_UNDECIDED    = "#888899"
CLR_UNDESIRABLE  = "#aa6a6a"
RATING_ITEM_COLORS = [CLR_TOP_PRIORITY, CLR_DESIRABLE, CLR_NEUTRAL, CLR_UNDECIDED, CLR_UNDESIRABLE]

# ── Shared accent / selection colors ─────────────────────────────────────────

_SEL_BG     = "#0a1e18"
_SEL_FG     = "#aaddcc"
_SEL_BORDER = "#1ec8a0"
_DIM_FG       = "#ccccdd"
_DIM_BG       = "#1a1a26"
_DIM_HOVER_FG = "#ddddf0"
_DIM_HOVER_BG = "#222230"
_DIM_LABEL_FG = "#ccccdd"

# ── Base dark theme ───────────────────────────────────────────────────────────

_THEME_DARK = "#0c0c20"
_CLR_RED    = "#cc3333"
_CLR_YELLOW = "#b0a040"

# ── Text colors ───────────────────────────────────────────────────────────────

CLR_TEXT_PRIMARY   = "#dddddd"
CLR_TEXT_SECONDARY = ColorUtils.blend(CLR_TEXT_PRIMARY, _THEME_DARK, 0.24)
CLR_TEXT_UI_LABEL  = ColorUtils.blend(CLR_TEXT_PRIMARY, _THEME_DARK, 0.40)
CLR_TEXT_GROUP     = ColorUtils.blend(CLR_TEXT_PRIMARY, _THEME_DARK, 0.65)
CLR_TEXT_SUBLABEL  = CLR_TEXT_GROUP
CLR_TEXT_COUNT     = ColorUtils.blend(CLR_TEXT_PRIMARY, _THEME_DARK, 0.72)
CLR_TEXT_GRAYEDOUT = CLR_TEXT_GROUP
CLR_TEXT_MUTED     = ColorUtils.blend(CLR_TEXT_PRIMARY, _THEME_DARK, 0.80)

# ── Background colors ─────────────────────────────────────────────────────────

CLR_BG_MAIN       = "#0d0d1c"
CLR_BG_ALT        = "#131326"
CLR_BG_SCORE_AREA = "#0a0a18"
CLR_BG_PANEL      = "#14142a"
CLR_BG_HEADER     = "#16213e"
CLR_BG_HEADER_BDR = "#1e1e38"
CLR_BG_DEEP       = "#080818"

# ── Neutral surfaces ──────────────────────────────────────────────────────────

_NEUTRAL_SURFACE      = "rgba(0, 0, 0, 140)"
CLR_SURFACE_NEUTRAL   = "#1a1a22"
CLR_SURFACE_SEPARATOR = "#252545"

# ── Gender colors ─────────────────────────────────────────────────────────────

CLR_GENDER_MALE    = "#2aaa99"
CLR_GENDER_FEMALE  = "#bb88dd"
CLR_GENDER_UNKNOWN = "#ccaa44"

_CHIP_GENDER_MALE    = (ColorUtils.derive_chip_bg(CLR_GENDER_MALE,    _THEME_DARK), CLR_GENDER_MALE)
_CHIP_GENDER_FEMALE  = (ColorUtils.derive_chip_bg(CLR_GENDER_FEMALE,  _THEME_DARK), CLR_GENDER_FEMALE)
_CHIP_GENDER_UNKNOWN = (ColorUtils.derive_chip_bg(CLR_GENDER_UNKNOWN, _THEME_DARK), CLR_GENDER_UNKNOWN)

# ── Interactive accent ────────────────────────────────────────────────────────

CLR_INTERACTIVE     = _SEL_BORDER
CLR_INTERACTIVE_BG  = ColorUtils.blend(_THEME_DARK, CLR_INTERACTIVE, 0.22)
CLR_INTERACTIVE_BDR = ColorUtils.blend(_THEME_DARK, CLR_INTERACTIVE, 0.34)
CLR_INTERACTIVE_HOV = ColorUtils.blend(CLR_INTERACTIVE, "#8ff8e0", 0.30)

CLR_HIGHLIGHT = "#eee"

# ── Value colors ──────────────────────────────────────────────────────────────

CLR_VALUE_POS     = CLR_INTERACTIVE
CLR_VALUE_POS_BG  = CLR_INTERACTIVE_BG
CLR_VALUE_NEG     = "#e04040"
CLR_VALUE_NEG_BG  = ColorUtils.blend(_THEME_DARK, CLR_VALUE_NEG, 0.15)
CLR_VALUE_NEUTRAL = "#888888"
_CLR_AGE_OLD      = _CLR_RED

# ── Sexuality display ─────────────────────────────────────────────────────────

_SEX_EMOJI_GAY = "🏳️‍🌈"
_SEX_EMOJI_BI  = "BI"

# ── Chip appearance constants ─────────────────────────────────────────────────

_CHIP_H       = 15
_CHIP_PAD_X   = 5
_CHIP_GAP     = 4
_CHIP_RADIUS  = 5

# ── Chip color pairs (bg, fg) ─────────────────────────────────────────────────

_CHIP_TOP_PRIORITY = ("#004040", "#60e8d8")
_CHIP_DESIRABLE   = ("#1d4a1d", "#a0e8a0")
_CHIP_UNDESIRABLE = ("#4a1d1d", "#e8a0a0")
_CHIP_NEUTRAL     = ("#3a3a10", "#d8d870")
_CHIP_UNDECIDED   = ("#252535", CLR_VALUE_NEUTRAL)
_CHIP_LOVE_SCOPE  = ("#2a1a2e", "#dd88cc")
_CHIP_LOVE_ROOM   = ("#1e1a2e", "#bb88ee")
_CHIP_HATE_SCOPE  = ("#2e1a1a", "#cc4444")
_CHIP_HATE_ROOM   = ("#2e1e10", "#cc7733")
_CHIP_AGGRO_HI    = ("#3a1a1a", "#cc6666")
_CHIP_AGGRO_LO    = ("#1a2a3a", "#6699cc")
_CHIP_AGE_WARN    = ("#3a2010", "#cc8833")
_CHIP_DIM         = (CLR_SURFACE_NEUTRAL, CLR_TEXT_GRAYEDOUT)

# ── Separator column color ────────────────────────────────────────────────────

_SEP_COL_COLOR = QColor("#4a4a88")

# ── Heatmap colors ────────────────────────────────────────────────────────────

_HEAT_POS = QColor(*ColorUtils.parse_hex(CLR_DESIRABLE),   55)
_HEAT_NEG = QColor(*ColorUtils.parse_hex(CLR_UNDESIRABLE), 55)
