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

# =============================================
# ARQUIVO DE DEBUG - cole na raiz do projeto
# rode com: streamlit run debug_ia.py
# =============================================

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.title("🔍 DEBUG - O que o Gemini retorna?")

if st.button("🚀 Gerar resposta de teste"):
    prompt = """
Você é uma IA especialista em apostas esportivas profissionais.

Analise a partida:
Flamengo x Vasco

Faça análise COMPLETA considerando:
- tendência de gols
- escanteios
- cartões
- intensidade
- faltas
- finalizações
- jogadores perigosos
- chances da partida

Depois gere:

🔥 APOSTA CRAVADA:
(aposta mais segura)

📊 CONFIANÇA:
(apenas número)

💎 OPORTUNIDADE DE OURO:
(aposta de valor)

⚽ GOLS:
(análise)

🚩 ESCANTEIOS:
(análise)

🟨 CARTÕES:
(análise)

🎯 JOGADORES:
- provável chute no gol
- provável sofrer faltas
- provável cartão

📈 SCORE GOLS:
(número)

📈 SCORE ESCANTEIOS:
(número)

📈 SCORE CARTÕES:
(número)

⚠️ RISCO:
(risco da partida)

FIM
"""

    with st.spinner("Chamando Gemini..."):
        try:
            response = client.models.generate_content(
                model="models/gemini-2.5-flash-lite",
                contents=prompt
            )
            texto = response.text
        except Exception as e:
            st.error(f"Erro na API: {e}")
            st.stop()

    # ---- MOSTRAR TEXTO BRUTO ----
    st.subheader("📄 TEXTO BRUTO DO GEMINI (exatamente o que veio)")
    st.code(texto, language=None)

    # ---- MOSTRAR REPR (caracteres invisíveis) ----
    st.subheader("🔬 REPR do texto (mostra caracteres especiais)")
    st.code(repr(texto[:500]))

    # ---- TESTAR CADA MARCADOR ----
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
            st.success(f"✅ '{inicio}' → ENCONTRADO: `{resultado.group(1).strip()[:80]}`")
        else:
            st.error(f"❌ '{inicio}' → NÃO ENCONTRADO")

            # Tenta encontrar o marcador sozinho no texto
            if inicio in texto:
                st.warning(f"   ⚠️ O marcador '{inicio}' EXISTE no texto, mas o regex falhou.")
                st.warning(f"   → Provavelmente o FIM '{fim}' não existe ou está diferente no texto.")
            else:
                st.error(f"   💀 O marcador '{inicio}' NÃO EXISTE no texto retornado!")
                # Mostra o que está próximo
                for linha in texto.split('\n'):
                    if any(c in linha for c in inicio if c.isalpha()):
                        st.info(f"   Linha próxima encontrada: `{linha}`")
                        break
