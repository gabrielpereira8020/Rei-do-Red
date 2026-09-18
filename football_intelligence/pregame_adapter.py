"""Adapter from the legacy API-Football data shape into typed pre-game context.

This module is isolated from the legacy pre-game flow. It reads through the existing
api_football._get client but does not change any existing behavior.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from api_football import _get

from .models import LeagueBaseline, MatchContext, TeamProfile


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _team_stats(team_id: int, league_id: int, season: int) -> dict[str, Any] | None:
    data = _get(f"teams/statistics?team={team_id}&league={league_id}&season={season}")
    return data if isinstance(data, dict) and data else None


def _extract_profile(team_id: int, name: str, league_id: int, season: int) -> TeamProfile | None:
    stats = _team_stats(team_id, league_id, season)
    if not stats:
        return None

    goals_for = stats.get("goals", {}).get("for", {}).get("average", {})
    goals_against = stats.get("goals", {}).get("against", {}).get("average", {})
    fixtures = stats.get("fixtures", {})

    played = fixtures.get("played", {})
    total_played = int(played.get("total") or 0)

    return TeamProfile(
        team_id=team_id,
        name=name,
        goals_for_avg=_to_float(goals_for.get("total")),
        goals_against_avg=_to_float(goals_against.get("total")),
        home_goals_for_avg=_to_float(goals_for.get("home")),
        home_goals_against_avg=_to_float(goals_against.get("home")),
        away_goals_for_avg=_to_float(goals_for.get("away")),
        away_goals_against_avg=_to_float(goals_against.get("away")),
        matches_sample=total_played,
    )


def _league_baseline(league_id: int, season: int, fallback_home: float = 1.45, fallback_away: float = 1.15) -> LeagueBaseline:
    fixtures = _get(f"fixtures?league={league_id}&season={season}&last=100")
    home_goals = away_goals = matches = 0
    if isinstance(fixtures, list):
        for item in fixtures:
            goals = item.get("goals", {})
            home = goals.get("home")
            away = goals.get("away")
            if home is None or away is None:
                continue
            try:
                home_goals += int(home)
                away_goals += int(away)
                matches += 1
            except (TypeError, ValueError):
                continue

    if matches == 0:
        return LeagueBaseline(
            league_id=league_id,
            season=season,
            home_goals_avg=fallback_home,
            away_goals_avg=fallback_away,
        )

    return LeagueBaseline(
        league_id=league_id,
        season=season,
        home_goals_avg=home_goals / matches,
        away_goals_avg=away_goals / matches,
    )


def build_match_context(jogo: dict[str, Any]) -> MatchContext | None:
    """Build a typed MatchContext from the selected legacy fixture dict.

    Returns None when the minimum statistical inputs are unavailable.
    Missing values are never coerced to zero.
    """
    fixture_id = int(jogo["id"])
    league_id = int(jogo["liga_id"])
    season = int(jogo.get("season") or datetime.now().year)
    home_id = int(jogo["casa_id"])
    away_id = int(jogo["fora_id"])

    home = _extract_profile(home_id, jogo["casa"], league_id, season)
    away = _extract_profile(away_id, jogo["fora"], league_id, season)
    if home is None or away is None:
        return None

    kickoff = datetime.fromisoformat(jogo["data"].replace("Z", "+00:00"))
    if kickoff.tzinfo is None:
        return None

    league = _league_baseline(league_id, season)

    return MatchContext(
        fixture_id=fixture_id,
        league_id=league_id,
        season=season,
        kickoff_utc=kickoff,
        home=home,
        away=away,
        league=league,
    )
