"""File system paths and directory resolution."""
import logging
import shutil
import sys
import os
import re
import platform
from pathlib import Path

logger = logging.getLogger(__name__)


def _bundle_dir() -> str:
    """Return the directory containing bundled app resources."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(os.path.join(__file__, "..", "..")))


def _app_dir() -> str:
    """Return the directory containing the running script or built executable."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(os.path.join(__file__, "..", "..")))


def _read_app_version() -> str:
    """Read the app version from the shared VERSION file."""
    candidates = [
        Path(_bundle_dir()) / "VERSION",
        Path(_app_dir()) / "VERSION",
        Path(__file__).resolve().parent.parent.parent.parent / "VERSION",
    ]
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return "dev"


# ── Platform-dependent directories ───────────────────────────────────────────

if platform.system() == "Linux":
    APPDATA_SAVE_DIR = os.path.join(
        str(Path.home()), ".steam", "steam", "steamapps",
        "compatdata", "686060", "pfx", "drive_c", "users", "steamuser", "AppData", "Roaming",
        "Glaiel Games", "Mewgenics", ".",
    )
    APPDATA_CONFIG_DIR = os.path.join(
        str(Path.home()), "MewgenicsBreedingManager",
    )
else:
    APPDATA_SAVE_DIR = os.path.join(
        os.environ.get("APPDATA", ""),
        "Glaiel Games", "Mewgenics", ".",
    )
    APPDATA_CONFIG_DIR = os.path.join(
        os.environ.get("APPDATA", str(Path.home())),
        "MewgenicsBreedingManager",
    )
os.makedirs(APPDATA_CONFIG_DIR, exist_ok=True)
APP_CONFIG_PATH = os.path.join(APPDATA_CONFIG_DIR, "settings.json")
LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
APP_VERSION = _read_app_version()


def _steam_library_paths() -> list[str]:
    candidates = [
        os.path.join(
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            "Steam",
            "steamapps",
            "libraryfolders.vdf",
        ),
        os.path.join(
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            "Steam",
            "steamapps",
            "libraryfolders.vdf",
        ),
        os.path.join(
            str(Path.home()),
            ".steam",
            "steam",
            "steamapps",
            "libraryfolders.vdf",
        ),
    ]
    libraries: list[str] = []
    for vdf_path in candidates:
        if not os.path.exists(vdf_path):
            continue
        try:
            with open(vdf_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            for match in re.finditer(r'"path"\s+"([^"]+)"', content):
                path = match.group(1).replace("\\\\", "\\")
                if path not in libraries:
                    libraries.append(path)
        except Exception:
            continue
    return libraries


# ── Sidecar file paths ───────────────────────────────────────────────────────

# Save-specific sidecar suffixes, in canonical order for backup/migration.
_SIDECAR_SUFFIXES = (
    ".blacklist",
    ".mustbreed",
    ".pinned",
    ".tags.json",
    ".gender_overrides.csv",
    ".calibration.json",
    ".planner_state.json",
    ".breeding_cache.json",
)


def _bp_sidecar_path() -> str:
    """Return the path for the breed-priority sidecar (app-global)."""
    return os.path.join(APPDATA_CONFIG_DIR, "breed_priority.json")


def _blacklist_path(save_path: str) -> str:
    """Return path for blacklist file associated with save."""
    return os.path.join(APPDATA_CONFIG_DIR, Path(save_path).stem + ".blacklist")


def _must_breed_path(save_path: str) -> str:
    """Return path for must-breed file associated with save."""
    return os.path.join(APPDATA_CONFIG_DIR, Path(save_path).stem + ".mustbreed")


def _pinned_path(save_path: str) -> str:
    """Return path for pinned-cats file associated with save."""
    return os.path.join(APPDATA_CONFIG_DIR, Path(save_path).stem + ".pinned")


def _tags_path(save_path: str) -> str:
    """Return JSON path for cat tag assignments associated with save."""
    return os.path.join(APPDATA_CONFIG_DIR, Path(save_path).stem + ".tags.json")


def _gender_overrides_path(save_path: str) -> str:
    """Return CSV path for manual gender overrides associated with save."""
    return os.path.join(APPDATA_CONFIG_DIR, Path(save_path).stem + ".gender_overrides.csv")


def _calibration_path(save_path: str) -> str:
    """Return JSON path for manual calibration data associated with save."""
    return os.path.join(APPDATA_CONFIG_DIR, Path(save_path).stem + ".calibration.json")


def _planner_state_path(save_path: str) -> str:
    """Return JSON path for planner state associated with save."""
    return os.path.join(APPDATA_CONFIG_DIR, Path(save_path).stem + ".planner_state.json")


def _breeding_cache_path(save_path: str) -> str:
    """Return JSON path for breeding cache associated with save."""
    return os.path.join(APPDATA_CONFIG_DIR, Path(save_path).stem + ".breeding_cache.json")


# ── Legacy sidecar paths (original alongside-.sav location) ──────────────────

def _legacy_blacklist_path(save_path: str) -> str:
    return save_path + ".blacklist"


def _legacy_must_breed_path(save_path: str) -> str:
    return save_path + ".mustbreed"


def _legacy_pinned_path(save_path: str) -> str:
    return save_path + ".pinned"


def _legacy_tags_path(save_path: str) -> str:
    return save_path + ".tags.json"


def _legacy_gender_overrides_path(save_path: str) -> str:
    return save_path + ".gender_overrides.csv"


def _legacy_calibration_path(save_path: str) -> str:
    return save_path + ".calibration.json"


def _legacy_planner_state_path(save_path: str) -> str:
    return save_path + ".planner_state.json"


def _legacy_breeding_cache_path(save_path: str) -> str:
    return save_path + ".breeding_cache.json"


def _save_specific_sidecar_pairs(save_path: str) -> list[tuple[str, str]]:
    """Return [(new_path, legacy_path), ...] for every save-specific sidecar."""
    stem = Path(save_path).stem
    return [
        (
            os.path.join(APPDATA_CONFIG_DIR, stem + suffix),
            save_path + suffix,
        )
        for suffix in _SIDECAR_SUFFIXES
    ]


def migrate_sidecars_to_config_dir(save_path: str) -> None:
    """One-shot back-compat copy of save-specific sidecars into APPDATA_CONFIG_DIR.

    For each sidecar: if the new path is missing AND the legacy path exists,
    copies legacy -> new using shutil.copy2 (preserves mtimes). Never deletes
    the legacy file. BP sidecar (breed_priority.json) is not part of this
    migration — it was already in the config dir.
    """
    for new_path, legacy_path in _save_specific_sidecar_pairs(save_path):
        if os.path.exists(new_path):
            continue
        if not os.path.exists(legacy_path):
            continue
        try:
            shutil.copy2(legacy_path, new_path)
            logger.info("Migrated sidecar %s -> %s", legacy_path, new_path)
        except Exception:
            logger.warning(
                "Could not migrate sidecar %s -> %s",
                legacy_path, new_path, exc_info=True,
            )
