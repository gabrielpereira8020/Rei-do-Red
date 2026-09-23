"""Streamlit comparison panel for legacy pre-game analysis vs Football Intelligence."""

from __future__ import annotations

import re
from typing import Any

import streamlit as st

from football_intelligence.engine import FootballIntelligenceEngine
from football_intelligence.pregame_adapter import build_match_context
from football_intelligence.pregame_market import fetch_pregame_quotes
from football_intelligence.shadow import run_shadow
from football_intelligence.supabase_shadow_store import SupabaseShadowSnapshotStore



def build_pregame_fi_context(jogo_info: dict) -> tuple[str, object | None, object | None]:
    """Return a compact, deterministic FI summary for Gemini plus raw result/shadow."""
    context = build_match_context(jogo_info)
    if context is None:
        return "Dados insuficientes para Football Intelligence.", None, None

    result = FootballIntelligenceEngine().analyze(context)
    odds_key = _secret("THE_ODDS_API_KEY")
    quotes = []
    if odds_key:
        try:
            quotes = fetch_pregame_quotes(jogo_info, odds_key)
        except Exception:
            quotes = []
    shadow = run_shadow(context, quotes)

    eligible = [x for x in shadow.assessments if x.decision.value == "BET_ELIGIBLE"]
    watch = [x for x in shadow.assessments if x.decision.value == "WATCH"]
    suggestion_pool = [
        x for x in watch
        if x.offered_odds is None
        and x.probability >= 0.70
        and x.data_quality >= 0.75
        and x.model_quality >= 0.35
    ]

    ranked = sorted(
        eligible if eligible else (suggestion_pool if suggestion_pool else watch),
        key=lambda x: (
            x.expected_value if x.expected_value is not None else -999,
            x.edge if x.edge is not None else -999,
            x.probability,
        ),
        reverse=True,
    )

    lines = [
        f"Jogo: {jogo_info.get('nome')}",
        f"Qualidade dados: {result.data_quality*100:.1f}%",
        f"Qualidade modelo: {result.model_quality*100:.1f}%",
        f"xG casa: {result.expected_home_goals:.2f}",
        f"xG fora: {result.expected_away_goals:.2f}",
    ]
    if not ranked:
        lines.append("Nenhum mercado com WATCH/BET_ELIGIBLE e preço compatível.")
    else:
        if not eligible and suggestion_pool:
            lines.append(
                "MODO SUGESTÃO: não há preço de mercado suficiente para validar valor. "
                "Os itens abaixo são somente indicações estatísticas e NÃO são BET_ELIGIBLE."
            )
        lines.append("Mercados ranqueados:")
        for idx, item in enumerate(ranked[:5], start=1):
            item_line = getattr(item, "line", None)
            line = "" if item_line is None else f" {item_line}"
            odd = f"{item.offered_odds:.2f}" if item.offered_odds is not None else "—"
            edge_txt = f"{item.edge*100:.1f}%" if item.edge is not None else "—"
            ev_txt = f"{item.expected_value*100:.1f}%" if item.expected_value is not None else "—"
            fair = f"{item.fair_odds:.2f}" if getattr(item, "fair_odds", None) is not None else "—"
            lines.append(
                f"{idx}. {item.market} {item.selection}{line} | status {item.decision.value} | "
                f"P modelo {item.probability*100:.1f}% | odd justa {fair} | odd mercado {odd} | "
                f"edge {edge_txt} | EV {ev_txt}"
            )
    return "\n".join(lines), result, shadow


def render_integrated_pregame_summary(jogo_info: dict, gemini_text: str, result, shadow) -> None:
    st.markdown("### 🧠 Rei-do-Red Intelligence — Pré-Jogo Integrado")
    st.caption("Football Intelligence escolhe o mercado; Gemini explica contexto, riscos e leitura do jogo.")

    eligible = [x for x in shadow.assessments if x.decision.value == "BET_ELIGIBLE"] if shadow else []
    if eligible:
        best = max(
            eligible,
            key=lambda x: (
                x.expected_value if x.expected_value is not None else -999,
                x.edge if x.edge is not None else -999,
            ),
        )
        best_line = getattr(best, "line", None)
        line = "" if best_line is None else f" {best_line}"
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Mercado principal", f"{best.selection}{line}")
        c2.metric("P modelo", _fmt_pct(best.probability))
        c3.metric("Odd mercado", _fmt_num(best.offered_odds))
        c4.metric("EV", _fmt_pct(best.expected_value))

        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Odd justa", _fmt_num(getattr(best, "fair_odds", None)))
        q2.metric("Edge", _fmt_pct(best.edge))
        q3.metric("Dados", _fmt_pct(result.data_quality if result else None))
        q4.metric("Modelo", _fmt_pct(result.model_quality if result else None))
    else:
        suggestions = [
            x for x in shadow.assessments
            if x.decision.value == "WATCH"
            and x.offered_odds is None
            and x.probability >= 0.70
            and x.data_quality >= 0.75
            and x.model_quality >= 0.35
        ] if shadow else []
        if suggestions:
            best_suggestion = max(suggestions, key=lambda x: x.probability)
            line = "" if best_suggestion.line is None else f" {best_suggestion.line}"
            st.warning(
                f"Sem BET_ELIGIBLE porque não há odd completa para validar valor. "
                f"Sugestão estatística: {best_suggestion.market} {best_suggestion.selection}{line} "
                f"com P modelo {_fmt_pct(best_suggestion.probability)} e odd justa {_fmt_num(best_suggestion.fair_odds)}. "
                "Isto é feeling/modelo, não entrada validada por preço."
            )
        else:
            st.info("Nenhum BET_ELIGIBLE e nenhuma sugestão estatística forte encontrada neste jogo.")

    with st.expander("🔎 Explicação integrada do Gemini", expanded=True):
        st.write(gemini_text)

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


def _legacy_signals(text: str | None) -> set[str]:
    """Extract coarse market mentions from the legacy Gemini text.

    This is intentionally descriptive only: it never converts the LLM text into
    a probability or decision. It is used solely to show agreement/divergence.
    """
    if not text:
        return set()

    normalized = re.sub(r"\s+", " ", text.lower())
    signals: set[str] = set()

    patterns = {
        "1X2_HOME": ("vitória mandante", "vitoria mandante", "casa vence", "home win"),
        "1X2_AWAY": ("vitória visitante", "vitoria visitante", "fora vence", "away win"),
        "BTTS_YES": ("ambas marcam", "btts sim", "both teams to score"),
        "DC_1X": ("dupla chance 1x", "double chance 1x", " 1x "),
        "DC_X2": ("dupla chance x2", "double chance x2", " x2 "),
    }

    for key, aliases in patterns.items():
        if any(alias in normalized for alias in aliases):
            signals.add(key)

    for direction, key_prefix in (("over", "OVER"), ("under", "UNDER")):
        for match in re.finditer(rf"{direction}\s*(\d+(?:[\.,]\d+)?)", normalized):
            line = match.group(1).replace(",", ".")
            signals.add(f"GOALS_{key_prefix}_{line}")

    return signals


def _assessment_signal(item: Any) -> str | None:
    market = item.market.upper()
    selection = item.selection.upper()

    if market == "1X2" and selection == "HOME":
        return "1X2_HOME"
    if market == "1X2" and selection == "AWAY":
        return "1X2_AWAY"
    if market == "BTTS" and selection == "YES":
        return "BTTS_YES"
    if market == "DOUBLE_CHANCE" and selection in {"1X", "X2"}:
        return f"DC_{selection}"
    if market == "TOTAL_GOALS" and item.line is not None:
        return f"GOALS_{selection}_{float(item.line):.1f}"
    return None


def _render_legacy_comparison(legacy_text: str | None, shadow) -> None:
    st.markdown("#### Comparação estruturada — Legado × Intelligence")

    if not legacy_text:
        st.caption("Gere também a análise legada para comparar concordância e divergência.")
        return

    legacy = _legacy_signals(legacy_text)
    eligible = [item for item in shadow.assessments if item.decision.value == "BET_ELIGIBLE"]

    if not eligible:
        st.info("O Football Intelligence não marcou nenhum mercado como BET_ELIGIBLE neste jogo.")
        return

    rows = []
    for item in eligible:
        signal = _assessment_signal(item)
        if signal is None:
            agreement = "NÃO CLASSIFICADO"
        elif signal in legacy:
            agreement = "CONCORDA"
        else:
            agreement = "NÃO IDENTIFICADO NO LEGADO"

        label = item.selection if item.line is None else f"{item.selection} {item.line}"
        rows.append({
            "Mercado": item.market,
            "Seleção": label,
            "P modelo": _fmt_pct(item.probability),
            "Edge": _fmt_pct(item.edge),
            "EV": _fmt_pct(item.expected_value),
            "Comparação": agreement,
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(
        "A comparação acima apenas detecta menções no texto legado. Ela não transforma a resposta do Gemini em probabilidade."
    )


def render_pregame_intelligence(
    jogo_info: dict,
    *,
    supabase=None,
    legacy_text: str | None = None,
) -> None:
    """Render and optionally persist the deterministic pre-game shadow analysis."""
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
                quotes = fetch_pregame_quotes(jogo_info, odds_key)
            except Exception:
                quotes = []

        shadow = run_shadow(context, quotes)

        persisted = False
        persistence_error = None
        if supabase is not None:
            try:
                SupabaseShadowSnapshotStore(supabase).save(
                    shadow,
                    match_meta={
                        "home_team": jogo_info.get("casa"),
                        "away_team": jogo_info.get("fora"),
                        "league_name": jogo_info.get("liga") or jogo_info.get("campeonato"),
                        "kickoff": jogo_info.get("data"),
                    },
                    gemini_text=legacy_text,
                )
                persisted = True
            except Exception as exc:
                persistence_error = str(exc)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("xG Casa", f"{result.expected_home_goals:.2f}")
    c2.metric("xG Fora", f"{result.expected_away_goals:.2f}")
    c3.metric("Qualidade dados", _fmt_pct(result.data_quality))
    c4.metric("Qualidade modelo", _fmt_pct(result.model_quality))

    if persisted:
        st.success("Snapshot pré-jogo salvo no Shadow Lab para comparação futura.")
    elif persistence_error:
        st.warning(f"Análise calculada, mas não consegui salvar o snapshot: {persistence_error}")

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

    _render_legacy_comparison(legacy_text, shadow)

    st.info(
        "Escanteios e cartões entrarão em modelos próprios na próxima etapa. "
        "O motor atual já separa probabilidade, qualidade do modelo, preço, edge, EV e decisão."
    )
