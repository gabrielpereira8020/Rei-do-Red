"""Player-prop baseline for shots, shots on target and goalkeeper saves."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial
from statistics import mean

from api_football import _get


@dataclass(frozen=True)
class PlayerPropEstimate:
    player_id: int
    player_name: str
    team_name: str
    position: str
    market: str
    line: float
    expected: float | None
    probability_over: float | None
    sample_size: int
    quality: float


def _poisson_cdf(k: int, lam: float) -> float:
    if lam < 0:
        return 0.0
    return sum(exp(-lam) * (lam ** i) / factorial(i) for i in range(k + 1))


def _prob_over(expected: float, line: float) -> float:
    threshold = int(line // 1)
    return max(0.0, min(1.0, 1.0 - _poisson_cdf(threshold, expected)))


def _collect_player_recent(player_id: int, team_id: int, limit: int = 8) -> dict[str, list[float]]:
    fixtures = _get(f"fixtures?team={team_id}&last={limit}")
    fixture_ids = [
        int(item["fixture"]["id"])
        for item in fixtures
        if item.get("fixture", {}).get("status", {}).get("short") in {"FT", "AET", "PEN"}
        and item.get("fixture", {}).get("id")
    ]

    shots: list[float] = []
    shots_on: list[float] = []
    saves: list[float] = []
    minutes: list[float] = []

    for fixture_id in fixture_ids:
        data = _get(f"fixtures/players?fixture={fixture_id}")
        for team in data:
            for item in team.get("players", []):
                player = item.get("player", {})
                if int(player.get("id") or 0) != int(player_id):
                    continue
                stats = (item.get("statistics") or [{}])[0]
                mins = stats.get("games", {}).get("minutes", 0) or 0
                if mins <= 0:
                    continue
                minutes.append(float(mins))
                shots.append(float(stats.get("shots", {}).get("total", 0) or 0))
                shots_on.append(float(stats.get("shots", {}).get("on", 0) or 0))
                saves.append(float(stats.get("goals", {}).get("saves", 0) or 0))

    return {"shots": shots, "shots_on": shots_on, "saves": saves, "minutes": minutes}


def _season_players(team_id: int, league_id: int, season: int) -> list[dict]:
    data = _get(f"players?team={team_id}&league={league_id}&season={season}")
    players: list[dict] = []
    for item in data:
        p = item.get("player", {})
        stats = (item.get("statistics") or [{}])[0]
        games = stats.get("games", {})
        minutes = games.get("minutes", 0) or 0
        appearances = games.get("appearences", 0) or 0
        if minutes <= 0 or appearances <= 0:
            continue
        players.append({
            "id": p.get("id"),
            "name": p.get("name", "?"),
            "position": games.get("position", "?"),
            "minutes": minutes,
            "appearances": appearances,
            "team_name": stats.get("team", {}).get("name", ""),
        })
    players.sort(key=lambda x: x["minutes"], reverse=True)
    return players[:8]


def _quality(sample: int) -> float:
    return max(0.0, min(1.0, sample / 8.0))


def estimate_player_props(jogo: dict, recent_matches: int = 8) -> list[PlayerPropEstimate]:
    league_id = jogo.get("liga_id")
    season = jogo.get("season")
    if not league_id or not season:
        return []

    output: list[PlayerPropEstimate] = []
    for team_id in (jogo.get("casa_id"), jogo.get("fora_id")):
        if not team_id:
            continue
        for player in _season_players(int(team_id), int(league_id), int(season)):
            player_id = player.get("id")
            if not player_id:
                continue
            recent = _collect_player_recent(int(player_id), int(team_id), limit=recent_matches)
            sample = len(recent["minutes"])
            if sample == 0:
                continue

            avg_shots = mean(recent["shots"]) if recent["shots"] else None
            avg_shots_on = mean(recent["shots_on"]) if recent["shots_on"] else None
            avg_saves = mean(recent["saves"]) if recent["saves"] else None
            q = _quality(sample)

            for line in (0.5, 1.5, 2.5, 3.5):
                if avg_shots is not None:
                    output.append(PlayerPropEstimate(
                        int(player_id), player["name"], player["team_name"] or "", player["position"],
                        "PLAYER_SHOTS", line, avg_shots, _prob_over(avg_shots, line), sample, q
                    ))

            for line in (0.5, 1.5, 2.5):
                if avg_shots_on is not None:
                    output.append(PlayerPropEstimate(
                        int(player_id), player["name"], player["team_name"] or "", player["position"],
                        "PLAYER_SHOTS_ON_TARGET", line, avg_shots_on, _prob_over(avg_shots_on, line), sample, q
                    ))

            if player["position"] == "Goalkeeper" and avg_saves is not None:
                for line in (1.5, 2.5, 3.5, 4.5):
                    output.append(PlayerPropEstimate(
                        int(player_id), player["name"], player["team_name"] or "", player["position"],
                        "GOALKEEPER_SAVES", line, avg_saves, _prob_over(avg_saves, line), sample, q
                    ))

    return output


def best_player_props(props: list[PlayerPropEstimate], top_n: int = 12) -> list[PlayerPropEstimate]:
    eligible = [p for p in props if p.probability_over is not None and p.quality >= 0.5]
    eligible.sort(
        key=lambda p: (
            p.probability_over if p.probability_over is not None else -1,
            p.quality,
            p.sample_size,
        ),
        reverse=True,
    )
    return eligible[:top_n]
