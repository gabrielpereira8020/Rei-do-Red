import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

# 1. ATUALIZA O APP SOZINHO A CADA 5 MINUTOS
st_autorefresh(interval=300000, key="bot_refresh")

# Chaves (Certifique-se que estas 4 estão nos Secrets do Streamlit)
API_KEY = st.secrets["API_KEY"]
ODDS_API_KEY = st.secrets["ODDS_API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={mensagem}"
        requests.get(url)
    except:
        pass

st.set_page_config(page_title="Sentinela Rei do Red", page_icon="🚨", layout="wide")
st.title("🚨 Sentinela Rei do Red: Ativo")
st.write("🔄 Monitorando jogos e enviando alertas para o Telegram...")

# Busca de Dados ao Vivo
url = "https://v3.football.api-sports.io/fixtures?live=all"
res = requests.get(url, headers={'x-rapidapi-key': API_KEY}).json()

if res.get('response'):
    for j in res['response']:
        tempo = j['fixture']['status']['elapsed'] or 0
        if tempo < 10: continue

        casa = j['teams']['home']['name']
        fora = j['teams']['away']['name']
        id_j = j['fixture']['id']

        # Busca Estatísticas para calcular IG e IC
        u_s = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_j}"
        s_res = requests.get(u_s, headers={'x-rapidapi-key': API_KEY}).json()
        
        no_alvo, fora_alvo, ataques_p = 0, 0, 0
        if s_res.get('response'):
            for s in s_res['response']:
                for stat in s['statistics']:
                    if stat['type'] == 'Shots on Goal' and stat['value']: no_alvo += stat['value']
                    if stat['type'] == 'Shots off Goal' and stat['value']: fora_alvo += stat['value']
                    if stat['type'] == 'Dangerous Attacks' and stat['value']: ataques_p += stat['value']

        # Cálculo dos Índices
        ig = (no_alvo * 8) + (ataques_p / 5)
        ic = ((no_alvo + fora_alvo) * 3) + (ataques_p / 3)

        # Lógica de Alerta (Só envia se o jogo estiver "pegando fogo")
        if ig > 50 or ic > 45:
            tipo = "⚽ GOL" if ig > 50 else "🚩 CANTOS"
            msg = f"🔥 ALERTA DE {tipo}!\n\n🏟️ {casa} x {fora}\n⏰ Tempo: {tempo}'\n🎯 IG: {ig:.1f} | IC: {ic:.1f}"
            
            # Evita repetir a mensagem no mesmo jogo
            if f"sent_{id_j}" not in st.session_state:
                enviar_telegram(msg)
                st.session_state[f"sent_{id_j}"] = True
                st.success(f"Alerta enviado: {casa} x {fora}")

        st.write(f"✅ Monitorando: {casa} x {fora} ({tempo}') - IG: {ig:.1f}")
else:
    st.info("Nenhum jogo quente no momento. Próxima varredura em 5 min...")
    
