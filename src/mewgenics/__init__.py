"""Mewgenics Breeding Manager package — module-level initialization."""

from mewgenics.utils.game_data import _reload_game_data
from mewgenics.utils.localization import (
    _log_startup_environment, _saved_language,
    _set_current_language, _refresh_localized_constants,
)
from mewgenics.utils.tags import _load_tag_definitions
from mewgenics.utils.thresholds import _apply_threshold_preferences, _load_threshold_preferences

_reload_game_data()
_log_startup_environment()
_set_current_language(_saved_language())
_refresh_localized_constants()
_load_tag_definitions()
_apply_threshold_preferences(_load_threshold_preferences())
