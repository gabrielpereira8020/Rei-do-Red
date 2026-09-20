"""Daily scanner UI for Rei-do-Red.

Phase 1: batch pre-game scan over selected major leagues using the deterministic
Football Intelligence engine. Alternative markets (corners/cards/player props)
will plug into this page as separate tabs/models later.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from api_football import buscar_jogos_da_liga
from football_intelligence.engine import FootballIntelligenceEngine
from football_intelligence.alternative_markets import estimate_corners_and_cards, recent_market_profile, hit_rate
from football_intelligence.pregame_adapter import build_match_context
from football_intelligence.player_props import estimate_player_props, best_player_props
from football_intelligence.pregame_market import fetch_pregame_quotes
from football_intelligence.shadow import run_shadow
from ligas import LIGAS, COMPETICOES_INTERNACIONAIS


DEFAULT_LEAGUES = [
    ("Inglaterra", "Premier League"),
    ("Espanha", "LaLiga"),
    ("Italia", "Serie A"),
    ("Alemanha", "Bundesliga"),
    ("Franca", "Ligue 1"),
    ("Brasil", "Serie A"),
]


def _league_catalog() -> dict[str, int]:
    result: dict[str, int] = {}
    for country, comps in LIGAS.items():
        for name, league_id in comps.items():
            result[f"{country} — {name}"] = league_id
    for name, league_id in COMPETICOES_INTERNACIONAIS.items():
        result[f"Internacional — {name}"] = league_id
    return result


def _default_labels(catalog: dict[str, int]) -> list[str]:
    wanted = {f"{country} — {name}" for country, name in DEFAULT_LEAGUES}
    return [label for label in catalog if label in wanted]


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _fmt_num(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _secret(name: str) -> str | None:
    try:
        return st.secrets.get(name)
    except Exception:
        return None


def _best_candidate(shadow):
    eligible = [x for x in shadow.assessments if x.decision.value == "BET_ELIGIBLE"]
    if eligible:
        return max(
            eligible,
            key=lambda x: (
                x.expected_value if x.expected_value is not None else -999,
                x.edge if x.edge is not None else -999,
            ),
        )
    watch = [x for x in shadow.assessments if x.decision.value == "WATCH"]
    if watch:
        return max(
            watch,
            key=lambda x: (
                x.expected_value if x.expected_value is not None else -999,
                x.edge if x.edge is not None else -999,
            ),
        )
    return None


def _candidate_label(item) -> str:
    if item is None:
        return "Sem candidato"
    item_line = getattr(item, "line", None)
    line = "" if item_line is None else f" {item_line}"
    return f"{item.market} • {item.selection}{line}"


def _scan_match(jogo: dict, odds_key: str | None) -> dict | None:
    context = build_match_context(jogo)
    if context is None:
        return None

    result = FootballIntelligenceEngine().analyze(context)
    quotes = []
    if odds_key:
        try:
            quotes = fetch_pregame_quotes(jogo, odds_key)
        except Exception:
            quotes = []
    shadow = run_shadow(context, quotes)
    candidate = _best_candidate(shadow)

    alternatives = estimate_corners_and_cards(jogo)
    recent_profile = recent_market_profile(jogo)
    best_corners = max((v for v in alternatives.values() if v.market == "TOTAL_CORNERS" and v.probability_over is not None), key=lambda x: x.probability_over, default=None)
    best_cards = max((v for v in alternatives.values() if v.market == "TOTAL_CARDS" and v.probability_over is not None), key=lambda x: x.probability_over, default=None)

    player_props = best_player_props(estimate_player_props(jogo))

    return {
        "fixture_id": jogo.get("id"),
        "game": jogo.get("nome"),
        "league": jogo.get("liga"),
        "kickoff": jogo.get("data"),
        "xg_home": result.expected_home_goals,
        "xg_away": result.expected_away_goals,
        "home_prob": result.probabilities["1x2_home"].probability,
        "draw_prob": result.probabilities["1x2_draw"].probability,
        "away_prob": result.probabilities["1x2_away"].probability,
        "over25_prob": result.probabilities["goals_over_2_5"].probability,
        "btts_prob": result.probabilities["btts_yes"].probability,
        "data_quality": result.data_quality,
        "model_quality": result.model_quality,
        "candidate": candidate,
        "status": candidate.decision.value if candidate is not None else "NO_MARKET",
        "alternatives": alternatives,
        "best_corners": best_corners,
        "best_cards": best_cards,
        "recent_profile": recent_profile,
        "player_props": player_props,
    }


def _render_match_card(row: dict) -> None:
    candidate = row.get("candidate")
    kickoff = row.get("kickoff") or ""
    try:
        kickoff_short = datetime.fromisoformat(str(kickoff).replace("Z", "+00:00")).strftime("%d/%m %H:%M")
    except Exception:
        kickoff_short = str(kickoff)[:16]

    st.markdown(f"### ⚽ {row['game']}")
    st.caption(f"{row['league']} • {kickoff_short}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("xG", f"{row['xg_home']:.2f} x {row['xg_away']:.2f}")
    c2.metric("Casa", _fmt_pct(row["home_prob"]))
    c3.metric("Over 2.5", _fmt_pct(row["over25_prob"]))
    c4.metric("BTTS", _fmt_pct(row["btts_prob"]))

    q1, q2, q3 = st.columns(3)
    q1.metric("Dados", _fmt_pct(row["data_quality"]))
    q2.metric("Modelo", _fmt_pct(row["model_quality"]))
    q3.metric("Status", row["status"])

    if candidate is not None:
        st.markdown(f"**Destaque atual:** {_candidate_label(candidate)}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("P modelo", _fmt_pct(candidate.probability))
        m2.metric("Odd justa", _fmt_num(getattr(candidate, "fair_odds", None)))
        m3.metric("Odd mercado", _fmt_num(getattr(candidate, "offered_odds", None)))
        m4.metric("EV", _fmt_pct(getattr(candidate, "expected_value", None)))

    with st.expander("Ver probabilidades do jogo"):
        st.dataframe(
            pd.DataFrame([
                {"Mercado": "Casa", "Probabilidade": _fmt_pct(row["home_prob"])},
                {"Mercado": "Empate", "Probabilidade": _fmt_pct(row["draw_prob"])},
                {"Mercado": "Fora", "Probabilidade": _fmt_pct(row["away_prob"])},
                {"Mercado": "Over 2.5", "Probabilidade": _fmt_pct(row["over25_prob"])},
                {"Mercado": "BTTS Sim", "Probabilidade": _fmt_pct(row["btts_prob"])},
            ]),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")


def tela_painel_do_dia() -> None:
    st.subheader("📊 Painel do Dia")
    st.caption(
        "Varredura em lote das principais ligas usando o Football Intelligence. "
        "Esta primeira versão prioriza resultado, gols e BTTS. "
        "Escanteios, cartões e props de jogadores entram em abas/modelos próprios."
    )

    catalog = _league_catalog()
    labels = list(catalog.keys())
    selected = st.multiselect(
        "Ligas para varrer",
        labels,
        default=_default_labels(catalog),
    )

    col1, col2 = st.columns([1, 2])
    with col1:
        run_scan = st.button("🔎 Varrer jogos", use_container_width=True)
    with col2:
        only_today = st.toggle("Somente jogos de hoje", value=True)

    if run_scan:
        odds_key = _secret("THE_ODDS_API_KEY")
        all_games: list[dict] = []
        seen: set[int] = set()

        progress = st.progress(0)
        status = st.empty()
        total = max(1, len(selected))

        for idx, label in enumerate(selected, start=1):
            status.caption(f"Buscando {label}...")
            league_id = catalog[label]
            for jogo in buscar_jogos_da_liga(league_id):
                if jogo.get("id") in seen:
                    continue
                if only_today and str(jogo.get("data", ""))[:10] != datetime.now().strftime("%Y-%m-%d"):
                    continue
                seen.add(jogo.get("id"))
                all_games.append(jogo)
            progress.progress(idx / total)

        rows = []
        total_games = max(1, len(all_games))
        for idx, jogo in enumerate(all_games, start=1):
            status.caption(f"Calculando {idx}/{len(all_games)} • {jogo.get('nome')}")
            try:
                row = _scan_match(jogo, odds_key)
                if row:
                    rows.append(row)
            except Exception:
                pass
            progress.progress(idx / total_games)

        status.empty()
        progress.empty()
        st.session_state["daily_scan_rows"] = rows

    rows = st.session_state.get("daily_scan_rows", [])
    if not rows:
        st.info("Escolha as ligas e toque em 'Varrer jogos'.")
        return

    st.success(f"{len(rows)} jogo(s) calculados.")

    f1, f2 = st.columns(2)
    with f1:
        statuses = sorted({r["status"] for r in rows})
        selected_status = st.multiselect("Filtrar status", statuses, default=statuses)
    with f2:
        sort_mode = st.selectbox(
            "Ordenar por",
            ["Qualidade dos dados", "Over 2.5", "Casa", "BTTS"],
        )

    filtered = [r for r in rows if r["status"] in selected_status]
    sort_key = {
        "Qualidade dos dados": lambda r: r["data_quality"],
        "Over 2.5": lambda r: r["over25_prob"],
        "Casa": lambda r: r["home_prob"],
        "BTTS": lambda r: r["btts_prob"],
    }[sort_mode]
    filtered.sort(key=sort_key, reverse=True)

    tab_res, tab_corners, tab_cards, tab_players = st.tabs(["⚽ Resultado & Gols", "🚩 Escanteios", "🟨 Cartões", "🎯 Jogadores"])

    with tab_res:
        for row in filtered:
            _render_match_card(row)

    with tab_corners:
        for row in filtered:
            item = row.get("best_corners")
            if item is None:
                continue
            st.markdown(f"### 🚩 {row['game']}")
            st.caption(f"{row['league']} • amostra recente: {item.sample_size} jogos por lado")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Projeção escanteios", _fmt_num(item.expected))
            c2.metric(f"Over {item.line}", _fmt_pct(item.probability_over))
            c3.metric("Qualidade", _fmt_pct(item.quality))
            c4.metric("Linha", str(item.line))
            profile = row.get("recent_profile", {}).get("corners", {})
            home_vals = profile.get("home", [])
            away_vals = profile.get("away", [])
            hr1, hr2, hr3, hr4 = st.columns(4)
            hr1.metric("Casa L5", _fmt_pct(hit_rate(home_vals[:5], item.line)))
            hr2.metric("Casa L10", _fmt_pct(hit_rate(home_vals[:10], item.line)))
            hr3.metric("Fora L5", _fmt_pct(hit_rate(away_vals[:5], item.line)))
            hr4.metric("Fora L10", _fmt_pct(hit_rate(away_vals[:10], item.line)))
            with st.expander("Ver linhas de escanteios"):
                rows_alt = []
                for alt in row.get("alternatives", {}).values():
                    if alt.market != "TOTAL_CORNERS":
                        continue
                    rows_alt.append({
                        "Mercado": f"Over {alt.line}",
                        "Projeção": _fmt_num(alt.expected),
                        "Probabilidade": _fmt_pct(alt.probability_over),
                        "Amostra": alt.sample_size,
                        "Qualidade": _fmt_pct(alt.quality),
                    })
                st.dataframe(rows_alt, use_container_width=True, hide_index=True)
            st.markdown("---")

    with tab_cards:
        for row in filtered:
            item = row.get("best_cards")
            if item is None:
                continue
            st.markdown(f"### 🟨 {row['game']}")
            st.caption(f"{row['league']} • amostra recente: {item.sample_size} jogos por lado")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Projeção cartões", _fmt_num(item.expected))
            c2.metric(f"Over {item.line}", _fmt_pct(item.probability_over))
            c3.metric("Qualidade", _fmt_pct(item.quality))
            c4.metric("Linha", str(item.line))
            profile = row.get("recent_profile", {}).get("cards", {})
            home_vals = profile.get("home", [])
            away_vals = profile.get("away", [])
            hr1, hr2, hr3, hr4 = st.columns(4)
            hr1.metric("Casa L5", _fmt_pct(hit_rate(home_vals[:5], item.line)))
            hr2.metric("Casa L10", _fmt_pct(hit_rate(home_vals[:10], item.line)))
            hr3.metric("Fora L5", _fmt_pct(hit_rate(away_vals[:5], item.line)))
            hr4.metric("Fora L10", _fmt_pct(hit_rate(away_vals[:10], item.line)))
            with st.expander("Ver linhas de cartões"):
                rows_alt = []
                for alt in row.get("alternatives", {}).values():
                    if alt.market != "TOTAL_CARDS":
                        continue
                    rows_alt.append({
                        "Mercado": f"Over {alt.line}",
                        "Projeção": _fmt_num(alt.expected),
                        "Probabilidade": _fmt_pct(alt.probability_over),
                        "Amostra": alt.sample_size,
                        "Qualidade": _fmt_pct(alt.quality),
                    })
                st.dataframe(rows_alt, use_container_width=True, hide_index=True)
            st.caption("Baseline estatístico inicial. Ainda não incorpora árbitro, suspensão ou jogador pendurado.")
            st.markdown("---")

    with tab_players:
        for row in filtered:
            props = row.get("player_props") or []
            if not props:
                continue
            st.markdown(f"### 🎯 {row['game']}")
            st.caption(f"{row['league']} • props calculadas a partir de jogos recentes e minutos efetivamente jogados")
            prop_rows = []
            for item in props:
                market_label = {
                    "PLAYER_SHOTS": "Chutes",
                    "PLAYER_SHOTS_ON_TARGET": "Chutes no gol",
                    "GOALKEEPER_SAVES": "Defesas",
                }.get(item.market, item.market)
                prop_rows.append({
                    "Jogador": item.player_name,
                    "Time": item.team_name,
                    "Mercado": market_label,
                    "Linha": f"Over {item.line}",
                    "Projeção": _fmt_num(item.expected),
                    "Probabilidade": _fmt_pct(item.probability_over),
                    "Amostra": item.sample_size,
                    "Qualidade": _fmt_pct(item.quality),
                })
            st.dataframe(prop_rows, use_container_width=True, hide_index=True)
            st.caption(
                "Baseline inicial: ainda não usa escalação confirmada, adversário por função, lesões, "
                "marcação individual, árbitro ou odds específicas de jogador."
            )
            st.markdown("---")

