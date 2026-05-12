import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

# Auto-refresh a cada 3 minutos
st_autorefresh(interval=180000, key="bot_refresh")

# Chaves nos Secrets
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

st.markdown("<h1 style='text-align: center;'>📊 CENTRAL DE INTELIGÊNCIA</h1>", unsafe_allow_html=True)

# --- PAINEL DE PERFORMANCE ---
c_g, c_r, c_a = st.columns(3)
with c_g:
    st.success(f"✅ GREENS: {st.session_state.greens}")
with c_r:
    st.error(f"❌ REDS: {st.session_state.reds}")
with c_a:
    total = st.session_state.greens + st.session_state.reds
    acc = (st.session_state.greens / total * 100) if total > 0 else 0
    st.info(f"📈 ACERTO: {acc:.1f}%")

st.markdown("---")

# --- BUSCA DE DADOS ---
url = "https://v3.football.api-sports.io/fixtures?live=all"
res = requests.get(url, headers={'x-rapidapi-key': API_KEY}).json()

if res.get('response'):
    col_alertas, col_radar = st.columns([1.5, 1])

    with col_alertas:
        st.subheader("🔥 Alertas de Alta Pressão")
        
    with col_radar:
        st.subheader("📡 Radar Global")

    for j in res['response']:
        tempo = j['fixture']['status']['elapsed'] or 0
        if tempo < 10: continue

        casa = j['teams']['home']['name']
        fora = j['teams']['away']['name']
        id_j = j['fixture']['id']
        placar = f"{j.get('goals', {}).get('home', 0)} - {j.get('goals', {}).get('away', 0)}"

        # Stats
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

        # 1. ALERTAS
        if ig >= 50 or ic >= 45:
            with col_alertas:
                st.markdown(f"**{casa} {placar} {fora}** ({tempo}')")
                btn_g, btn_r = st.columns(2)
                if btn_g.button(f"✅ Green", key=f"g_{id_j}"):
                    st.session_state.greens += 1
                    st.rerun()
                if btn_r.button(f"❌ Red", key=f"r_{id_j}"):
                    st.session_state.reds += 1
                    st.rerun()
                
                if f"sent_{id_j}" not in st.session_state:
                    enviar_telegram(f"🚨 ENTRADA!\n🏟️ {casa} x {fora}\n📈 IG: {ig:.1f}")
                    st.session_state[f"sent_{id_j}"] = True
                st.markdown("---")

        # 2. RADAR
        with col_radar:
            with st.expander(f"⚽ {casa} x {fora}"):
                st.write(f"IG: {ig:.1f} | IC: {ic:.1f} | Tempo: {tempo}'")

else:
    st.info("Varrendo o mercado...")
    
