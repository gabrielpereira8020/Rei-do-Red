"""Adapters for building live MatchContext from API-Football payloads."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import LeagueBaseline, LiveState, MatchContext, TeamProfile


def _stat(stats, name):
    for item in stats:
        if item.get("type") == name:
            value = item.get("value")
            if value is None:
                return None
            try:
                return int(str(value).replace("%", ""))
            except Exception:
                return None
    return None


def build_live_context(jogo: dict, stats: list[dict], *, league_home_avg: float = 1.45, league_away_avg: float = 1.15) -> MatchContext:
    if not stats or len(stats) < 2:
        raise ValueError("two team statistics blocks are required")

    home_stats = stats[0].get("statistics", [])
    away_stats = stats[1].get("statistics", [])

    kickoff_raw = jogo.get("data")
    try:
        kickoff = datetime.fromisoformat(str(kickoff_raw).replace("Z", "+00:00")) if kickoff_raw else datetime.now(timezone.utc)
    except Exception:
        kickoff = datetime.now(timezone.utc)
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)

    live = LiveState(
        minute=int(jogo.get("minuto") or 0),
        home_goals=int(jogo.get("gols_home") or 0),
        away_goals=int(jogo.get("gols_away") or 0),
        home_shots=_stat(home_stats, "Total Shots"),
        away_shots=_stat(away_stats, "Total Shots"),
        home_shots_on_target=_stat(home_stats, "Shots on Goal"),
        away_shots_on_target=_stat(away_stats, "Shots on Goal"),
        home_corners=_stat(home_stats, "Corner Kicks"),
        away_corners=_stat(away_stats, "Corner Kicks"),
        home_cards=_stat(home_stats, "Yellow Cards"),
        away_cards=_stat(away_stats, "Yellow Cards"),
        home_fouls=_stat(home_stats, "Fouls"),
        away_fouls=_stat(away_stats, "Fouls"),
        home_red_cards=_stat(home_stats, "Red Cards"),
        away_red_cards=_stat(away_stats, "Red Cards"),
    )

    home = TeamProfile(
        team_id=int(jogo["casa_id"]),
        name=jogo["casa"],
        home_goals_for_avg=league_home_avg,
        home_goals_against_avg=league_away_avg,
        matches_sample=0,
    )
    away = TeamProfile(
        team_id=int(jogo["fora_id"]),
        name=jogo["fora"],
        away_goals_for_avg=league_away_avg,
        away_goals_against_avg=league_home_avg,
        matches_sample=0,
    )
    league_id = int(jogo.get("liga_id") or 1)
    season = int(jogo.get("season") or datetime.now().year)
    league = LeagueBaseline(
        league_id=league_id,
        season=season,
        home_goals_avg=league_home_avg,
        away_goals_avg=league_away_avg,
    )

    return MatchContext(
        fixture_id=int(jogo["id"]),
        league_id=league_id,
        season=season,
        kickoff_utc=kickoff,
        home=home,
        away=away,
        league=league,
        live=live,
    )
