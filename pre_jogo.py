import streamlit as st

from ligas import LIGAS

from api_football import buscar_jogos_da_liga

from ia_engine import gerar_analise_ia

from formatacao import exibir_analise


def tela_pre_jogo():

    st.header("⚽ MODO PRÉ JOGO")

    pais = st.selectbox(
        "🌍 Escolha o país",
        list(LIGAS.keys())
    )

    competicoes = LIGAS[pais]

    campeonato = st.selectbox(
        "🏆 Escolha a competição",
        list(competicoes.keys())
    )

    league_id = competicoes[campeonato]

    jogos = buscar_jogos_da_liga(league_id)

    if not jogos:
        st.error("Nenhum jogo encontrado.")
        return

    jogo_escolhido = st.selectbox(
        "⚽ Escolha o jogo",
        [j["nome"] for j in jogos]
    )

    jogo_info = next(
        j for j in jogos
        if j["nome"] == jogo_escolhido
    )

    if st.button("🔥 GERAR ANÁLISE"):

        with st.spinner("IA analisando partida..."):

            resposta = gerar_analise_ia(
                jogo_info
            )

        exibir_analise(resposta)
