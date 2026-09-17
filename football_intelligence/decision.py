"""Conservative deterministic decision rules for shadow mode."""

from __future__ import annotations

from .models import DecisionStatus, MarketAssessment, MarketProbability, OddsQuote


def decide(
    *,
    probability: float,
    offered_odds: float | None,
    market_probability_devig: float | None,
    data_quality: float,
    model_quality: float,
    min_edge: float = 0.04,
    min_ev: float = 0.03,
    min_data_quality: float = 0.75,
    min_model_quality: float = 0.35,
) -> tuple[DecisionStatus, tuple[str, ...]]:
    reasons: list[str] = []

    if data_quality < min_data_quality:
        return DecisionStatus.INSUFFICIENT_DATA, ("data_quality_below_threshold",)

    if model_quality < min_model_quality:
        return DecisionStatus.WATCH, ("baseline_model_quality_still_low",)

    if offered_odds is None or market_probability_devig is None:
        return DecisionStatus.WATCH, ("market_price_unavailable_or_incomplete",)

    edge = probability - market_probability_devig
    ev = (probability * offered_odds) - 1.0

    if edge <= 0 or ev <= 0:
        reasons.extend(["no_positive_edge", "no_positive_expected_value"])
        return DecisionStatus.NO_BET, tuple(reasons)

    if edge < min_edge or ev < min_ev:
        reasons.append("positive_but_below_shadow_threshold")
        return DecisionStatus.WATCH, tuple(reasons)

    return DecisionStatus.BET_ELIGIBLE, ("shadow_thresholds_met",)


def build_assessment(
    *,
    market: str,
    selection: str,
    probability: float,
    offered_odds: float | None,
    market_probability_devig: float | None,
    fair_odds: float | None,
    data_quality: float,
    model_quality: float,
    min_edge: float = 0.04,
    min_ev: float = 0.03,
    min_data_quality: float = 0.75,
    min_model_quality: float = 0.35,
) -> MarketAssessment:
    decision, reasons = decide(
        probability=probability,
        offered_odds=offered_odds,
        market_probability_devig=market_probability_devig,
        data_quality=data_quality,
        model_quality=model_quality,
        min_edge=min_edge,
        min_ev=min_ev,
        min_data_quality=min_data_quality,
        min_model_quality=min_model_quality,
    )
    edge = None if market_probability_devig is None else probability - market_probability_devig
    ev = None if offered_odds is None else (probability * offered_odds) - 1.0
    return MarketAssessment(
        market=market,
        selection=selection,
        probability=probability,
        offered_odds=offered_odds,
        market_probability_devig=market_probability_devig,
        fair_odds=fair_odds,
        edge=edge,
        expected_value=ev,
        data_quality=data_quality,
        model_quality=model_quality,
        decision=decision,
        reasons=reasons,
    )


def assess_market(
    *,
    probability: MarketProbability,
    quote: OddsQuote | None,
    market_probability_devig: float | None,
    data_quality: float,
    model_quality: float,
    min_edge: float = 0.04,
    min_ev: float = 0.03,
    min_data_quality: float = 0.75,
    min_model_quality: float = 0.35,
) -> MarketAssessment:
    """Compatibility adapter used by the shadow runner.

    Converts the typed market probability and optional odds quote into the
    deterministic assessment contract used by Shadow mode.
    """
    return build_assessment(
        market=probability.market,
        selection=probability.selection,
        probability=probability.probability,
        offered_odds=None if quote is None else quote.decimal_odds,
        market_probability_devig=market_probability_devig,
        fair_odds=probability.fair_odds,
        data_quality=data_quality,
        model_quality=model_quality,
        min_edge=min_edge,
        min_ev=min_ev,
        min_data_quality=min_data_quality,
        min_model_quality=min_model_quality,
    )
