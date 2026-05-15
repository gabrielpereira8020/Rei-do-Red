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
.main { background-color: #0b1020; }
.block-container { padding-top: 1rem; }
h1, h2, h3 { color: white; }
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
div[data-testid="stSidebar"] { background-color: #111827; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# LIGAS
# =====================================================
LIGAS_ELITE = [71,72,73,39,40,140,141,78,79,135,136,61,62,94]

# =====================================================
# TELEGRAM — DEVE SER DEFINIDO ANTES DE USAR
# =====================================================
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# =====================================================
# INIT SERVICES
# =====================================================
@st.cache_resource
def init_services():
    try:
        supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

        # Força o modelo com maior quota: gemini-1.5-flash = 1500 req/dia grátis
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        return supabase, model
    except Exception as e:
        return None, None

supabase, gemini = init_services()

if supabase is None or gemini is None:
    st.error("❌ Erro ao conectar serviços. Verifique as secrets no Streamlit Cloud.")
    st.stop()

API_KEY = st.secrets["API_KEY"]
HEADERS = {
    'x-rapidapi-key': API_KEY,
    'x-rapidapi-host': 'v3.football.api-sports.io'
}

# =====================================================
# API FOOTBALL
# =====================================================
@st.cache_data(ttl=60)
def fetch_api(endpoint):
    try:
        url = f"https://v3.football.api-sports.io/{endpoint}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return []
        return response.json().get("response", [])
    except:
        return []

# =====================================================
# TELEGRAM
# =====================================================
def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, json=payload, timeout=10)
    except:
        pass

# =====================================================
# IA — gemini-1.5-flash (1500 chamadas/dia grátis)
# =====================================================
def analisar_com_ia(contexto):
    try:
        prompt = f"""
Você é o REI DA BOLA.
Analise o jogo como trader esportivo profissional.

CONTEXTO:
{contexto}

FORMATO:
🎯 VEREDITO:
🔥 FEELING:
📈 CONFIANÇA:
💰 OPORTUNIDADE:
"""
        resposta = gemini.generate_content(prompt)
        if hasattr(resposta, "text"):
            return resposta.text
        return "IA sem resposta"
    except Exception as e:
        return f"ERRO REAL DA IA: {str(e)}"

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

# =====================================================
# HISTÓRICO (sidebar)
# =====================================================
greens = 0
reds = 0
winrate = 0

try:
    historico = supabase.table("historico").select("*").execute()
    if historico.data:
        df_hist = pd.DataFrame(historico.data)
        greens = len(df_hist[df_hist["resultado"] == "GREEN"])
        reds = len(df_hist[df_hist["resultado"] == "RED"])
        total = greens + reds
        if total > 0:
            winrate = round((greens / total) * 100, 1)
except:
    pass

st.sidebar.metric("✅ Greens", greens)
st.sidebar.metric("❌ Reds", reds)
st.sidebar.metric("📈 Winrate", f"{winrate}%")

# =====================================================
# HEADER
# =====================================================
st.title("🏆 IA REI DA BOLA PRO")
st.caption("Radar inteligente para traders esportivos")

# =====================================================
# TABS
# =====================================================
aba1, aba2, aba3 = st.tabs([
    "🎯 AO VIVO",
    "🔮 PRÉ-JOGO",
    "📊 HISTÓRICO"
])

# =====================================================
# AO VIVO
# =====================================================
with aba1:
    st.subheader("🎯 Radar ao Vivo")
    with st.spinner("Buscando jogos..."):
        jogos = fetch_api("fixtures?live=all")
        elite = [j for j in jogos if j["league"]["id"] in LIGAS_ELITE]

    if not elite:
        st.info("Nenhum jogo ao vivo")

    for jogo in elite:
        fixture_id = jogo["fixture"]["id"]
        home = jogo["teams"]["home"]["name"]
        away = jogo["teams"]["away"]["name"]
        gols_home = jogo["goals"]["home"]
        gols_away = jogo["goals"]["away"]
        tempo = jogo["fixture"]["status"]["elapsed"]

        with st.expander(f"⏱️ {tempo}' | {home} {gols_home}x{gols_away} {away}"):
            col1, col2, col3 = st.columns(3)
            col1.metric("Mandante", home)
            col2.metric("Placar", f"{gols_home}-{gols_away}")
            col3.metric("Visitante", away)

            if st.button("Consultar IA", key=f"live_{fixture_id}"):
                stats = fetch_api(f"fixtures/statistics?fixture={fixture_id}")
                pressao = calcular_pressao(stats)
                st.metric("🔥 Pressão", pressao)
                analise = analisar_com_ia(
                    f"Jogo ao vivo: {home} x {away}, minuto {tempo}, pressão {pressao}"
                )
                st.markdown(analise)

                c1, c2 = st.columns(2)
                if c1.button("✅ GREEN", key=f"green_{fixture_id}"):
                    salvar_resultado(f"{home} x {away}", "GREEN", pressao)
                if c2.button("❌ RED", key=f"red_{fixture_id}"):
                    salvar_resultado(f"{home} x {away}", "RED", pressao)

# =====================================================
# PRÉ JOGO
# =====================================================
with aba2:
    hoje = datetime.now().strftime("%Y-%m-%d")
    agenda = fetch_api(f"fixtures?date={hoje}")
    jogos_hoje = [j for j in agenda if j["league"]["id"] in LIGAS_ELITE]

    for jogo in jogos_hoje:
        home = jogo["teams"]["home"]["name"]
        away = jogo["teams"]["away"]["name"]
        fixture_id = jogo["fixture"]["id"]

        with st.expander(f"⚽ {home} x {away}"):
            if st.button("Gerar análise", key=f"pre_{fixture_id}"):
                with st.spinner("Analisando partida..."):
                    time.sleep(1)
                    analise = analisar_com_ia(f"Pré jogo: {home} x {away}")
                    st.markdown(analise)

# =====================================================
# HISTÓRICO
# =====================================================
with aba3:
    st.subheader("📊 Histórico")
    try:
        historico = supabase.table("historico").select("*").execute()
        if historico.data:
            df = pd.DataFrame(historico.data)
            st.dataframe(df.sort_values("data", ascending=False), use_container_width=True)
        else:
            st.info("Sem histórico")
    except Exception as e:
        st.error(f"Erro: {e}")
