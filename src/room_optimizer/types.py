"""Data models for the room optimizer."""

from dataclasses import dataclass, field
from enum import Enum

from save_parser import Cat


class RoomType(Enum):
    """Room designation types used by the optimizer."""

    BREEDING = "breeding"
    FALLBACK = "fallback"
    GENERAL = "general"
    NONE = "none"


@dataclass
class RoomConfig:
    """Configuration for a single room."""

    key: str
    room_type: RoomType
    max_cats: int | None
    base_stim: float = 50.0

    @property
    def display_name(self) -> str:
        from save_parser import ROOM_DISPLAY

        return ROOM_DISPLAY.get(self.key, self.key)


@dataclass
class ScoredPair:
    """A breeding pair with score metadata."""

    cat_a: Cat
    cat_b: Cat
    risk: float
    quality: float


@dataclass
class RoomAssignment:
    """Cats assigned to a room."""

    room: RoomConfig
    cats: list[Cat]
    pairs: list[ScoredPair]
    eternal_youth_cats: list[Cat] = field(default_factory=list)


@dataclass
class OptimizationParams:
    """Optimizer configuration."""

    min_stats: int = 0
    max_risk: float = 10.0
    stimulation: float = 50.0
    maximize_throughput: bool = False
    minimize_variance: bool = True
    avoid_lovers: bool = True
    prefer_low_aggression: bool = True
    prefer_high_libido: bool = True
    mode_family: bool = False
    use_sa: bool = False
    sa_temperature: float = 8.0
    sa_cooling_rate: float = 0.95
    sa_neighbors_per_temp: int = 120
    risk_barrier_lambda: float = 20.0
    move_penalty_weight: float = 0.5
    planner_traits: list[dict] = field(default_factory=list)


@dataclass
class OptimizationStats:
    """Summary statistics for an optimization run."""

    total_cats: int
    assigned_cats: int
    total_pairs: int
    breeding_rooms_used: int
    general_rooms_used: int
    avg_pair_quality: float
    avg_risk_percent: float


@dataclass
class OptimizationResult:
    """Final optimizer output."""

    rooms: list[RoomAssignment]
    excluded_cats: list[Cat]
    stats: OptimizationStats


DEFAULT_ROOM_CONFIGS = [
    RoomConfig("Floor1_Large", RoomType.BREEDING, 6, 50.0),
    RoomConfig("Floor1_Small", RoomType.BREEDING, 6, 50.0),
    RoomConfig("Attic", RoomType.FALLBACK, None, 50.0),
    RoomConfig("Floor2_Large", RoomType.NONE, None, 50.0),
    RoomConfig("Floor2_Small", RoomType.NONE, None, 50.0),
]
