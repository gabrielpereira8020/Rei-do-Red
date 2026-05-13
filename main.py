import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from datetime import datetime
from supabase import create_client
import time

# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="IA REI DA BOLA PRO",
    page_icon="🏆",
    layout="wide"
)

# =====================================================
# CSS PREMIUM
# =====================================================

st.markdown("""
<style>

.main {
    background-color: #0b1020;
}

.block-container {
    padding-top: 1rem;
}

h1, h2, h3 {
    color: white;
}

.stMetric {
    background: linear-gradient(145deg,#141b2d,#1d2840);
    border-radius: 15px;
    padding: 15px;
    border: 1px solid #7a3cff;
}

.stButton>button {
    width: 100%;
    border-radius: 10px;
    background: linear-gradient(90deg,#7a3cff,#4f46e5);
    color: white;
    font-weight: bold;
    border: none;
    padding: 12px;
}

.stExpander {
    border: 1px solid #252f48;
    border-radius: 15px;
    background: #121a2b;
}

div[data-testid="stSidebar"] {
    background-color: #111827;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# LIGAS
# =====================================================

LIGAS_ELITE = [71,72,73,39,40,140,141,78,79,135,136,61,62,94]

# =====================================================
# INIT
# =====================================================

@st.cache_resource
def init_services():

    try:

        supabase = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"]
        )

        genai.configure(
            api_key=st.secrets["GEMINI_API_KEY"]
        )

        model = genai.GenerativeModel(
            "gemini-1.5-flash"
        )

        return supabase, model

    except Exception as e:

        st.error(f"Erro ao iniciar serviços: {e}")

        return None, None

supabase, gemini = init_services()

API_KEY = st.secrets["API_KEY"]

HEADERS = {
    'x-rapidapi-key': API_KEY,
    'x-rapidapi-host': 'v3.football.api-sports.io'
}

# =====================================================
# API
# =====================================================

@st.cache_data(ttl=60)
def fetch_api(endpoint):

    try:

        url = f"https://v3.football.api-sports.io/{endpoint}"

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        if response.status_code != 200:
            return []

        return response.json().get("response", [])

    except:
        return []

# =====================================================
# IA
# =====================================================

def analisar_com_ia(contexto):

    if not gemini:
        return "IA offline"

    prompt = f"""
Você é o REI DA BOLA.

Faça uma análise profissional de trader esportivo.

Analise:
- pressão
- momento
- gols
- intensidade
- possíveis zebras
- oportunidade de over
- oportunidade de gol tardio

CONTEXTO:
{contexto}

FORMATO:

🎯 VEREDITO:
🔥 FEELING:
📈 CONFIANÇA:
💰 OPORTUNIDADE:
"""

    try:

        resposta = gemini.generate_content(prompt)

        if resposta.text:
            return resposta.text

        return "Sem resposta da IA"

    except:
        return "Erro temporário da IA"

# =====================================================
# PRESSÃO
# =====================================================

def calcular_pressao(stats):

    if not stats or len(stats) < 2:
        return 0

    def pegar(stats_list, nome):

        for item in stats_list:

            if item["type"] == nome:

                valor = item["value"]

                if valor is None:
                    return 0

                try:
                    return int(str(valor).replace("%", ""))
                except:
                    return 0

        return 0

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]

    pontos_home = (
        pegar(home, "Shots on Goal") * 6 +
        pegar(home, "Corner Kicks") * 3 +
        pegar(home, "Total Shots") * 2
    )

    pontos_away = (
        pegar(away, "Shots on Goal") * 6 +
        pegar(away, "Corner Kicks") * 3 +
        pegar(away, "Total Shots") * 2
    )

    return max(pontos_home, pontos_away)

# =====================================================
# BANCO
# =====================================================

def salvar_resultado(jogo, resultado, confianca):

    try:

        supabase.table("historico").insert({
            "data": datetime.now().isoformat(),
            "jogo": jogo,
            "resultado": resultado,
            "confianca": confianca
        }).execute()

        st.success(f"{resultado} registrado")

    except Exception as e:

        st.error(f"Erro ao salvar: {e}")

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.title("🏆 REI DA BOLA")
st.sidebar.markdown("Painel Premium")
