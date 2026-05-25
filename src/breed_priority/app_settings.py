"""Per-user settings persisted to ``%APPDATA%\\MewgenicsBreedingManager\\settings.json``.

This module is intentionally standalone (no imports from ``mewgenics``) so it
can be used from inside the breed_priority package without creating a
circular dependency. It reads/writes the *same* ``settings.json`` file used
by the rest of the app, sharing keys without parsing or touching state it
doesn't own.

The plan calls this file ``%LOCALAPPDATA%/MewgenicsBreedingManager/settings.json``;
we use ``%APPDATA%`` to match the location the rest of the app already uses.
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Optional

# Key names in settings.json
KEY_GAME_INSTALL_PATH = "game_install_path"
KEY_FFDEC_JAR_PATH = "ffdec_jar_path"
KEY_JAVA_EXE_PATH = "java_exe_path"


def _app_config_dir() -> str:
    """Return the per-user MewgenicsBreedingManager config directory.

    Matches the directory used by ``src/mewgenics/utils/paths.py`` so the
    same ``settings.json`` is shared.
    """
    if platform.system() == "Linux":
        return os.path.join(str(Path.home()), "MewgenicsBreedingManager")
    return os.path.join(
        os.environ.get("APPDATA", str(Path.home())),
        "MewgenicsBreedingManager",
    )


def app_config_path() -> str:
    return os.path.join(_app_config_dir(), "settings.json")


def icons_dir() -> str:
    """Return the per-user icons directory.

    ``<config_dir>/assets/icons/`` — created lazily by the extractor.
    """
    return os.path.join(_app_config_dir(), "assets", "icons")


def _load_settings() -> dict:
    path = app_config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_settings(data: dict) -> None:
    try:
        os.makedirs(_app_config_dir(), exist_ok=True)
        with open(app_config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
    except Exception:
        pass


def get_game_install_path() -> Optional[str]:
    value = _load_settings().get(KEY_GAME_INSTALL_PATH, "")
    if isinstance(value, str):
        value = value.strip()
        if value and os.path.isdir(value):
            return value
    return None


def set_game_install_path(path: str) -> None:
    cleaned = (path or "").strip()
    data = _load_settings()
    if cleaned:
        data[KEY_GAME_INSTALL_PATH] = cleaned
    else:
        data.pop(KEY_GAME_INSTALL_PATH, None)
    _save_settings(data)


def _get_existing_file_setting(key: str) -> Optional[str]:
    value = _load_settings().get(key, "")
    if isinstance(value, str):
        value = value.strip()
        if value and os.path.isfile(value):
            return value
    return None


def _set_file_setting(key: str, path: str) -> None:
    cleaned = (path or "").strip()
    data = _load_settings()
    if cleaned:
        data[key] = cleaned
    else:
        data.pop(key, None)
    _save_settings(data)


def get_ffdec_jar_path() -> Optional[str]:
    return _get_existing_file_setting(KEY_FFDEC_JAR_PATH)


def set_ffdec_jar_path(path: str) -> None:
    _set_file_setting(KEY_FFDEC_JAR_PATH, path)


def get_java_exe_path() -> Optional[str]:
    return _get_existing_file_setting(KEY_JAVA_EXE_PATH)


def set_java_exe_path(path: str) -> None:
    _set_file_setting(KEY_JAVA_EXE_PATH, path)


def derive_install_path_from_gpak(gpak_path: str) -> Optional[str]:
    """Given a full path to ``resources.gpak``, return the install root.

    The rest of the app stores the absolute gpak file path under
    ``gpak_path``; the install root is its parent directory.
    """
    if not gpak_path or not os.path.isfile(gpak_path):
        return None
    return os.path.dirname(gpak_path)
