import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh
import pandas as pd # Para organizar o histórico em tabela

# 🔄 Auto-refresh a cada 3 minutos
st_autorefresh(interval=180000, key="bot_refresh")

# Configurações iniciais
API_KEY = st.secrets["API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

# "Banco de Dados" em Memória
if 'greens' not in st.session_state: st.session_state.greens = 0
if 'reds' not in st.session_state: st.session_state.reds = 0
if 'historico' not in st.session_state: st.session_state.historico = []

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
        requests.get(url)
    except: pass

st.set_page_config(page_title="IA Rei da Bola: Pro", layout="wide")

# --- PAINEL DE PERFORMANCE ---
st.title("🏆 Central de Comando IA")
c1, c2, c3 = st.columns(3)
c1.metric("✅ Greens", st.session_state.greens)
c2.metric("❌ Reds", st.session_state.reds)
total = st.session_state.greens + st.session_state.reds
acc = (st.session_state.greens / total * 100) if total > 0 else 0
c3.metric("📈 Taxa de Acerto", f"{acc:.1f}%")

# --- ORGANIZAÇÃO EM ABAS ---
tab1, tab2 = st.tabs(["⚽ AO VIVO & ANÁLISE", "📚 HISTÓRICO DE ENTRADAS"])

with tab1:
    url_live = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url_live, headers={'x-rapidapi-key': API_KEY}).json()

    if res.get('response'):
        st.subheader("🔥 Jogos com Pressão Detectada")
        jogos_frios = []

        for j in res['response']:
            tempo = j['fixture']['status']['elapsed'] or 0
            if tempo < 1: continue 

            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            id_jogo = j['fixture']['id']
            placar = f"{j['goals']['home']}x{j['goals']['away']}"

            # Stats (Busca rápida)
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

            # Exibição de Jogos Quentes
            if ig >= 30:
                with st.expander(f"🏟️ {casa} x {fora} | IG: {ig:.1f}"):
                    st.write(f"⏰ Tempo: {tempo}' | Placar: {placar}")
                    
                    col_b1, col_b2 = st.columns(2)
                    if col_b1.button(f"✅ Green", key=f"win_{id_jogo}"):
                        st.session_state.greens += 1
                        st.session_state.historico.append({"Jogo": f"{casa} x {fora}", "IG": ig, "Resultado": "✅ GREEN", "Tempo": f"{tempo}'"})
                        st.rerun()
                    if col_b2.button(f"❌ Red", key=f"loss_{id_jogo}"):
                        st.session_state.reds += 1
                        st.session_state.historico.append({"Jogo": f"{casa} x {fora}", "IG": ig, "Resultado": "❌ RED", "Tempo": f"{tempo}'"})
                        st.rerun()

                    if ig >= 50 and f"s_{id_jogo}" not in st.session_state:
                        enviar_telegram(f"🚨 ALERTA: {casa} x {fora}\nIG: {ig:.1f}")
                        st.session_state[f"s_{id_jogo}"] = True
            else:
                jogos_frios.append({"Jogo": f"{casa} x {fora}", "Tempo": f"{tempo}'", "IG": f"{ig:.1f}"})

        st.markdown("---")
        st.subheader("📡 Radar de Monitoramento (Tudo)")
        if jogos_frios:
            df_frios = pd.DataFrame(jogos_frios)
            st.table(df_frios) # Mostra todos os outros jogos em uma tabela limpa

with tab2:
    st.subheader("📖 Relatório de Entradas do Dia")
    if st.session_state.historico:
        df_hist = pd.DataFrame(st.session_state.historico)
        st.dataframe(df_hist, use_container_width=True)
        if st.button("Limpar Histórico"):
            st.session_state.historico = []
            st.session_state.greens = 0
            st.session_state.reds = 0
            st.rerun()
    else:
        st.info("Nenhuma entrada registrada ainda hoje.")
        
