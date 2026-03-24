"""Room optimization logic for Mewgenics breeding."""

from .types import (
    DEFAULT_ROOM_CONFIGS,
    OptimizationParams,
    OptimizationResult,
    OptimizationStats,
    RoomAssignment,
    RoomConfig,
    RoomType,
    ScoredPair,
)
from .optimizer import build_room_configs, optimize_room_distribution, score_pair

__all__ = [
    "DEFAULT_ROOM_CONFIGS",
    "OptimizationParams",
    "OptimizationResult",
    "OptimizationStats",
    "RoomAssignment",
    "RoomConfig",
    "RoomType",
    "ScoredPair",
    "build_room_configs",
    "optimize_room_distribution",
    "score_pair",
]
