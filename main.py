import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh
import pandas as pd

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

st.set_page_config(page_title="IA Rei da Bola: Trader", layout="wide")

# --- DASHBOARD ---
st.title("🏆 IA Rei da Bola: Estrategista")
c1, c2, c3 = st.columns(3)
c1.metric("✅ Greens", st.session_state.greens)
c2.metric("❌ Reds", st.session_state.reds)
total = st.session_state.greens + st.session_state.reds
acc = (st.session_state.greens / total * 100) if total > 0 else 0
c3.metric("📈 Assertividade", f"{acc:.1f}%")

tab1, tab2 = st.tabs(["🎯 ANÁLISE & ENTRADAS", "📚 MEU HISTÓRICO"])

with tab1:
    url_live = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url_live, headers={'x-rapidapi-key': API_KEY}).json()

    if res.get('response'):
        for j in res['response']:
            tempo = j['fixture']['status']['elapsed'] or 0
            if tempo < 1: continue 

            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            id_jogo = j['fixture']['id']
            placar = f"{j['goals']['home']}x{j['goals']['away']}"

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

            # --- DEFINIÇÃO DA ENTRADA ---
            sugestao = ""
            cor_box = "white"
            
            if ig >= 50:
                sugestao = "⚽ ENTRADA: Próximo Gol (Over 0.5)"
                cor_box = "orange"
            elif ic >= 45:
                sugestao = "🚩 ENTRADA: Próximo Escanteio"
                cor_box = "blue"
            elif ig >= 35:
                sugestao = "👀 ATENÇÃO: Jogo ficando bom para GOL"
            
            if ig >= 35 or ic >= 40:
                with st.expander(f"🏟️ {casa} x {fora} | IG: {ig:.1f} | IC: {ic:.1f}"):
                    st.write(f"⏰ {tempo}' | Placar: {placar}")
                    
                    if sugestao:
                        st.markdown(f"### {sugestao}")
                    
                    c1, c2 = st.columns(2)
                    if c1.button(f"✅ Green", key=f"g_{id_jogo}"):
                        st.session_state.greens += 1
                        st.session_state.historico.append({"Jogo": casa, "Mercado": sugestao, "Res": "✅"})
                        st.rerun()
                    if c2.button(f"❌ Red", key=f"r_{id_jogo}"):
                        st.session_state.reds += 1
                        st.session_state.historico.append({"Jogo": casa, "Mercado": sugestao, "Res": "❌"})
                        st.rerun()

                    # Alerta Automático para o Telegram
                    if (ig >= 50 or ic >= 45) and f"s_{id_jogo}" not in st.session_state:
                        enviar_telegram(f"🚨 NOVA ENTRADA!\n🏟️ {casa} x {fora}\n🎯 {sugestao}\n📈 IG: {ig:.1f} | IC: {ic:.1f}")
                        st.session_state[f"s_{id_jogo}"] = True

with tab2:
    if st.session_state.historico:
        st.table(pd.DataFrame(st.session_state.historico))
    else:
        st.info("Nenhuma entrada registrada.")
        
