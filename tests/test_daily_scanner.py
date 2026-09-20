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
