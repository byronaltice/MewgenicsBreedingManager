"""
Consolidated breeding pair evaluation helpers.

Deduplicates logic previously defined as nested functions in both
RoomOptimizerWorker and PerfectCatPlannerView.
"""

import logging
from typing import Optional
from save_parser import Cat, can_breed, risk_percent

logger = logging.getLogger("mewgenics.breeding")


def pair_key(a: Cat, b: Cat) -> tuple[int, int]:
    """Normalized pair key — smaller db_key first."""
    ak, bk = a.db_key, b.db_key
    return (ak, bk) if ak < bk else (bk, ak)


def is_hater_conflict(a: Cat, b: Cat,
                      hater_key_map: dict[int, set[int]]) -> bool:
    """Check if either cat hates the other."""
    return (b.db_key in hater_key_map.get(a.db_key, set()) or
            a.db_key in hater_key_map.get(b.db_key, set()))


def is_mutual_lover_pair(a: Cat, b: Cat,
                         lover_key_map: dict[int, set[int]]) -> bool:
    """Check if both cats are mutual lovers."""
    return (b.db_key in lover_key_map.get(a.db_key, set()) and
            a.db_key in lover_key_map.get(b.db_key, set()))


def is_lover_conflict(a: Cat, b: Cat,
                      lover_key_map: dict[int, set[int]],
                      avoid_lovers: bool) -> bool:
    """Check if pairing conflicts with existing lover relationships."""
    if not avoid_lovers:
        return False
    la = lover_key_map.get(a.db_key, set())
    lb = lover_key_map.get(b.db_key, set())
    return (la and b.db_key not in la) or (lb and a.db_key not in lb)


def trait_or_default(v: Optional[float], default: float = 0.5) -> float:
    """Clamp a trait value to [0, 1], using default if None."""
    return default if v is None else max(0.0, min(1.0, float(v)))


def personality_score(cats: list[Cat],
                      prefer_low_aggression: bool,
                      prefer_high_libido: bool) -> float:
    """Score personality traits for a group of cats."""
    score = 0.0
    n = len(cats)
    if not n:
        return 0.0
    if prefer_low_aggression:
        score += sum(1.0 - trait_or_default(c.aggression) for c in cats) / n
    if prefer_high_libido:
        score += sum(trait_or_default(c.libido) for c in cats) / n
    return score


def is_direct_family_pair(a: Cat, b: Cat,
                          parent_key_map: dict[int, set[int]]) -> bool:
    """Check if two cats are parent-child or siblings."""
    parents_a = parent_key_map.get(a.db_key, set())
    parents_b = parent_key_map.get(b.db_key, set())
    if a.db_key in parents_b or b.db_key in parents_a:
        return True
    return bool(parents_a & parents_b)


def evaluate_pair(a: Cat, b: Cat, *,
                  hater_key_map: dict[int, set[int]],
                  lover_key_map: dict[int, set[int]],
                  avoid_lovers: bool,
                  cache=None,
                  parent_key_map: Optional[dict[int, set[int]]] = None,
                  pair_eval_cache: Optional[dict] = None,
                  ) -> tuple[bool, str, float]:
    """
    Unified pair evaluation. Returns (can_breed, reason, risk_pct).

    Pass parent_key_map to enable direct-family checking (used by
    PerfectCatPlanner). Pass None to skip it (used by RoomOptimizer).
    """
    if pair_eval_cache is not None:
        key = pair_key(a, b)
        cached = pair_eval_cache.get(key)
        if cached is not None:
            return cached

    ok, reason = can_breed(a, b)

    if ok and parent_key_map is not None:
        if is_direct_family_pair(a, b, parent_key_map):
            ok, reason = False, "Direct family pair"

    if ok and is_hater_conflict(a, b, hater_key_map):
        ok, reason = False, "These cats hate each other"

    if ok:
        if cache is not None and cache.ready:
            risk = cache.risk_pct.get(cache._pair_key(a.db_key, b.db_key), 0.0)
        else:
            risk = risk_percent(a, b)
    else:
        risk = 0.0

    result = (ok, reason, risk)
    if pair_eval_cache is not None:
        pair_eval_cache[pair_key(a, b)] = result
    return result
