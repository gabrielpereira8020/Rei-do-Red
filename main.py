import streamlit as st
import requests

# Configurações de API
API_KEY = st.secrets["API_KEY"]
HEADERS = {'x-rapidapi-key': API_KEY}

st.set_page_config(page_title="IA Futebol Elite", page_icon="⚽", layout="wide")

st.title("⚽ IA Rei da Bola: Analisador Elite")
st.markdown("---")

if st.button("🚀 ESCANEAR OPORTUNIDADES AGORA"):
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url, headers=HEADERS).json()
    
    if res.get('response'):
        for j in res['response']:
            # Puxa o tempo com segurança (se for None, vira 0)
            tempo = j['fixture']['status']['elapsed'] if j['fixture']['status']['elapsed'] else 0
            
            id_jogo = j['fixture']['id']
            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            p_casa = j['goals']['home'] if j['goals']['home'] is not None else 0
            p_fora = j['goals']['away'] if j['goals']['away'] is not None else 0
            liga = j['league']['name']
            
            # 1. BUSCANDO ESTATÍSTICAS (Radar de Escanteios)
            url_stats = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_jogo}"
            s_res = requests.get(url_stats, headers=HEADERS).json()
            
            chutes_alvo = 0
            ataques_perigosos = 0
            escanteios = 0
            
            if s_res.get('response'):
                for s in s_res['response']:
                    for stat in s['statistics']:
                        if stat['type'] == 'Shots on Goal' and stat['value']:
                            chutes_alvo += stat['value']
                        if stat['type'] == 'Dangerous Attacks' and stat['value']:
                            ataques_perigosos += stat['value']
                        if stat['type'] == 'Corner Kicks' and stat['value']:
                            escanteios += stat['value']

            # 2. ÍNDICE DE PERIGO (PI)
            indice_perigo = (chutes_alvo * 3) + (ataques_perigosos / 4)
            
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.subheader(f"{casa} {p_casa} x {p_fora} {fora}")
                    st.caption(f"🏆 {liga} • {tempo} min")
                    st.write(f"🚩 Escanteios Totais: {escanteios}")
                
                with col2:
                    if indice_perigo > 20:
                        st.success(f"🔥 PRESSÃO EXTREMA (PI: {indice_perigo:.1f})")
                    elif indice_perigo > 10:
                        st.warning(f"⚖️ JOGO MOVIMENTADO (PI: {indice_perigo:.1f})")
                    else:
                        st.error(f"❄️ JOGO TRANCADO (PI: {indice_perigo:.1f})")
                
                with col3:
                    # 3. VEREDITO FINAL DA IA
                    if tempo > 75 and ataques_perigosos > 35 and abs(p_casa - p_fora) <= 1:
                        st.button("🚩 Sugestão: +0.5 Cantos", key=f"c_{id_jogo}")
                    elif tempo < 35 and indice_perigo > 12:
                        st.button("⚽ Sugestão: Over 0.5 HT", key=f"h_{id_jogo}")
                    elif indice_perigo < 5 and tempo > 60:
                        st.button("🔒 Sugestão: Under Gols", key=f"u_{id_jogo}")
                    else:
                        st.button("👀 Só Observar", key=f"n_{id_jogo}")
                
                st.markdown("---")
    else:
        st.info("Nenhum jogo com dados ao vivo agora. Tente em instantes!")

st.sidebar.title("🤖 Inteligência Rei da Bola")
st.sidebar.write("A IA agora ignora jogos sem dados e foca em Pressão Real.")
