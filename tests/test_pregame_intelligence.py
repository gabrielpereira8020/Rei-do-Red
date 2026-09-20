from datetime import datetime, timezone

from football_intelligence.decision import assess_market
from football_intelligence.engine import FootballIntelligenceEngine
from football_intelligence.market import proportional_devig
from football_intelligence.models import (
    DecisionStatus,
    LeagueBaseline,
    MatchContext,
    OddsQuote,
    TeamProfile,
)
from football_intelligence.pregame_market import choose_best_prices
from football_intelligence.shadow import run_shadow


def _context() -> MatchContext:
    return MatchContext(
        fixture_id=123,
        league_id=39,
        season=2026,
        kickoff_utc=datetime(2026, 9, 17, 18, 0, tzinfo=timezone.utc),
        home=TeamProfile(
            team_id=1,
            name="Home",
            goals_for_avg=1.8,
            goals_against_avg=1.0,
            home_goals_for_avg=2.0,
            home_goals_against_avg=0.9,
            away_goals_for_avg=1.4,
            away_goals_against_avg=1.2,
            matches_sample=20,
        ),
        away=TeamProfile(
            team_id=2,
            name="Away",
            goals_for_avg=1.4,
            goals_against_avg=1.3,
            home_goals_for_avg=1.6,
            home_goals_against_avg=1.1,
            away_goals_for_avg=1.2,
            away_goals_against_avg=1.5,
            matches_sample=20,
        ),
        league=LeagueBaseline(
            league_id=39,
            season=2026,
            home_goals_avg=1.55,
            away_goals_avg=1.20,
        ),
    )


def test_engine_probabilities_are_bounded():
    result = FootballIntelligenceEngine().analyze(_context())
    assert result.expected_home_goals >= 0
    assert result.expected_away_goals >= 0
    assert 0 <= result.data_quality <= 1
    assert 0 <= result.model_quality <= 1
    assert abs(
        result.probabilities["1x2_home"].probability
        + result.probabilities["1x2_draw"].probability
        + result.probabilities["1x2_away"].probability
        - 1.0
    ) < 1e-6


def test_choose_best_prices_keeps_highest_quote():
    now = datetime.now(timezone.utc)
    quotes = [
        OddsQuote("A", "TOTAL_GOALS", "OVER", 1.80, now, 2.5),
        OddsQuote("B", "TOTAL_GOALS", "OVER", 1.95, now, 2.5),
    ]
    best = choose_best_prices(quotes)
    assert len(best) == 1
    assert best[0].bookmaker == "B"
    assert best[0].decimal_odds == 1.95


def test_proportional_devig_two_way_sums_to_one():
    probs = proportional_devig({"OVER": 1.90, "UNDER": 1.95})
    assert abs(sum(probs.values()) - 1.0) < 1e-12


def test_decision_requires_positive_edge_and_ev():
    result = FootballIntelligenceEngine().analyze(_context())
    p = result.probabilities["goals_over_2_5"]
    quote = OddsQuote(
        "Test",
        "TOTAL_GOALS",
        "OVER",
        max((p.fair_odds or 2.0) * 1.10, 1.01),
        datetime.now(timezone.utc),
        2.5,
    )
    assessment = assess_market(
        probability=p,
        quote=quote,
        market_probability_devig=max(0.0, p.probability - 0.05),
        data_quality=result.data_quality,
        model_quality=result.model_quality,
    )
    assert assessment.edge is not None and assessment.edge > 0
    assert assessment.expected_value is not None and assessment.expected_value > 0
    assert assessment.decision in {DecisionStatus.BET_ELIGIBLE, DecisionStatus.WATCH}


def test_run_shadow_uses_best_price_but_same_bookmaker_for_devig():
    now = datetime.now(timezone.utc)
    quotes = [
        OddsQuote("A", "TOTAL_GOALS", "OVER", 2.05, now, 2.5),
        OddsQuote("A", "TOTAL_GOALS", "UNDER", 1.80, now, 2.5),
        OddsQuote("B", "TOTAL_GOALS", "OVER", 1.95, now, 2.5),
        OddsQuote("B", "TOTAL_GOALS", "UNDER", 1.95, now, 2.5),
    ]
    snapshot = run_shadow(_context(), quotes, min_edge=-1.0, min_ev=-1.0)
    over = next(
        item for item in snapshot.assessments
        if item.market == "TOTAL_GOALS" and item.selection == "OVER" and item.offered_odds is not None
    )
    assert over.offered_odds == 2.05
    expected = proportional_devig({"OVER": 2.05, "UNDER": 1.80})["OVER"]
    assert over.market_probability_devig is not None
    assert abs(over.market_probability_devig - expected) < 1e-12


def test_run_shadow_rejects_incomplete_book_for_devig():
    now = datetime.now(timezone.utc)
    quotes = [
        OddsQuote("A", "TOTAL_GOALS", "OVER", 2.05, now, 2.5),
        OddsQuote("B", "TOTAL_GOALS", "UNDER", 1.95, now, 2.5),
    ]
    snapshot = run_shadow(_context(), quotes)
    over = next(
        item for item in snapshot.assessments
        if item.market == "TOTAL_GOALS" and item.selection == "OVER" and item.offered_odds is not None
    )
    assert over.offered_odds == 2.05
    assert over.market_probability_devig is None


def test_live_intelligence_modules_exist():
    from pathlib import Path
    assert Path("football_intelligence/live_engine.py").exists()
    assert Path("football_intelligence/live_adapter.py").exists()
    live_engine = Path("football_intelligence/live_engine.py").read_text(encoding="utf-8")
    radar = Path("radar_ao_vivo_automatico.py").read_text(encoding="utf-8")
    assert "def analyze_live" in live_engine
    assert "Football Intelligence" in radar
    assert "REI-DO-RED" in radar


def test_live_engine_includes_corners_and_cards_signals():
    from datetime import datetime, timezone
    from football_intelligence.live_engine import analyze_live
    from football_intelligence.models import LeagueBaseline, LiveState, MatchContext, TeamProfile

    ctx = MatchContext(
        fixture_id=999,
        league_id=39,
        season=2026,
        kickoff_utc=datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc),
        home=TeamProfile(team_id=1, name="Home", home_goals_for_avg=1.5, home_goals_against_avg=1.0, matches_sample=20),
        away=TeamProfile(team_id=2, name="Away", away_goals_for_avg=1.2, away_goals_against_avg=1.4, matches_sample=20),
        league=LeagueBaseline(league_id=39, season=2026, home_goals_avg=1.5, away_goals_avg=1.2),
        live=LiveState(
            minute=60,
            home_goals=1,
            away_goals=0,
            home_shots=10,
            away_shots=7,
            home_shots_on_target=4,
            away_shots_on_target=2,
            home_corners=5,
            away_corners=3,
            home_cards=2,
            away_cards=1,
            home_fouls=8,
            away_fouls=10,
        ),
    )

    result = analyze_live(ctx, 1.5, 1.2)
    keys = {s.key for s in result.signals}
    assert "two_more_corners" in keys
    assert "one_more_card" in keys
    assert result.expected_remaining_corners >= 0
    assert result.expected_remaining_cards >= 0
