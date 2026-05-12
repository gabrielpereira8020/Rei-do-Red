import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

# Auto-refresh a cada 3 minutos para ser mais dinâmico
st_autorefresh(interval=180000, key="bot_refresh")

# Configuração de chaves
API_KEY = st.secrets["API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

# Inicializa placar
if 'greens' not in st.session_state: st.session_state.greens = 0
if 'reds' not in st.session_state: st.session_state.reds = 0

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
        requests.get(url)
    except: pass

st.set_page_config(page_title="IA Rei do Red: Visual Pro", layout="wide")

# --- CABEÇALHO ---
st.markdown("<h1 style='text-align: center; color: #EDECEC;'>📊 CENTRAL DE INTELIGÊNCIA ESPORTIVA</h1>", unsafe_allow_html=True)

# --- PAINEL DE PERFORMANCE ---
c_g, c_r, c_a = st.columns(3)
with c_g:
    st.markdown(f"<div style='background-color:#1b4332; padding:15px; border-radius:10px; border: 2px solid #2d6a4f; text-align:center'><h3 style='color:#74c69d; margin:0'>✅ GREENS</h3><h1 style='color:white; margin:0'>{st.session_state.greens}</h1></div>", unsafe_allow_html=True)
with c_r:
    st.markdown(f"<div style='background-color:#431b1b; padding:15px; border-radius:10px; border: 2px solid #6a2d2d; text-align:center'><h3 style='color:#ff8787; margin:0'>❌ REDS</h3><h1 style='color:white; margin:0'>{st.session_state.reds}</h1></div>", unsafe_allow_html=True)
with c_a:
    total = st.session_state.greens + st.session_state.reds
    assertividade = (st.session_state.greens / total * 100) if total > 0 else 0
    st.markdown(f"<div style='background-color:#2b2d42; padding:15px; border-radius:10px; border: 2px solid #8d99ae; text-align:center'><h3 style='color:#edf2f4; margin:0'>📈 TAXA DE ACERTO</h3><h1 style='color:white; margin:0'>{assertividade:.1f}%</h1></div>", unsafe_allow_html=True)

st.markdown("---")

# --- BUSCA DE DADOS ---
url = "https://v3.football.api-sports.io/fixtures?live=all"
res = requests.get(url, headers={'x-rapidapi-key': API_KEY}).json()

if res.get('response'):
    col_alertas, col_radar = st.columns([1.5, 1])

    with col_alertas:
        st.subheader("🔥 Alertas de Alta Pressão")
        
    with col_radar:
        st.subheader("📡 Radar Global (Analisando)")

    for j in res['response']:
        tempo = j['fixture']['status']['elapsed'] or 0
        if tempo < 10: continue

        casa = j['teams']['home']['name']
        fora = j['teams']['away']['name']
        id_j = j['fixture']['id']
        placar = f"{j['goals']['home']} - {j['goals']['away']}"

        # Busca Stats
        u_s = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_j}"
        s_res = requests.get(u_s, headers={'x-rapidapi-key': API_KEY}).json()
        
        no_alvo, fora_alvo, ataques_p = 0, 0, 0
        if s_res.get('response'):
            for s in s_res['response']:
                for stat in s['statistics']:
                    if stat['type'] == 'Shots on Goal' and stat['value']: no_alvo += stat['value']
                    if stat['type'] == 'Shots off Goal' and stat['value']: fora_alvo += stat['value']
                    if stat['type'] == 'Dangerous Attacks' and stat['value']: ataques_p += stat['value']

        ig = (no_alvo * 8) + (ataques_p / 5)
        ic = ((no_alvo + fora_alvo) * 3) + (ataques_p / 3)

        # 1. LÓGICA DE ALERTA (IG 50+)
        if ig >= 50 or ic >= 45:
            with col_alertas:
                with st.container():
                    st.markdown(f"**{casa} {placar} {fora}** | ⏰ {tempo}'")
                    st.progress(min(ig/100, 1.0))
                    c1, c2, c3 = st.columns([1,1,1])
                    c1.button(f"✅ Green", key=f"g_{id_j}", on_click=lambda: setattr(st.session_state, 'greens', st.session_state.greens + 1))
                    c2.button(f"❌ Red", key=f"r_{id_j
                    
