import streamlit as st

from ligas import LIGAS, COMPETICOES_INTERNACIONAIS
from api_football import buscar_jogos_da_liga
from ia_engine import gerar_analise_pre_jogo
from formatacao import exibir_analise
from pregame_intelligence_panel import render_pregame_intelligence


def tela_pre_jogo(enviar_telegram, salvar_resultado, supabase=None):

    st.subheader("⚽ Análise Pré-Jogo")

    LIGAS_COMPLETO = dict(LIGAS)
    LIGAS_COMPLETO["🌍 Internacional / Copas"] = COMPETICOES_INTERNACIONAIS

    pais = st.selectbox(
        "🌍 Escolha o país ou competição internacional",
        list(LIGAS_COMPLETO.keys())
    )

    competicoes = LIGAS_COMPLETO[pais]

    campeonato = st.selectbox(
        "🏆 Escolha a competição",
        list(competicoes.keys())
    )

    league_id = competicoes[campeonato]
    jogos = buscar_jogos_da_liga(league_id)

    if not jogos:
        st.error("Nenhum jogo encontrado para essa competição.")
        return

    nomes_jogos = [jogo["nome"] for jogo in jogos]

    jogo_escolhido = st.selectbox(
        "⚽ Escolha o jogo",
        nomes_jogos
    )

    jogo_info = next(
        (jogo for jogo in jogos if jogo["nome"] == jogo_escolhido),
        None
    )

    if not jogo_info:
        st.error("Erro ao carregar informações do jogo.")
        return

    st.markdown("### 🔬 Comparação: Legado × Football Intelligence")
    st.caption(
        "O sistema antigo continua intacto. O motor novo roda em paralelo para você comparar as duas leituras."
    )

    legacy_key = f"legacy_pre_{jogo_info.get('id', jogo_escolhido)}"

    col_legacy, col_shadow = st.columns(2)

    with col_legacy:
        st.markdown("#### 🧠 Legado (Gemini)")
        st.caption("Fluxo atual do Rei-do-Red.")

        if st.button("🔥 GERAR ANÁLISE LEGADA", key="gerar_pre_legado"):
            with st.spinner("O Rei-do-Red está analisando a partida pelo fluxo legado..."):
                try:
                    resposta = gerar_analise_pre_jogo(jogo_info)
                    st.session_state[legacy_key] = resposta

                    enviar_telegram(
                        "<b>🔮 PRÉ-JOGO - REI-DO-RED</b>\n\n"
                        + jogo_info["nome"]
                        + "\n\n"
                        + resposta[:1000]
                    )
                except Exception as erro:
                    st.error(f"Erro ao gerar análise legada: {erro}")

        resposta_legada = st.session_state.get(legacy_key)
        if resposta_legada:
            exibir_analise(resposta_legada)

            st.markdown("#### Registrar resultado:")
            c1, c2 = st.columns(2)
            jogo_id = str(jogo_info.get("id", jogo_escolhido))

            if c1.button("✅ GREEN", key=f"green_pre_{jogo_id}"):
                salvar_resultado(jogo_info["nome"], "GREEN", 0)

            if c2.button("❌ RED", key=f"red_pre_{jogo_id}"):
                salvar_resultado(jogo_info["nome"], "RED", 0)

    with col_shadow:
        st.markdown("#### 📐 Football Intelligence")
        st.caption("Baseline matemático independente do Gemini.")

        if st.button("🧪 GERAR ANÁLISE INTELLIGENCE", key="gerar_pre_shadow"):
            try:
                render_pregame_intelligence(
                    jogo_info,
                    supabase=supabase,
                    legacy_text=st.session_state.get(legacy_key),
                )
            except Exception as erro:
                st.error(f"Erro no Football Intelligence: {erro}")
