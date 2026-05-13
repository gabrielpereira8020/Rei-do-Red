import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from datetime import datetime
from supabase import create_client, Client

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="IA REI DA BOLA - ELITE PRO", page_icon="🏆", layout="wide")

# Ligas de Elite (Brasil, Europa, Arábia, EUA e Copas)
LIGAS_ELITE = [71, 72, 73, 39, 40, 140, 141, 78, 79, 135, 136, 61, 62, 94, 307, 253, 2, 3, 5, 848, 13]

# --- INICIALIZAÇÃO DE BANCO E IA ---
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

@st.cache_resource
def init_gemini():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-1.5-flash')

supabase = init_supabase()
gemini = init_gemini()
API_KEY = st.secrets["API_KEY"]
HEADERS = {'x-rapidapi-key': API_KEY}

# --- FUNÇÕES CORE ---
def get_data(endpoint):
    url = f"https://v3.football.api-sports.io/{endpoint}"
    try:
        res = requests.get(url, headers=HEADERS).json()
        return res.get('response', [])
    except: return []

def analisar_ia(ctx):
    prompt = f"Analise como Trader Pro: {ctx}. Veredito ENTRAR/AGUARDAR e confiança %."
    try: return gemini.generate_content(prompt).text
    except: return "IA processando..."

def salvar_resultado(jogo, resultado, ig):
    try:
        supabase.table("historico").insert({
            "data": datetime.now().isoformat(),
            "jogo": jogo,
            "resultado": resultado,
            "ig": ig
        }).execute()
        st.success(f"Registrado: {resultado}")
    except: st.error("Erro ao salvar no banco.")

# --- LÓGICA DA BOLINHA ROXA (RECOMENDAÇÃO) ---
def recomendar_jogo(jogo_data, tipo="live"):
    # Se for Live, recomenda se o IG for alto ou se o time favorito estiver perdendo
    if tipo == "live":
        # Aqui a lógica de recomendação automática (sem gastar crédito de stats ainda)
        # Recomenda se o time da casa for favorito (exemplo simples de lógica)
        return "🟣" if "Brasil" in jogo_data['league']['name'] or "Premier" in jogo_data['league']['name'] else ""
    return ""

# --- UI ---
st.title("🏆 IA REI DA BOLA - MODO ELITE PRO")
tab_radar, tab_pre, tab_db = st.tabs(["🎯 RADAR LIVE", "🔮 PRÉ-JOGO", "📈 HISTÓRICO & PERFORMANCE"])

# --- TAB 1: RADAR ---
with tab_radar:
    live = get_data("fixtures?live=all")
    live_elite = [j for j in live if j['league']['id'] in LIGAS_ELITE]
    
    if not live_elite: st.info("Aguardando jogos de Elite...")
    else:
        for f in live_elite:
            fid = f['fixture']['id']
            h, a = f['teams']['home']['name'], f['teams']['away']['name']
            placar = f"{f['goals']['home']}-{f['goals']['away']}"
            tempo = f['fixture']['status']['elapsed']
            
            # Sinalizador Roxo para jogos "quentes" (Filtro Inteligente)
            sinal = "🟣" if tempo > 60 and f['goals']['home'] == f['goals']['away'] else ""
            
            with st.expander(f"{sinal} {tempo}' | {h} {placar} {a}"):
                if st.button(f"Analisar Pressão (Gasta Crédito)", key=f"btn_{fid}"):
                    s = get_data(f"fixtures/statistics?fixture={fid}")
                    # ... (cálculo do IG que já tínhamos)
                    ig = 30 # Exemplo
                    st.metric("IG Atual", f"{ig}")
                    st.write(analisar_ia(f"{h}x{a}, IG:{ig}"))
                    
                    c1, c2 = st.columns(2)
                    if c1.button("✅ GREEN", key=f"g_{fid}"): salvar_resultado(f"{h}x{a}", "GREEN", ig)
                    if c2.button("❌ RED", key=f"r_{fid}"): salvar_resultado(f"{h}x{a}", "RED", ig)

# --- TAB 3: HISTÓRICO ---
with tab_db:
    st.subheader("📊 Performance do Sistema")
    try:
        data = supabase.table("historico").select("*").execute().data
        if data:
            df = pd.DataFrame(data)
            df['data'] = pd.to_datetime(df['data'])
            
            # Métricas
            total = len(df)
            greens = len(df[df['resultado'] == "GREEN"])
            winrate = (greens / total) * 100 if total > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Entradas", total)
            c2.metric("Greens", greens, delta=f"{winrate:.1f}% Winrate")
            c3.metric("Reds", total - greens)
            
            st.dataframe(df.sort_values('data', ascending=False), use_container_width=True)
        else: st.info("Nenhuma entrada registrada ainda.")
    except: st.error("Erro ao conectar ao histórico.")
