import streamlit as st

from api_football import (
    buscar_estatisticas_jogo
)

from ia_engine import (
    gerar_analise_ia
)

from formatacao import (
    exibir_analise
)

def tela_pre_jogo():

    st.header("⚽ MODO PRÉ JOGO")

    jogo = st.text_input(
        "Digite o jogo",
        placeholder="Ex: Real Madrid x Barcelona"
    )

    if st.button("🔥 GERAR ANÁLISE"):

        if jogo.strip() == "":
            st.warning("Digite um jogo.")
            return

        with st.spinner("Buscando dados da API Football..."):

            dados = buscar_estatisticas_jogo(jogo)

        with st.spinner("IA analisando partida..."):

            resposta = gerar_analise_ia(
                jogo,
                dados
            )

        exibir_analise(resposta)
