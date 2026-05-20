"""Breed Priority — cat name-tag symbol display helpers.

Maps ``cat.name_tag`` string values (assigned in-game UI markers) to
a human-readable friendly name used in tooltips, and provides lazy-
loaded QPixmap access to the matching in-game icon PNG.

Possible name_tag values (20 known):
  ""            → no symbol (show nothing)
  Stat icons:   str, dex, con, int, spd, cha, lck
  Room stats:   stimulation, comfort, appeal, health, evolution
  Shapes/misc:  star2, circle, triangle, sword, shield2, poop
  Unknown:      any other value → shown as [tag] fallback

Asset layout:
  src/breed_priority/assets/symbols/<name_tag>.png
  Exception: "con" tag maps to "con_.png" (Windows reserved name).
"""

import pathlib

# PySide6 import is deferred to symbol_pixmap() to keep this module
# importable in headless / non-Qt contexts (e.g. investigation scripts).

# ── Asset location ────────────────────────────────────────────────────────────

_ASSETS_DIR = pathlib.Path(__file__).parent / "assets" / "symbols"

# Windows reserves the filename CON; the asset is stored as con_.png.
_CON_TAG      = "con"
_CON_FILENAME = "con_.png"

_SYMBOL_TOOLTIP_PREFIX = "Symbol: "


# ── Friendly name mapping ─────────────────────────────────────────────────────

# Maps name_tag value → human-readable friendly label for tooltips.
_FRIENDLY: dict[str, str] = {
    # Stat icons
    "str":         "Muscle (STR)",
    "dex":         "Bow (DEX)",
    "con":         "Heart (CON)",
    "int":         "Light Bulb (INT)",
    "spd":         "Boot (SPD)",
    "cha":         "Lips (CHA)",
    "lck":         "Clover (LCK)",
    # Room-stat icons
    "stimulation": "Yarn (Stimulation)",
    "comfort":     "Sleeping Cat (Comfort)",
    "appeal":      "House (Appeal)",
    "health":      "Caduceus (Health)",
    "evolution":   "DNA (Evolution)",
    # Shape / object icons
    "star2":       "Star",
    "star":        "Star",
    "circle":      "Circle",
    "square":      "Square",
    "triangle":    "Triangle",
    "sword":       "Sword",
    "shield2":     "Shield",
    "shield":      "Shield",
    "poop":        "Poop",
}


def symbol_friendly(name_tag: str) -> str:
    """Return a human-readable tooltip label for name_tag, or '' if none."""
    if not name_tag:
        return ""
    label = _FRIENDLY.get(name_tag)
    if label is not None:
        return _SYMBOL_TOOLTIP_PREFIX + label
    return _SYMBOL_TOOLTIP_PREFIX + name_tag


# ── Pixmap cache ──────────────────────────────────────────────────────────────

# Populated lazily by symbol_pixmap().  None sentinel means "tried and failed".
_pixmap_cache: dict[str, object] = {}


def _asset_path(name_tag: str) -> pathlib.Path:
    """Return the filesystem path for name_tag's PNG asset."""
    filename = _CON_FILENAME if name_tag == _CON_TAG else f"{name_tag}.png"
    return _ASSETS_DIR / filename


def symbol_pixmap(name_tag: str):
    """Return a QPixmap for name_tag, or None if the tag is empty / unknown.

    Results are cached after the first load.  Returns None on any error
    (missing file, unsupported format, no Qt display).
    """
    if not name_tag:
        return None

    if name_tag in _pixmap_cache:
        cached = _pixmap_cache[name_tag]
        return None if cached is None else cached

    asset = _asset_path(name_tag)
    if not asset.exists():
        _pixmap_cache[name_tag] = None
        return None

    try:
        from PySide6.QtGui import QPixmap
        px = QPixmap(str(asset))
        result = px if not px.isNull() else None
    except Exception:
        result = None

    _pixmap_cache[name_tag] = result
    return result
