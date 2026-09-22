import streamlit as st
from ia_engine import gerar_analise_ao_vivo
from formatacao import exibir_analise_ao_vivo
from football_intelligence.live_adapter import build_live_context
from football_intelligence.live_engine import analyze_live
from football_intelligence.live_value import evaluate_all_live_value

LIGAS_ELITE = [
    71, 72, 73,
    39, 40,
    140, 141,
    78, 79,
    135, 136,
    61, 62,
    94,
    13, 11,
    2, 3, 848,
]


def calcular_pressao(stats):
    if not stats or len(stats) < 2:
        return 0

    def pegar(s, nome):
        for item in s:
            if item["type"] == nome:
                v = item["value"]
                if v is None: return 0
                try: return int(str(v).replace("%", ""))
                except: return 0
        return 0

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]
    ph = pegar(home,"Shots on Goal")*6 + pegar(home,"Corner Kicks")*3 + pegar(home,"Total Shots")*2
    pa = pegar(away,"Shots on Goal")*6 + pegar(away,"Corner Kicks")*3 + pegar(away,"Total Shots")*2
    return max(ph, pa)


def descrever_stats(stats):
    if not stats or len(stats) < 2:
        return "Estatísticas indisponíveis."

    def pegar(s, nome):
        for item in s:
            if item["type"] == nome:
                v = item["value"]
                return v if v is not None else 0
        return 0

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]
    th = stats[0].get("team", {}).get("name", "Casa")
    ta = stats[1].get("team", {}).get("name", "Fora")

    return (
        th + ": Chutes " + str(pegar(home,"Total Shots")) +
        ", No gol " + str(pegar(home,"Shots on Goal")) +
        ", Escanteios " + str(pegar(home,"Corner Kicks")) +
        ", Posse " + str(pegar(home,"Ball Possession")) + "%" +
        ", Faltas " + str(pegar(home,"Fouls")) +
        ", Cartões A" + str(pegar(home,"Yellow Cards")) +
        "/V" + str(pegar(home,"Red Cards")) +
        " | " +
        ta + ": Chutes " + str(pegar(away,"Total Shots")) +
        ", No gol " + str(pegar(away,"Shots on Goal")) +
        ", Escanteios " + str(pegar(away,"Corner Kicks")) +
        ", Posse " + str(pegar(away,"Ball Possession")) + "%" +
        ", Faltas " + str(pegar(away,"Fouls")) +
        ", Cartões A" + str(pegar(away,"Yellow Cards")) +
        "/V" + str(pegar(away,"Red Cards"))
    )


def tela_ao_vivo(fetch_api, enviar_telegram, salvar_resultado):
    st.subheader("🔴 Radar ao Vivo")

    col_btn, col_toggle = st.columns([1, 2])
    with col_btn:
        if st.button("🔄 Atualizar jogos"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Buscando jogos ao vivo..."):
        todos_live = fetch_api("fixtures?live=all")

    if not todos_live:
        st.warning("⚠️ Nenhum jogo ao vivo no momento.")
        return

    elite_live  = [j for j in todos_live if j["league"]["id"] in LIGAS_ELITE]
    outros_live = [j for j in todos_live if j["league"]["id"] not in LIGAS_ELITE]

    with col_toggle:
        mostrar_todos = st.toggle("Mostrar todas as ligas", value=False)

    jogos_exibir = todos_live if mostrar_todos else (elite_live if elite_live else todos_live)

    if not jogos_exibir:
        st.info("⚽ Nenhum jogo ao vivo nas ligas monitoradas. Ative 'Mostrar todas as ligas'.")
        return

    st.success(
        "🟢 " + str(len(elite_live)) + " jogo(s) nas ligas principais | " +
        str(len(outros_live)) + " em outras ligas"
    )

    for jogo in jogos_exibir:
        fixture_id = jogo["fixture"]["id"]
        home       = jogo["teams"]["home"]["name"]
        away       = jogo["teams"]["away"]["name"]
        home_id    = jogo["teams"]["home"]["id"]
        away_id    = jogo["teams"]["away"]["id"]
        gols_home  = jogo["goals"]["home"] or 0
        gols_away  = jogo["goals"]["away"] or 0
        tempo      = jogo["fixture"]["status"]["elapsed"] or "?"
        liga       = jogo["league"]["name"]
        pais       = jogo["league"]["country"]

        label = "⏱️ " + str(tempo) + "' | " + pais + " - " + liga + " | " + home + " " + str(gols_home) + "x" + str(gols_away) + " " + away

        with st.expander(label):
            col1, col2, col3 = st.columns(3)
            col1.metric("Mandante", home)
            col2.metric("Placar", str(gols_home) + " - " + str(gols_away))
            col3.metric("Visitante", away)

            if st.button("⚡ Consultar IA ao Vivo", key="live_" + str(fixture_id)):
                with st.spinner("Analisando jogadores e momento do jogo..."):
                    stats       = fetch_api("fixtures/statistics?fixture=" + str(fixture_id))
                    pressao     = calcular_pressao(stats)
                    stats_texto = descrever_stats(stats)

                    st.metric("🔥 Índice de Pressão", pressao)

                    jogo_info = {
                        "id":        fixture_id,
                        "casa":      home,
                        "fora":      away,
                        "casa_id":   home_id,
                        "fora_id":   away_id,
                        "minuto":    str(tempo),
                        "placar":    home + " " + str(gols_home) + " x " + str(gols_away) + " " + away,
                        "stats":     stats_texto,
                        "stats_raw": stats,       # stats brutas para contexto completo
                        "pressao":   pressao
                    }

                    jogo_info["liga_id"] = jogo["league"]["id"]
                    jogo_info["season"] = jogo["league"].get("season") or 2026
                    jogo_info["data"] = jogo["fixture"].get("date")
                    jogo_info["gols_home"] = gols_home
                    jogo_info["gols_away"] = gols_away

                    live_context = build_live_context(jogo_info, stats)
                    live_result = analyze_live(
                        live_context,
                        pregame_home_xg=live_context.league.home_goals_avg,
                        pregame_away_xg=live_context.league.away_goals_avg,
                    )

                    st.markdown("#### 📡 Football Intelligence Ao Vivo")
                    cfi1, cfi2, cfi3 = st.columns(3)
                    cfi1.metric("Dados", f"{live_result.data_quality*100:.0f}%")
                    cfi2.metric("Modelo", f"{live_result.model_quality*100:.0f}%")
                    cfi3.metric("Pressão", f"{live_result.pressure_home:.0f} x {live_result.pressure_away:.0f}")

                    st.caption(f"Restante projetado: {live_result.expected_remaining_corners:.2f} escanteios • {live_result.expected_remaining_cards:.2f} cartões")

                    st.markdown("##### ⚡ Sinais do motor")
                    for signal in live_result.signals:
                        fair_text = f"{signal.fair_odds:.2f}" if signal.fair_odds is not None else "—"
                        badge_class = {
                            "SIGNAL": "badge-signal",
                            "WATCH": "badge-watch",
                            "NO_BET": "badge-no",
                            "INSUFFICIENT_DATA": "badge-data",
                        }.get(signal.status, "badge-data")
                        st.markdown(
                            "<div class='signal-card'>"
                            f"<div class='signal-title'>{signal.label}"
                            f"<span class='badge {badge_class}'>{signal.status}</span></div>"
                            f"<div class='signal-meta'>Probabilidade {signal.probability*100:.1f}% · Odd justa {fair_text}</div>"
                            f"<div class='signal-meta'>{signal.reason}</div>"
                            "</div>",
                            unsafe_allow_html=True,
                        )

                    st.markdown("##### ⏱️ Janelas rápidas")
                    window_signals = [
                        s for s in live_result.signals
                        if s.key in {"corner_next_10m", "card_next_10m", "goal_next_10m"}
                    ]
                    if window_signals:
                        cols = st.columns(len(window_signals))
                        for col, signal in zip(cols, window_signals):
                            with col:
                                fair_text = f"{signal.fair_odds:.2f}" if signal.fair_odds is not None else "—"
                                st.metric(signal.label, f"{signal.probability*100:.1f}%")
                                st.caption(f"Odd justa {fair_text} · {signal.status}")

                    odds_payload = fetch_api("odds/live?fixture=" + str(fixture_id))
                    value_candidates = evaluate_all_live_value(
                        live_result,
                        current_goals=int(gols_home + gols_away),
                        current_corners=int((live_context.live.home_corners or 0) + (live_context.live.away_corners or 0)),
                        current_cards=int((live_context.live.home_cards or 0) + (live_context.live.away_cards or 0)),
                        odds_payload=odds_payload,
                    )
                    if value_candidates:
                        st.markdown("##### 💎 Valor de mercado")
                        for candidate in value_candidates:
                            market_p = candidate.market_probability_devig if candidate.market_probability_devig is not None else candidate.market_probability_raw
                            st.write(
                                f"**{candidate.label} @ {candidate.odds:.2f}** — "
                                f"Modelo {candidate.model_probability*100:.1f}% | "
                                f"Mercado {market_p*100:.1f}% | "
                                f"Edge {candidate.edge*100:.1f}% | "
                                f"EV {candidate.expected_value*100:.1f}% | "
                                f"{candidate.status}"
                            )

                    resposta = gerar_analise_ao_vivo(jogo_info, fi_signals=live_result.signals)
                    exibir_analise_ao_vivo(
                        resposta,
                        nome_casa=home,
                        nome_fora=away
                    )

                    st.markdown("#### Registrar resultado:")
                    c1, c2 = st.columns(2)
                    if c1.button("✅ GREEN", key="green_live_" + str(fixture_id)):
                        salvar_resultado(home + " x " + away, "GREEN", pressao)
                    if c2.button("❌ RED", key="red_live_" + str(fixture_id)):
                        salvar_resultado(home + " x " + away, "RED", pressao)

                    melhores = sorted(
                        live_result.signals,
                        key=lambda s: s.probability,
                        reverse=True,
                    )[:3]
                    linhas_fi = "\n".join(
                        f"• {s.label}: {s.probability*100:.1f}% | {s.status}"
                        for s in melhores
                    )

                    enviar_telegram(
                        "<b>⚡ AO VIVO - REI-DO-RED</b>\n\n"
                        + str(tempo) + "' | " + home + " " + str(gols_home) + "x" + str(gols_away) + " " + away + "\n"
                        + "Liga: " + liga + "\n"
                        + "Pressão: " + str(pressao) + "\n\n"
                        + "<b>📡 Football Intelligence</b>\n"
                        + linhas_fi + "\n\n"
                        + "<b>🧠 Gemini</b>\n"
                        + resposta[:700]
                    )

                    
