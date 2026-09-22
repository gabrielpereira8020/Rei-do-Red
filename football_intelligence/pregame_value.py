"""Pregame value evaluation for Rei-do-Red.

Bridges statistical pregame estimates (corners/cards) with real bookmaker prices
when compatible quotes are available, and builds conservative multi-game combos.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .market import edge, expected_value, implied_probability, proportional_devig


@dataclass(frozen=True)
class PregameValueCandidate:
    fixture_id: int
    game: str
    market: str
    line: float | None
    selection: str
    odds: float
    model_probability: float
    market_probability_raw: float
    market_probability_devig: float | None
    edge: float
    expected_value: float
    data_quality: float
    model_quality: float
    status: str
    bookmaker: str
    label: str


@dataclass(frozen=True)
class PregameValueCombo:
    legs: tuple[PregameValueCandidate, ...]
    combined_odds: float
    combined_probability: float
    expected_value: float
    status: str


def assess_pregame_candidate(
    fixture_id: int,
    game: str,
    market: str,
    line: float | None,
    selection: str,
    model_probability: float,
    odds: float,
    bookmaker: str,
    data_quality: float,
    model_quality: float,
    opposite_odds: float | None = None,
    min_edge: float = 0.04,
    min_ev: float = 0.03,
    min_odds: float = 1.20,
) -> PregameValueCandidate:
    raw_market_p = implied_probability(odds)
    devig_p = None
    if opposite_odds and opposite_odds > 1.0:
        try:
            devig_p = proportional_devig(
                {selection: odds, "OPPOSITE": opposite_odds}
            )[selection]
        except Exception:
            devig_p = None

    reference_p = devig_p if devig_p is not None else raw_market_p
    candidate_edge = edge(model_probability, reference_p)
    ev = expected_value(model_probability, odds)

    if data_quality < 0.75:
        status = "INSUFFICIENT_DATA"
    elif model_quality < 0.35:
        status = "WATCH"
    elif odds < min_odds:
        status = "WATCH"
    elif candidate_edge >= min_edge and ev >= min_ev:
        status = "BET_ELIGIBLE"
    elif candidate_edge > 0 and ev > 0:
        status = "WATCH"
    else:
        status = "NO_BET"

    line_text = "" if line is None else f" {line:.1f}"
    return PregameValueCandidate(
        fixture_id=fixture_id,
        game=game,
        market=market,
        line=line,
        selection=selection,
        odds=odds,
        model_probability=model_probability,
        market_probability_raw=raw_market_p,
        market_probability_devig=devig_p,
        edge=candidate_edge,
        expected_value=ev,
        data_quality=data_quality,
        model_quality=model_quality,
        status=status,
        bookmaker=bookmaker,
        label=f"{market} {selection}{line_text}".strip(),
    )


def alternative_value_candidates(
    fixture_id: int,
    game: str,
    estimates: dict,
    quotes: list,
    data_quality: float,
    model_quality: float,
    min_edge: float = 0.04,
    min_ev: float = 0.03,
    min_odds: float = 1.20,
) -> list[PregameValueCandidate]:
    """Evaluate TOTAL_CORNERS / TOTAL_CARDS when matching quotes exist.

    This function deliberately refuses to invent prices. If a real matching
    quote is absent, the estimate remains informational only.
    """
    by_key = {}
    for quote in quotes:
        key = (quote.market, quote.selection, quote.line, quote.bookmaker)
        by_key[key] = quote

    candidates = []
    for estimate in estimates.values():
        if estimate.probability_over is None or estimate.line is None:
            continue
        if estimate.market not in {"TOTAL_CORNERS", "TOTAL_CARDS"}:
            continue

        for quote in quotes:
            if (
                quote.market != estimate.market
                or quote.selection != "OVER"
                or quote.line != estimate.line
            ):
                continue

            opposite = by_key.get(
                (quote.market, "UNDER", quote.line, quote.bookmaker)
            )
            candidate = assess_pregame_candidate(
                fixture_id=fixture_id,
                game=game,
                market=estimate.market,
                line=estimate.line,
                selection="OVER",
                model_probability=estimate.probability_over,
                odds=quote.decimal_odds,
                bookmaker=quote.bookmaker,
                data_quality=min(data_quality, estimate.quality),
                model_quality=model_quality,
                opposite_odds=opposite.decimal_odds if opposite else None,
                min_edge=min_edge,
                min_ev=min_ev,
                min_odds=min_odds,
            )
            candidates.append(candidate)

    return sorted(
        candidates,
        key=lambda c: (
            c.status == "BET_ELIGIBLE",
            c.expected_value,
            c.edge,
        ),
        reverse=True,
    )


def build_pregame_value_combos(
    candidates: list[PregameValueCandidate],
    target_min_odds: float = 1.40,
    target_max_odds: float = 1.60,
    max_legs: int = 3,
) -> list[PregameValueCombo]:
    """Build conservative pregame combos from independently eligible legs."""
    pool = [c for c in candidates if c.status == "BET_ELIGIBLE"]
    combos = []
    for size in range(2, max_legs + 1):
        for legs in combinations(pool, size):
            fixture_ids = {leg.fixture_id for leg in legs}
            if len(fixture_ids) != size:
                continue

            combined_odds = 1.0
            combined_probability = 1.0
            for leg in legs:
                combined_odds *= leg.odds
                combined_probability *= leg.model_probability

            combo_ev = combined_probability * combined_odds - 1.0
            if target_min_odds <= combined_odds <= target_max_odds and combo_ev > 0:
                combos.append(
                    PregameValueCombo(
                        legs=legs,
                        combined_odds=combined_odds,
                        combined_probability=combined_probability,
                        expected_value=combo_ev,
                        status="VALUE_COMBO",
                    )
                )

    midpoint = (target_min_odds + target_max_odds) / 2.0
    return sorted(
        combos,
        key=lambda c: (
            abs(c.combined_odds - midpoint),
            -c.expected_value,
            len(c.legs),
        ),
    )
