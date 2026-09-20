from pathlib import Path
import importlib.util

def test_daily_panel_file_exists():
    path = Path("painel_do_dia.py")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Painel do Dia" in text
    assert "Alternativos" in text
    assert "Varrer jogos" in text

def test_main_wires_daily_panel():
    text = Path("main.py").read_text(encoding="utf-8")
    assert "from painel_do_dia import tela_painel_do_dia" in text
    assert '"📊 PAINEL DO DIA"' in text
    assert "tela_painel_do_dia()" in text

def test_alternative_markets_wired():
    panel = Path("painel_do_dia.py").read_text(encoding="utf-8")
    engine = Path("football_intelligence/alternative_markets.py").read_text(encoding="utf-8")
    assert "estimate_corners_and_cards" in panel
    assert "TOTAL_CORNERS" in engine
    assert "TOTAL_CARDS" in engine
    assert "Escanteios" in panel
    assert "Cartões" in panel

def test_recent_hit_rate_helpers_present():
    engine = Path("football_intelligence/alternative_markets.py").read_text(encoding="utf-8")
    panel = Path("painel_do_dia.py").read_text(encoding="utf-8")
    assert "def hit_rate" in engine
    assert "def recent_market_profile" in engine
    assert "Casa L5" in panel
    assert "Fora L10" in panel

def test_player_props_wired():
    props = Path("football_intelligence/player_props.py").read_text(encoding="utf-8")
    panel = Path("painel_do_dia.py").read_text(encoding="utf-8")
    assert "PLAYER_SHOTS" in props
    assert "PLAYER_SHOTS_ON_TARGET" in props
    assert "GOALKEEPER_SAVES" in props
    assert "🎯 Jogadores" in panel
    assert "estimate_player_props" in panel

def test_candidate_label_tolerates_market_assessment_without_line():
    panel = Path("painel_do_dia.py").read_text(encoding="utf-8")
    assert 'getattr(item, "line", None)' in panel
