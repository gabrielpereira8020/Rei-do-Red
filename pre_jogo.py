import streamlit as st

from ligas import LIGAS
from api_football import buscar_jogos_da_liga
from ia_engine import gerar_analise_pre_jogo
from formatacao import exibir_analise


def tela_pre_jogo(enviar_telegram, salvar_resultado):

    st.subheader("⚽ Análise Pré-Jogo")

    # País
    pais = st.selectbox(
        "🌍 Escolha o país",
        list(LIGAS.keys())
    )

    # Competições
    competicoes = LIGAS[pais]

    campeonato = st.selectbox(
        "🏆 Escolha a competição",
        list(competicoes.keys())
    )

    # ID da liga
    league_id = competicoes[campeonato]

    # Buscar jogos
    jogos = buscar_jogos_da_liga(league_id)

    # Sem jogos
    if not jogos:
        st.error("Nenhum jogo encontrado para essa competição.")
        return

    # Lista dos nomes dos jogos
    nomes_jogos = [
        jogo["nome"]
        for jogo in jogos
    ]

    # Escolher jogo
    jogo_escolhido = st.selectbox(
        "⚽ Escolha o jogo",
        nomes_jogos
    )

    # Encontrar informações do jogo
    jogo_info = next(
        (
            jogo
            for jogo in jogos
            if jogo["nome"] == jogo_escolhido
        ),
        None
    )

    # Segurança extra
    if not jogo_info:
        st.error("Erro ao carregar informações do jogo.")
        return

    # Botão IA
    if st.button("🔥 GERAR ANÁLISE"):

        with st.spinner(
            "O Rei da Bola está analisando a partida..."
        ):

            try:

                # IA
                resposta = gerar_analise_pre_jogo(
                    jogo_info
                )

                # Mostrar análise
                exibir_analise(resposta)

                st.markdown("#### Registrar resultado:")

                c1, c2 = st.columns(2)

                jogo_id = str(
                    jogo_info.get("id", jogo_escolhido)
                )

                # GREEN
                if c1.button(
                    "✅ GREEN",
                    key=f"green_pre_{jogo_id}"
                ):

                    salvar_resultado(
                        jogo_info["nome"],
                        "GREEN",
                        0
                    )

                # RED
                if c2.button(
                    "❌ RED",
                    key=f"red_pre_{jogo_id}"
                ):

                    salvar_resultado(
                        jogo_info["nome"],
                        "RED",
                        0
                    )

                # Telegram
                enviar_telegram(
                    "<b>🔮 PRÉ-JOGO - REI DA BOLA</b>\n\n"
                    + jogo_info["nome"]
                    + "\n\n"
                    + resposta[:1000]
                )

            except Exception as erro:

                st.error(
                    f"Erro ao gerar análise: {erro}"
                )
