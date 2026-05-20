import streamlit as st
import re


def pegar(texto, inicio, fim):
    try:
        padrao = f"{re.escape(inicio)}(.*?){re.escape(fim)}"
        resultado = re.search(padrao, texto, re.DOTALL)
        if resultado:
            return resultado.group(1).strip()
        return "Não encontrado"
    except:
        return "Erro"


def limpar(texto):
    """Remove asteriscos, ### e --- do markdown do Gemini."""
    texto = re.sub(r'\*+', '', texto)
    texto = re.sub(r'^#+\s*', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'^-{3,}', '', texto, flags=re.MULTILINE)
    return texto.strip()


def pegar_numero(texto):
    """Extrai o primeiro número inteiro encontrado no texto."""
    numeros = re.findall(r'\d+', texto)
    return numeros[0] if numeros else "0"


def exibir_analise(texto):

    cravada = limpar(pegar(texto, "🔥 APOSTA CRAVADA:", "📊 CONFIANÇA:"))
    confianca = limpar(pegar(texto, "📊 CONFIANÇA:", "💎 OPORTUNIDADE DE OURO:"))
    oportunidade = limpar(pegar(texto, "💎 OPORTUNIDADE DE OURO:", "⚽ GOLS:"))
    gols = limpar(pegar(texto, "⚽ GOLS:", "🚩 ESCANTEIOS:"))
    escanteios = limpar(pegar(texto, "🚩 ESCANTEIOS:", "🟨 CARTÕES:"))
    cartoes = limpar(pegar(texto, "🟨 CARTÕES:", "🎯 JOGADORES:"))
    jogadores = limpar(pegar(texto, "🎯 JOGADORES:", "📈 SCORE GOLS:"))
    score_gols = pegar(texto, "📈 SCORE GOLS:", "📈 SCORE ESCANTEIOS:")
    score_escanteios = pegar(texto, "📈 SCORE ESCANTEIOS:", "📈 SCORE CARTÕES:")
    score_cartoes = pegar(texto, "📈 SCORE CARTÕES:", "⚠️ RISCO:")
    risco = limpar(pegar(texto, "⚠️ RISCO:", "FIM"))

    # Extrai só o número dos scores
    score_gols_num = pegar_numero(score_gols)
    score_escanteios_num = pegar_numero(score_escanteios)
    score_cartoes_num = pegar_numero(score_cartoes)

    # Extrai só o número da confiança (ex: "8/10" → "8")
    confianca_num = pegar_numero(confianca)

    st.markdown("---")

    st.markdown("## 🔥 APOSTA CRAVADA")
    st.success(cravada)

    st.markdown("## 📊 CONFIANÇA")
    st.metric("Confiança IA", f"{confianca_num}/10")

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
        val = min(int(score_gols_num), 100)
        st.progress(val / 100)
        st.write(f"Gols: {score_gols_num}")
    except:
        st.write(f"Gols: {score_gols}")

    try:
        val = min(int(score_escanteios_num), 100)
        st.progress(val / 100)
        st.write(f"Escanteios: {score_escanteios_num}")
    except:
        st.write(f"Escanteios: {score_escanteios}")

    try:
        val = min(int(score_cartoes_num), 100)
        st.progress(val / 100)
        st.write(f"Cartões: {score_cartoes_num}")
    except:
        st.write(f"Cartões: {score_cartoes}")

    st.markdown("## ⚠️ RISCO")
    st.error(risco)
