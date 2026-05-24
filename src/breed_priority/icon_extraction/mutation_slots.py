"""Canonical mutation slot list.

The save parser (``src/save_parser.py``) groups visual mutations by a
``group_key`` field on each entry in ``Cat.visual_mutation_entries``. This
module exposes the canonical list of those group keys, the
short abbreviation used in placeholder glyphs, and a normalization helper
so callers can pass any case/form (e.g. ``"Body"`` or ``"BODY"``) and have
it resolve to the canonical key used on disk.

Sources cross-checked:
  * ``_VISUAL_MUTATION_FIELDS`` in ``src/save_parser.py`` — runtime data.
  * GON filenames under ``defect-investigation/game-files/resources/
    gpak-text/data/mutations/`` (body, ears, eyebrows, eyes, head, legs,
    mouth, tail, texture).
  * ``src/visual_mutation_catalog.py`` fallback table keys.

Note: ``texture.gon`` in the gpak corresponds to the parser's ``fur``
group key. ``arms`` has no dedicated GON (it shares ``legs.gon``) but is a
distinct ``group_key`` in parsed data, so it gets its own placeholder.
"""

from __future__ import annotations

# Canonical slot identifiers (must match ``group_key`` produced by
# ``_read_visual_mutation_entries`` in save_parser.py).
SLOT_BODY = "body"
SLOT_HEAD = "head"
SLOT_TAIL = "tail"
SLOT_LEGS = "legs"
SLOT_ARMS = "arms"
SLOT_EYES = "eyes"
SLOT_EYEBROWS = "eyebrows"
SLOT_EARS = "ears"
SLOT_MOUTH = "mouth"
SLOT_FUR = "fur"

MUTATION_SLOTS: tuple[str, ...] = (
    SLOT_BODY,
    SLOT_HEAD,
    SLOT_TAIL,
    SLOT_LEGS,
    SLOT_ARMS,
    SLOT_EYES,
    SLOT_EYEBROWS,
    SLOT_EARS,
    SLOT_MOUTH,
    SLOT_FUR,
)

# Two-letter glyph rendered on each placeholder PNG. Chosen for at-a-glance
# distinctness (Eb vs. Ey vs. Er, Lg vs. Ar).
SLOT_GLYPH: dict[str, str] = {
    SLOT_BODY: "Bd",
    SLOT_HEAD: "Hd",
    SLOT_TAIL: "Tl",
    SLOT_LEGS: "Lg",
    SLOT_ARMS: "Ar",
    SLOT_EYES: "Ey",
    SLOT_EYEBROWS: "Eb",
    SLOT_EARS: "Er",
    SLOT_MOUTH: "Mo",
    SLOT_FUR: "Fu",
}


def normalize_slot(slot: str) -> str | None:
    """Return the canonical slot key for any case/form, or ``None`` if unknown."""
    if not slot:
        return None
    key = slot.strip().lower()
    return key if key in SLOT_GLYPH else None
