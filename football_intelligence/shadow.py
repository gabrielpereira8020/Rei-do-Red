"""Side-effect-free shadow evaluation and observability helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Optional, Sequence

from .decision import assess_market
from .engine import FootballIntelligenceEngine
from .market import proportional_devig
from .models import DecisionStatus, IntelligenceResult, MarketAssessment, MatchContext, OddsQuote


@dataclass(frozen=True)
class ShadowSnapshot:
    fixture_id: int
    generated_at: datetime
    model_name: str
    expected_home_goals: float
    expected_away_goals: float
    data_quality: float
    model_quality: float
    assessments: Sequence[MarketAssessment]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["generated_at"] = self.generated_at.isoformat()
        for item in payload["assessments"]:
            decision = item.get("decision")
            if isinstance(decision, DecisionStatus):
                item["decision"] = decision.value
        return payload


def _quote_key(quote: OddsQuote) -> tuple[str, str, Optional[float]]:
    return (quote.market.upper(), quote.selection.upper(), quote.line)


def _group_odds(quotes: Iterable[OddsQuote]) -> dict[tuple[str, Optional[float], str], dict[str, float]]:
    grouped: dict[tuple[str, Optional[float], str], dict[str, float]] = {}
    for quote in quotes:
        key = (quote.market.upper(), quote.line, quote.bookmaker)
        grouped.setdefault(key, {})[quote.selection.upper()] = quote.decimal_odds
    return grouped


def _expected_selection_count(market: str) -> int | None:
    market = market.upper()
    if market == "1X2":
        return 3
    if market in {"TOTAL_GOALS", "BTTS"}:
        return 2
    return None


def _devig_lookup(quotes: Iterable[OddsQuote]) -> dict[tuple[str, str, Optional[float], str], float]:
    result: dict[tuple[str, str, Optional[float], str], float] = {}
    for (market, line, bookmaker), selections in _group_odds(quotes).items():
        expected = _expected_selection_count(market)
        if expected is not None and len(selections) != expected:
            continue
        if expected is None and len(selections) < 2:
            continue
        try:
            fair = proportional_devig(selections)
        except ValueError:
            continue
        for selection, probability in fair.items():
            result[(market, selection, line, bookmaker)] = probability
    return result


def run_shadow(
    context: MatchContext,
    odds: Sequence[OddsQuote] = (),
    *,
    min_edge: float = 0.04,
    min_ev: float = 0.03,
    min_data_quality: float = 0.75,
    min_model_quality: float = 0.35,
) -> ShadowSnapshot:
    """Evaluate a match without side effects.

    Complete bookmaker books are retained for de-vigging. The best available
    offered price is selected separately for EV/edge evaluation.
    """
    base: IntelligenceResult = FootballIntelligenceEngine().analyze(context)

    quote_map: dict[tuple[str, str, Optional[float]], OddsQuote] = {}
    for quote in odds:
        key = _quote_key(quote)
        current = quote_map.get(key)
        if current is None or quote.decimal_odds > current.decimal_odds:
            quote_map[key] = quote

    devig_map = _devig_lookup(odds)

    assessments: list[MarketAssessment] = []
    for probability in base.probabilities.values():
        key = (probability.market.upper(), probability.selection.upper(), probability.line)
        quote = quote_map.get(key)
        market_probability = None
        if quote is not None:
            market_probability = devig_map.get(
                (quote.market.upper(), quote.selection.upper(), quote.line, quote.bookmaker)
            )

        assessments.append(
            assess_market(
                probability=probability,
                quote=quote,
                market_probability_devig=market_probability,
                data_quality=base.data_quality,
                model_quality=base.model_quality,
                min_edge=min_edge,
                min_ev=min_ev,
                min_data_quality=min_data_quality,
                min_model_quality=min_model_quality,
            )
        )

    return ShadowSnapshot(
        fixture_id=base.fixture_id,
        generated_at=datetime.now(timezone.utc),
        model_name=base.model_name,
        expected_home_goals=base.expected_home_goals,
        expected_away_goals=base.expected_away_goals,
        data_quality=base.data_quality,
        model_quality=base.model_quality,
        assessments=tuple(assessments),
    )


def summarize_shadow(snapshot: ShadowSnapshot) -> Mapping[str, int | float | str]:
    counts = {status.value: 0 for status in DecisionStatus}
    for assessment in snapshot.assessments:
        counts[assessment.decision.value] += 1
    return {
        "fixture_id": snapshot.fixture_id,
        "model": snapshot.model_name,
        "data_quality": snapshot.data_quality,
        "model_quality": snapshot.model_quality,
        **counts,
    }
