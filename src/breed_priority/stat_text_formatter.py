"""Stat text formatting — emoji substitution and tooltip summary extraction.

Standalone module — no imports from mewgenics_manager to avoid circular deps.
"""

import re as _re


class StatTextFormatter:
    """Formats stat abbreviations, mutation tooltips, and ability tooltips into
    emoji-rich display strings."""

    EMOJI = {
        "STR": "💪", "str": "💪",
        "DEX": "🏹", "dex": "🏹",
        "CON": "🧡", "con": "🧡",
        "INT": "💡", "int": "💡",
        "SPD": "👟", "spd": "👟",
        "CHA": "👄", "cha": "👄",
        "LCK": "☘️", "lck": "☘️",
    }

    _STAT_NAMES = ("STR", "DEX", "CON", "INT", "SPD", "CHA", "LCK",
                   "str", "dex", "con", "int", "spd", "cha", "lck")

    @staticmethod
    def _sort_parts(desc: str) -> str:
        """Sort comma-separated stat parts so positives come before negatives."""
        parts = [p.strip() for p in desc.split(",")]
        if len(parts) <= 1:
            return desc
        parts.sort(key=lambda p: 1 if p.lstrip().startswith("-") else 0)
        return ", ".join(parts)

    @staticmethod
    def _extract_english(text: str) -> str:
        """Extract only the English portion from a possibly multi-locale string."""
        if ".," in text:
            text = text.split(".,")[0]
        return text.rstrip(".")

    @classmethod
    def emojify(cls, desc: str) -> str:
        """Sort stat parts (positives first), replace stat abbreviations with emoji.

        e.g. '-1 LCK, +2 DEX' → '+2🏹, -1☘️'
             '+1 Holy Shield'  → '+1 Holy Shield'  (unchanged)
        """
        if not desc:
            return desc
        result = cls._sort_parts(desc)
        for name in cls._STAT_NAMES:
            if name in result:
                result = _re.sub(r'\b' + _re.escape(name) + r'\b', cls.EMOJI[name], result)
        result = _re.sub(r'(\+?-?\d+)\s+([^\x00-\x7F])', r'\1\2', result)
        return result

    @classmethod
    def mutation_summary(cls, tip: str) -> str:
        """Extract the stat effect line from a mutation tooltip.

        Mutation tooltips have the format:
            'Body Eyes Mutation (ID 300)\\nBody Mutation\\n+2 DEX, -1 LCK'
        We want just the stat effect part (last line if it contains +/- numbers).
        """
        if not tip:
            return ""
        for line in reversed(tip.strip().split("\n")):
            line = line.strip()
            if not line:
                continue
            if _re.search(r'[+-]\d+\s*\w', line):
                return cls.emojify(cls._extract_english(line))
            for stat_name in cls.EMOJI:
                if stat_name in line:
                    return cls.emojify(cls._extract_english(line))
        return ""

    @classmethod
    def ability_summary(cls, tip: str) -> str:
        """Extract a short summary from an ability tooltip.

        Ability tips may be multi-line. First line is typically the short description.
        Replace stat names with emoji.
        """
        if not tip:
            return ""
        return cls.emojify(tip.strip().split("\n")[0].strip())
