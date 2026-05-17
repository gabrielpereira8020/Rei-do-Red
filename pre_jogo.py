# =========================================
# ARQUIVO: pre_jogo.py
# =========================================

import streamlit as st
from analise_pre_jogo import analisar_pre_jogo

def tela_pre_jogo():

    st.header("⚽ Modo Pré Jogo")

    jogo = st.text_input(
        "Digite o jogo",
        placeholder="Ex: Real Madrid x Barcelona"
    )

    if st.button("🔥 GERAR ANÁLISE COMPLETA"):

        if jogo.strip() == "":
            st.warning("Digite um jogo.")
            return

        with st.spinner("Analisando partida..."):

            resposta = analisar_pre_jogo(jogo)

            st.markdown("---")

            st.markdown("## 🔥 APOSTA CRAVADA")
            st.success(resposta["cravada"])

            st.markdown("## 📊 CONFIANÇA DA IA")
            st.metric(
                "Confiança",
                f'{resposta["confianca"]}%'
            )

            st.markdown("## 💎 OPORTUNIDADE DE OURO")
            st.warning(resposta["oportunidade"])

            st.markdown("## ⚽ ANÁLISE DE GOLS")
            st.info(resposta["gols"])

            st.markdown("## 🚩 ANÁLISE DE ESCANTEIOS")
            st.info(resposta["escanteios"])

            st.markdown("## 🟨 ANÁLISE DE CARTÕES")
            st.info(resposta["cartoes"])

            st.markdown("## 🎯 JOGADORES EM DESTAQUE")

            for jogador in resposta["jogadores"]:
                st.markdown(f"""
                ### 👤 {jogador['nome']}
                - Mercado: {jogador['mercado']}
                - Chance: {jogador['chance']}%
                """)

            st.markdown("## 📈 SCORE DOS MERCADOS")

            st.progress(resposta["score_gols"] / 100)
            st.write(f'Over 1.5 Gols: {resposta["score_gols"]}%')

            st.progress(resposta["score_escanteios"] / 100)
            st.write(f'Escanteios: {resposta["score_escanteios"]}%')

            st.progress(resposta["score_cartoes"] / 100)
            st.write(f'Cartões: {resposta["score_cartoes"]}%')

            st.markdown("## ⚠️ RISCO DA PARTIDA")
            st.error(resposta["risco"])
