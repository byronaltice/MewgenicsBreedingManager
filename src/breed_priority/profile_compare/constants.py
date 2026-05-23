"""Profile Compare dialog — layout and label constants."""

# Column widths for the grid layout
COL_LABEL_WIDTH = 240
COL_SLOT_WIDTH  = 180

# Number of profile slots
NUM_PROFILES = 5

# Button label
COMPARE_BTN_LABEL = "…"

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

# Placeholder text shown for empty profile columns
EMPTY_SLOT_PLACEHOLDER = "— empty —"
