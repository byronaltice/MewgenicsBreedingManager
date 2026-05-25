"""Profile Compare dialog — layout and label constants."""

# Column widths for the grid layout
COL_LABEL_WIDTH     = 280   # widened to accommodate emoji-formatted trait names
COL_LABEL_MIN_WIDTH = 180   # minimum so labels don't collapse when window is narrow

# Number of profile slots
NUM_PROFILES = 5

# Button label
COMPARE_BTN_LABEL = "…"

# Row label font size (px)
LABEL_FONT_SIZE_PX = 11

# Alternating row stripe background colours
ROW_BG_EVEN = "#0c1424"
ROW_BG_ODD  = "#101a2e"

# Int parameter ranges for weight spin editors
# (matches the mapping in breed_priority/__init__.py)
INT_PARAM_RANGES: dict[str, tuple[int, int]] = {
    "stat_7_threshold":          (1, 20),
    "age_threshold":             (1, 30),
    "seven_sub_threshold":       (1, 20),
    "gene_risk_threshold":       (0, 50),
    "mate_imbalance_threshold":  (0, 50),
    "gene_risk_penalty_scale":   (1, 100),
    "stat_count_threshold":      (1, 7),
}

# Group titles (display order determines row-section order)
GROUP_TITLES = {
    "name":            "Name",
    "weights":         "Weights",
    "complex_weights": "Complex Weights",
    "active":          "Active Abilities",
    "passive":         "Passive Abilities",
    "disorders":       "Disorders",
    "good_mutations":  "Good Mutations",
    "defects":         "Defects",
}

# Section header styling constants (Fix 2: headers must stand out above row labels)
SECTION_HEADER_FONT_SIZE_PX   = 14
SECTION_HEADER_COLOR          = "#cce0ff"
SECTION_HEADER_BORDER_COLOR   = "#2a4a8a"

# Diff marker asterisk styling
DIFF_MARKER_COLOR        = "#e8c050"
DIFF_MARKER_FONT_SIZE_PX = 13
DIFF_MARKER_WIDTH        = 14   # fixed px width so rows don't shift when marker appears

# Copy button styling
COPY_BTN_GLYPH       = "↶"          # glyph rendered in the copy button
COPY_BTN_SIZE_PX     = 16           # width and height of the copy button
COPY_BTN_FONT_SIZE   = 12           # font size (px) for the glyph
COPY_BTN_STYLE = (
    "QPushButton { background:transparent; color:#6688aa; border:none;"
    f" font-size:{COPY_BTN_FONT_SIZE}px; padding:0; min-width:{COPY_BTN_SIZE_PX}px;"
    f" max-width:{COPY_BTN_SIZE_PX}px; min-height:{COPY_BTN_SIZE_PX}px;"
    f" max-height:{COPY_BTN_SIZE_PX}px; opacity:0.6; }}"
    "QPushButton:hover { color:#aaccff; opacity:1.0; }"
)

# Flash animation for copy feedback (destination cells)
COPY_FLASH_COLOR     = "#e8c050"    # yellow border flash colour
COPY_FLASH_DURATION  = 300          # milliseconds

# Toast widget styling and timing
TOAST_AUTO_DISMISS_MS = 4000        # auto-dismiss after 4 seconds
TOAST_BG_COLOR        = "#1a2a44"
TOAST_BORDER_COLOR    = "#2244aa"
TOAST_TEXT_COLOR      = "#aabbcc"
TOAST_UNDO_COLOR      = "#88aadd"
TOAST_HEIGHT          = 36          # px
TOAST_MARGIN          = 12          # px inset from dialog edges
