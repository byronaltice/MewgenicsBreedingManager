import os
import sys
from pathlib import Path
from types import SimpleNamespace

_proj_root = Path(__file__).resolve().parents[1]
_src_dir = _proj_root / "src"
sys.path.insert(0, str(_src_dir))
sys.path.insert(0, str(_proj_root))

import save_parser as sp
from save_parser import (
    _appearance_group_names,
    _appearance_preview_text,
    _read_visual_mutation_entries,
    _visual_mutation_chip_items,
)


def test_visual_mutation_chip_items_merge_duplicate_slots(monkeypatch):
    monkeypatch.setattr(sp, "load_visual_mutation_names", lambda: {})
    monkeypatch.setattr(sp, "_VISUAL_MUT_DATA", {"legs": {401: ("Mutation 401", "Fast")}})

    table = [0] * 72
    table[18] = 401
    table[23] = 401

    entries = _read_visual_mutation_entries(table)
    chips = _visual_mutation_chip_items(entries)

    assert chips == [
        (
            "Leg Mutation",
            "Leg Mutation (ID 401)\nLeg Mutation\nFast\nAffects: Left Leg, Right Leg",
            False,
        )
    ]


def test_visual_mutation_entries_use_part_birth_defect_label(monkeypatch):
    monkeypatch.setattr(sp, "load_visual_mutation_names", lambda: {("legs", 705): "club foot2"})
    monkeypatch.setattr(sp, "_VISUAL_MUT_DATA", {})

    table = [0] * 72
    table[18] = 705

    entries = _read_visual_mutation_entries(table)
    assert len(entries) == 1
    assert entries[0]["is_defect"] is True
    assert entries[0]["name"] == "Leg Birth Defect"


def test_appearance_group_names_and_preview_text():
    cat = SimpleNamespace(
        visual_mutation_entries=[
            {"group_key": "fur", "name": "Tabby"},
            {"group_key": "fur", "name": "Spotted"},
            {"group_key": "tail", "name": "Long"},
        ]
    )

    assert _appearance_group_names(cat, "fur") == ["Tabby", "Spotted"]
    assert _appearance_group_names(cat, "body") == ["Base Body"]
    assert _appearance_group_names(cat, "tail") == ["Long"]
    assert _appearance_preview_text(["Tabby"], ["Tabby"]) == "Likely Tabby"
    assert _appearance_preview_text(["Tabby"], ["Spotted"]) == "Probabilistic: Tabby or Spotted"
    assert _appearance_preview_text([], []) == "No distinct appearance data"
