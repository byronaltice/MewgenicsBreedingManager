"""Planner blob persistence, foundation pairs, and offspring selection."""
import json
from typing import Optional

from save_parser import Cat

from mewgenics.utils.paths import _planner_state_path
from mewgenics.utils.config import _load_app_config, _save_app_config
from mewgenics.utils.cat_analysis import _cat_uid


_PLANNER_STATE_GLOBAL_MIRROR_KEYS = {"room_optimizer_state", "room_priority_config"}


def _load_planner_state_blob(save_path: Optional[str]) -> dict:
    if not save_path:
        return {}
    try:
        with open(_planner_state_path(save_path), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_planner_state_blob(save_path: Optional[str], blob: dict):
    if not save_path:
        return
    try:
        with open(_planner_state_path(save_path), "w", encoding="utf-8") as f:
            json.dump(blob if isinstance(blob, dict) else {}, f, indent=2, sort_keys=True)
    except Exception:
        pass


def _load_planner_state_value(key: str, default=None, save_path: Optional[str] = None):
    if save_path:
        if key in _PLANNER_STATE_GLOBAL_MIRROR_KEYS:
            try:
                data = _load_app_config()
                value = data.get(key)
                if value not in (None, {}, []):
                    blob = _load_planner_state_blob(save_path)
                    if blob.get(key) != value:
                        blob[key] = value
                        _save_planner_state_blob(save_path, blob)
                    return value
            except Exception:
                pass
        blob = _load_planner_state_blob(save_path)
        if key in blob:
            return blob[key]
        try:
            data = _load_app_config()
            if key in data:
                value = data.get(key)
                blob[key] = value
                _save_planner_state_blob(save_path, blob)
                return value
        except Exception:
            return default
        return default
    try:
        data = _load_app_config()
        return data.get(key, default)
    except Exception:
        return default


def _save_planner_state_value(key: str, value, save_path: Optional[str] = None, *, mirror_global: bool = False):
    try:
        if save_path:
            blob = _load_planner_state_blob(save_path)
            blob[key] = value
            _save_planner_state_blob(save_path, blob)
            if mirror_global or key in _PLANNER_STATE_GLOBAL_MIRROR_KEYS:
                data = _load_app_config()
                data[key] = value
                _save_app_config(data)
            return
        data = _load_app_config()
        data[key] = value
        _save_app_config(data)
    except Exception:
        pass


# ── Foundation pairs ─────────────────────────────────────────────────────────

def _default_perfect_planner_foundation_pairs(count: int = 4) -> list[dict]:
    count = max(1, min(12, int(count or 4)))
    return [
        {"cat_a_uid": "", "cat_b_uid": "", "using": False}
        for _ in range(count)
    ]


def _load_perfect_planner_foundation_pairs(save_path: Optional[str] = None) -> list[dict]:
    try:
        cfg = _load_planner_state_value("perfect_planner_foundation_pairs", [], save_path=save_path)
        if isinstance(cfg, list):
            out: list[dict] = []
            for slot_data in cfg[:12]:
                slot = slot_data if isinstance(slot_data, dict) else {}
                out.append({
                    "cat_a_uid": str(slot.get("cat_a_uid") or "").strip().lower(),
                    "cat_b_uid": str(slot.get("cat_b_uid") or "").strip().lower(),
                    "using": bool(slot.get("using", False)),
                })
            if out:
                return out
    except Exception:
        pass
    return _default_perfect_planner_foundation_pairs()


def _save_perfect_planner_foundation_pairs(config: list[dict], save_path: Optional[str] = None):
    try:
        normalized = []
        for slot in (config or [])[:12]:
            if not isinstance(slot, dict):
                continue
            normalized.append({
                "cat_a_uid": str(slot.get("cat_a_uid") or "").strip().lower(),
                "cat_b_uid": str(slot.get("cat_b_uid") or "").strip().lower(),
                "using": bool(slot.get("using", False)),
            })
        if not normalized:
            normalized = _default_perfect_planner_foundation_pairs()
        _save_planner_state_value("perfect_planner_foundation_pairs", normalized, save_path=save_path)
    except Exception:
        pass


# ── Offspring selection ──────────────────────────────────────────────────────

def _default_perfect_planner_selected_offspring() -> dict[str, str]:
    return {}


def _load_perfect_planner_selected_offspring(save_path: Optional[str] = None) -> dict[str, str]:
    try:
        cfg = _load_planner_state_value("perfect_planner_selected_offspring", {}, save_path=save_path)
        if isinstance(cfg, dict):
            normalized: dict[str, str] = {}
            for pair_key, child_uid in cfg.items():
                pair_key = str(pair_key or "").strip().lower()
                child_uid = str(child_uid or "").strip().lower()
                if pair_key and child_uid:
                    normalized[pair_key] = child_uid
            return normalized
    except Exception:
        pass
    return _default_perfect_planner_selected_offspring()


def _save_perfect_planner_selected_offspring(config: dict[str, str], save_path: Optional[str] = None):
    try:
        normalized: dict[str, str] = {}
        for pair_key, child_uid in (config or {}).items():
            pair_key = str(pair_key or "").strip().lower()
            child_uid = str(child_uid or "").strip().lower()
            if pair_key and child_uid:
                normalized[pair_key] = child_uid
        _save_planner_state_value("perfect_planner_selected_offspring", normalized, save_path=save_path)
    except Exception:
        pass


def _planner_pair_uid_key(cat_a: Cat, cat_b: Cat) -> str:
    a = _cat_uid(cat_a)
    b = _cat_uid(cat_b)
    if not a or not b:
        return ""
    left, right = sorted((a, b))
    return f"{left}|{right}"


def _planner_import_trait_display(trait: dict) -> str:
    display = str(trait.get("display", trait.get("name", "?"))).strip() or "?"
    return display.split("] ", 1)[-1]


def _planner_import_traits_summary(traits: "list[dict]", limit: int = 4) -> str:
    valid_traits = [trait for trait in traits if isinstance(trait, dict)]
    names: list[str] = []
    for trait in valid_traits[:limit]:
        display = _planner_import_trait_display(trait)
        weight = trait.get("weight", "?")
        names.append(f"{display}({weight})")
    summary = ", ".join(names)
    if len(valid_traits) > limit:
        summary += f" +{len(valid_traits) - limit} more"
    return summary


def _planner_import_traits_tooltip(traits: "list[dict]", *, empty_text: str) -> str:
    valid_traits = [trait for trait in traits if isinstance(trait, dict)]
    if not valid_traits:
        return empty_text
    lines = [f"Imported traits ({len(valid_traits)}):"]
    for trait in valid_traits:
        display = _planner_import_trait_display(trait)
        weight = trait.get("weight", "?")
        lines.append(f"- {display} ({weight})")
    return "\n".join(lines)
