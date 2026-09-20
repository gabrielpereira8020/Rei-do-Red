"""Deterministic live intelligence baseline for Rei-do-Red.

This first live model updates the pre-game expectation using remaining time and
current live pressure. It is intentionally conservative and independent from the
LLM. The LLM can explain the result afterwards, but does not set probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial

from .models import MatchContext


@dataclass(frozen=True)
class LiveMarketSignal:
    key: str
    label: str
    probability: float
    fair_odds: float | None
    status: str
    reason: str


@dataclass(frozen=True)
class LiveIntelligenceResult:
    fixture_id: int
    minute: int
    home_goals: int
    away_goals: int
    pressure_home: float
    pressure_away: float
    remaining_home_goals: float
    remaining_away_goals: float
    data_quality: float
    model_quality: float
    signals: tuple[LiveMarketSignal, ...]


def _fair_odds(p: float) -> float | None:
    return None if p <= 0 else 1.0 / p


def _poisson_cdf(k: int, lam: float) -> float:
    return sum(exp(-lam) * (lam ** i) / factorial(i) for i in range(k + 1))


def _prob_at_least(lam: float, n: int) -> float:
    if n <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - _poisson_cdf(n - 1, lam)))


def _status(probability: float, data_quality: float, model_quality: float) -> str:
    if data_quality < 0.60:
        return "INSUFFICIENT_DATA"
    if model_quality < 0.35:
        return "WATCH"
    if probability >= 0.72:
        return "STRONG_WATCH"
    if probability >= 0.60:
        return "WATCH"
    return "NO_BET"


def _pressure_score(shots: int | None, sot: int | None, corners: int | None) -> float:
    return float((sot or 0) * 6 + (corners or 0) * 3 + (shots or 0) * 2)


def analyze_live(context: MatchContext, pregame_home_xg: float, pregame_away_xg: float) -> LiveIntelligenceResult:
    live = context.live
    if live is None or live.minute is None:
        raise ValueError("live state with minute is required")

    minute = max(1, min(int(live.minute), 120))
    home_goals = int(live.home_goals or 0)
    away_goals = int(live.away_goals or 0)
    remaining_fraction = max(0.02, (95 - min(minute, 95)) / 95.0)

    pressure_home = _pressure_score(live.home_shots, live.home_shots_on_target, live.home_corners)
    pressure_away = _pressure_score(live.away_shots, live.away_shots_on_target, live.away_corners)
    total_pressure = max(1.0, pressure_home + pressure_away)
    share_home = pressure_home / total_pressure
    share_away = pressure_away / total_pressure

    # Conservative live adjustment around the pre-game prior.
    home_modifier = 0.80 + 0.40 * share_home
    away_modifier = 0.80 + 0.40 * share_away

    if home_goals < away_goals:
        home_modifier *= 1.08
    elif home_goals > away_goals:
        away_modifier *= 1.08

    rem_home = max(0.0, pregame_home_xg * remaining_fraction * home_modifier)
    rem_away = max(0.0, pregame_away_xg * remaining_fraction * away_modifier)
    rem_total = rem_home + rem_away

    observed_fields = [
        live.home_shots, live.away_shots,
        live.home_shots_on_target, live.away_shots_on_target,
        live.home_corners, live.away_corners,
        live.home_cards, live.away_cards,
    ]
    completeness = sum(v is not None for v in observed_fields) / len(observed_fields)
    data_quality = max(0.0, min(1.0, 0.45 + 0.55 * completeness))
    model_quality = max(0.0, min(1.0, 0.30 + 0.50 * completeness + 0.20 * min(minute, 70) / 70.0))

    p_goal = _prob_at_least(rem_total, 1)
    p_two_goals = _prob_at_least(rem_total, 2)
    p_home_goal = _prob_at_least(rem_home, 1)
    p_away_goal = _prob_at_least(rem_away, 1)

    signals = (
        LiveMarketSignal(
            "next_goal_any", "Sai pelo menos 1 gol", p_goal, _fair_odds(p_goal),
            _status(p_goal, data_quality, model_quality),
            f"Restante esperado de gols: {rem_total:.2f}",
        ),
        LiveMarketSignal(
            "two_more_goals", "Saem pelo menos 2 gols", p_two_goals, _fair_odds(p_two_goals),
            _status(p_two_goals, data_quality, model_quality),
            f"Restante esperado de gols: {rem_total:.2f}",
        ),
        LiveMarketSignal(
            "home_scores", f"{context.home.name} marca", p_home_goal, _fair_odds(p_home_goal),
            _status(p_home_goal, data_quality, model_quality),
            f"Pressão relativa casa: {share_home:.0%}",
        ),
        LiveMarketSignal(
            "away_scores", f"{context.away.name} marca", p_away_goal, _fair_odds(p_away_goal),
            _status(p_away_goal, data_quality, model_quality),
            f"Pressão relativa fora: {share_away:.0%}",
        ),
    )

    return LiveIntelligenceResult(
        fixture_id=context.fixture_id,
        minute=minute,
        home_goals=home_goals,
        away_goals=away_goals,
        pressure_home=pressure_home,
        pressure_away=pressure_away,
        remaining_home_goals=rem_home,
        remaining_away_goals=rem_away,
        data_quality=data_quality,
        model_quality=model_quality,
        signals=signals,
    )
