import streamlit as st
from ia_engine import gerar_analise_ao_vivo
from formatacao import exibir_analise_ao_vivo

LIGAS_ELITE = [
    71, 72, 73,           # Brasil Série A, B, C
    39, 40,               # Premier League, Championship
    140, 141,             # LaLiga, LaLiga2
    78, 79,               # Bundesliga, 2.Bundesliga
    135, 136,             # Serie A, Serie B
    61, 62,               # Ligue 1, Ligue 2
    94,                   # Primeira Liga Portugal
    13,                   # Copa Libertadores
    11,                   # Copa Sudamericana
    2,                    # Champions League
    3,                    # Europa League
    848,                  # Conference League
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

    if st.button("🔄 Atualizar jogos"):
        st.cache_data.clear()

    with st.spinner("Buscando jogos ao vivo..."):
        jogos_live = fetch_api("fixtures?live=all")
        elite_live = [j for j in jogos_live if j["league"]["id"] in LIGAS_ELITE]

    if not elite_live:
        st.info("⚽ Nenhum jogo ao vivo nas ligas monitoradas.")
        return

    st.success("🟢 " + str(len(elite_live)) + " jogo(s) ao vivo")

    for jogo in elite_live:
        fixture_id = jogo["fixture"]["id"]
        home       = jogo["teams"]["home"]["name"]
        away       = jogo["teams"]["away"]["name"]
        home_id    = jogo["teams"]["home"]["id"]
        away_id    = jogo["teams"]["away"]["id"]
        gols_home  = jogo["goals"]["home"] or 0
        gols_away  = jogo["goals"]["away"] or 0
        tempo      = jogo["fixture"]["status"]["elapsed"] or "?"
        liga       = jogo["league"]["name"]

        with st.expander("⏱️ " + str(tempo) + "' | " + liga + " | " + home + " " + str(gols_home) + "x" + str(gols_away) + " " + away):
            col1, col2, col3 = st.columns(3)
            col1.metric("Mandante", home)
            col2.metric("Placar", str(gols_home) + " - " + str(gols_away))
            col3.metric("Visitante", away)

            if st.button("⚡ Consultar IA ao Vivo", key="live_" + str(fixture_id)):
                with st.spinner("Analisando jogadores e momento do jogo..."):
                    stats       = fetch_api("fixtures/statistics?fixture=" + str(fixture_id))
                    pressao     = calcular_pressao(stats)
                    stats_texto = descrever_stats(stats)

                    col_p1, col_p2 = st.columns([1, 3])
                    col_p1.metric("🔥 Pressão", pressao)

                    jogo_info = {
                        "id":      fixture_id,
                        "casa":    home,
                        "fora":    away,
                        "casa_id": home_id,
                        "fora_id": away_id,
                        "minuto":  str(tempo),
                        "placar":  home + " " + str(gols_home) + " x " + str(gols_away) + " " + away,
                        "stats":   stats_texto,
                        "pressao": pressao
                    }

                    resposta = gerar_analise_ao_vivo(jogo_info)
                    exibir_analise_ao_vivo(resposta)

                    st.markdown("#### Registrar resultado:")
                    c1, c2 = st.columns(2)
                    if c1.button("✅ GREEN", key="green_live_" + str(fixture_id)):
                        salvar_resultado(home + " x " + away, "GREEN", pressao)
                    if c2.button("❌ RED", key="red_live_" + str(fixture_id)):
                        salvar_resultado(home + " x " + away, "RED", pressao)

                    enviar_telegram(
                        "<b>⚡ AO VIVO - REI DA BOLA</b>\n\n" +
                        str(tempo) + "' | " + home + " " + str(gols_home) + "x" + str(gols_away) + " " + away + "\n" +
                        "Liga: " + liga + "\n" +
                        "Pressão: " + str(pressao) + "\n\n" +
                        resposta[:800]
                    )
