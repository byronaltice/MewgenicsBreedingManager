"""Profile Compare — pure copy helpers (no Qt imports).

Functions here mutate the staged dict directly and are importable without
a Qt runtime, which makes them straightforward to reason about and test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ── Section field definitions ─────────────────────────────────────────────────

# Section key → list of top-level staged-dict keys to copy verbatim.
# Trait sections use the special "TRAIT:" prefix (handled in copy_section).
_SECTION_SIMPLE_KEYS: dict[str, list[str]] = {
    "name":            ["name"],
    "weights":         ["weights"],
    "complex_weights": ["complex_weights_enabled_ids"],
}

_TRAIT_SECTION_KEYS = frozenset({"active", "passive", "disorders", "good_mutations", "defects"})


# ── Section copy ──────────────────────────────────────────────────────────────

def copy_section(
    staged: dict[int, dict],
    section_key: str,
    src_slot: int,
    dst_slot: int,
    trait_list: list[str] | None = None,
) -> None:
    """Copy one section's data from src_slot to dst_slot within staged.

    For simple sections (name, weights, complex_weights): deep-copy the
    relevant top-level key(s) from source to destination.

    For trait sections (active, passive, disorders, good_mutations, defects):
    copy the ma_ratings entries for every trait in trait_list. Traits in
    trait_list that are absent from the source are explicitly removed from
    the destination so the destination mirrors the source exactly.

    Args:
        staged:      The shared staging dict, keyed by slot number.
        section_key: One of the keys in GROUP_TITLES (see constants.py).
        src_slot:    Source slot number.
        dst_slot:    Destination slot number.
        trait_list:  Required for trait sections; the list of trait keys
                     belonging to this section.
    """
    import copy as _copy

    src_blob = staged[src_slot]
    dst_blob = staged[dst_slot]

    if section_key in _SECTION_SIMPLE_KEYS:
        for key in _SECTION_SIMPLE_KEYS[section_key]:
            if key in src_blob:
                dst_blob[key] = _copy.deepcopy(src_blob[key])
            else:
                dst_blob.pop(key, None)

    elif section_key in _TRAIT_SECTION_KEYS:
        if trait_list is None:
            raise ValueError(f"trait_list is required for section_key={section_key!r}")
        src_ratings: dict = src_blob.get("ma_ratings") or {}
        if "ma_ratings" not in dst_blob or dst_blob["ma_ratings"] is None:
            dst_blob["ma_ratings"] = {}
        dst_ratings: dict = dst_blob["ma_ratings"]
        for trait in trait_list:
            if trait in src_ratings:
                dst_ratings[trait] = src_ratings[trait]
            else:
                dst_ratings.pop(trait, None)

    else:
        raise ValueError(f"Unknown section_key: {section_key!r}")


# ── Row copy ──────────────────────────────────────────────────────────────────

def copy_row(
    staged: dict[int, dict],
    value_getter,
    value_setter_fn,
    src_slot: int,
    dst_slot: int,
) -> None:
    """Copy a single row's value from src_slot to dst_slot.

    Uses value_getter to read from src and value_setter_fn(dst_blob, value)
    to write into dst's staged blob. The caller is responsible for updating
    the destination editor widget via RowDescriptor.value_setter.

    Args:
        staged:         The shared staging dict.
        value_getter:   Callable(blob) -> value; reads the row value.
        value_setter_fn: Callable(blob, value) -> None; writes to dst blob.
        src_slot:       Source slot number.
        dst_slot:       Destination slot number.
    """
    src_value = value_getter(staged[src_slot])
    value_setter_fn(staged[dst_slot], src_value)
