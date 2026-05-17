import streamlit as st
import re

def pegar(texto, inicio, fim):
    try:
        inicio_escaped = re.escape(inicio)
        fim_escaped = re.escape(fim)
        # Ignora asteriscos e espaços ao redor dos marcadores
        padrao = rf"\*{{0,2}}{inicio_escaped}\*{{0,2}}\s*(.*?)\s*\*{{0,2}}{fim_escaped}"
        resultado = re.search(padrao, texto, re.DOTALL)
        if resultado:
            return resultado.group(1).strip()
        return "Não encontrado"
    except:
        return "Erro"

def exibir_analise(texto):

    cravada = pegar(
        texto,
        "🔥 APOSTA CRAVADA:",
        "📊 CONFIANÇA:"
    )

    confianca = pegar(
        texto,
        "📊 CONFIANÇA:",
        "💎 OPORTUNIDADE DE OURO:"
    )

    oportunidade = pegar(
        texto,
        "💎 OPORTUNIDADE DE OURO:",
        "⚽ GOLS:"
    )

    gols = pegar(
        texto,
        "⚽ GOLS:",
        "🚩 ESCANTEIOS:"
    )

    escanteios = pegar(
        texto,
        "🚩 ESCANTEIOS:",
        "🟨 CARTÕES:"
    )

    cartoes = pegar(
        texto,
        "🟨 CARTÕES:",
        "🎯 JOGADORES:"
    )

    jogadores = pegar(
        texto,
        "🎯 JOGADORES:",
        "📈 SCORE GOLS:"
    )

    score_gols = pegar(
        texto,
        "📈 SCORE GOLS:",
        "📈 SCORE ESCANTEIOS:"
    )

    score_escanteios = pegar(
        texto,
        "📈 SCORE ESCANTEIOS:",
        "📈 SCORE CARTÕES:"
    )

    score_cartoes = pegar(
        texto,
        "📈 SCORE CARTÕES:",
        "⚠️ RISCO:"
    )

    risco = pegar(
        texto,
        "⚠️ RISCO:",
        "FIM"
    )

    st.markdown("---")

    st.markdown("## 🔥 APOSTA CRAVADA")
    st.success(cravada)

    st.markdown("## 📊 CONFIANÇA")
    st.metric(
        "Confiança IA",
        confianca
    )

    st.markdown("## 💎 OPORTUNIDADE DE OURO")
    st.warning(oportunidade)

    st.markdown("## ⚽ GOLS")
    st.info(gols)

    st.markdown("## 🚩 ESCANTEIOS")
    st.info(escanteios)

    st.markdown("## 🟨 CARTÕES")
    st.info(cartoes)

    st.markdown("## 🎯 JOGADORES")
    st.write(jogadores)

    st.markdown("## 📈 SCORE DOS MERCADOS")

    try:
        st.progress(int(score_gols)/100)
        st.write(f"Gols: {score_gols}%")
    except:
        pass

    try:
        st.progress(int(score_escanteios)/100)
        st.write(f"Escanteios: {score_escanteios}%")
    except:
        pass

    try:
        st.progress(int(score_cartoes)/100)
        st.write(f"Cartões: {score_cartoes}%")
    except:
        pass

    st.markdown("## ⚠️ RISCO")
    st.error(risco)
