import streamlit as st
from ligas import LIGAS
from api_football import buscar_jogos_da_liga
from ia_engine import gerar_analise_pre_jogo
from formatacao import exibir_analise


def tela_pre_jogo(enviar_telegram, salvar_resultado):
    st.subheader("⚽ Análise Pré-Jogo")

    # Escolha país
    pais = st.selectbox(
        "🌍 Escolha o país",
        list(LIGAS.keys())
    )

    # Escolha competição
    competicoes = LIGAS[pais]

    campeonato = st.selectbox(
        "🏆 Escolha a competição",
        list(competicoes.keys())
    )

    league_id = competicoes[campeonato]

    # Buscar jogos
    jogos = buscar_jogos_da_liga(league_id)


    # Sem jogos
    if not jogos:
        st.error("Nenhum jogo encontrado para essa competição.")
        return

    # Validar formato dos jogos
    jogos_validos = []

    for jogo in jogos:
        if isinstance(jogo, dict):

            nome = jogo.get("nome")

            if not nome:
                # tenta montar automaticamente
                casa = jogo.get("time_casa", "Casa")
                fora = jogo.get("time_fora", "Fora")
                nome = f"{casa} x {fora}"

                jogo["nome"] = nome

            jogos_validos.append(jogo)

    # Ainda sem jogos válidos
    if not jogos_validos:
        st.error("A API retornou jogos em formato inválido.")
        st.write(jogos)
        return

    # Selectbox dos jogos
    nomes_jogos = [j["nome"] for j in jogos_validos]

    jogo_escolhido = st.selectbox(
        "⚽ Escolha o jogo",
        nomes_jogos
    )

    # Encontrar jogo selecionado
    jogo_info = next(
        (j for j in jogos_validos if j["nome"] == jogo_escolhido),
        None
    )

    if not jogo_info:
        st.error("Erro ao localizar informações do jogo.")
        st.write(jogos_validos)
        return

    # Botão gerar análise
    if st.button("🔥 GERAR ANÁLISE"):

        with st.spinner("O Rei da Bola está analisando a partida..."):

            try:
                resposta = gerar_analise_pre_jogo(jogo_info)

                exibir_analise(resposta)

                # Registrar resultado
                st.markdown("#### Registrar resultado:")

                c1, c2 = st.columns(2)

                jogo_id = str(jogo_info.get("id", jogo_escolhido))

                if c1.button("✅ GREEN", key="green_pre_" + jogo_id):
                    salvar_resultado(
                        jogo_info["nome"],
                        "GREEN",
                        0
                    )

                if c2.button("❌ RED", key="red_pre_" + jogo_id):
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
                st.error(f"Erro ao gerar análise: {erro}")
                st.write(jogo_info)
