import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="IA REI DA BOLA - ELITE PRO", page_icon="🏆", layout="wide")

# Lista de IDs das principais ligas (Atualizada com Arábia e EUA)
LIGAS_ELITE = [
    71, 72, 73, # Brasil A, B, C
    39, 40,    # Inglaterra 1 e 2
    140, 141,  # Espanha 1 e 2
    78, 79,    # Alemanha 1 e 2
    135, 136,  # Itália 1 e 2
    61, 62,    # França 1 e 2
    94,        # Portugal
    307,       # Arábia Saudita (Saudi Pro League)
    253,       # Estados Unidos (MLS)
    2, 3, 5, 848, # Champions, Europa League, Libertadores, Sul-Americana
    13,        # Copa do Brasil
]

# --- INICIALIZAÇÃO ---
@st.cache_resource
def init_gemini():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-1.5-flash')

gemini = init_gemini()
API_KEY = st.secrets["API_KEY"]
HEADERS = {'x-rapidapi-key': API_KEY}

def get_data(endpoint):
    url = f"https://v3.football.api-sports.io/{endpoint}"
    try:
        res = requests.get(url, headers=HEADERS).json()
        return res.get('response', [])
    except:
        return []

def analisar_ia(ctx):
    prompt = f"Trader Profissional: Analise {ctx}. Dê veredito ENTRAR/AGUARDAR e confiança %."
    try: return gemini.generate_content(prompt).text
    except: return "IA processando..."

# --- UI ---
st.title("🏆 IA REI DA BOLA - MODO ELITE PRO")
st.sidebar.success("✅ Plano PRO: Ligas de Elite + Arábia/EUA")

tab_radar, tab_pre = st.tabs(["🎯 RADAR LIVE (ELITE)", "🔮 PRÉ-JOGO DOSSIÊ"])

# --- TAB 1: RADAR AO VIVO ---
with tab_radar:
    live = get_data("fixtures?live=all")
    live_elite = [j for j in live if j['league']['id'] in LIGAS_ELITE]
    
    if not live_elite:
        st.info("Aguardando jogos das ligas selecionadas...")
    else:
        for f in live_elite:
            fid = f['fixture']['id']
            h, a = f['teams']['home']['name'], f['teams']['away']['name']
            placar = f"{f['goals']['home']}-{f['goals']['away']}"
            tempo = f['fixture']['status']['elapsed']
            liga_nome = f['league']['name']
            
            # Puxa Stats detalhadas
            s = get_data(f"fixtures/statistics?fixture={fid}")
            ig = 0
            if s:
                try:
                    # Cálculo do IG Pro: Foca em Ataques Perigosos e Chutes no Alvo
                    stats_h = {st['type']: st['value'] for st in s[0]['statistics']}
                    stats_a = {st['type']: st['value'] for st in s[1]['statistics']}
                    
                    atq_p = (stats_h.get('Dangerous Attacks', 0) or 0) + (stats_a.get('Dangerous Attacks', 0) or 0)
                    chutes = (stats_h.get('Shots on Goal', 0) or 0) + (stats_a.get('Shots on Goal', 0) or 0)
                    
                    ig = (atq_p * 0.5) + (chutes * 5)
                except: ig = 0

            color = "white"
            if ig > 25: color = "#ff4b4b" # Alerta vermelho para pressão alta
            
            with st.expander(f"⚽ {tempo}' | {h} {placar} {a} | IG: {ig:.1f}"):
                st.markdown(f"**Liga:** {liga_nome}")
                st.write(f"Pressão Total: {ig:.1f}")
                if st.button(f"Análise Especializada", key=f"live_{fid}"):
                    ctx_ia = f"{h}x{a}, Liga {liga_nome}, IG:{ig:.1f}, {tempo}min, {placar}"
                    st.info(analisar_ia(ctx_ia))

# --- TAB 2: PRÉ-JOGO ---
with tab_pre:
    hoje = datetime.now().strftime("%Y-%m-%d")
    pre_fixtures = get_data(f"fixtures?date={hoje}")
    pre_elite = [j for j in pre_fixtures if j['league']['id'] in LIGAS_ELITE and j['fixture']['status']['short'] == "NS"]
    
    if pre_elite:
        for p in pre_elite[:25]:
            h_p, a_p = p['teams']['home']['name'], p['teams']['away']['name']
            hora = p['fixture']['date'][11:16]
            with st.expander(f"📅 {hora} | {h_p} x {a_p}"):
                st.write(f"🏆 {p['league']['name']}")
                if st.button("Gerar Análise Pré-Jogo", key=f"pre_{p['fixture']['id']}"):
                    h2h = get_data(f"fixtures/headtohead?h2h={p['teams']['home']['id']}-{p['teams']['away']['id']}")
                    resumos = [f"{m['goals']['home']}x{m['goals']['away']}" for m in h2h[:3]]
                    st.markdown(analisar_ia(f"Análise Pré-Jogo: {h_p}x{a_p}. H2H: {resumos}"))
