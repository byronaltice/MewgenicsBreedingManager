import os
import sys
from types import SimpleNamespace

_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_proj_root, "src")
sys.path.insert(0, _src_dir)
sys.path.insert(0, _proj_root)

from room_optimizer import OptimizationParams, RoomConfig, RoomType, build_room_configs, optimize_room_distribution
from save_parser import STAT_NAMES


def _make_cat(
    db_key: int,
    *,
    gender: str,
    sexuality: str = "straight",
    room: str = "Floor1_Large",
    generation: int = 0,
    parent_a=None,
    parent_b=None,
    must_breed: bool = False,
    disorders=None,
    aggression: float = 0.3,
    libido: float = 0.7,
    stat_seed: int = 5,
):
    return SimpleNamespace(
        db_key=db_key,
        name=f"Cat{db_key}",
        gender=gender,
        sexuality=sexuality,
        gender_display=gender,
        status="In House",
        room=room,
        room_display=room,
        generation=generation,
        parent_a=parent_a,
        parent_b=parent_b,
        must_breed=must_breed,
        disorders=list(disorders or []),
        aggression=aggression,
        libido=libido,
        base_stats={stat: stat_seed for stat in STAT_NAMES},
        haters=[],
        lovers=[],
    )


def _room_for_cat(result, db_key: int) -> str | None:
    for assignment in result.rooms:
        if any(cat.db_key == db_key for cat in assignment.cats):
            return assignment.room.key
    return None


def test_build_room_configs_preserves_roles():
    configs = build_room_configs(
        [
            {"room": "Floor1_Large", "type": "breeding"},
            {"room": "Attic", "type": "fallback"},
        ],
        available_rooms=["Floor1_Large", "Attic"],
    )

    assert [cfg.key for cfg in configs] == ["Floor1_Large", "Attic"]
    assert configs[0].room_type == RoomType.BREEDING
    assert configs[1].room_type == RoomType.FALLBACK


def test_optimize_room_distribution_finds_same_sex_pair():
    cat_a = _make_cat(1, gender="male", sexuality="bi", must_breed=True, stat_seed=8)
    cat_b = _make_cat(2, gender="male", sexuality="bi", must_breed=True, stat_seed=8)
    cat_c = _make_cat(3, gender="female", sexuality="straight", stat_seed=4)

    room_configs = [
        RoomConfig("Floor1_Large", RoomType.BREEDING, 2, 50.0),
        RoomConfig("Attic", RoomType.FALLBACK, None, 50.0),
    ]
    result = optimize_room_distribution(
        [cat_a, cat_b, cat_c],
        room_configs,
        OptimizationParams(max_risk=10.0, avoid_lovers=False),
        cache=None,
        excluded_keys=set(),
    )

    paired_ids = {
        tuple(sorted((pair.cat_a.db_key, pair.cat_b.db_key)))
        for assignment in result.rooms
        for pair in assignment.pairs
    }

    assert (1, 2) in paired_ids
    assert result.stats.total_pairs >= 1


def test_optimize_room_distribution_enforces_risk_cutoff():
    cat_a = _make_cat(1, gender="male", sexuality="bi", stat_seed=6)
    cat_b = _make_cat(2, gender="female", sexuality="straight", stat_seed=6)

    room_configs = [
        RoomConfig("Floor1_Large", RoomType.BREEDING, 2, 50.0),
        RoomConfig("Attic", RoomType.FALLBACK, None, 50.0),
    ]
    result = optimize_room_distribution(
        [cat_a, cat_b],
        room_configs,
        OptimizationParams(max_risk=1.0, avoid_lovers=False),
        cache=None,
        excluded_keys=set(),
    )

    assert result.stats.total_pairs == 0
    assert all(not assignment.pairs for assignment in result.rooms)


def test_optimize_room_distribution_family_mode_separates_siblings():
    dad = _make_cat(1, gender="male", sexuality="bi")
    mom = _make_cat(2, gender="female", sexuality="bi")
    sibling_a = _make_cat(3, gender="male", sexuality="bi", parent_a=dad, parent_b=mom, generation=1)
    sibling_b = _make_cat(4, gender="female", sexuality="bi", parent_a=dad, parent_b=mom, generation=1)
    unrelated = _make_cat(5, gender="male", sexuality="bi")

    room_configs = [
        RoomConfig("Floor1_Large", RoomType.BREEDING, 6, 50.0),
        RoomConfig("Floor1_Small", RoomType.BREEDING, 6, 50.0),
        RoomConfig("Attic", RoomType.FALLBACK, None, 50.0),
    ]
    result = optimize_room_distribution(
        [dad, mom, sibling_a, sibling_b, unrelated],
        room_configs,
        OptimizationParams(mode_family=True, avoid_lovers=False),
        cache=None,
        excluded_keys=set(),
    )

    assert _room_for_cat(result, 3) != _room_for_cat(result, 4)
