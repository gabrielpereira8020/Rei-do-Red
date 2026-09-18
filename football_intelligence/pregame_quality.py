"""Data quality scoring for pre-game Football Intelligence."""

from __future__ import annotations

from dataclasses import dataclass

from .models import MatchContext


@dataclass(frozen=True)
class PregameQualityReport:
    score: float
    reasons: tuple[str, ...]


def assess_pregame_quality(context: MatchContext) -> PregameQualityReport:
    score = 1.0
    reasons: list[str] = []

    home = context.home
    away = context.away

    required = {
        "home.home_goals_for_avg": home.home_goals_for_avg,
        "home.home_goals_against_avg": home.home_goals_against_avg,
        "away.away_goals_for_avg": away.away_goals_for_avg,
        "away.away_goals_against_avg": away.away_goals_against_avg,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        return PregameQualityReport(0.0, tuple(f"missing:{name}" for name in missing))

    minimum_sample = min(home.matches_sample, away.matches_sample)
    if minimum_sample < 5:
        score -= 0.45
        reasons.append("very_small_sample")
    elif minimum_sample < 10:
        score -= 0.25
        reasons.append("small_sample")
    elif minimum_sample < 15:
        score -= 0.10
        reasons.append("moderate_sample")

    # General averages are useful corroboration but not required by the baseline.
    if home.goals_for_avg is None or home.goals_against_avg is None:
        score -= 0.05
        reasons.append("home_general_averages_missing")
    if away.goals_for_avg is None or away.goals_against_avg is None:
        score -= 0.05
        reasons.append("away_general_averages_missing")

    # League baseline is valid by contract, but tiny/implausible totals should lower trust.
    league_total = context.league.total_goals_avg
    if league_total < 1.0 or league_total > 5.0:
        score -= 0.20
        reasons.append("league_baseline_outlier")

    score = max(0.0, min(1.0, score))
    if not reasons:
        reasons.append("core_pregame_data_complete")
    return PregameQualityReport(score, tuple(reasons))
