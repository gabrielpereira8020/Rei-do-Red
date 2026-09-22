"""Pre-game market quote normalization for Football Intelligence.

Reads existing odds providers without changing legacy behavior and converts
supported markets into typed OddsQuote objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from the_odds_api import buscar_odds_jogo

from .models import OddsQuote


def _safe_float(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value > 1.0 else None


def _norm(text: Any) -> str:
    return str(text or "").strip().lower()


def _quotes_from_the_odds_api(payload: dict[str, Any] | None) -> list[OddsQuote]:
    if not payload:
        return []

    home = _norm(payload.get("home_team"))
    away = _norm(payload.get("away_team"))
    captured_at = datetime.now(timezone.utc)
    quotes: list[OddsQuote] = []

    for bm in payload.get("bookmakers", []):
        bookmaker = str(bm.get("title") or "unknown")
        for market in bm.get("markets", []):
            key = market.get("key")
            outcomes = market.get("outcomes", [])

            if key == "h2h":
                for outcome in outcomes:
                    price = _safe_float(outcome.get("price"))
                    if price is None:
                        continue
                    name = _norm(outcome.get("name"))
                    if name == home:
                        selection = "HOME"
                    elif name == away:
                        selection = "AWAY"
                    elif name in {"draw", "empate"}:
                        selection = "DRAW"
                    else:
                        continue
                    quotes.append(OddsQuote(bookmaker, "1X2", selection, price, captured_at))

            elif key == "totals":
                for outcome in outcomes:
                    price = _safe_float(outcome.get("price"))
                    point = outcome.get("point")
                    if price is None or point is None:
                        continue
                    name = _norm(outcome.get("name"))
                    if name == "over":
                        selection = "OVER"
                    elif name == "under":
                        selection = "UNDER"
                    else:
                        continue
                    quotes.append(
                        OddsQuote(bookmaker, "TOTAL_GOALS", selection, price, captured_at, float(point))
                    )

            elif key in {"alternate_totals", "alternate_spreads"}:
                # Not mapped here: these provider-specific keys are not reliably
                # equivalent to corners/cards totals without an explicit market id.
                continue

            elif key in {"totals_corners", "corners", "alternate_totals_corners"}:
                for outcome in outcomes:
                    price = _safe_float(outcome.get("price"))
                    point = outcome.get("point")
                    if price is None or point is None:
                        continue
                    name = _norm(outcome.get("name"))
                    if name == "over":
                        selection = "OVER"
                    elif name == "under":
                        selection = "UNDER"
                    else:
                        continue
                    quotes.append(OddsQuote(bookmaker, "TOTAL_CORNERS", selection, price, captured_at, float(point)))

            elif key in {"totals_cards", "cards", "alternate_totals_cards"}:
                for outcome in outcomes:
                    price = _safe_float(outcome.get("price"))
                    point = outcome.get("point")
                    if price is None or point is None:
                        continue
                    name = _norm(outcome.get("name"))
                    if name == "over":
                        selection = "OVER"
                    elif name == "under":
                        selection = "UNDER"
                    else:
                        continue
                    quotes.append(OddsQuote(bookmaker, "TOTAL_CARDS", selection, price, captured_at, float(point)))

            elif key == "btts":
                for outcome in outcomes:
                    price = _safe_float(outcome.get("price"))
                    if price is None:
                        continue
                    name = _norm(outcome.get("name"))
                    if name in {"yes", "sim"}:
                        selection = "YES"
                    elif name in {"no", "não", "nao"}:
                        selection = "NO"
                    else:
                        continue
                    quotes.append(OddsQuote(bookmaker, "BTTS", selection, price, captured_at))

    return quotes


def fetch_pregame_quotes(jogo: dict[str, Any], api_key: str | None) -> list[OddsQuote]:
    """Return normalized supported pre-game quotes.

    If the provider/key is unavailable, returns an empty list. Missing price is kept
    missing; nothing is coerced to zero.
    """
    if not api_key:
        return []
    payload = buscar_odds_jogo(
        jogo["casa"],
        jogo["fora"],
        int(jogo["liga_id"]),
        api_key,
        odd_min=1.01,
        odd_max=100.0,
    )
    return _quotes_from_the_odds_api(payload)


def choose_best_prices(quotes: Iterable[OddsQuote]) -> list[OddsQuote]:
    """Keep the highest valid decimal price for each market/selection/line."""
    best: dict[tuple[str, str, float | None], OddsQuote] = {}
    for quote in quotes:
        key = (quote.market, quote.selection, quote.line)
        current = best.get(key)
        if current is None or quote.decimal_odds > current.decimal_odds:
            best[key] = quote
    return list(best.values())
