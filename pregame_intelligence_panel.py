"""Streamlit comparison panel for legacy pre-game analysis vs Football Intelligence."""

from __future__ import annotations

import streamlit as st

from football_intelligence.engine import FootballIntelligenceEngine
from football_intelligence.pregame_adapter import build_match_context


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _prob(result, key: str):
    return result.probabilities.get(key)


def render_pregame_intelligence(jogo_info: dict) -> None:
    """Render the deterministic pre-game baseline next to the legacy analysis.

    This function does not call Gemini, Telegram or place/register bets.
    """
    st.markdown("### 🧠 Football Intelligence — Pré-Jogo")
    st.caption("Baseline estatístico em paralelo ao sistema legado. Ainda não substitui a análise atual.")

    with st.spinner("Calculando baseline estatístico do pré-jogo..."):
        context = build_match_context(jogo_info)
        if context is None:
            st.warning("Dados estatísticos insuficientes para o motor novo neste jogo.")
            return
        result = FootballIntelligenceEngine().analyze(context)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("xG Casa", f"{result.expected_home_goals:.2f}")
    c2.metric("xG Fora", f"{result.expected_away_goals:.2f}")
    c3.metric("Qualidade dados", _fmt_pct(result.data_quality))
    c4.metric("Qualidade modelo", _fmt_pct(result.model_quality))

    p_home = _prob(result, "1x2_home")
    p_draw = _prob(result, "1x2_draw")
    p_away = _prob(result, "1x2_away")
    p_1x = _prob(result, "dc_1x")
    p_x2 = _prob(result, "dc_x2")
    p_12 = _prob(result, "dc_12")
    p_btts_yes = _prob(result, "btts_yes")
    p_btts_no = _prob(result, "btts_no")

    st.markdown("#### Resultado / Dupla chance")
    rows = []
    for label, item in (
        ("Casa", p_home), ("Empate", p_draw), ("Fora", p_away),
        ("1X", p_1x), ("X2", p_x2), ("12", p_12),
    ):
        if item is not None:
            rows.append({
                "Mercado": label,
                "Probabilidade": _fmt_pct(item.probability),
                "Odd justa": "—" if item.fair_odds is None else f"{item.fair_odds:.2f}",
            })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("#### Gols")
    goal_rows = []
    for key, item in result.probabilities.items():
        if item.market != "TOTAL_GOALS":
            continue
        goal_rows.append({
            "Mercado": f"{item.selection} {item.line}",
            "Probabilidade": _fmt_pct(item.probability),
            "Odd justa": "—" if item.fair_odds is None else f"{item.fair_odds:.2f}",
        })
    st.dataframe(goal_rows, use_container_width=True, hide_index=True)

    st.markdown("#### Ambas marcam")
    btts_rows = []
    for label, item in (("SIM", p_btts_yes), ("NÃO", p_btts_no)):
        if item is not None:
            btts_rows.append({
                "Seleção": label,
                "Probabilidade": _fmt_pct(item.probability),
                "Odd justa": "—" if item.fair_odds is None else f"{item.fair_odds:.2f}",
            })
    st.dataframe(btts_rows, use_container_width=True, hide_index=True)

    st.info(
        "Escanteios e cartões serão adicionados em modelos separados. "
        "Nesta fase o objetivo é validar gols, 1X2, dupla chance e BTTS sem depender do Gemini."
    )
