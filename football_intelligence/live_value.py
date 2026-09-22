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
