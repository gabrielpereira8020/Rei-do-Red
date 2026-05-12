import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

# 🔄 Auto-refresh a cada 3 minutos para manter o radar ativo
st_autorefresh(interval=180000, key="bot_refresh")

# Chaves
API_KEY = st.secrets["API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

# Inicializa o placar de Greens e Reds
if 'greens' not in st.session_state: st.session_state.greens = 0
if 'reds' not in st.session_state: st.session_state.reds = 0

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
        requests.get(url)
    except: pass

st.set_page_config(page_title="IA Rei do Red", page_icon="⚽")

# --- TÍTULO E PLACAR ---
st.title("💰 IA Rei da Bola")

col_stats = st.columns(3)
col_stats[0].metric("✅ Greens", st.session_state.greens)
col_stats[1].metric("❌ Reds", st.session_state.reds)
total = st.session_state.greens + st.session_state.reds
acc = (st.session_state.greens / total * 100) if total > 0 else 0
col_stats[2].metric("📈 Acerto", f"{acc:.1f}%")

st.markdown("---")

# --- BUSCA DE DADOS ---
url_live = "https://v3.football.api-sports.io/fixtures?live=all"
res = requests.get(url_live, headers={'x-rapidapi-key': API_KEY}).json()

if res.get('response'):
    for j in res['response']:
        tempo = j['fixture']['status']['elapsed'] or 0
        if tempo < 10: continue

        casa = j['teams']['home']['name']
        fora = j['teams']['away']['name']
        id_jogo = j['fixture']['id']
        g_casa = j['goals']['home'] or 0
        g_fora = j['goals']['away'] or 0

        # Busca Estatísticas Detalhadas
        u_s = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_jogo}"
        s_res = requests.get(u_s, headers={'x-rapidapi-key': API_KEY}).json()
        
        no_alvo, fora_alvo, ataques_p = 0, 0, 0
        if s_res.get('response'):
            for s in s_res['response']:
                for stat in s['statistics']:
                    if stat['type'] == 'Shots on Goal' and stat['value']: no_alvo += stat['value']
                    if stat['type'] == 'Shots off Goal' and stat['value']: fora_alvo += stat['value']
                    if stat['type'] == 'Dangerous Attacks' and stat['value']: ataques_p += stat['value']

        # Fórmulas IG e IC
        ig = (no_alvo * 8) + (ataques_p / 5)
        ic = ((no_alvo + fora_alvo) * 3) + (ataques_p / 3)

        # --- DESIGN DE CARD ORIGINAL ---
        with st.expander(f"🏟️ {casa} {g_casa} x {g_fora} {fora} ({tempo}')"):
            st.write(f"📊 **IG (Gols):** {ig:.1f} | **IC (Cantos):** {ic:.1f}")
            
            # Alertas baseados na pressão
            if ig > 50:
                st.success("🔥 PRESSÃO CRÍTICA: Chance alta de GOL!")
                if f"s_{id_jogo}" not in st.session_state:
                    enviar_telegram(f"🚨 ALERTA GOL: {casa} x {fora}\nIG: {ig:.1f}")
                    st.session_state[f"s_{id_jogo}"] = True
            elif ig > 30:
                st.warning("⚠️ JOGO ESQUENTANDO: Ficar de olho.")
            else:
                st.info("❄️ JOGO PARADO: Pouca pressão no momento.")

            # Botões de Validação para o Placar
            c1, c2 = st.columns(2)
            if c1.button(f"✅ Green", key=f"win_{id_jogo}"):
                st.session_state.greens += 1
                st.rerun()
            if c2.button(f"❌ Red", key=f"loss_{id_jogo}"):
                st.session_state.reds += 1
                st.rerun()
else:
    st.info("Nenhum jogo ao vivo encontrado agora. Monitorando mercado...")

if st.sidebar.button("Zerar Placar"):
    st.session_state.greens = 0
    st.session_state.reds = 0
    st.rerun()
    
