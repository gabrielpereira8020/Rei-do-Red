"""Match live bookmaker totals to Football Intelligence probabilities."""

from __future__ import annotations

from dataclasses import dataclass

from .market import edge, expected_value, implied_probability, proportional_devig


@dataclass(frozen=True)
class LiveValueCandidate:
    market: str
    line: float
    selection: str
    odds: float
    model_probability: float
    market_probability_raw: float
    market_probability_devig: float | None
    edge: float | None
    expected_value: float
    status: str
    label: str


def _norm(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _extract_side_and_line(value: str) -> tuple[str | None, float | None]:
    text = _norm(value).replace(",", ".")
    side = None
    if any(token in text for token in ("over", "mais de", "acima de")):
        side = "OVER"
    elif any(token in text for token in ("under", "menos de", "abaixo de")):
        side = "UNDER"

    line = None
    for token in text.replace("+", " ").replace("-", " ").split():
        try:
            line = float(token)
        except Exception:
            continue
    return side, line


def _looks_like_corner_market(name: str) -> bool:
    n = _norm(name)
    return any(token in n for token in ("corner", "corners", "escanteio", "escanteios"))


def _looks_like_goal_market(name: str) -> bool:
    n = _norm(name)
    return (
        ("goal" in n or "gols" in n or "goles" in n)
        and "corner" not in n
        and "escante" not in n
        and "card" not in n
        and "cart" not in n
    )


def _looks_like_card_market(name: str) -> bool:
    n = _norm(name)
    return any(token in n for token in ("card", "cards", "cartao", "cartão", "cartoes", "cartões"))


def parse_live_corner_totals(payload) -> dict[float, dict[str, float]]:
    """Return {line: {"OVER": odd, "UNDER": odd}} from API-Football live odds payload."""
    books: list[dict] = []
    for item in payload or []:
        if isinstance(item, dict) and item.get("bookmakers"):
            for bookmaker in item.get("bookmakers") or []:
                books.append(bookmaker)
        elif isinstance(item, dict):
            books.append(item)

    by_line: dict[float, dict[str, float]] = {}
    for book in books:
        for bet in book.get("bets", []) or []:
            if not _looks_like_corner_market(bet.get("name", "")):
                continue
            for option in bet.get("values", []) or []:
                side, line = _extract_side_and_line(option.get("value", ""))
                if side is None or line is None:
                    continue
                try:
                    odd = float(option.get("odd"))
                except Exception:
                    continue
                if odd <= 1.0:
                    continue
                by_line.setdefault(line, {})
                previous = by_line[line].get(side)
                if previous is None or odd > previous:
                    by_line[line][side] = odd
    return by_line


def corner_probability_map(live_result) -> dict[int, float]:
    mapping = {}
    key_to_more = {
        "one_more_corner": 1,
        "two_more_corners": 2,
        "three_more_corners": 3,
    }
    for signal in live_result.signals:
        n = key_to_more.get(signal.key)
        if n:
            mapping[n] = signal.probability
    return mapping


def evaluate_corner_value(live_result, current_corners: int, odds_payload,
                          min_edge: float = 0.04, min_ev: float = 0.03) -> list[LiveValueCandidate]:
    lines = parse_live_corner_totals(odds_payload)
    probs = corner_probability_map(live_result)
    candidates: list[LiveValueCandidate] = []

    for more_corners, model_p in probs.items():
        line = float(current_corners + more_corners) - 0.5
        prices = lines.get(line)
        if not prices or "OVER" not in prices:
            continue

        over_odd = prices["OVER"]
        raw_market_p = implied_probability(over_odd)
        devig_p = None
        if "UNDER" in prices:
            try:
                devig_p = proportional_devig({"OVER": over_odd, "UNDER": prices["UNDER"]})["OVER"]
            except Exception:
                devig_p = None

        reference_p = devig_p if devig_p is not None else raw_market_p
        candidate_edge = edge(model_p, reference_p)
        ev = expected_value(model_p, over_odd)

        if live_result.data_quality < 0.70 or live_result.model_quality < 0.50:
            status = "INSUFFICIENT_DATA"
        elif candidate_edge >= min_edge and ev >= min_ev:
            status = "BET_ELIGIBLE"
        elif candidate_edge > 0 and ev > 0:
            status = "WATCH"
        else:
            status = "NO_BET"

        candidates.append(
            LiveValueCandidate(
                market="TOTAL_CORNERS",
                line=line,
                selection="OVER",
                odds=over_odd,
                model_probability=model_p,
                market_probability_raw=raw_market_p,
                market_probability_devig=devig_p,
                edge=candidate_edge,
                expected_value=ev,
                status=status,
                label=f"Over {line:.1f} escanteios",
            )
        )

    return sorted(
        candidates,
        key=lambda item: (
            item.status == "BET_ELIGIBLE",
            item.expected_value,
            item.edge or -1.0,
        ),
        reverse=True,
    )


def _parse_total_market(payload, predicate) -> dict[float, dict[str, float]]:
    books: list[dict] = []
    for item in payload or []:
        if isinstance(item, dict) and item.get("bookmakers"):
            for bookmaker in item.get("bookmakers") or []:
                books.append(bookmaker)
        elif isinstance(item, dict):
            books.append(item)

    by_line: dict[float, dict[str, float]] = {}
    for book in books:
        for bet in book.get("bets", []) or []:
            if not predicate(bet.get("name", "")):
                continue
            for option in bet.get("values", []) or []:
                side, line = _extract_side_and_line(option.get("value", ""))
                if side is None or line is None:
                    continue
                try:
                    odd = float(option.get("odd"))
                except Exception:
                    continue
                if odd <= 1.0:
                    continue
                by_line.setdefault(line, {})
                previous = by_line[line].get(side)
                if previous is None or odd > previous:
                    by_line[line][side] = odd
    return by_line


def parse_live_goal_totals(payload) -> dict[float, dict[str, float]]:
    return _parse_total_market(payload, _looks_like_goal_market)


def parse_live_card_totals(payload) -> dict[float, dict[str, float]]:
    return _parse_total_market(payload, _looks_like_card_market)


def _signal_probability(live_result, key: str) -> float | None:
    for signal in live_result.signals:
        if signal.key == key:
            return signal.probability
    return None


def _evaluate_over_lines(live_result, market: str, labels: str, current_total: int,
                         odds_lines: dict[float, dict[str, float]],
                         probability_by_more: dict[int, float | None],
                         min_edge: float = 0.04, min_ev: float = 0.03) -> list[LiveValueCandidate]:
    candidates: list[LiveValueCandidate] = []
    for more, model_p in probability_by_more.items():
        if model_p is None:
            continue
        line = float(current_total + more) - 0.5
        prices = odds_lines.get(line)
        if not prices or "OVER" not in prices:
            continue

        over_odd = prices["OVER"]
        raw_market_p = implied_probability(over_odd)
        devig_p = None
        if "UNDER" in prices:
            try:
                devig_p = proportional_devig({"OVER": over_odd, "UNDER": prices["UNDER"]})["OVER"]
            except Exception:
                devig_p = None

        reference_p = devig_p if devig_p is not None else raw_market_p
        candidate_edge = edge(model_p, reference_p)
        ev = expected_value(model_p, over_odd)

        if live_result.data_quality < 0.70 or live_result.model_quality < 0.50:
            status = "INSUFFICIENT_DATA"
        elif candidate_edge >= min_edge and ev >= min_ev:
            status = "BET_ELIGIBLE"
        elif candidate_edge > 0 and ev > 0:
            status = "WATCH"
        else:
            status = "NO_BET"

        candidates.append(
            LiveValueCandidate(
                market=market,
                line=line,
                selection="OVER",
                odds=over_odd,
                model_probability=model_p,
                market_probability_raw=raw_market_p,
                market_probability_devig=devig_p,
                edge=candidate_edge,
                expected_value=ev,
                status=status,
                label=f"Over {line:.1f} {labels}",
            )
        )
    return candidates


def evaluate_goal_value(live_result, current_goals: int, odds_payload,
                        min_edge: float = 0.04, min_ev: float = 0.03) -> list[LiveValueCandidate]:
    odds_lines = parse_live_goal_totals(odds_payload)
    candidates = _evaluate_over_lines(
        live_result,
        market="TOTAL_GOALS",
        labels="gols",
        current_total=current_goals,
        odds_lines=odds_lines,
        probability_by_more={
            1: _signal_probability(live_result, "next_goal_any"),
            2: _signal_probability(live_result, "two_more_goals"),
        },
        min_edge=min_edge,
        min_ev=min_ev,
    )
    return sorted(candidates, key=lambda item: (item.status == "BET_ELIGIBLE", item.expected_value, item.edge or -1.0), reverse=True)


def evaluate_card_value(live_result, current_cards: int, odds_payload,
                        min_edge: float = 0.04, min_ev: float = 0.03) -> list[LiveValueCandidate]:
    odds_lines = parse_live_card_totals(odds_payload)
    candidates = _evaluate_over_lines(
        live_result,
        market="TOTAL_CARDS",
        labels="cartões",
        current_total=current_cards,
        odds_lines=odds_lines,
        probability_by_more={
            1: _signal_probability(live_result, "one_more_card"),
            2: _signal_probability(live_result, "two_more_cards"),
        },
        min_edge=min_edge,
        min_ev=min_ev,
    )
    return sorted(candidates, key=lambda item: (item.status == "BET_ELIGIBLE", item.expected_value, item.edge or -1.0), reverse=True)


def evaluate_all_live_value(live_result, current_goals: int, current_corners: int,
                            current_cards: int, odds_payload,
                            min_edge: float = 0.04, min_ev: float = 0.03) -> list[LiveValueCandidate]:
    candidates = []
    candidates.extend(evaluate_goal_value(live_result, current_goals, odds_payload, min_edge, min_ev))
    candidates.extend(evaluate_corner_value(live_result, current_corners, odds_payload, min_edge, min_ev))
    candidates.extend(evaluate_card_value(live_result, current_cards, odds_payload, min_edge, min_ev))
    return sorted(candidates, key=lambda item: (item.status == "BET_ELIGIBLE", item.expected_value, item.edge or -1.0), reverse=True)


@dataclass(frozen=True)
class LiveValueCombo:
    legs: tuple[LiveValueCandidate, ...]
    combined_odds: float
    combined_probability: float
    expected_value: float
    status: str


def build_value_combos(
    candidates_by_fixture: dict[int, list[LiveValueCandidate]],
    target_min_odds: float = 1.40,
    target_max_odds: float = 1.60,
    min_leg_odds: float = 1.12,
    max_legs: int = 3,
) -> list[LiveValueCombo]:
    """Build conservative multi-game combos from individually qualified value legs.

    Rules:
    - only BET_ELIGIBLE legs
    - at most one leg per fixture to avoid same-game correlation
    - each leg must meet minimum decimal odds
    - prefer 2 legs, allow 3 only if needed to reach the target band
    """
    from itertools import combinations

    pool: list[tuple[int, LiveValueCandidate]] = []
    for fixture_id, candidates in candidates_by_fixture.items():
        eligible = [
            c for c in candidates
            if c.status == "BET_ELIGIBLE" and c.odds >= min_leg_odds
        ]
        if eligible:
            best = max(
                eligible,
                key=lambda c: (
                    c.expected_value,
                    c.edge or -1.0,
                    c.model_probability,
                ),
            )
            pool.append((fixture_id, best))

    combos: list[LiveValueCombo] = []
    for size in range(2, max_legs + 1):
        for items in combinations(pool, size):
            fixture_ids = [fixture_id for fixture_id, _ in items]
            if len(set(fixture_ids)) != size:
                continue

            legs = tuple(candidate for _, candidate in items)
            combined_odds = 1.0
            combined_probability = 1.0
            for leg in legs:
                combined_odds *= leg.odds
                combined_probability *= leg.model_probability

            combo_ev = combined_probability * combined_odds - 1.0
            if target_min_odds <= combined_odds <= target_max_odds and combo_ev > 0:
                combos.append(
                    LiveValueCombo(
                        legs=legs,
                        combined_odds=combined_odds,
                        combined_probability=combined_probability,
                        expected_value=combo_ev,
                        status="VALUE_COMBO",
                    )
                )

    return sorted(
        combos,
        key=lambda combo: (
            abs(((target_min_odds + target_max_odds) / 2.0) - combo.combined_odds),
            -combo.expected_value,
            len(combo.legs),
        ),
    )
