import streamlit as st
import requests

API_KEY = st.secrets["API_KEY"]
HEADERS = {'x-rapidapi-key': API_KEY}

st.set_page_config(page_title="IA Rei da Bola: Híbrido", page_icon="🏆", layout="wide")

st.title("🏆 IA Rei da Bola: Análise Híbrida")
st.sidebar.info("IA + API-Football + SofaScore (Manual Check)")

if st.button("🔥 SCANEAR MERCADO"):
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url, headers=HEADERS).json()
    
    if res.get('response'):
        for j in res['response']:
            tempo = j['fixture']['status']['elapsed'] if j['fixture']['status']['elapsed'] else 0
            if tempo < 5: continue 

            id_jogo = j['fixture']['id']
            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            liga = j['league']['name']
            
            # BUSCA ESTATÍSTICAS
            url_stats = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_jogo}"
            s_res = requests.get(url_stats, headers=HEADERS).json()
            
            no_alvo, fora_alvo, ataques_p, escanteios = 0, 0, 0, 0
            if s_res.get('response'):
                for s in s_res['response']:
                    for stat in s['statistics']:
                        if stat['type'] == 'Shots on Goal' and stat['value']: no_alvo += stat['value']
                        if stat['type'] == 'Shots off Goal' and stat['value']: fora_alvo += stat['value']
                        if stat['type'] == 'Dangerous Attacks' and stat['value']: ataques_p += stat['value']
                        if stat['type'] == 'Corner Kicks' and stat['value']: escanteios += stat['value']

            # CÁLCULOS SEPARADOS (GOLS vs CANTOS)
            ig = (no_alvo * 8) + (ataques_p / 5)
            ic = ((no_alvo + fora_alvo) * 3) + (ataques_p / 3)
            
            with st.container():
                c1, c2, c3 = st.columns([2, 2, 1.5])
                with c1:
                    st.subheader(f"{casa} x {fora}")
                    st.caption(f"🏆 {liga} | ⏰ {tempo}'")
                    # Link dinâmico para o SofaScore (Busca automática pelo nome dos times)
                    search_url = f"https://www.sofascore.com/search?q={casa.replace(' ', '+')}+vs+{fora.replace(' ', '+')}"
                    st.markdown(f"[📊 **Abrir Momentum no SofaScore**]({search_url})")
                
                with c2:
                    if ig > 40: st.success(f"⚽ IG: {ig:.1f} (Foco: Gol)")
                    if ic > 35: st.warning(f"🚩 IC: {ic:.1f} (Foco: Cantos)")
                    if ig <= 40 and ic <= 35: st.info("⚖️ Jogo Neutro")
                
                with c3:
                    if ic > 40 and tempo > 70:
                        st.button("💰 ENTRAR: CANTOS", key=f"c_{id_jogo}")
                    elif ig > 45 and tempo < 40:
                        st.button("⚽ ENTRAR: GOL HT", key=f"h_{id_jogo}")
                    else:
                        st.write("👀 Aguardando Padrão...")
                st.markdown("---")
                
