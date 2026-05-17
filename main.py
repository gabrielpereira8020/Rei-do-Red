import streamlit as st
from pre_jogo import tela_pre_jogo
from ao_vivo import tela_ao_vivo

st.set_page_config(
    page_title="Rei do Red",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 REI DO RED")

modo = st.sidebar.selectbox(
    "Escolha o modo",
    ["Pré Jogo", "Ao Vivo"]
)

if modo == "Pré Jogo":
    tela_pre_jogo()

elif modo == "Ao Vivo":
    tela_ao_vivo()

import streamlit as st
import re
from google import genai

import streamlit as st
import re
from google import genai
from ligas import LIGAS
from api_football import buscar_jogos_da_liga
from ia_engine import gerar_analise_ia

# =============================================
# ARQUIVO DE DEBUG v2 - testa com jogo real
# rode com: streamlit run debug_ia.py
# =============================================

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.title("🔍 DEBUG v2 - Jogo Real")

pais = st.selectbox("🌍 País", list(LIGAS.keys()))
competicoes = LIGAS[pais]
campeonato = st.selectbox("🏆 Competição", list(competicoes.keys()))
league_id = competicoes[campeonato]
jogos = buscar_jogos_da_liga(league_id)

if not jogos:
    st.error("Nenhum jogo encontrado.")
    st.stop()

jogo_escolhido = st.selectbox("⚽ Jogo", [j["nome"] for j in jogos])
jogo_info = next(j for j in jogos if j["nome"] == jogo_escolhido)

st.markdown("### 📦 Dados do jogo que vão para a IA:")
st.json(jogo_info)

if st.button("🚀 Gerar e Debugar"):
    with st.spinner("Chamando Gemini..."):
        texto = gerar_analise_ia(jogo_info)

    st.markdown("---")
    st.subheader("📄 TEXTO BRUTO (exatamente o que o Gemini retornou)")
    st.code(texto, language=None)

    st.subheader("🔬 REPR dos primeiros 800 caracteres")
    st.code(repr(texto[:800]))

    st.subheader("🧪 Teste de cada marcador")

    marcadores = [
        ("🔥 APOSTA CRAVADA:", "📊 CONFIANÇA:"),
        ("📊 CONFIANÇA:", "💎 OPORTUNIDADE DE OURO:"),
        ("💎 OPORTUNIDADE DE OURO:", "⚽ GOLS:"),
        ("⚽ GOLS:", "🚩 ESCANTEIOS:"),
        ("🚩 ESCANTEIOS:", "🟨 CARTÕES:"),
        ("🟨 CARTÕES:", "🎯 JOGADORES:"),
        ("🎯 JOGADORES:", "📈 SCORE GOLS:"),
        ("📈 SCORE GOLS:", "📈 SCORE ESCANTEIOS:"),
        ("📈 SCORE ESCANTEIOS:", "📈 SCORE CARTÕES:"),
        ("📈 SCORE CARTÕES:", "⚠️ RISCO:"),
        ("⚠️ RISCO:", "FIM"),
    ]

    for inicio, fim in marcadores:
        padrao = f"{re.escape(inicio)}(.*?){re.escape(fim)}"
        resultado = re.search(padrao, texto, re.DOTALL)

        if resultado:
            st.success(f"✅ `{inicio}` → `{resultado.group(1).strip()[:80]}`")
        else:
            st.error(f"❌ `{inicio}` → NÃO ENCONTRADO")
            if inicio in texto:
                st.warning(f"   ⚠️ Marcador início existe, mas FIM `{fim}` não foi achado.")
            else:
                st.error(f"   💀 O marcador `{inicio}` não existe no texto!")

            # Mostra linhas próximas com emojis parecidos
            st.info("Linhas do texto que podem ser o marcador:")
            for linha in texto.split('\n'):
                linha = linha.strip()
                if linha and any(c in linha for c in ['🔥','📊','💎','⚽','🚩','🟨','🎯','📈','⚠️','FIM']):
                    st.code(repr(linha))
