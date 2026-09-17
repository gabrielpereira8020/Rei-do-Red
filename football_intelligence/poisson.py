"""Pure statistical Poisson helpers for the shadow engine."""

from __future__ import annotations

import math
from typing import Dict, Tuple


def poisson_pmf(k: int, lam: float) -> float:
    if k < 0:
        return 0.0
    if lam < 0:
        raise ValueError("lambda cannot be negative")
    if lam == 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 10) -> Dict[Tuple[int, int], float]:
    matrix: Dict[Tuple[int, int], float] = {}
    total = 0.0
    for home_goals in range(max_goals + 1):
        p_home = poisson_pmf(home_goals, lambda_home)
        for away_goals in range(max_goals + 1):
            probability = p_home * poisson_pmf(away_goals, lambda_away)
            matrix[(home_goals, away_goals)] = probability
            total += probability
    if total > 0:
        matrix = {score: p / total for score, p in matrix.items()}
    return matrix


def one_x_two(lambda_home: float, lambda_away: float, max_goals: int = 10) -> tuple[float, float, float]:
    matrix = score_matrix(lambda_home, lambda_away, max_goals=max_goals)
    home = sum(p for (h, a), p in matrix.items() if h > a)
    draw = sum(p for (h, a), p in matrix.items() if h == a)
    away = sum(p for (h, a), p in matrix.items() if h < a)
    total = home + draw + away
    return home / total, draw / total, away / total


def total_goals_over(lambda_total: float, line: float) -> float:
    if lambda_total < 0:
        raise ValueError("lambda cannot be negative")
    if line < 0 or not float(line).is_integer() and line % 1 != 0.5:
        raise ValueError("only non-negative integer or half-goal lines are supported")
    # This baseline treats integer lines as strict-over probability only; push-aware
    # settlement is intentionally left to a later Asian-lines module.
    threshold = math.floor(line) + 1
    probability_under_or_equal = sum(poisson_pmf(k, lambda_total) for k in range(threshold))
    return max(0.0, min(1.0, 1.0 - probability_under_or_equal))


def btts_yes(lambda_home: float, lambda_away: float) -> float:
    p_home_zero = poisson_pmf(0, lambda_home)
    p_away_zero = poisson_pmf(0, lambda_away)
    return max(0.0, min(1.0, 1.0 - p_home_zero - p_away_zero + (p_home_zero * p_away_zero)))
