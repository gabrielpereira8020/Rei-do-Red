import streamlit as st

from ligas import LIGAS

from api_football import (
    buscar_jogos_da_liga
)

from ia_engine import gerar_analise_ia

from formatacao import exibir_analise

st.set_page_config(layout="wide")

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

    lista_jogos = [
        jogo["nome"] for jogo in jogos
    ]

    jogo_escolhido = st.selectbox(
        "⚽ Escolha o jogo",
        lista_jogos
    )

    if st.button("🔥 GERAR ANÁLISE"):

        with st.spinner("IA analisando partida..."):

        resposta = gerar_analise_ia(
    jogo_info
            )

        exibir_analise(resposta)
