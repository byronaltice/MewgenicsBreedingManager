"""Application configuration persistence and coercion helpers."""
import os
import json
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget, QSplitter
from PySide6.QtCore import QByteArray

from mewgenics.utils.paths import (
    APP_CONFIG_PATH, APPDATA_CONFIG_DIR, APPDATA_SAVE_DIR,
    _app_dir, _bundle_dir, _steam_library_paths,
)


def _load_app_config() -> dict:
    if not os.path.exists(APP_CONFIG_PATH):
        return {}
    try:
        with open(APP_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_app_config(data: dict):
    try:
        os.makedirs(APPDATA_CONFIG_DIR, exist_ok=True)
        with open(APP_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
    except Exception:
        pass


# ── Coercion helpers ─────────────────────────────────────────────────────────

def _coerce_int(value, default: int, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        result = int(float(value))
    except (TypeError, ValueError):
        result = default
    if min_value is not None:
        result = max(min_value, result)
    if max_value is not None:
        result = min(max_value, result)
    return result


def _coerce_float(value, default: float, min_value: float | None = None, max_value: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    if min_value is not None:
        result = max(min_value, result)
    if max_value is not None:
        result = min(max_value, result)
    return result


def _coerce_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


# ── Save / gpak path helpers ────────────────────────────────────────────────

def _saved_gpak_path() -> str:
    data = _load_app_config()
    value = data.get("gpak_path", "")
    return value.strip() if isinstance(value, str) else ""


def _saved_save_dir() -> str:
    data = _load_app_config()
    value = data.get("save_dir", "")
    return value.strip() if isinstance(value, str) else ""


def _save_root_dir() -> str:
    return _saved_save_dir() or APPDATA_SAVE_DIR


def _saved_default_save() -> Optional[str]:
    """Get the default save file path, if one is configured."""
    data = _load_app_config()
    value = data.get("default_save", "")
    if isinstance(value, str):
        value = value.strip()
        if value and os.path.exists(value):
            return value
    return None


def _set_default_save(path: Optional[str]):
    """Set or clear the default save file path."""
    data = _load_app_config()
    if path:
        data["default_save"] = path
    else:
        data.pop("default_save", None)
    _save_app_config(data)


def _set_save_dir(path: str):
    cleaned = path.strip()
    if not cleaned:
        return
    data = _load_app_config()
    data["save_dir"] = cleaned
    _save_app_config(data)


def _save_current_view(name: str):
    """Persist the current view name to settings.json."""
    data = _load_app_config()
    data["current_view"] = name
    _save_app_config(data)


def _load_current_view() -> str:
    """Return the last saved view name, defaulting to 'table'."""
    return _load_app_config().get("current_view", "table")


def _candidate_gpak_paths() -> list[str]:
    candidates: list[str] = []

    env_path = os.environ.get("MEWGENICS_GPAK_PATH", "").strip()
    if env_path:
        candidates.append(env_path)

    direct_paths = [
        os.path.join(
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            "Steam", "steamapps", "common", "Mewgenics", "resources.gpak",
        ),
        os.path.join(
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            "Steam", "steamapps", "common", "Mewgenics", "resources.gpak",
        ),
        r"D:\Games\Mewgenics\resources.gpak",
        os.path.join(os.getcwd(), "resources.gpak"),
        os.path.join(_app_dir(), "resources.gpak"),
        os.path.join(_bundle_dir(), "resources.gpak"),
        "/mnt/c/Program Files (x86)/Steam/steamapps/common/Mewgenics/resources.gpak",
        "/mnt/c/Program Files/Steam/steamapps/common/Mewgenics/resources.gpak",
    ]
    candidates.extend(direct_paths)

    for library in _steam_library_paths():
        candidates.append(os.path.join(library, "steamapps", "common", "Mewgenics", "resources.gpak"))

    saved_path = _saved_gpak_path()
    if saved_path:
        candidates.append(saved_path)

    ordered: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        norm = os.path.normcase(os.path.normpath(path))
        if norm in seen:
            continue
        seen.add(norm)
        ordered.append(path)
    return ordered


def find_save_files() -> list[str]:
    saves = []
    base  = Path(_save_root_dir())
    if not base.is_dir():
        return saves
    for profile in base.iterdir():
        saves_dir = profile / "saves"
        if saves_dir.is_dir():
            saves.extend(str(p) for p in saves_dir.glob("*.sav"))
    saves.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return saves


# ── Optimizer flags ──────────────────────────────────────────────────────────

def _saved_optimizer_flag(name: str, default: bool = False) -> bool:
    data = _load_app_config()
    value = data.get("optimizer_flags", {}).get(name, default)
    return bool(value)


def _set_optimizer_flag(name: str, value: bool):
    data = _load_app_config()
    flags = data.get("optimizer_flags")
    if not isinstance(flags, dict):
        flags = {}
    flags[name] = bool(value)
    data["optimizer_flags"] = flags
    _save_app_config(data)


def _saved_room_optimizer_auto_recalc(default: bool = False) -> bool:
    return _saved_optimizer_flag("room_optimizer_auto_recalc", default)


def _set_room_optimizer_auto_recalc(enabled: bool):
    _set_optimizer_flag("room_optimizer_auto_recalc", enabled)


# ── UI state persistence ─────────────────────────────────────────────────────

def _load_ui_state(key: str) -> dict:
    data = _load_app_config()
    state = data.get(key, {})
    return state if isinstance(state, dict) else {}


def _save_ui_state(key: str, state: dict):
    try:
        data = _load_app_config()
        data[key] = state if isinstance(state, dict) else {}
        _save_app_config(data)
    except Exception:
        pass


# ── Splitter state persistence ───────────────────────────────────────────────

def _load_splitter_states() -> dict[str, str]:
    data = _load_app_config()
    state = data.get("splitter_states", {})
    return state if isinstance(state, dict) else {}


def _save_splitter_states(states: dict[str, str]):
    try:
        data = _load_app_config()
        data["splitter_states"] = states if isinstance(states, dict) else {}
        _save_app_config(data)
    except Exception:
        pass


def _restore_splitter_state(splitter: QSplitter):
    key = splitter.objectName().strip()
    if not key:
        return
    encoded = _load_splitter_states().get(key)
    if not encoded:
        return
    try:
        splitter.restoreState(QByteArray.fromBase64(encoded.encode("ascii")))
    except Exception:
        pass


def _save_splitter_state(splitter: QSplitter):
    key = splitter.objectName().strip()
    if not key:
        return
    try:
        states = _load_splitter_states()
        states[key] = splitter.saveState().toBase64().data().decode("ascii")
        _save_splitter_states(states)
    except Exception:
        pass


def _bind_splitter_persistence(root: Optional[QWidget]):
    if root is None:
        return
    for splitter in root.findChildren(QSplitter):
        key = splitter.objectName().strip()
        if not key or splitter.property("_splitter_persist_bound"):
            continue
        splitter.setProperty("_splitter_persist_bound", True)
        _restore_splitter_state(splitter)
        splitter.splitterMoved.connect(lambda *_ , s=splitter: _save_splitter_state(s))
