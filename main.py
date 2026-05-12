import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

# Auto-Refresh a cada 5 min
st_autorefresh(interval=300000, key="bot_refresh")

# Chaves
API_KEY = st.secrets["API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

# Inicializa o placar
if 'greens' not in st.session_state: st.session_state.greens = 0
if 'reds' not in st.session_state: st.session_state.reds = 0

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={mensagem}"
        requests.get(url)
    except: pass

st.set_page_config(page_title="IA Rei do Red: Multi-Filtro", layout="wide")

# --- PAINEL DE PERFORMANCE ---
st.title("🏆 Dashboard de Performance Profissional")
c_g, c_r, c_a = st.columns(3)
with c_g:
    st.markdown(f"<div style='background-color:#d4edda; padding:20px; border-radius:10px; text-align:center'><h2 style='color:#155724'>✅ GREENS</h2><h1>{st.session_state.greens}</h1></div>", unsafe_allow_html=True)
with c_r:
    st.markdown(f"<div style='background-color:#f8d7da; padding:20px; border-radius:10px; text-align:center'><h2 style='color:#721c24'>❌ REDS</h2><h1>{st.session_state.reds}</h1></div>", unsafe_allow_html=True)
with c_a:
    total = st.session_state.greens + st.session_state.reds
    assertividade = (st.session_state.greens / total * 100) if total > 0 else 0
    st.markdown(f"<div style='background-color:#fff3cd; padding:20px; border-radius:10px; text-align:center'><h2 style='color:#856404'>📈 ACERTO</h2><h1>{assertividade:.1f}%</h1></div>", unsafe_allow_html=True)

st.markdown("---")

# --- BUSCA DE JOGOS ---
url = "https://v3.football.api-sports.io/fixtures?live=all"
res = requests.get(url, headers={'x-rapidapi-key': API_KEY}).json()

if res.get('response'):
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔥 ENTRADA CONFIRMADA (IG 50+)")
    with col2:
        st.subheader("👀 EM OBSERVAÇÃO (IG 30+)")
        
    for j in res['response']:
        tempo = j['fixture']['status']['elapsed'] or 0
        if tempo < 10: continue

        casa = j['teams']['home']['name']
        fora = j['teams']['away']['name']
        id_j = j['fixture']['id']

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

        # SEPARAÇÃO POR COLUNAS
        if ig >= 50 or ic >= 45:
            with col1:
                st.info(f"🚀 {casa} x {fora} ({tempo}')\nIG: {ig:.1f} | IC: {ic:.1f}")
                cg, cr = st.columns(2)
                if cg.button(f"✅ Bateu", key=f"g_{id_j}"):
                    st.session_state.greens += 1
                    st.rerun()
                if cr.button(f"❌ Errou", key=f"r_{id_j}"):
                    st.session_state.reds += 1
                    st.rerun()
                
                # Manda Telegram só para os de 50+
                if f"sent_{id_j}" not in st.session_state:
                    enviar_telegram(f"🚨 ENTRADA CONFIRMADA!\n🏟️ {casa} x {fora}\n📈 IG: {ig:.1f} | IC: {ic:.1f}")
                    st.session_state[f"sent_{id_j}"] = True

        elif ig >= 30 or ic >= 25:
            with col2:
                st.warning(f"⚠️ {casa} x {fora} ({tempo}')\nIG: {ig:.1f} | IC: {ic:.1f}")
else:
    st.info("Varrendo o mercado em busca de oportunidades...")
