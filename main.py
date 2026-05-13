import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

# 🔄 Auto-refresh a cada 3 minutos
st_autorefresh(interval=180000, key="bot_refresh")

# Chaves
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

st.set_page_config(page_title="IA Rei da Bola", page_icon="💰")

# --- TÍTULO E PLACAR ---
st.title("💰 IA Rei da Bola")

c1, c2, c3 = st.columns(3)
c1.metric("✅ Greens", st.session_state.greens)
c2.metric("❌ Reds", st.session_state.reds)
total = st.session_state.greens + st.session_state.reds
acc = (st.session_state.greens / total * 100) if total > 0 else 0
c3.metric("📈 Acerto", f"{acc:.1f}%")

st.markdown("---")

# --- BUSCA DE DADOS ---
url_live = "https://v3.football.api-sports.io/fixtures?live=all"
res = requests.get(url_live, headers={'x-rapidapi-key': API_KEY}).json()

if res.get('response'):
    st.subheader("🔥 Jogos em Destaque (Alta Pressão)")
    
    # Criamos uma lista para os jogos "frios" aparecerem depois
    jogos_frios = []

    for j in res['response']:
        tempo = j['fixture']['status']['elapsed'] or 0
        # MUDANÇA: Agora aceita jogos desde o minuto 1
        if tempo < 1: continue 

        casa = j['teams']['home']['name']
        fora = j['teams']['away']['name']
        id_jogo = j['fixture']['id']
        g_casa = j.get('goals', {}).get('home', 0)
        g_fora = j.get('goals', {}).get('away', 0)

        # Estatísticas
        u_s = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_jogo}"
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

        # LÓGICA DE EXIBIÇÃO
        if ig >= 30 or ic >= 25:
            with st.expander(f"🏟️ {casa} {g_casa} x {g_fora} {fora} ({tempo}')"):
                st.write(f"📊 IG: {ig:.1f} | IC: {ic:.1f}")
                
                if ig >= 50:
                    st.success("🔥 PRESSÃO CRÍTICA!")
                    if f"s_{id_jogo}" not in st.session_state:
                        enviar_telegram(f"🚨 ALERTA GOL: {casa} x {fora}\nIG: {ig:.1f}")
                        st.session_state[f"s_{id_jogo}"] = True
                
                col_b1, col_b2 = st.columns(2)
                if col_b1.button(f"✅ Green", key=f"w_{id_jogo}"):
                    st.session_state.greens += 1
                    st.rerun()
                if col_b2.button(f"❌ Red", key=f"l_{id_jogo}"):
                    st.session_state.reds += 1
                    st.rerun()
        else:
            # Guarda os jogos frios para mostrar depois
            jogos_frios.append(f"{casa} x {fora} ({tempo}') - IG: {ig:.1f}")

    # --- RADAR SECUNDÁRIO ---
    st.markdown("---")
    with st.expander("📡 Radar de Monitoramento (Jogos Iniciais/Lentos)"):
        for info in jogos_frios:
            st.write(info)

else:
    st.info("Buscando jogos no mundo inteiro...")

if st.sidebar.button("Zerar Placar"):
    st.session_state.greens = 0
    st.session_state.reds = 0
    st.rerun()
    
