"""Breed Priority — scoring helpers and main scoring function.

Standalone module — no imports from mewgenics_manager to avoid circular deps.
"""

from .constants import (
    BREED_PRIORITY_WEIGHTS, BREED_PRIORITY_TIERS, SCORE_COLUMNS,
    TRAIT_LOW_THRESHOLD, TRAIT_HIGH_THRESHOLD,
    _STAT_COL_NAMES,
)


# ── Scoring helpers ───────────────────────────────────────────────────────────

class ScoreResult:
    __slots__ = ("total", "tier", "tier_color", "breakdown", "subtotals",
                 "scope_relatives_count")

    def __init__(self, total: float, tier: str, tier_color: str, breakdown: list,
                 subtotals: dict | None = None, scope_relatives_count: int = 0):
        self.total = total
        self.tier = tier
        self.tier_color = tier_color
        self.breakdown = breakdown
        self.subtotals = subtotals or {}
        self.scope_relatives_count = scope_relatives_count


def priority_tier(score: float) -> tuple:
    for threshold, label, color in BREED_PRIORITY_TIERS:
        if threshold is None or score >= threshold:
            return label, color
    return "Cull", "#e04040"


def is_basic_trait(name: str) -> bool:
    """Return True for generic starter traits that should be ignored."""
    return name.lower().startswith("basic")


def ability_base(name: str) -> str:
    """Strip trailing '2' if present (e.g. 'Vurp2' → 'Vurp'). When Breeding, we only care about the base ability."""
    if len(name) > 1 and name[-1] == "2":
        return name[:-1]
    return name


def compute_breed_priority_score(cat, scope_cats: list, ma_ratings: dict,
                         stat_names: list, weights: dict = None,
                         mutation_display_name=None,
                         scope_stat_sums: list = None,
                         hated_by: list = None) -> ScoreResult:
    """Compute breed priority score for a cat.

    stat_names: ordered list of stat keys (e.g. ["STR","DEX",...]).
    mutation_display_name: callable(str) -> str for display labels in breakdown.
    ma_ratings: {trait_key: int} where 1=Desirable, 0=Neutral, -1=Undesirable.
      Ability keys are base ability names; mutation keys are display strings.
    scope_stat_sums: sorted list of total base-stat sums for all scope cats,
      used to compute percentile rank for stat_sum scoring.
    hated_by: list of cats (in scope/room) that have *this* cat as their rival.
    """
    _w = weights if weights is not None else BREED_PRIORITY_WEIGHTS
    _display = mutation_display_name if mutation_display_name else (lambda n: n)
    breakdown: list = []
    subtotals: dict = {
        "stat_7": 0.0, "stat_7_count": 0.0, "unique_ma_max": 0.0,
        "low_aggression": 0.0, "high_aggression": 0.0,
        "unknown_gender": 0.0,
        "high_libido": 0.0, "low_libido": 0.0,
        "no_children": 0.0, "many_children": 0.0,
        "stat_sum": 0.0, "age_penalty": 0.0,
        "love_interest": 0.0, "rivalry": 0.0,
    }
    scope_set = {id(c) for c in scope_cats}
    _cat_in_scope = id(cat) in scope_set

    # ── Positive attributes ───────────────────────────────────────────────────
    if cat.gender == "?":
        breakdown.append(("Unknown gender (?)", _w["unknown_gender"]))
        subtotals["unknown_gender"] = _w["unknown_gender"]

    if cat.aggression is not None and cat.aggression < TRAIT_LOW_THRESHOLD:
        breakdown.append(("Low aggression", _w["low_aggression"]))
        subtotals["low_aggression"] = _w["low_aggression"]

    if cat.libido is not None and cat.libido >= TRAIT_HIGH_THRESHOLD:
        breakdown.append(("High libido", _w["high_libido"]))
        subtotals["high_libido"] = _w["high_libido"]

    _sex = getattr(cat, 'sexuality', 'straight') or 'straight'
    if _sex == 'gay' and _w.get("gay_pref", 0.0) != 0.0:
        breakdown.append(("Gay", _w["gay_pref"]))
        subtotals["gay_pref"] = _w["gay_pref"]
    elif _sex == 'bi' and _w.get("bi_pref", 0.0) != 0.0:
        breakdown.append(("Bi", _w["bi_pref"]))
        subtotals["bi_pref"] = _w["bi_pref"]

    _TARGET_N = int(round(_w.get("stat_7_threshold", 7.0)))  # cats with a 7 before score scales down
    _STAT7_BASE = _w["stat_7"]
    for stat_name in stat_names:
        if cat.base_stats.get(stat_name) == 7:
            n_scope = sum(1 for c in scope_cats if c.base_stats.get(stat_name) == 7)
            n = n_scope if _cat_in_scope else n_scope + 1
            # Sole owner of a 7 in this stat - extra bonus
            if n == 1:
                w = _w["stat_7"] * 2
                label = f"7 in {stat_name} (sole ★★)"
            # Full user weight up to target; beyond target, overflow portion
            # uses the default base weight so user increases favour the first 7
            elif n <= _TARGET_N:
                w = _w["stat_7"]
                label = f"7 in {stat_name} ({n} in scope)"
            else:
                w = round(_STAT7_BASE * _TARGET_N / n, 3)
                label = f"7 in {stat_name} ({n} in scope, ÷{n / _TARGET_N:.1f})"
            breakdown.append((label, float(w)))
            subtotals["stat_7"] += float(w)

    # ── 7-count bonus: scaled by how many 7's this cat personally owns ────────
    _w_7ct = _w.get("stat_7_count", 0.0)
    if _w_7ct != 0.0:
        _n_sevens = sum(1 for sn in stat_names if cat.base_stats.get(sn) == 7)
        if _n_sevens > 0:
            _7ct_pts = round(_w_7ct * _n_sevens, 3)
            _s = "s" if _n_sevens != 1 else ""
            breakdown.append((f"{_n_sevens} stat{_s} at 7", _7ct_pts))
            subtotals["stat_7_count"] = _7ct_pts

    # Combined trait set per scope cat (ability base names + mutation display strings)
    scope_base_traits = {
        id(c): (
            {ability_base(a) for a in list(c.abilities) + list(c.passive_abilities) + list(getattr(c, 'disorders', []))}
            | set(c.mutations)
            | set(getattr(c, 'defects', []))
        )
        for c in scope_cats
    }
    _u = _w["unique_ma_max"]

    # Score abilities (active + passive), normalized to base names
    all_ability_bases = list({
        ability_base(m) for m in list(cat.abilities) + list(cat.passive_abilities) + list(getattr(cat, 'disorders', []))
        if not is_basic_trait(m)
    })
    def _score_trait(label: str, rating, n: int):
        if rating in (None, 0):
            return
        if n == 1:
            if rating == 2:
                pts = 10 * _u
                tag = "Sole owner (top priority)"
            elif rating == 1:
                pts = 2 * _u
                tag = "Sole owner (desirable)"
            else:
                pts = -_u
                tag = "Sole owner (undesirable)"
        elif rating == 2:
            pts = round(5 * _u / n, 3)
            tag = f"Top Priority (÷{n})"
        elif rating == 1:
            pts = round(_u / n, 3)
            tag = f"Desirable (÷{n})"
        elif rating == -1:
            pts = -_u
            tag = "Undesirable"
        else:
            return
        breakdown.append((f"{tag}: {label}", pts))
        subtotals["unique_ma_max"] += pts

    for ma in all_ability_bases:
        rating = ma_ratings.get(ma)
        n_scope = sum(1 for c in scope_cats if ma in scope_base_traits[id(c)])
        n = max(1, n_scope if _cat_in_scope else n_scope + 1)
        _score_trait(_display(ma), rating, n)

    # Score visual mutations (keyed by display string from cat.mutations)
    for ma in cat.mutations:
        if is_basic_trait(ma):
            continue
        rating = ma_ratings.get(ma)
        n_scope = sum(1 for c in scope_cats if ma in scope_base_traits[id(c)])
        n = max(1, n_scope if _cat_in_scope else n_scope + 1)
        _score_trait(ma, rating, n)

    # Score birth defects (visual mutation IDs 700-706)
    for ma in getattr(cat, 'defects', []):
        if is_basic_trait(ma):
            continue
        rating = ma_ratings.get(ma)
        n_scope = sum(1 for c in scope_cats if ma in scope_base_traits[id(c)])
        n = max(1, n_scope if _cat_in_scope else n_scope + 1)
        _score_trait(ma, rating, n)

    # ── Negative attributes ───────────────────────────────────────────────────
    if cat.aggression is not None and cat.aggression >= TRAIT_HIGH_THRESHOLD:
        breakdown.append(("High aggression", _w["high_aggression"]))
        subtotals["high_aggression"] = _w["high_aggression"]

    if cat.libido is not None and cat.libido < TRAIT_LOW_THRESHOLD:
        breakdown.append(("Low libido", _w["low_libido"]))
        subtotals["low_libido"] = _w["low_libido"]

    # Genetic Novelty: no relatives in comparison scope
    relatives_in_scope: list = []
    frontier = [cat]
    visited = {id(cat)}
    while frontier:
        node = frontier.pop()
        for rel in [node.parent_a, node.parent_b] + list(node.children):
            if rel is None or id(rel) in visited:
                continue
            visited.add(id(rel))
            if id(rel) in scope_set and id(rel) != id(cat):
                relatives_in_scope.append(rel)
                frontier.append(rel)
    children_in_scope = [c for c in cat.children if id(c) in scope_set]

    if not relatives_in_scope:
        breakdown.append(("Genetic Novelty", _w["no_children"]))
        subtotals["no_children"] = _w["no_children"]
    if len(children_in_scope) >= 4:
        breakdown.append((
            f"{len(children_in_scope)} children in scope (≥4)",
            _w["many_children"],
        ))
        subtotals["many_children"] = _w["many_children"]

    # ── Stat sum percentile scoring ───────────────────────────────────────────
    w_sum = _w.get("stat_sum", 0.0)
    if w_sum != 0 and scope_stat_sums:
        cat_sum = sum(cat.base_stats.values())
        n = len(scope_stat_sums)
        rank = sum(1 for v in scope_stat_sums if v <= cat_sum)
        pct = rank / n * 100
        if pct >= 90:
            pts = w_sum
        elif pct >= 75:
            pts = max(0.0, w_sum - 1)
        elif pct >= 50:
            pts = max(0.0, w_sum - 2)
        else:
            pts = 0.0
        if pts:
            breakdown.append((f"Stat sum {cat_sum} ({pct:.0f}th percentile)", pts))
            subtotals["stat_sum"] = pts

    # ── Age penalty ───────────────────────────────────────────────────────────
    w_age = _w.get("age_penalty", 0.0)
    if w_age != 0.0:
        age = getattr(cat, 'age', None)
        if age is not None:
            _age_thr = int(round(_w.get("age_threshold", 10.0)))
            if age > _age_thr:
                _over = age - _age_thr
                _mult = 1 + (_over - 1) // 3
                pts = round(_mult * w_age, 2)
                breakdown.append((f"Age {age} (+{_over} over threshold, {_mult}×)", pts))
                subtotals["age_penalty"] = pts

    # ── Love interest bonus ────────────────────────────────────────────────────
    w_love = _w.get("love_interest", 0.0)
    if w_love != 0.0:
        for lover in getattr(cat, 'lovers', []):
            if id(lover) in scope_set:
                pts = round(w_love, 2)
                breakdown.append((f"Loves {lover.name} (in scope)", pts))
                subtotals["love_interest"] = pts
                break  # flat bonus - only once

    # ── Rivalry penalty ────────────────────────────────────────────────────────
    w_rival = _w.get("rivalry", 0.0)
    if w_rival != 0.0:
        _rival_total = 0.0
        # Cat's own rivals in scope
        for hater in getattr(cat, 'haters', []):
            if id(hater) in scope_set:
                pts = round(w_rival, 2)
                breakdown.append((f"Hates {hater.name} (in scope)", pts))
                _rival_total += pts
        # Cats in scope that hate this cat (reverse)
        for hater in (hated_by or []):
            if id(hater) in scope_set and hater not in getattr(cat, 'haters', []):
                pts = round(w_rival, 2)
                breakdown.append((f"Hated by {hater.name} (in scope)", pts))
                _rival_total += pts
        if _rival_total:
            subtotals["rivalry"] = _rival_total

    # ── Love interest (room) bonus ─────────────────────────────────────────────
    w_love_room = _w.get("love_interest_room", 0.0)
    if w_love_room != 0.0:
        _cat_room = getattr(cat, 'room', None)
        if _cat_room:
            for lover in getattr(cat, 'lovers', []):
                if getattr(lover, 'room', None) == _cat_room:
                    pts = round(w_love_room, 2)
                    breakdown.append((f"Loves {lover.name} (in room)", pts))
                    subtotals["love_interest_room"] = pts
                    break

    # ── Rivalry (room) penalty ─────────────────────────────────────────────────
    w_rival_room = _w.get("rivalry_room", 0.0)
    if w_rival_room != 0.0:
        _cat_room = getattr(cat, 'room', None)
        if _cat_room:
            _rr_total = 0.0
            for hater in getattr(cat, 'haters', []):
                if getattr(hater, 'room', None) == _cat_room:
                    pts = round(w_rival_room, 2)
                    breakdown.append((f"Hates {hater.name} (in room)", pts))
                    _rr_total += pts
            for hater in (hated_by or []):
                if hater not in getattr(cat, 'haters', []) and getattr(hater, 'room', None) == _cat_room:
                    pts = round(w_rival_room, 2)
                    breakdown.append((f"Hated by {hater.name} (in room)", pts))
                    _rr_total += pts
            if _rr_total:
                subtotals["rivalry_room"] = _rr_total

    total = sum(pts for _, pts in breakdown)
    tier, color = priority_tier(total)
    return ScoreResult(total=total, tier=tier, tier_color=color,
                       breakdown=breakdown, subtotals=subtotals,
                       scope_relatives_count=len(relatives_in_scope))
