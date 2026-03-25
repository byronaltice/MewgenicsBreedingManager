import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from contextlib import contextmanager

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

_proj_root = Path(__file__).resolve().parents[1]
_src_dir = _proj_root / "src"
sys.path.insert(0, str(_src_dir))
sys.path.insert(0, str(_proj_root))

import mewgenics_manager as mm
from mewgenics_manager import (
    BreedingCache,
    _apply_calibration_data,
    _effective_thresholds_for_cats,
    _learn_gender_token_map,
    _load_calibration_data,
    _load_threshold_preferences,
    _load_gender_overrides,
    _save_calibration_data,
    _save_threshold_preferences,
)


def _make_cat(
    uid: str,
    name: str,
    *,
    gender: str = "male",
    status: str = "In House",
    gender_source: str = "sex_code",
    gender_token: str = "",
    age: float = 1.0,
    aggression: float = 0.2,
    libido: float = 0.3,
    inbredness: float = 0.1,
    sexuality: str = "straight",
    base_stats: dict | None = None,
):
    return SimpleNamespace(
        unique_id=uid,
        name=name,
        gender=gender,
        status=status,
        gender_source=gender_source,
        gender_token=gender_token,
        age=age,
        aggression=aggression,
        libido=libido,
        inbredness=inbredness,
        sexuality=sexuality,
        base_stats=dict(base_stats or {stat: 3 for stat in mm.STAT_NAMES}),
    )


@contextmanager
def _workspace_temp_dir():
    base = _proj_root / "tmp" / "_codex_test_runs"
    base.mkdir(parents=True, exist_ok=True)
    path = base / uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_find_save_files_orders_by_mtime(monkeypatch):
    with _workspace_temp_dir() as td:
        root = td / "library"
        old_save = root / "ProfileA" / "saves" / "old.sav"
        new_save = root / "ProfileB" / "saves" / "new.sav"
        old_save.parent.mkdir(parents=True)
        new_save.parent.mkdir(parents=True)
        old_save.write_text("old", encoding="utf-8")
        new_save.write_text("new", encoding="utf-8")
        os.utime(old_save, (1_700_000_000, 1_700_000_000))
        os.utime(new_save, (1_700_000_100, 1_700_000_100))

        monkeypatch.setattr(mm, "_save_root_dir", lambda: str(root))

        result = mm.find_save_files()
        assert [Path(path).name for path in result] == ["new.sav", "old.sav"]


def test_load_gender_overrides_prefers_uid_then_unique_name():
    with _workspace_temp_dir() as td:
        save_path = td / "profile" / "test.sav"
        save_path.parent.mkdir(parents=True)
        save_path.write_text("", encoding="utf-8")

        cats = [
            _make_cat("0x1", "Alpha", gender="female"),
            _make_cat("0x2", "Bravo", gender="male"),
            _make_cat("0x3", "Shared", gender="male"),
            _make_cat("0x4", "Shared", gender="female"),
        ]

        sidecar = Path(str(save_path) + ".gender_overrides.csv")
        sidecar.write_text(
            "gender,unique_id,name\n"
            "M,0x1,\n"
            "f,,Bravo\n"
            "male,,Shared\n"
            "n/a,,Alpha\n",
            encoding="utf-8",
        )

        applied, rows_read = _load_gender_overrides(str(save_path), cats)

        assert (applied, rows_read) == (2, 4)
        assert cats[0].gender == "male"
        assert cats[1].gender == "female"
        assert cats[2].gender == "male"
        assert cats[3].gender == "female"


def test_calibration_round_trip_and_application():
    with _workspace_temp_dir() as td:
        save_path = td / "profile" / "test.sav"
        save_path.parent.mkdir(parents=True)
        save_path.write_text("", encoding="utf-8")

        learned_cats = [
            _make_cat("0x1", "A", gender_source="token_fallback", gender_token="tok"),
            _make_cat("0x2", "B", gender_source="token_fallback", gender_token="tok"),
            _make_cat("0x3", "C", gender_source="token_fallback", gender_token="tok"),
            _make_cat("0x4", "D", gender_source="token_fallback", gender_token="tok"),
            _make_cat("0x5", "E", gender_source="token_fallback", gender_token="tok"),
        ]
        learned_overrides = {
            "0x1": {"gender": "male"},
            "0x2": {"gender": "male"},
            "0x3": {"gender": "male"},
            "0x4": {"gender": "female"},
            "0x5": {"gender": "male"},
        }
        assert _learn_gender_token_map(learned_cats, learned_overrides) == {"tok": "male"}

        cats = [
            _make_cat("0x10", "TokenCat", gender="male", gender_source="token_fallback", gender_token="tok"),
            _make_cat(
                "0x11",
                "ExplicitCat",
                gender="male",
                gender_source="sex_code",
                age=2.0,
                aggression=0.2,
                libido=0.8,
                inbredness=0.15,
            ),
            _make_cat("0x12", "GoneCat", gender="female", status="Gone", gender_source="token_fallback", gender_token="tok"),
        ]
        overrides = {
            "0x11": {
                "gender": "F",
                "age": "7",
                "aggression": "high",
                "libido": "low",
                "inbredness": "extreme",
                "sexuality": "gay",
                "base_stats": {"STR": 10, "DEX": "11", "BAD": 99},
            },
            "0x12": {"gender": "male"},
        }
        payload = {"version": 1, "overrides": overrides, "gender_token_map": {"tok": "female"}}

        assert _save_calibration_data(str(save_path), payload)
        assert _load_calibration_data(str(save_path)) == payload

        explicit, token_applied, override_rows = _apply_calibration_data(payload, cats)

        assert (explicit, token_applied, override_rows) == (1, 1, 2)
        assert cats[0].gender == "female"
        assert cats[1].gender == "female"
        assert cats[1].age == 7.0
        assert cats[1].aggression == 1.0
        assert cats[1].libido == 0.0
        assert cats[1].inbredness == 0.85
        assert cats[1].sexuality == "gay"
        assert cats[1].base_stats["STR"] == 10
        assert cats[1].base_stats["DEX"] == 11
        assert "BAD" not in cats[1].base_stats
        assert cats[2].gender == "female"


def test_breeding_cache_round_trip():
    with _workspace_temp_dir() as td:
        save_path = td / "profile" / "test.sav"
        save_path.parent.mkdir(parents=True)
        save_path.write_text("seed", encoding="utf-8")

        cat_a = _make_cat("0x1", "A")
        cat_a.db_key = 1
        cat_a.parent_a = None
        cat_a.parent_b = None
        cat_b = _make_cat("0x2", "B")
        cat_b.db_key = 2
        cat_b.parent_a = None
        cat_b.parent_b = None
        signature = mm._breeding_save_signature([cat_a, cat_b])

        cache = BreedingCache()
        cache.ready = True
        cache.risk_pct[(1, 2)] = 12.5
        cache.shared_counts[(1, 2)] = (3, 1)
        cache.save_to_disk(str(save_path), signature)

        loaded = BreedingCache.load_from_disk(str(save_path), signature)
        assert loaded is not None
        assert loaded.ready is True

        assert loaded.get_risk(cat_a, cat_b) == 12.5
        assert loaded.get_shared(cat_a, cat_b) == (3, 1)
        assert BreedingCache.load_from_disk(str(save_path), "bogus-signature") is None


def test_breeding_cache_uses_pedigree_coi_memo_when_risk_missing():
    cache = BreedingCache()
    cache.ready = True
    cache.pedigree_coi_memos[(1, 2)] = 0.25

    cat_a = _make_cat("0x1", "A")
    cat_a.db_key = 1
    cat_b = _make_cat("0x2", "B")
    cat_b.db_key = 2

    expected = mm._combined_malady_chance(0.25) * 100.0
    assert cache.get_risk(cat_a, cat_b) == pytest.approx(expected)


def test_threshold_preferences_round_trip_and_curve_math(monkeypatch):
    with _workspace_temp_dir() as td:
        config_path = td / "settings.json"
        monkeypatch.setattr(mm, "APPDATA_CONFIG_DIR", str(td))
        monkeypatch.setattr(mm, "APP_CONFIG_PATH", str(config_path))

        prefs = {
            "exceptional_sum_threshold": 40,
            "donation_sum_threshold": 34,
            "donation_max_top_stat": 6,
            "adaptive_enabled": True,
            "adaptive_reference_avg_sum": 28.0,
            "adaptive_curve_strength": 0.2,
        }
        assert _save_threshold_preferences(prefs)
        assert _load_threshold_preferences() == prefs

        cats = [
            _make_cat("0x1", "A", base_stats={stat: 6 for stat in mm.STAT_NAMES}),
            _make_cat("0x2", "B", base_stats={stat: 4 for stat in mm.STAT_NAMES}),
        ]

        exceptional, donation, top_stat, avg_sum = _effective_thresholds_for_cats(prefs, cats)

        assert avg_sum == 35.0
        assert (exceptional, donation, top_stat) == (40, 34, 6)


def test_start_breeding_cache_uses_save_signature_for_disk_lookup(monkeypatch):
    with _workspace_temp_dir() as td:
        save_path = td / "profile" / "test.sav"
        save_path.parent.mkdir(parents=True)
        save_path.write_text("seed", encoding="utf-8")

        class _SignalStub:
            def connect(self, _slot):
                return None

        class _DummyProgress:
            def __init__(self):
                self.values = []
                self.visible = False
                self.formats = []

            def setValue(self, value):
                self.values.append(value)

            def show(self):
                self.visible = True

            def setFormat(self, text):
                self.formats.append(text)

        class _DummyWorker:
            def __init__(self, cats, save_path="", existing_pairwise=None, prev_cache=None, prev_parent_keys=None, save_signature=None, pedigree_coi_memos=None, parent=None):
                self.cats = cats
                self.save_path = save_path
                self.existing_pairwise = existing_pairwise
                self.prev_cache = prev_cache
                self.prev_parent_keys = prev_parent_keys
                self.save_signature = save_signature
                self.pedigree_coi_memos = pedigree_coi_memos
                self.parent = parent
                self.progress = _SignalStub()
                self.phase1_ready = _SignalStub()
                self.finished_cache = _SignalStub()
                self.finished = _SignalStub()
                self.started = False

            def start(self):
                self.started = True

            def quit(self):
                return None

            def wait(self, _timeout):
                return None

        seen = {}

        def _load_from_disk(_path, expected_signature=None):
            seen["path"] = _path
            seen["signature"] = expected_signature
            return None

        monkeypatch.setattr(mm.BreedingCache, "load_from_disk", staticmethod(_load_from_disk))
        monkeypatch.setattr(mm, "BreedingCacheWorker", _DummyWorker)

        window = mm.MainWindow.__new__(mm.MainWindow)
        window._breeding_cache = None
        window._cache_worker = None
        window._current_save = str(save_path)
        window._cache_progress = _DummyProgress()
        window._prev_parent_keys = {}
        alpha = _make_cat("0x1", "Alpha")
        alpha.db_key = 1
        alpha.parent_a = None
        alpha.parent_b = None
        window._cats = [alpha]
        window._only_display_changed = lambda cats: False
        window._source_model = SimpleNamespace(set_breeding_cache=lambda cache: None)
        window._safe_breeding_view = None
        window._room_optimizer_view = None
        window._perfect_planner_view = None

        mm.MainWindow._start_breeding_cache(window, window._cats)

        assert isinstance(window._cache_worker, _DummyWorker)
        assert window._cache_worker.existing_pairwise is None
        assert window._cache_worker.started is True
        assert window._cache_progress.visible is True
        assert seen["path"] == str(save_path)
        assert seen["signature"] == mm._breeding_save_signature(window._cats)
        assert window._cache_worker.save_signature == mm._breeding_save_signature(window._cats)
