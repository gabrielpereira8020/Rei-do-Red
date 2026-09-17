"""Typed domain contracts for the Rei-do-Red shadow intelligence engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Optional, Sequence

from .exceptions import InvalidInputError


class DataStatus(str, Enum):
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    VALID = "valid"
    INVALID = "invalid"


class DecisionStatus(str, Enum):
    BET_ELIGIBLE = "BET_ELIGIBLE"
    WATCH = "WATCH"
    NO_BET = "NO_BET"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class TeamProfile:
    team_id: int
    name: str
    goals_for_avg: Optional[float] = None
    goals_against_avg: Optional[float] = None
    home_goals_for_avg: Optional[float] = None
    home_goals_against_avg: Optional[float] = None
    away_goals_for_avg: Optional[float] = None
    away_goals_against_avg: Optional[float] = None
    recent_points_per_game: Optional[float] = None
    matches_sample: int = 0

    def __post_init__(self) -> None:
        if self.team_id <= 0:
            raise InvalidInputError("team_id must be positive")
        if not self.name.strip():
            raise InvalidInputError("team name cannot be empty")
        if self.matches_sample < 0:
            raise InvalidInputError("matches_sample cannot be negative")
        for field_name in (
            "goals_for_avg",
            "goals_against_avg",
            "home_goals_for_avg",
            "home_goals_against_avg",
            "away_goals_for_avg",
            "away_goals_against_avg",
            "recent_points_per_game",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise InvalidInputError(f"{field_name} cannot be negative")


@dataclass(frozen=True)
class LeagueBaseline:
    league_id: int
    season: int
    home_goals_avg: float
    away_goals_avg: float

    def __post_init__(self) -> None:
        if self.league_id <= 0:
            raise InvalidInputError("league_id must be positive")
        if self.home_goals_avg < 0 or self.away_goals_avg < 0:
            raise InvalidInputError("league goal averages cannot be negative")

    @property
    def total_goals_avg(self) -> float:
        return self.home_goals_avg + self.away_goals_avg


@dataclass(frozen=True)
class LiveState:
    minute: Optional[int] = None
    home_goals: Optional[int] = None
    away_goals: Optional[int] = None
    home_shots: Optional[int] = None
    away_shots: Optional[int] = None
    home_shots_on_target: Optional[int] = None
    away_shots_on_target: Optional[int] = None
    home_corners: Optional[int] = None
    away_corners: Optional[int] = None
    home_cards: Optional[int] = None
    away_cards: Optional[int] = None
    home_fouls: Optional[int] = None
    away_fouls: Optional[int] = None
    home_possession: Optional[float] = None
    away_possession: Optional[float] = None
    home_red_cards: Optional[int] = None
    away_red_cards: Optional[int] = None

    def __post_init__(self) -> None:
        if self.minute is not None and not 0 <= self.minute <= 130:
            raise InvalidInputError("minute is outside supported bounds")
        for name, value in self.__dict__.items():
            if name == "minute" or value is None:
                continue
            if value < 0:
                raise InvalidInputError(f"{name} cannot be negative")


@dataclass(frozen=True)
class MatchContext:
    fixture_id: int
    league_id: int
    season: int
    kickoff_utc: datetime
    home: TeamProfile
    away: TeamProfile
    league: LeagueBaseline
    live: Optional[LiveState] = None

    def __post_init__(self) -> None:
        if self.fixture_id <= 0:
            raise InvalidInputError("fixture_id must be positive")
        if self.league_id != self.league.league_id:
            raise InvalidInputError("league_id does not match league baseline")
        if self.season != self.league.season:
            raise InvalidInputError("season does not match league baseline")
        if self.kickoff_utc.tzinfo is None:
            raise InvalidInputError("kickoff_utc must be timezone-aware")


@dataclass(frozen=True)
class OddsQuote:
    bookmaker: str
    market: str
    selection: str
    decimal_odds: float
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    line: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.bookmaker.strip():
            raise InvalidInputError("bookmaker cannot be empty")
        if self.decimal_odds <= 1.0:
            raise InvalidInputError("decimal_odds must be greater than 1")
        if self.captured_at.tzinfo is None:
            raise InvalidInputError("captured_at must be timezone-aware")


@dataclass(frozen=True)
class MarketProbability:
    market: str
    selection: str
    probability: float
    fair_odds: Optional[float]
    line: Optional[float] = None

    def __post_init__(self) -> None:
        if not 0 <= self.probability <= 1:
            raise InvalidInputError("probability must be within [0, 1]")
        if self.fair_odds is not None and self.fair_odds < 1:
            raise InvalidInputError("fair_odds cannot be below 1")


@dataclass(frozen=True)
class MarketAssessment:
    market: str
    selection: str
    probability: float
    offered_odds: Optional[float]
    market_probability_devig: Optional[float]
    fair_odds: Optional[float]
    edge: Optional[float]
    expected_value: Optional[float]
    data_quality: float
    model_quality: float
    decision: DecisionStatus
    reasons: Sequence[str] = ()


@dataclass(frozen=True)
class IntelligenceResult:
    fixture_id: int
    model_name: str
    generated_at: datetime
    expected_home_goals: float
    expected_away_goals: float
    probabilities: Mapping[str, MarketProbability]
    assessments: Sequence[MarketAssessment] = ()
    data_quality: float = 0.0
    model_quality: float = 0.0

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise InvalidInputError("generated_at must be timezone-aware")
        if self.expected_home_goals < 0 or self.expected_away_goals < 0:
            raise InvalidInputError("expected goals cannot be negative")
        for score in (self.data_quality, self.model_quality):
            if not 0 <= score <= 1:
                raise InvalidInputError("quality scores must be within [0, 1]")
