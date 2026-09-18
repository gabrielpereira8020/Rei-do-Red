"""Deterministic baseline engine for Rei-do-Red shadow mode."""

from __future__ import annotations

from datetime import datetime, timezone

from .exceptions import InsufficientDataError
from .market import fair_odds
from .models import IntelligenceResult, MarketProbability, MatchContext
from .poisson import btts_yes, one_x_two, total_goals_over
from .pregame_quality import assess_pregame_quality


class FootballIntelligenceEngine:
    """Small, side-effect-free statistical baseline.

    This engine deliberately does not call Gemini, Telegram, Supabase or legacy code.
    """

    name = "shadow-poisson-baseline-v1"

    def _shrink(self, value: float, sample: int, league_mean: float, prior_weight: float = 8.0) -> float:
        if sample <= 0:
            return league_mean
        weight = sample / (sample + prior_weight)
        return (value * weight) + (league_mean * (1.0 - weight))

    def _expected_goals(self, context: MatchContext) -> tuple[float, float, float]:
        home = context.home
        away = context.away
        league = context.league

        required = (
            home.home_goals_for_avg,
            home.home_goals_against_avg,
            away.away_goals_for_avg,
            away.away_goals_against_avg,
        )
        if any(value is None for value in required):
            raise InsufficientDataError("home/away scoring and conceding averages are required")

        home_attack = self._shrink(home.home_goals_for_avg, home.matches_sample, league.home_goals_avg)
        away_defence = self._shrink(away.away_goals_against_avg, away.matches_sample, league.home_goals_avg)
        away_attack = self._shrink(away.away_goals_for_avg, away.matches_sample, league.away_goals_avg)
        home_defence = self._shrink(home.home_goals_against_avg, home.matches_sample, league.away_goals_avg)

        lambda_home = max(0.0, (home_attack + away_defence) / 2.0)
        lambda_away = max(0.0, (away_attack + home_defence) / 2.0)

        minimum_sample = min(home.matches_sample, away.matches_sample)
        model_quality = min(1.0, minimum_sample / 20.0)
        return lambda_home, lambda_away, model_quality

    def analyze(self, context: MatchContext) -> IntelligenceResult:
        lambda_home, lambda_away, model_quality = self._expected_goals(context)
        quality_report = assess_pregame_quality(context)
        p_home, p_draw, p_away = one_x_two(lambda_home, lambda_away)
        total_lambda = lambda_home + lambda_away
        p_btts = btts_yes(lambda_home, lambda_away)

        probabilities: dict[str, MarketProbability] = {}

        def add(key: str, market: str, selection: str, probability: float, line: float | None = None) -> None:
            probabilities[key] = MarketProbability(
                market=market,
                selection=selection,
                probability=probability,
                fair_odds=fair_odds(probability),
                line=line,
            )

        add("1x2_home", "1X2", "HOME", p_home)
        add("1x2_draw", "1X2", "DRAW", p_draw)
        add("1x2_away", "1X2", "AWAY", p_away)
        add("dc_1x", "DOUBLE_CHANCE", "1X", p_home + p_draw)
        add("dc_x2", "DOUBLE_CHANCE", "X2", p_draw + p_away)
        add("dc_12", "DOUBLE_CHANCE", "12", p_home + p_away)

        for line in (0.5, 1.5, 2.5, 3.5, 4.5):
            p_over = total_goals_over(total_lambda, line)
            add(f"goals_over_{str(line).replace('.', '_')}", "TOTAL_GOALS", "OVER", p_over, line)
            add(f"goals_under_{str(line).replace('.', '_')}", "TOTAL_GOALS", "UNDER", 1.0 - p_over, line)

        add("btts_yes", "BTTS", "YES", p_btts)
        add("btts_no", "BTTS", "NO", 1.0 - p_btts)

        return IntelligenceResult(
            fixture_id=context.fixture_id,
            model_name=self.name,
            generated_at=datetime.now(timezone.utc),
            expected_home_goals=lambda_home,
            expected_away_goals=lambda_away,
            probabilities=probabilities,
            data_quality=quality_report.score,
            model_quality=model_quality,
        )
