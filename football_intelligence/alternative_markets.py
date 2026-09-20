"""Alternative-market baseline helpers for corners and cards.

These are deliberately conservative descriptive models for scanner v1.
They estimate team/match rates from recent completed fixtures and convert
expected counts into over-line probabilities with a Poisson baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial
from statistics import mean
from typing import Iterable

from api_football import _get


@dataclass(frozen=True)
class CountMarketEstimate:
    market: str
    line: float
    expected: float | None
    probability_over: float | None
    sample_size: int
    quality: float
    reasons: tuple[str, ...] = ()


def _poisson_cdf(k: int, lam: float) -> float:
    if lam < 0:
        return 0.0
    return sum(exp(-lam) * (lam ** i) / factorial(i) for i in range(k + 1))


def probability_over_line(expected: float, line: float) -> float:
    """P(total > line) for half-goal/count lines such as 8.5 or 4.5."""
    threshold = int(line // 1)
    return max(0.0, min(1.0, 1.0 - _poisson_cdf(threshold, expected)))


def _stat(stats: list[dict], name: str) -> float | None:
    for item in stats:
        if item.get("type") != name:
            continue
        value = item.get("value")
        if value is None:
            return None
        try:
            return float(str(value).replace("%", ""))
        except Exception:
            return None
    return None


def _fixture_totals(fixture_id: int) -> tuple[float | None, float | None]:
    data = _get(f"fixtures/statistics?fixture={fixture_id}")
    if not data or len(data) < 2:
        return None, None

    home_stats = data[0].get("statistics", [])
    away_stats = data[1].get("statistics", [])

    h_corners = _stat(home_stats, "Corner Kicks")
    a_corners = _stat(away_stats, "Corner Kicks")
    h_yellow = _stat(home_stats, "Yellow Cards")
    a_yellow = _stat(away_stats, "Yellow Cards")
    h_red = _stat(home_stats, "Red Cards") or 0.0
    a_red = _stat(away_stats, "Red Cards") or 0.0

    corners = None
    if h_corners is not None and a_corners is not None:
        corners = h_corners + a_corners

    cards = None
    if h_yellow is not None and a_yellow is not None:
        # Red cards get a light extra weight rather than being ignored.
        cards = h_yellow + a_yellow + 1.5 * (h_red + a_red)

    return corners, cards


def _recent_completed_fixture_ids(team_id: int, limit: int = 8) -> list[int]:
    fixtures = _get(f"fixtures?team={team_id}&last={limit}")
    result: list[int] = []
    for item in fixtures:
        status = item.get("fixture", {}).get("status", {}).get("short")
        if status not in {"FT", "AET", "PEN"}:
            continue
        fixture_id = item.get("fixture", {}).get("id")
        if fixture_id:
            result.append(int(fixture_id))
    return result


def _collect_team_totals(team_id: int, limit: int = 8) -> tuple[list[float], list[float]]:
    corners: list[float] = []
    cards: list[float] = []
    for fixture_id in _recent_completed_fixture_ids(team_id, limit=limit):
        c, y = _fixture_totals(fixture_id)
        if c is not None:
            corners.append(c)
        if y is not None:
            cards.append(y)
    return corners, cards


def _blend(home_values: Iterable[float], away_values: Iterable[float]) -> tuple[float | None, int]:
    home = list(home_values)
    away = list(away_values)
    sample = min(len(home), len(away))
    if not home or not away:
        return None, sample
    return (mean(home) + mean(away)) / 2.0, sample


def _quality(sample_size: int) -> float:
    return max(0.0, min(1.0, sample_size / 8.0))


def estimate_corners_and_cards(jogo: dict, recent_matches: int = 8) -> dict[str, CountMarketEstimate]:
    home_id = jogo.get("casa_id")
    away_id = jogo.get("fora_id")
    if not home_id or not away_id:
        return {}

    home_corners, home_cards = _collect_team_totals(int(home_id), limit=recent_matches)
    away_corners, away_cards = _collect_team_totals(int(away_id), limit=recent_matches)

    expected_corners, corner_sample = _blend(home_corners, away_corners)
    expected_cards, card_sample = _blend(home_cards, away_cards)

    output: dict[str, CountMarketEstimate] = {}

    for line in (7.5, 8.5, 9.5, 10.5, 11.5):
        output[f"corners_over_{str(line).replace('.', '_')}"] = CountMarketEstimate(
            market="TOTAL_CORNERS",
            line=line,
            expected=expected_corners,
            probability_over=(
                probability_over_line(expected_corners, line)
                if expected_corners is not None else None
            ),
            sample_size=corner_sample,
            quality=_quality(corner_sample),
            reasons=() if expected_corners is not None else ("missing_recent_corner_data",),
        )

    for line in (2.5, 3.5, 4.5, 5.5):
        output[f"cards_over_{str(line).replace('.', '_')}"] = CountMarketEstimate(
            market="TOTAL_CARDS",
            line=line,
            expected=expected_cards,
            probability_over=(
                probability_over_line(expected_cards, line)
                if expected_cards is not None else None
            ),
            sample_size=card_sample,
            quality=_quality(card_sample),
            reasons=() if expected_cards is not None else ("missing_recent_card_data",),
        )

    return output
