import streamlit as st
from ligas import LIGAS
from api_football import buscar_jogos_da_liga
from ia_engine import gerar_analise_pre_jogo
from formatacao import exibir_analise


def tela_pre_jogo(enviar_telegram, salvar_resultado):
    st.subheader("⚽ Análise Pré-Jogo")

    pais = st.selectbox("🌍 Escolha o país", list(LIGAS.keys()))
    competicoes = LIGAS[pais]
    campeonato = st.selectbox("🏆 Escolha a competição", list(competicoes.keys()))
    league_id = competicoes[campeonato]

    jogos = buscar_jogos_da_liga(league_id)

    st.write(jogos)

    if not jogos:
        st.error("Nenhum jogo encontrado para essa competição.")
    return de

    jogo_escolhido = st.selectbox("⚽ Escolha o jogo", [j["nome"] for j in jogos])
    jogo_info = next(j for j in jogos if j["nome"] == jogo_escolhido)

    if st.button("🔥 GERAR ANÁLISE"):
        with st.spinner("O Rei da Bola está analisando a partida..."):
            resposta = gerar_analise_pre_jogo(jogo_info)
            exibir_analise(resposta)

            # Registrar resultado
            st.markdown("#### Registrar resultado:")
            c1, c2 = st.columns(2)
            if c1.button("✅ GREEN", key="green_pre_" + str(jogo_info["id"])):
                salvar_resultado(jogo_info["nome"], "GREEN", 0)
            if c2.button("❌ RED", key="red_pre_" + str(jogo_info["id"])):
                salvar_resultado(jogo_info["nome"], "RED", 0)

            # Telegram
            enviar_telegram(
                "<b>🔮 PRÉ-JOGO - REI DA BOLA</b>\n\n" +
                jogo_info["nome"] + "\n\n" +
                resposta[:1000]
            )
