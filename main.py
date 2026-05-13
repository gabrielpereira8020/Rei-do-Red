import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh
import pandas as pd

# 🔄 Auto-refresh a cada 3 minutos
st_autorefresh(interval=180000, key="bot_refresh")

API_KEY = st.secrets["API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

if 'greens' not in st.session_state: st.session_state.greens = 0
if 'reds' not in st.session_state: st.session_state.reds = 0
if 'historico' not in st.session_state: st.session_state.historico = []

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
        requests.get(url)
    except: pass

st.set_page_config(page_title="IA Rei da Bola: Analista Pro", layout="wide")

# --- DASHBOARD ---
st.title("💰 IA Rei da Bola: Analista Pro")
c1, c2, c3 = st.columns(3)
c1.metric("✅ Greens", st.session_state.greens)
c2.metric("❌ Reds", st.session_state.reds)
total = st.session_state.greens + st.session_state.reds
acc = (st.session_state.greens / total * 100) if total > 0 else 0
c3.metric("📈 Assertividade", f"{acc:.1f}%")

tab1, tab2 = st.tabs(["🎯 ANÁLISE DETALHADA", "📚 MEU HISTÓRICO"])

with tab1:
    url_live = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url_live, headers={'x-rapidapi-key': API_KEY}).json()

    if res.get('response'):
        st.subheader("📊 Monitoramento de Pressão em Tempo Real")
        
        for j in res['response']:
            tempo = j['fixture']['status']['elapsed'] or 0
            if tempo < 1: continue 

            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            id_jogo = j['fixture']['id']
            placar = f"{j['goals']['home']}x{j['goals']['away']}"

            # Busca Estatísticas Detalhadas
            u_s = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_jogo}"
            s_res = requests.get(u_s, headers={'x-rapidapi-key': API_KEY}).json()
            
            # Zerando variáveis para o Raio-X
            no_alvo, fora_alvo, ataques_p, escanteios, posse = 0, 0, 0, 0, 0
            
            if s_res.get('response'):
                for s in s_res['response']:
                    for stat in s['statistics']:
                        val = stat['value'] if stat['value'] else 0
                        if stat['type'] == 'Shots on Goal': no_alvo += val
                        if stat['type'] == 'Shots off Goal': fora_alvo += val
                        if stat['type'] == 'Dangerous Attacks': ataques_p += val
                        if stat['type'] == 'Corner Kicks': escanteios += val
                        if stat['type'] == 'Ball Possession': posse = val

            ig = (no_alvo * 8) + (ataques_p / 5)
            ic = ((no_alvo + fora_alvo) * 3) + (ataques_p / 3)

            # Só mostra o expander se o jogo tiver o mínimo de movimento (IG > 15)
            if ig > 15 or ic > 15:
                with st.expander(f"🏟️ {casa} {placar} {fora} ({tempo}')"):
                    
                    # --- RAIO-X DO JOGO ---
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.write(f"🎯 **No Alvo:** {no_alvo}")
                        st.write(f"🥅 **Para Fora:** {fora_alvo}")
                    with col_info2:
                        st.write(f"🧨 **Atq. Perigosos:** {ataques_p}")
                        st.write(f"🚩 **Escanteios:** {escanteios}")
                    with col_info3:
                        st.write(f"📈 **IG (Gols):** {ig:.1f}")
                        st.write(f"📐 **IC (Cantos):** {ic:.1f}")

                    # --- VEREDIT
                    
