"""Static configuration for the Party Builder UI."""

from __future__ import annotations

MAX_PARTY_SIZE = 4
DEFAULT_MIN_SCORE = 10

GRAPH_MIN_HEIGHT = 240
GRAPH_MAX_BAR_WIDTH = 84
GRAPH_MAX_GAP_WIDTH = 18
GRAPH_MIN_GAP_WIDTH = 10
GRAPH_SIDE_MARGIN = 8
GRAPH_LEFT_LABEL_WIDTH = 58
GRAPH_TOP_MARGIN = 18
GRAPH_BOTTOM_MARGIN = 28
GRAPH_PLOT_MAX_WIDTH = 720
PREVIEW_ALPHA = 160

CLASS_BAR_MAX_WIDTH = 360
CLASS_ROW_MIN_HEIGHT = 28
CLASS_COUNT_BADGE_SIZE = 22
CLASS_COUNT_BADGE_COLOR = "#27e0d7"

PARTY_SLOT_SIZE = 120

RECOMMENDATION_WHEEL_STEP = 10
RECOMMENDATION_TEXT_COLOR = "#f5f5f5"
RECOMMENDATION_NAME_WIDTH = 130
RECOMMENDATION_BAR_HEIGHT = 12
RECOMMENDATION_BAR_RADIUS = 5
RECOMMENDATION_BAR_SCALE = 1000
RECOMMENDATION_BAR_COLOR = "#91ba81"
RECOMMENDATION_BAR_MID_COLOR = "#c9bf68"
RECOMMENDATION_BAR_LOW_COLOR = "#ba7c81"
RECOMMENDATION_BAR_BORDER_COLOR = "#35502c"

HINT_TEXT_STYLESHEET = "color:#888;"

CATEGORIES = (
    "Tankiness",
    "Damage",
    "Reach",
    "Sustain",
    "Crowd Control",
    "Utility",
)

LETTER_TO_SCORE = {
    "D": 0,
    "C": 1,
    "B": 3,
    "A": 4,
    "S": 6,
}
SCORE_TO_LETTER = {score: letter for letter, score in LETTER_TO_SCORE.items()}

CLASS_RATINGS = {
    "Collarless": {category: 1 for category in CATEGORIES},
    "Jester": {category: 2 for category in CATEGORIES},
    "Fighter": {"Tankiness": "B", "Damage": "S", "Reach": "C", "Sustain": "D", "Crowd Control": "B", "Utility": "D"},
    "Mage": {"Tankiness": "D", "Damage": "A", "Reach": "A", "Sustain": "D", "Crowd Control": "A", "Utility": "A"},
    "Monk": {"Tankiness": "B", "Damage": "S", "Reach": "A", "Sustain": "B", "Crowd Control": "C", "Utility": "D"},
    "Necromancer": {"Tankiness": "S", "Damage": "C", "Reach": "C", "Sustain": "A", "Crowd Control": "C", "Utility": "C"},
    "Druid": {"Tankiness": "A", "Damage": "C", "Reach": "B", "Sustain": "A", "Crowd Control": "B", "Utility": "A"},
    "Hunter": {"Tankiness": "C", "Damage": "A", "Reach": "S", "Sustain": "D", "Crowd Control": "A", "Utility": "C"},
    "Cleric": {"Tankiness": "B", "Damage": "D", "Reach": "D", "Sustain": "S", "Crowd Control": "C", "Utility": "S"},
    "Tinker": {"Tankiness": "B", "Damage": "B", "Reach": "B", "Sustain": "B", "Crowd Control": "C", "Utility": "B"},
    "Tank": {"Tankiness": "S", "Damage": "B", "Reach": "C", "Sustain": "C", "Crowd Control": "S", "Utility": "C"},
    "Butcher": {"Tankiness": "A", "Damage": "A", "Reach": "A", "Sustain": "A", "Crowd Control": "C", "Utility": "D"},
    "Psychic": {"Tankiness": "D", "Damage": "C", "Reach": "A", "Sustain": "D", "Crowd Control": "S", "Utility": "A"},
    "Thief": {"Tankiness": "D", "Damage": "A", "Reach": "S", "Sustain": "D", "Crowd Control": "D", "Utility": "B"},
}


# CLASS_RATINGS = {
#     "Collarless": {category: 0 for category in CATEGORIES},
#     "Jester": {category: 1 for category in CATEGORIES},
#     "Fighter": {"Tankiness": "B", "Damage": "S", "Reach": "C", "Sustain": "D", "Crowd Control": "B", "Utility": "D"},
#     "Mage": {"Tankiness": "D", "Damage": "A", "Reach": "A", "Sustain": "D", "Crowd Control": "A", "Utility": "B"},
#     "Monk": {"Tankiness": "B", "Damage": "A", "Reach": "A", "Sustain": "B", "Crowd Control": "C", "Utility": "D"},
#     "Necromancer": {"Tankiness": "S", "Damage": "C", "Reach": "C", "Sustain": "A", "Crowd Control": "C", "Utility": "C"},
#     "Druid": {"Tankiness": "A", "Damage": "C", "Reach": "B", "Sustain": "A", "Crowd Control": "C", "Utility": "A"},
#     "Hunter": {"Tankiness": "C", "Damage": "A", "Reach": "S", "Sustain": "D", "Crowd Control": "A", "Utility": "C"},
#     "Cleric": {"Tankiness": "B", "Damage": "D", "Reach": "D", "Sustain": "S", "Crowd Control": "C", "Utility": "S"},
#     "Tinker": {"Tankiness": "B", "Damage": "B", "Reach": "B", "Sustain": "B", "Crowd Control": "C", "Utility": "A"},
#     "Tank": {"Tankiness": "S", "Damage": "B", "Reach": "C", "Sustain": "C", "Crowd Control": "S", "Utility": "C"},
#     "Butcher": {"Tankiness": "A", "Damage": "A", "Reach": "A", "Sustain": "A", "Crowd Control": "C", "Utility": "D"},
#     "Psychic": {"Tankiness": "D", "Damage": "C", "Reach": "A", "Sustain": "D", "Crowd Control": "S", "Utility": "A"},
#     "Thief": {"Tankiness": "C", "Damage": "S", "Reach": "A", "Sustain": "D", "Crowd Control": "D", "Utility": "B"},
# }

CLASS_NAMES = tuple(CLASS_RATINGS)

CLASS_COLORS = {
    "Druid": "#4b2f1f",
    "Tank": "#b08a5a",
    "Fighter": "#d96b6b",
    "Butcher": "#b84a4a",
    "Hunter": "#2f5e2f",
    "Psychic": "#8a5fd3",
    "Mage": "#3f6fe8",
    "Cleric": "#e4e4df",
    "Monk": "#7d7d7d",
    "Tinker": "#58d8c5",
    "Necromancer": "#111111",
    "Thief": "#efe7a2",
    "Collarless": "#b8b8b8",
    "Jester": "#d0b1ff",
}
