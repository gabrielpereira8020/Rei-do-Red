"""Streamlit comparison panel for legacy pre-game analysis vs Football Intelligence."""

from __future__ import annotations

import streamlit as st

from football_intelligence.engine import FootballIntelligenceEngine
from football_intelligence.pregame_adapter import build_match_context
from football_intelligence.pregame_market import choose_best_prices, fetch_pregame_quotes
from football_intelligence.shadow import run_shadow


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _fmt_num(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _prob(result, key: str):
    return result.probabilities.get(key)


def _secret(name: str) -> str | None:
    try:
        return st.secrets.get(name)
    except Exception:
        return None


def render_pregame_intelligence(jogo_info: dict) -> None:
    """Render the deterministic pre-game baseline next to the legacy analysis.

    This function does not call Gemini, Telegram or register bets. When a supported
    odds provider is configured, it also calculates de-vig market probability,
    edge, EV and a conservative shadow decision.
    """
    st.markdown("### 🧠 Football Intelligence — Pré-Jogo")
    st.caption(
        "Baseline estatístico em paralelo ao sistema legado. Probabilidade do modelo, "
        "qualidade, preço de mercado e decisão permanecem separados."
    )

    with st.spinner("Calculando Football Intelligence do pré-jogo..."):
        context = build_match_context(jogo_info)
        if context is None:
            st.warning("Dados estatísticos insuficientes para o motor novo neste jogo.")
            return

        result = FootballIntelligenceEngine().analyze(context)

        odds_key = _secret("THE_ODDS_API_KEY")
        quotes = []
        if odds_key:
            try:
                quotes = choose_best_prices(fetch_pregame_quotes(jogo_info, odds_key))
            except Exception:
                quotes = []

        shadow = run_shadow(context, quotes)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("xG Casa", f"{result.expected_home_goals:.2f}")
    c2.metric("xG Fora", f"{result.expected_away_goals:.2f}")
    c3.metric("Qualidade dados", _fmt_pct(result.data_quality))
    c4.metric("Qualidade modelo", _fmt_pct(result.model_quality))

    if not odds_key:
        st.info("THE_ODDS_API_KEY não configurada: probabilidades continuam disponíveis, mas edge/EV não são calculados.")
    elif not quotes:
        st.warning("Não encontrei odds compatíveis para este jogo; o motor mantém a análise estatística e não força edge/EV.")

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
                "Odd justa": _fmt_num(item.fair_odds),
            })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.markdown("#### Gols")
    goal_rows = []
    for item in result.probabilities.values():
        if item.market != "TOTAL_GOALS":
            continue
        goal_rows.append({
            "Mercado": f"{item.selection} {item.line}",
            "Probabilidade": _fmt_pct(item.probability),
            "Odd justa": _fmt_num(item.fair_odds),
        })
    st.dataframe(goal_rows, use_container_width=True, hide_index=True)

    st.markdown("#### Ambas marcam")
    btts_rows = []
    for label, item in (("SIM", p_btts_yes), ("NÃO", p_btts_no)):
        if item is not None:
            btts_rows.append({
                "Seleção": label,
                "Probabilidade": _fmt_pct(item.probability),
                "Odd justa": _fmt_num(item.fair_odds),
            })
    st.dataframe(btts_rows, use_container_width=True, hide_index=True)

    st.markdown("#### Mercado / Edge / EV / Decisão")
    assessed_rows = []
    for item in shadow.assessments:
        # Keep the first screen focused on markets for which a market price exists.
        if item.offered_odds is None:
            continue
        label = item.selection if item.line is None else f"{item.selection} {item.line}"
        assessed_rows.append({
            "Mercado": item.market,
            "Seleção": label,
            "P modelo": _fmt_pct(item.probability),
            "Odd": _fmt_num(item.offered_odds),
            "P mercado devig": _fmt_pct(item.market_probability_devig),
            "Edge": _fmt_pct(item.edge),
            "EV": _fmt_pct(item.expected_value),
            "Decisão": item.decision.value,
        })

    if assessed_rows:
        st.dataframe(assessed_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("Sem preços completos suficientes para calcular de-vig/edge/EV neste jogo.")

    st.info(
        "Escanteios e cartões entrarão em modelos próprios na próxima etapa. "
        "O motor atual já separa probabilidade, qualidade do modelo, preço, edge, EV e decisão."
    )
