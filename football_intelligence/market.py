"""Market math: implied probability, de-vig, fair odds, edge and EV."""

from __future__ import annotations

from typing import Mapping


def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError("decimal odds must be greater than 1")
    return 1.0 / decimal_odds


def proportional_devig(selection_odds: Mapping[str, float]) -> dict[str, float]:
    if len(selection_odds) < 2:
        raise ValueError("at least two mutually exclusive selections are required")
    raw = {name: implied_probability(odds) for name, odds in selection_odds.items()}
    overround = sum(raw.values())
    if overround <= 0:
        raise ValueError("invalid overround")
    return {name: probability / overround for name, probability in raw.items()}


def fair_odds(probability: float) -> float | None:
    if not 0 <= probability <= 1:
        raise ValueError("probability must be within [0, 1]")
    return None if probability == 0 else 1.0 / probability


def edge(model_probability: float, market_probability: float) -> float:
    if not 0 <= model_probability <= 1 or not 0 <= market_probability <= 1:
        raise ValueError("probabilities must be within [0, 1]")
    return model_probability - market_probability


def expected_value(model_probability: float, decimal_odds: float) -> float:
    if not 0 <= model_probability <= 1:
        raise ValueError("probability must be within [0, 1]")
    if decimal_odds <= 1.0:
        raise ValueError("decimal odds must be greater than 1")
    return (model_probability * decimal_odds) - 1.0
