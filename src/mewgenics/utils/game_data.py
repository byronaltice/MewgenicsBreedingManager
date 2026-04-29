"""GPAK loading and game data reload."""
import os

from save_parser import (
    GameData,
    FurnitureDefinition,
    set_visual_mut_data,
    set_class_stat_mods,
    set_cat_head_placements_per_frame,
)

from mewgenics.utils.config import _load_app_config, _save_app_config, _candidate_gpak_paths
from mewgenics.utils.abilities import _load_ability_descriptions, _ABILITY_DESC


# ── Mutable module state ─────────────────────────────────────────────────────

_GPAK_SEARCH_PATHS: list[str] = []
_GPAK_PATH: str | None = None
_VISUAL_MUT_DATA: dict = {}
_FURNITURE_DATA: dict[str, FurnitureDefinition] = {}


def _reload_game_data():
    global _GPAK_SEARCH_PATHS, _GPAK_PATH, _VISUAL_MUT_DATA, _FURNITURE_DATA
    _GPAK_SEARCH_PATHS = _candidate_gpak_paths()
    _GPAK_PATH = next((p for p in _GPAK_SEARCH_PATHS if os.path.exists(p)), None)
    _ABILITY_DESC.clear()
    _ABILITY_DESC.update(_load_ability_descriptions(_GPAK_PATH))
    game_data = GameData.from_gpak(_GPAK_PATH)
    _VISUAL_MUT_DATA = game_data.visual_mutation_data
    _FURNITURE_DATA = game_data.furniture_data
    set_visual_mut_data(_VISUAL_MUT_DATA)
    set_class_stat_mods(game_data.class_stat_mods)
    set_cat_head_placements_per_frame(game_data.cat_head_placements_per_frame)


def _set_gpak_path(path: str):
    cleaned = path.strip()
    if not cleaned:
        return
    data = _load_app_config()
    data["gpak_path"] = cleaned
    _save_app_config(data)
    _reload_game_data()


def get_gpak_path() -> str | None:
    return _GPAK_PATH


def get_visual_mut_data() -> dict:
    return _VISUAL_MUT_DATA


def get_furniture_data() -> dict[str, FurnitureDefinition]:
    return _FURNITURE_DATA
