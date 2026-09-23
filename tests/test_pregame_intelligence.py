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


def test_expanded_leagues_are_available():
    from ligas import LIGAS
    assert LIGAS["Argentina"]["Liga Profesional"] == 128
    assert LIGAS["Holanda"]["Eredivisie"] == 88
    assert LIGAS["Belgica"]["Jupiler Pro League"] == 144
    assert LIGAS["Austria"]["Bundesliga"] == 218
    assert LIGAS["Suica"]["Super League"] == 207
    assert LIGAS["Turquia"]["Super Lig"] == 203


def test_gemini_live_is_bound_to_football_intelligence():
    from pathlib import Path
    ia = Path("ia_engine.py").read_text(encoding="utf-8")
    radar = Path("radar_ao_vivo_automatico.py").read_text(encoding="utf-8")
    ao = Path("ao_vivo.py").read_text(encoding="utf-8")
    assert "fi_signals=None" in ia
    assert "Football Intelligence é a fonte principal" in ia
    assert "fi_signals=actionable" in radar
    assert "fi_signals=live_result.signals" in ao


def test_live_engine_includes_next_10_minute_signals():
    from datetime import datetime, timezone
    from football_intelligence.live_engine import analyze_live
    from football_intelligence.models import LeagueBaseline, LiveState, MatchContext, TeamProfile

    ctx = MatchContext(
        fixture_id=1001,
        league_id=39,
        season=2026,
        kickoff_utc=datetime(2026, 9, 21, 20, 0, tzinfo=timezone.utc),
        home=TeamProfile(team_id=1, name="Home", home_goals_for_avg=1.6, home_goals_against_avg=1.0, matches_sample=20),
        away=TeamProfile(team_id=2, name="Away", away_goals_for_avg=1.1, away_goals_against_avg=1.4, matches_sample=20),
        league=LeagueBaseline(league_id=39, season=2026, home_goals_avg=1.5, away_goals_avg=1.2),
        live=LiveState(
            minute=55,
            home_goals=1,
            away_goals=1,
            home_shots=12,
            away_shots=8,
            home_shots_on_target=5,
            away_shots_on_target=3,
            home_corners=5,
            away_corners=4,
            home_cards=1,
            away_cards=2,
            home_fouls=7,
            away_fouls=9,
        ),
    )

    result = analyze_live(ctx, 1.5, 1.2)
    keys = {s.key for s in result.signals}
    assert "corner_next_10m" in keys
    assert "card_next_10m" in keys
    assert "goal_next_10m" in keys


def test_live_ui_contains_signal_cards():
    from pathlib import Path
    main = Path("main.py").read_text(encoding="utf-8")
    ao = Path("ao_vivo.py").read_text(encoding="utf-8")
    assert ".signal-card" in main
    assert "Janelas rápidas" in ao


def test_live_value_matches_corner_total_line():
    from football_intelligence.live_value import evaluate_corner_value
    from types import SimpleNamespace

    live_result = SimpleNamespace(
        data_quality=1.0,
        model_quality=0.9,
        signals=(
            SimpleNamespace(key="one_more_corner", probability=0.80),
            SimpleNamespace(key="two_more_corners", probability=0.65),
            SimpleNamespace(key="three_more_corners", probability=0.45),
        ),
    )
    payload = [{
        "bets": [{
            "name": "Corners",
            "values": [
                {"value": "Over 9.5", "odd": "1.50"},
                {"value": "Under 9.5", "odd": "2.40"},
            ],
        }]
    }]

    result = evaluate_corner_value(live_result, current_corners=9, odds_payload=payload)
    assert result
    assert result[0].line == 9.5
    assert result[0].label == "Over 9.5 escanteios"


def test_live_value_can_mark_bet_eligible():
    from football_intelligence.live_value import evaluate_corner_value
    from types import SimpleNamespace

    live_result = SimpleNamespace(
        data_quality=1.0,
        model_quality=0.9,
        signals=(SimpleNamespace(key="one_more_corner", probability=0.90),),
    )
    payload = [{
        "bets": [{
            "name": "Total Corners",
            "values": [
                {"value": "Over 9.5", "odd": "1.45"},
                {"value": "Under 9.5", "odd": "2.70"},
            ],
        }]
    }]

    result = evaluate_corner_value(live_result, current_corners=9, odds_payload=payload)
    assert result[0].status == "BET_ELIGIBLE"
    assert result[0].expected_value > 0


def test_live_value_matches_goal_total_line():
    from football_intelligence.live_value import evaluate_goal_value
    from types import SimpleNamespace

    live_result = SimpleNamespace(
        data_quality=1.0,
        model_quality=0.9,
        signals=(
            SimpleNamespace(key="next_goal_any", probability=0.82),
            SimpleNamespace(key="two_more_goals", probability=0.44),
        ),
    )
    payload = [{
        "bets": [{
            "name": "Total Goals",
            "values": [
                {"value": "Over 2.5", "odd": "1.55"},
                {"value": "Under 2.5", "odd": "2.35"},
            ],
        }]
    }]

    result = evaluate_goal_value(live_result, current_goals=2, odds_payload=payload)
    assert result
    assert result[0].label == "Over 2.5 gols"


def test_live_value_matches_card_total_line():
    from football_intelligence.live_value import evaluate_card_value
    from types import SimpleNamespace

    live_result = SimpleNamespace(
        data_quality=1.0,
        model_quality=0.9,
        signals=(
            SimpleNamespace(key="one_more_card", probability=0.80),
            SimpleNamespace(key="two_more_cards", probability=0.52),
        ),
    )
    payload = [{
        "bets": [{
            "name": "Total Cards",
            "values": [
                {"value": "Over 3.5", "odd": "1.70"},
                {"value": "Under 3.5", "odd": "2.05"},
            ],
        }]
    }]

    result = evaluate_card_value(live_result, current_cards=3, odds_payload=payload)
    assert result
    assert result[0].label == "Over 3.5 cartões"


def test_all_live_value_combines_supported_markets():
    from football_intelligence.live_value import evaluate_all_live_value
    from types import SimpleNamespace

    live_result = SimpleNamespace(
        data_quality=1.0,
        model_quality=0.9,
        signals=(
            SimpleNamespace(key="next_goal_any", probability=0.80),
            SimpleNamespace(key="two_more_goals", probability=0.40),
            SimpleNamespace(key="one_more_corner", probability=0.85),
            SimpleNamespace(key="two_more_corners", probability=0.60),
            SimpleNamespace(key="three_more_corners", probability=0.35),
            SimpleNamespace(key="one_more_card", probability=0.78),
            SimpleNamespace(key="two_more_cards", probability=0.48),
        ),
    )
    payload = [{
        "bets": [
            {"name": "Total Goals", "values": [{"value": "Over 1.5", "odd": "1.60"}, {"value": "Under 1.5", "odd": "2.20"}]},
            {"name": "Total Corners", "values": [{"value": "Over 7.5", "odd": "1.50"}, {"value": "Under 7.5", "odd": "2.45"}]},
            {"name": "Total Cards", "values": [{"value": "Over 2.5", "odd": "1.65"}, {"value": "Under 2.5", "odd": "2.10"}]},
        ]
    }]

    result = evaluate_all_live_value(live_result, current_goals=1, current_corners=7, current_cards=2, odds_payload=payload)
    markets = {item.market for item in result}
    assert "TOTAL_GOALS" in markets
    assert "TOTAL_CORNERS" in markets
    assert "TOTAL_CARDS" in markets


def test_value_combo_uses_only_individually_eligible_different_fixtures():
    from football_intelligence.live_value import LiveValueCandidate, build_value_combos

    def c(label, odds, p, ev, status="BET_ELIGIBLE"):
        return LiveValueCandidate(
            market="TOTAL_CORNERS",
            line=9.5,
            selection="OVER",
            odds=odds,
            model_probability=p,
            market_probability_raw=0.7,
            market_probability_devig=0.68,
            edge=0.08,
            expected_value=ev,
            status=status,
            label=label,
        )

    candidates = {
        1: [c("A", 1.20, 0.88, 0.056)],
        2: [c("B", 1.25, 0.86, 0.075)],
        3: [c("C", 1.10, 0.93, 0.023, status="WATCH")],
    }

    combos = build_value_combos(candidates, target_min_odds=1.40, target_max_odds=1.60)
    assert combos
    combo = combos[0]
    assert len(combo.legs) == 2
    assert 1.40 <= combo.combined_odds <= 1.60
    assert all(leg.status == "BET_ELIGIBLE" for leg in combo.legs)
    assert combo.expected_value > 0


def test_pregame_alternative_value_requires_real_matching_quote():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from football_intelligence.models import OddsQuote
    from football_intelligence.pregame_value import alternative_value_candidates

    estimates = {
        "corners": SimpleNamespace(
            market="TOTAL_CORNERS",
            line=8.5,
            probability_over=0.78,
            quality=0.9,
        )
    }
    quotes = [
        OddsQuote("Book", "TOTAL_CORNERS", "OVER", 1.55, datetime.now(timezone.utc), 8.5),
        OddsQuote("Book", "TOTAL_CORNERS", "UNDER", 2.20, datetime.now(timezone.utc), 8.5),
    ]
    result = alternative_value_candidates(
        fixture_id=1,
        game="Home x Away",
        estimates=estimates,
        quotes=quotes,
        data_quality=0.95,
        model_quality=0.8,
    )
    assert result
    assert result[0].market == "TOTAL_CORNERS"
    assert result[0].odds == 1.55


def test_pregame_combo_allows_same_fixture_when_legs_are_individually_eligible():
    from football_intelligence.pregame_value import PregameValueCandidate, build_pregame_value_combos

    def c(fid, odds, p, ev, status="BET_ELIGIBLE"):
        return PregameValueCandidate(
            fixture_id=fid,
            game=f"Game {fid}",
            market="TOTAL_GOALS",
            line=1.5,
            selection="OVER",
            odds=odds,
            model_probability=p,
            market_probability_raw=1/odds,
            market_probability_devig=0.7,
            edge=0.07,
            expected_value=ev,
            data_quality=0.9,
            model_quality=0.8,
            status=status,
            bookmaker="Book",
            label="TOTAL_GOALS OVER 1.5",
        )

    combos = build_pregame_value_combos([
        c(1, 1.20, 0.88, 0.056),
        c(2, 1.25, 0.86, 0.075),
        c(1, 1.22, 0.87, 0.061),
        c(3, 1.10, 0.94, 0.034, status="WATCH"),
    ])
    assert combos
    assert all(leg.status == "BET_ELIGIBLE" for leg in combos[0].legs)

    same_game = build_pregame_value_combos([
        c(1, 1.20, 0.88, 0.056),
        c(1, 1.25, 0.86, 0.075),
    ])
    assert same_game
    assert all(leg.fixture_id == 1 for leg in same_game[0].legs)


def test_pregame_premium_value_card_ui_exists():
    from pathlib import Path
    painel = Path("painel_do_dia.py").read_text(encoding="utf-8")
    main = Path("main.py").read_text(encoding="utf-8")
    assert "Por que o Rei-do-Red escolheu este mercado?" in painel
    assert "def _entry_score" in painel
    assert "value-card-premium" in painel
    assert ".value-card-premium" in main


def test_pregame_gemini_is_bound_to_football_intelligence():
    from pathlib import Path
    ia = Path("ia_engine.py").read_text(encoding="utf-8")
    pre = Path("pre_jogo.py").read_text(encoding="utf-8")
    panel = Path("pregame_intelligence_panel.py").read_text(encoding="utf-8")
    assert "def gerar_analise_pre_jogo(jogo, fi_context=None)" in ia
    assert "Football Intelligence é a fonte principal" in ia
    assert "GERAR ANÁLISE INTEGRADA" in pre
    assert "build_pregame_fi_context" in pre
    assert "render_integrated_pregame_summary" in pre
    assert "def build_pregame_fi_context" in panel


def test_integrated_pregame_does_not_require_marketassessment_line_attribute():
    from pathlib import Path
    panel = Path("pregame_intelligence_panel.py").read_text(encoding="utf-8")
    assert 'getattr(item, "line", None)' in panel
    assert 'getattr(best, "line", None)' in panel


def test_pregame_gemini_has_fallback_model_and_graceful_outage():
    from pathlib import Path
    ia = Path("ia_engine.py").read_text(encoding="utf-8")
    pre = Path("pre_jogo.py").read_text(encoding="utf-8")
    assert "models/gemini-2.5-flash-lite" in ia
    assert "GEMINI INDISPONÍVEL NO MOMENTO" in ia
    assert "A decisão matemática do Football Intelligence continua válida" in ia
    assert "Gemini indisponível no momento" in pre


def test_market_assessment_preserves_line_for_pregame_suggestions():
    from football_intelligence.engine import FootballIntelligenceEngine
    from football_intelligence.shadow import run_shadow
    snapshot = run_shadow(_context(), odds=())
    over25 = next(
        x for x in snapshot.assessments
        if x.market == "TOTAL_GOALS" and x.selection == "OVER" and x.line == 2.5
    )
    assert over25.line == 2.5


def test_pregame_suggestion_mode_is_labeled_not_validated():
    from pathlib import Path
    panel = Path("pregame_intelligence_panel.py").read_text(encoding="utf-8")
    ia = Path("ia_engine.py").read_text(encoding="utf-8")
    assert "MODO SUGESTÃO" in panel
    assert "Sugestão estatística" in panel
    assert "SUGESTÃO / FEELING" in ia
    assert "SEM ENTRADA VALIDADA" in ia
