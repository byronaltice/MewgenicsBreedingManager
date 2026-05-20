"""Breed Priority — cat name-tag symbol display helpers.

Maps ``cat.name_tag`` string values (assigned in-game UI markers) to
a Unicode emoji and a human-readable friendly name used in tooltips.

Possible name_tag values (20 known):
  ""            → no symbol (show nothing)
  Stat icons:   str, dex, con, int, spd, cha, lck
  Room stats:   stimulation, comfort, appeal, health, evolution
  Shapes/misc:  star2, circle, triangle, sword, shield2, poop
  Unknown:      any other value → shown as [tag] fallback
"""

from typing import NamedTuple


class _SymbolInfo(NamedTuple):
    emoji: str
    friendly: str


# Maps name_tag value → (emoji, friendly label)
_SYMBOL_MAP: dict[str, _SymbolInfo] = {
    # Stat icons — reuse the same emoji as StatTextFormatter
    "str":         _SymbolInfo("💪", "Muscle (STR)"),
    "dex":         _SymbolInfo("🏹", "Bow (DEX)"),
    "con":         _SymbolInfo("🧡", "Heart (CON)"),
    "int":         _SymbolInfo("💡", "Light Bulb (INT)"),
    "spd":         _SymbolInfo("👟", "Boot (SPD)"),
    "cha":         _SymbolInfo("👄", "Lips (CHA)"),
    "lck":         _SymbolInfo("☘️", "Clover (LCK)"),
    # Room-stat icons
    "stimulation": _SymbolInfo("🧶", "Yarn (Stimulation)"),
    "comfort":     _SymbolInfo("😴", "Sleeping Cat (Comfort)"),
    "appeal":      _SymbolInfo("🏠", "House (Appeal)"),
    "health":      _SymbolInfo("⚕️", "Caduceus (Health)"),
    "evolution":   _SymbolInfo("🧬", "DNA (Evolution)"),
    # Shape / object icons
    "star2":       _SymbolInfo("⭐", "Star"),
    "star":        _SymbolInfo("⭐", "Star"),
    "circle":      _SymbolInfo("⭕", "Circle"),
    "square":      _SymbolInfo("🟦", "Square"),
    "triangle":    _SymbolInfo("🔺", "Triangle"),
    "sword":       _SymbolInfo("⚔️", "Sword"),
    "shield2":     _SymbolInfo("🛡️", "Shield"),
    "shield":      _SymbolInfo("🛡️", "Shield"),
    "poop":        _SymbolInfo("💩", "Poop"),
}

_SYMBOL_TOOLTIP_PREFIX = "Symbol: "


def symbol_emoji(name_tag: str) -> str:
    """Return the display emoji for a name_tag, or '' if none."""
    if not name_tag:
        return ""
    info = _SYMBOL_MAP.get(name_tag)
    if info is not None:
        return info.emoji
    # Unknown tag — show nothing (graceful fallback)
    return f"[{name_tag}]"


def symbol_friendly(name_tag: str) -> str:
    """Return a human-readable label for use in tooltips, or '' if none."""
    if not name_tag:
        return ""
    info = _SYMBOL_MAP.get(name_tag)
    if info is not None:
        return _SYMBOL_TOOLTIP_PREFIX + info.friendly
    return _SYMBOL_TOOLTIP_PREFIX + name_tag


def format_name_with_symbol(cat_name: str, name_tag: str) -> str:
    """Return the cat name with its symbol emoji appended (space-separated).

    If name_tag is empty or maps to no display, returns cat_name unchanged.
    """
    emoji = symbol_emoji(name_tag)
    if not emoji:
        return cat_name
    return f"{cat_name} {emoji}"
