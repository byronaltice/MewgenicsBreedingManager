import os
import sys
import uuid
from types import SimpleNamespace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_proj_root, "src")
sys.path.insert(0, _src_dir)
sys.path.insert(0, _proj_root)

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QApplication, QTableWidgetItem

import mewgenics_manager as mm
from save_parser import STAT_NAMES


def _make_cat(
    db_key: int,
    *,
    unique_id: str,
    gender_display: str,
    name: str,
    room: str = "1st FL L",
    room_display: str = "1st FL L",
    status: str = "In House",
    age: int = 3,
    generation: int = 0,
    aggression: float = 0.2,
    libido: float = 0.8,
    inbredness: float = 0.1,
    lovers=None,
    mutations=None,
    passive_abilities=None,
    disorders=None,
    abilities=None,
):
    class _HashableNamespace(SimpleNamespace):
        def __hash__(self):
            return hash(self.db_key)

    return _HashableNamespace(
        db_key=db_key,
        unique_id=unique_id,
        name=name,
        gender=gender_display,
        gender_display=gender_display,
        status=status,
        room=room,
        room_display=room_display,
        age=age,
        generation=generation,
        must_breed=False,
        is_blacklisted=False,
        parent_a=None,
        parent_b=None,
        haters=[],
        base_stats={stat: 6 for stat in STAT_NAMES},
        aggression=aggression,
        libido=libido,
        inbredness=inbredness,
        lovers=list(lovers or []),
        mutations=list(mutations or []),
        passive_abilities=list(passive_abilities or []),
        disorders=list(disorders or []),
        abilities=list(abilities or []),
        tags=[],
    )


def _make_tracker_row(pair_index: int, cat_a, cat_b, children: list):
    projection = {
        "stat_ranges": {stat: (4, 6) for stat in STAT_NAMES},
        "expected_stats": {stat: 5.5 for stat in STAT_NAMES},
        "sum_range": (34, 42),
    }
    return {
        "pair_index": pair_index,
        "cat_a": cat_a,
        "cat_b": cat_b,
        "known_offspring": children,
        "projection": projection,
        "risk": 2.0,
        "coi": 0.0,
        "shared": (0, 0),
        "source": "using",
        "slot_index": 0,
    }


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture()
def planner_config(monkeypatch):
    scratch_root = Path(_proj_root) / "_codex_test_write"
    config_path = scratch_root / f"planner-settings-{uuid.uuid4().hex}.json"
    monkeypatch.setattr(mm, "APPDATA_CONFIG_DIR", str(scratch_root))
    monkeypatch.setattr(mm, "APP_CONFIG_PATH", str(config_path))
    yield config_path
    config_path.unlink(missing_ok=True)


def test_selected_offspring_config_round_trip(planner_config):
    state = {"uid-a|uid-b": "uid-child"}
    mm._save_perfect_planner_selected_offspring(state)
    assert mm._load_perfect_planner_selected_offspring() == state


def test_foundation_pairs_config_round_trip(planner_config):
    config = [
        {"cat_a_uid": "uid-a", "cat_b_uid": "uid-b", "using": True},
        {"cat_a_uid": "uid-c", "cat_b_uid": "uid-d", "using": False},
        {"cat_a_uid": "", "cat_b_uid": "", "using": False},
        {"cat_a_uid": "uid-e", "cat_b_uid": "uid-f", "using": True},
        {"cat_a_uid": "uid-g", "cat_b_uid": "uid-h", "using": False},
        {"cat_a_uid": "uid-i", "cat_b_uid": "uid-j", "using": True},
    ]
    mm._save_perfect_planner_foundation_pairs(config)
    loaded = mm._load_perfect_planner_foundation_pairs()

    assert len(loaded) == 6
    assert loaded[0] == {"cat_a_uid": "uid-a", "cat_b_uid": "uid-b", "using": True}
    assert loaded[5] == {"cat_a_uid": "uid-i", "cat_b_uid": "uid-j", "using": True}


def test_foundation_panel_slot_count_updates_visible_rows(qt_app, planner_config):
    panel = mm.PerfectPlannerFoundationPairsPanel()
    panel.set_slot_count(3)

    assert panel._slot_count == 3
    assert len(panel._slots) == 3
    assert all(not slot["use_btn"].isEnabled() for slot in panel._slots)


def test_suggested_foundation_pairs_do_not_override_auto_plan(qt_app, planner_config, monkeypatch):
    cats = [
        _make_cat(1, unique_id="uid-a", gender_display="M", name="Alpha"),
        _make_cat(2, unique_id="uid-b", gender_display="F", name="Bravo"),
        _make_cat(3, unique_id="uid-c", gender_display="M", name="Charlie"),
        _make_cat(4, unique_id="uid-d", gender_display="F", name="Delta"),
    ]

    def _fake_score_pair_factors(cat_a, cat_b, *args, **kwargs):
        names = {cat_a.name, cat_b.name}
        if names == {"Charlie", "Delta"}:
            score = 7.0
            locked = list(STAT_NAMES)
            missing = []
        elif names == {"Alpha", "Bravo"}:
            score = 1.0
            locked = []
            missing = list(STAT_NAMES)
        else:
            score = 2.0
            locked = STAT_NAMES[:2]
            missing = STAT_NAMES[2:]

        projection = {
            "stat_ranges": {stat: (6, 7) for stat in STAT_NAMES},
            "expected_stats": {stat: 6.5 for stat in STAT_NAMES},
            "sum_range": (42, 49),
            "seven_plus_total": score,
            "locked_stats": locked,
            "reachable_stats": list(STAT_NAMES),
            "missing_stats": missing,
            "distance_total": 0.0,
        }
        return SimpleNamespace(
            compatible=True,
            risk=0.0,
            projection=projection,
            personality_bonus=0.0,
        )

    monkeypatch.setattr(mm, "score_pair_factors", _fake_score_pair_factors)
    monkeypatch.setattr(mm, "planner_pair_allows_breeding", lambda *args, **kwargs: True)

    view = mm.PerfectCatPlannerView()
    view.set_cats(cats)
    view._starter_pairs_input.setValue(1)
    view._foundation_panel.set_config([
        {"cat_a_uid": "uid-a", "cat_b_uid": "uid-b", "using": False},
    ])

    view._calculate_plan()

    stage_data = view._table.item(0, 0).data(Qt.UserRole)
    assert stage_data["actions"][0]["target"].startswith("Suggested: Charlie (M) x Delta (F)")


def test_using_foundation_pairs_override_auto_plan(qt_app, planner_config, monkeypatch):
    cats = [
        _make_cat(1, unique_id="uid-a", gender_display="M", name="Alpha"),
        _make_cat(2, unique_id="uid-b", gender_display="F", name="Bravo"),
        _make_cat(3, unique_id="uid-c", gender_display="M", name="Charlie"),
        _make_cat(4, unique_id="uid-d", gender_display="F", name="Delta"),
    ]

    def _fake_score_pair_factors(cat_a, cat_b, *args, **kwargs):
        names = {cat_a.name, cat_b.name}
        if names == {"Charlie", "Delta"}:
            score = 7.0
            locked = list(STAT_NAMES)
            missing = []
        elif names == {"Alpha", "Bravo"}:
            score = 1.0
            locked = []
            missing = list(STAT_NAMES)
        else:
            score = 2.0
            locked = STAT_NAMES[:2]
            missing = STAT_NAMES[2:]

        projection = {
            "stat_ranges": {stat: (6, 7) for stat in STAT_NAMES},
            "expected_stats": {stat: 6.5 for stat in STAT_NAMES},
            "sum_range": (42, 49),
            "seven_plus_total": score,
            "locked_stats": locked,
            "reachable_stats": list(STAT_NAMES),
            "missing_stats": missing,
            "distance_total": 0.0,
        }
        return SimpleNamespace(
            compatible=True,
            risk=0.0,
            projection=projection,
            personality_bonus=0.0,
        )

    monkeypatch.setattr(mm, "score_pair_factors", _fake_score_pair_factors)
    monkeypatch.setattr(mm, "planner_pair_allows_breeding", lambda *args, **kwargs: True)

    view = mm.PerfectCatPlannerView()
    view.set_cats(cats)
    view._starter_pairs_input.setValue(1)
    view._foundation_panel.set_config([
        {"cat_a_uid": "uid-a", "cat_b_uid": "uid-b", "using": True},
    ])

    view._calculate_plan()

    stage_data = view._table.item(0, 0).data(Qt.UserRole)
    assert stage_data["actions"][0]["target"].startswith("Using these: Alpha (M) x Bravo (F)")


def test_planner_view_uses_split_layout_and_tabs(qt_app, planner_config):
    view = mm.PerfectCatPlannerView()

    assert view._splitter.orientation() == Qt.Vertical
    assert view._bottom_splitter.orientation() == Qt.Horizontal
    assert view._bottom_tabs.count() == 4
    assert view._bottom_tabs.currentIndex() == 0
    assert view._bottom_splitter.widget(0) is view._details_pane
    assert view._bottom_tabs.widget(0) is view._guide_panel
    assert view._bottom_tabs.widget(1) is view._foundation_panel
    assert view._bottom_tabs.widget(2) is view._offspring_tracker
    assert view._bottom_tabs.widget(3) is view._cat_locator
    headers = [
        view._details_pane._actions_table.horizontalHeaderItem(i).text()
        for i in range(view._details_pane._actions_table.columnCount())
    ]
    assert headers == ["Target", "7s", "Risk%"]


def test_cat_locator_includes_offspring_and_pair_colors(qt_app):
    parent_a = _make_cat(1, unique_id="uid-a", gender_display="M", name="Alpha")
    parent_b = _make_cat(2, unique_id="uid-b", gender_display="F", name="Bravo")
    child = _make_cat(3, unique_id="uid-c", gender_display="F", name="Kid", age=1)
    parent_c = _make_cat(4, unique_id="uid-d", gender_display="M", name="Charlie")
    parent_d = _make_cat(5, unique_id="uid-e", gender_display="F", name="Delta")

    locator = mm.RoomOptimizerCatLocator()
    locator.show_assignments([
        {
            "name": parent_a.name,
            "gender_display": parent_a.gender_display,
            "db_key": parent_a.db_key,
            "has_lover": True,
            "tags": [],
            "age": parent_a.age,
            "current_room": "1st FL L",
            "assigned_room": "Pair 1",
            "room_order": 0,
            "needs_move": False,
        },
        {
            "name": parent_b.name,
            "gender_display": parent_b.gender_display,
            "db_key": parent_b.db_key,
            "has_lover": False,
            "tags": [],
            "age": parent_b.age,
            "current_room": "1st FL L",
            "assigned_room": "Pair 1",
            "room_order": 0,
            "needs_move": False,
        },
        {
            "name": child.name,
            "gender_display": child.gender_display,
            "db_key": child.db_key,
            "has_lover": False,
            "tags": [],
            "age": child.age,
            "current_room": "1st FL L",
            "assigned_room": "Pair 1 offspring",
            "room_order": 0.2,
            "needs_move": False,
        },
        {
            "name": parent_c.name,
            "gender_display": parent_c.gender_display,
            "db_key": parent_c.db_key,
            "has_lover": False,
            "tags": [],
            "age": parent_c.age,
            "current_room": "2nd FL R",
            "assigned_room": "Pair 2",
            "room_order": 1,
            "needs_move": False,
        },
        {
            "name": parent_d.name,
            "gender_display": parent_d.gender_display,
            "db_key": parent_d.db_key,
            "has_lover": False,
            "tags": [],
            "age": parent_d.age,
            "current_room": "2nd FL R",
            "assigned_room": "Pair 2",
            "room_order": 1,
            "needs_move": False,
        },
    ])

    assert locator._table.rowCount() == 5
    assert any("♥" in locator._table.item(row, 0).text() for row in range(locator._table.rowCount()))
    assert locator._table.item(2, 0).text().startswith("Kid")
    first_color = locator._table.item(0, 0).background().color()
    assert first_color == locator._table.item(1, 0).background().color()
    assert first_color == locator._table.item(2, 0).background().color()
    assert first_color != locator._table.item(3, 0).background().color()


def test_foundation_config_changed_schedules_plan_refresh(qt_app, planner_config, monkeypatch):
    refresh_calls = []

    def _fake_calculate_plan(self):
        refresh_calls.append(self)

    monkeypatch.setattr(mm.PerfectCatPlannerView, "_calculate_plan", _fake_calculate_plan)
    view = mm.PerfectCatPlannerView()
    view.set_cats([_make_cat(1, unique_id="uid-a", gender_display="M", name="Oguzok")])

    view._foundation_panel.configChanged.emit()
    for _ in range(5):
        qt_app.processEvents()
        QThread.msleep(25)
    qt_app.processEvents()

    assert refresh_calls == [view]


def test_room_optimizer_restores_state_and_reuses_imported_traits(qt_app, planner_config, monkeypatch):
    saved_traits = [{"category": "mutation", "key": "twoedarm", "display": "[Mutation] Two-Toed Arm", "weight": 3}]
    mm._save_ui_state("mutation_planner_state", {"selected_traits": saved_traits, "last_mode": "multi"})
    mm._save_ui_state(
        "room_optimizer_state",
        {
            "min_stats": "120",
            "max_risk": "15.5",
            "mode_family": True,
            "use_sa": True,
            "has_run": True,
        },
    )

    calls = []
    monkeypatch.setattr(
        mm.RoomOptimizerView,
        "_calculate_optimal_distribution",
        lambda self, use_sa=False: calls.append(use_sa),
    )

    view = mm.RoomOptimizerView()
    view.set_planner_view(SimpleNamespace(get_selected_traits=lambda: list(saved_traits)))
    view.set_cats([
        _make_cat(1, unique_id="uid-a", gender_display="M", name="Alpha"),
        _make_cat(2, unique_id="uid-b", gender_display="F", name="Bravo"),
    ])

    assert view._min_stats_input.text() == "120"
    assert view._max_risk_input.text() == "15.5"
    assert view._mode_toggle_btn.isChecked() is True
    assert view._planner_traits == saved_traits
    assert calls == [True]


def test_perfect_planner_restores_last_session_and_autoruns(qt_app, planner_config, monkeypatch):
    mm._save_ui_state(
        "perfect_planner_state",
        {
            "min_stats": "110",
            "max_risk": "25.0",
            "starter_pairs": 6,
            "stimulation": 42,
            "use_sa": True,
            "avoid_lovers": True,
            "prefer_low_aggression": False,
            "prefer_high_libido": True,
            "has_run": True,
        },
    )

    calls = []
    monkeypatch.setattr(mm.PerfectCatPlannerView, "_calculate_plan", lambda self: calls.append(self))

    view = mm.PerfectCatPlannerView()
    view.set_cats([
        _make_cat(1, unique_id="uid-a", gender_display="M", name="Alpha"),
        _make_cat(2, unique_id="uid-b", gender_display="F", name="Bravo"),
    ])

    assert view._min_stats_input.text() == "110"
    assert view._max_risk_input.text() == "25.0"
    assert view._starter_pairs_input.value() == 6
    assert view._stimulation_input.value() == 42
    assert view._deep_optimize_btn.isChecked() is True
    assert view._avoid_lovers_checkbox.isChecked() is True
    assert view._prefer_low_aggression_checkbox.isChecked() is False
    assert view._prefer_high_libido_checkbox.isChecked() is True
    assert calls == [view]


def test_mutation_planner_restores_saved_traits_and_plan_mode(qt_app, planner_config, monkeypatch):
    saved_traits = [
        {"category": "mutation", "key": "twoedarm", "display": "[Mutation] Two-Toed Arm", "weight": 4},
        {"category": "ability", "key": "pawmissile", "display": "[Ability] Paw Missile", "weight": -1},
    ]
    mm._save_ui_state(
        "mutation_planner_state",
        {
            "room": "1st FL L",
            "stim": 72,
            "selected_traits": saved_traits,
            "last_mode": "multi",
        },
    )

    calls = []
    monkeypatch.setattr(
        mm.MutationDisorderPlannerView,
        "_update_multi_trait_plan",
        lambda self: calls.append([dict(t) for t in self._selected_traits]),
    )

    view = mm.MutationDisorderPlannerView()
    view.set_cats([
        _make_cat(
            1,
            unique_id="uid-a",
            gender_display="M",
            name="Alpha",
            room="1st FL L",
            mutations=["twoedarm"],
            abilities=["pawmissile"],
        ),
        _make_cat(
            2,
            unique_id="uid-b",
            gender_display="F",
            name="Bravo",
            room="1st FL L",
            mutations=["twoedarm"],
            abilities=["pawmissile"],
        ),
    ])

    assert view._room_combo.currentData() == "1st FL L"
    assert view._stim_spin.value() == 72
    assert view._selected_traits == saved_traits
    assert calls == [saved_traits]


def test_offspring_tracker_selection_is_exclusive_and_persistent(qt_app, planner_config):
    parent_a = _make_cat(1, unique_id="uid-a", gender_display="M", name="Oguzok")
    parent_b = _make_cat(2, unique_id="uid-b", gender_display="F", name="Molly Moo")
    child_one = _make_cat(3, unique_id="uid-c1", gender_display="F", name="Krita", age=1)
    child_two = _make_cat(4, unique_id="uid-c2", gender_display="M", name="Trigger", age=1)
    rows = [_make_tracker_row(1, parent_a, parent_b, [child_one, child_two])]

    tracker = mm.PerfectPlannerOffspringTracker()
    tracker.set_rows(rows)
    tracker._on_cell_clicked(0, 3)

    assert tracker._table.item(0, 3).text() == "☑"
    assert tracker._table.item(1, 3).text() == "☐"
    assert mm._load_perfect_planner_selected_offspring() == {"uid-a|uid-b": "uid-c1"}

    restored = mm.PerfectPlannerOffspringTracker()
    restored.set_rows(rows)
    assert restored._table.item(0, 3).text() == "☑"
    assert restored._table.item(1, 3).text() == "☐"

    restored._on_cell_clicked(1, 3)
    assert restored._table.item(0, 3).text() == "☐"
    assert restored._table.item(1, 3).text() == "☑"
    assert mm._load_perfect_planner_selected_offspring() == {"uid-a|uid-b": "uid-c2"}


def test_offspring_selection_updates_stage_details_and_requests_refresh(qt_app, planner_config, monkeypatch):
    refresh_calls = []

    def _fake_refresh(self):
        refresh_calls.append(self)

    monkeypatch.setattr(mm.PerfectCatPlannerView, "_request_plan_refresh", _fake_refresh)
    view = mm.PerfectCatPlannerView()

    details_calls = []
    monkeypatch.setattr(
        view._details_pane,
        "show_stage",
        lambda data, context_note=None: details_calls.append((data, context_note)),
    )

    stage_data = {
        "stage": "Stage 1",
        "details": "Best unrelated pairs to start pushing 7s immediately",
        "summary": "Stage summary",
        "notes": ["note one"],
        "actions": [],
    }
    item = QTableWidgetItem("Stage 1")
    item.setData(Qt.UserRole, stage_data)
    view._table.setRowCount(1)
    view._table.setItem(0, 0, item)
    view._selected_stage_row = 0

    parent_a = _make_cat(1, unique_id="uid-a", gender_display="M", name="Oguzok")
    parent_b = _make_cat(2, unique_id="uid-b", gender_display="F", name="Molly Moo")
    child = _make_cat(3, unique_id="uid-c1", gender_display="F", name="Krita", age=1)
    row = {"pair": {"cat_a": parent_a, "cat_b": parent_b, "known_offspring": [child]}, "child": child}

    view._on_offspring_selected(row)

    assert refresh_calls == [view]
    assert details_calls
    assert details_calls[-1][0] == stage_data
    assert "Selected offspring pair: Oguzok x Molly Moo" in details_calls[-1][1]
    assert "Selected: Krita" in details_calls[-1][1]
