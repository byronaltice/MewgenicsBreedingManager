"""Pure Party Builder scoring and preview logic."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import CATEGORIES, CLASS_NAMES, CLASS_RATINGS, DEFAULT_MIN_SCORE, LETTER_TO_SCORE, MAX_PARTY_SIZE


@dataclass(frozen=True)
class PartyGap:
    category: str
    current_total: int
    missing_points: int


@dataclass(frozen=True)
class RecommendationEntry:
    class_name: str
    total: int
    contribution: dict[str, int]


def _letter_value(letter: str) -> int:
    return LETTER_TO_SCORE[letter.upper()]


def class_score(class_name: str) -> dict[str, int]:
    ratings = CLASS_RATINGS[class_name]
    return {
        category: _letter_value(rating) if isinstance(rating, str) else int(rating)
        for category, rating in ratings.items()
    }


def party_totals(party: list[str]) -> dict[str, int]:
    totals = {category: 0 for category in CATEGORIES}
    for class_name in party:
        class_totals = class_score(class_name)
        for category in CATEGORIES:
            totals[category] += class_totals[category]
    return totals


def balance_gaps(party: list[str], min_score: int = DEFAULT_MIN_SCORE) -> list[PartyGap]:
    totals = party_totals(party)
    return [
        PartyGap(category, totals[category], max(0, min_score - totals[category]))
        for category in CATEGORIES
    ]


def party_is_balanced(party: list[str], min_score: int = DEFAULT_MIN_SCORE) -> bool:
    return all(gap.missing_points == 0 for gap in balance_gaps(party, min_score=min_score))


def candidate_contribution(candidate: str, party: list[str], min_score: int = DEFAULT_MIN_SCORE) -> dict[str, int]:
    totals = party_totals(party)
    class_totals = class_score(candidate)
    contribution: dict[str, int] = {}
    for category in CATEGORIES:
        missing = max(0, min_score - totals[category])
        contribution[category] = min(class_totals[category], missing)
    return contribution


def recommend_classes(party: list[str], min_score: int = DEFAULT_MIN_SCORE) -> list[RecommendationEntry]:
    recommendations = [
        RecommendationEntry(
            class_name=class_name,
            total=sum(contribution.values()),
            contribution=contribution,
        )
        for class_name in CLASS_NAMES
        for contribution in [candidate_contribution(class_name, party, min_score=min_score)]
    ]
    recommendations.sort(key=lambda entry: (-entry.total, entry.class_name))
    return recommendations


def recommendation_total_range(entries: list[RecommendationEntry]) -> tuple[int, int]:
    if not entries:
        return 0, 0
    return entries[-1].total, entries[0].total


def preview_party(party: list[str], preview_class: str | None, max_party_size: int = MAX_PARTY_SIZE) -> list[str]:
    preview = list(party)
    if preview_class is not None and len(preview) < max_party_size:
        preview.append(preview_class)
    return preview
