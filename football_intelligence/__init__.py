"""Rei-do-Red Football Intelligence Engine (shadow mode)."""

from .engine import FootballIntelligenceEngine
from .models import MatchContext, TeamProfile, LeagueBaseline, IntelligenceResult

__all__ = [
    "FootballIntelligenceEngine",
    "MatchContext",
    "TeamProfile",
    "LeagueBaseline",
    "IntelligenceResult",
]
