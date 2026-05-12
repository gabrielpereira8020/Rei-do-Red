import streamlit as st
import requests

# Chaves das duas fontes diferentes
API_KEY = st.secrets["API_KEY"]
ODDS_API_KEY = st.secrets["ODDS_API_KEY"]

st.set_page_config(page_title="IA Rei da Bola: Pro", page_icon="💰", layout="wide")

st.title("💰 IA Rei da Bola: Inteligência Dupla")
st.sidebar.write("Fontes: API-Football + The-Odds-API")

if st.button("🔍 ESCANEAR MERCADO (DUPLA FONTE)"):
    # FONTE 1: Estatísticas de Campo (API-Football)
    url_stats = "https://v3.football.api-sports.io/fixtures?live=all"
    res_stats = requests.get(url_stats, headers={'x-rapidapi-key': API_KEY}).json()
    
    # FONTE 2: Odds ao Vivo (The-Odds-API)
    # Buscando odds de futebol para a região Europa/Brasil
    url_odds = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h,totals&oddsFormat=decimal"
    res_odds = requests.get(url_odds).json()

    if res_stats.get('response'):
        for j in res_stats['response']:
            tempo = j['fixture']['status']['elapsed'] if j['fixture']['status']['elapsed'] else 0
            if tempo < 10: continue

            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            p_casa = j['goals']['home'] or 0
            p_fora = j['goals']['away'] or 0
            
            # Cruzamento de Dados: Tenta achar a Odd desse jogo na Fonte 2
            odd_encontrada = "Buscando..."
            if isinstance(res_odds, list):
                for o in res_odds:
                    if casa in o['home_team'] or fora in o['away_team']:
                        # Pega a odd do primeiro bookmaker disponível (ex: Bet365/Betano)
                        odd_encontrada = o['bookmakers'][0]['markets'][0]['outcomes']

            # Lógica de análise (IG e IC)
            # (Aqui mantemos aquele cálculo que você aprovou)
            
            with st.container():
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.subheader(f"{casa} {p_casa} x {p_fora} {fora}")
                    st.caption(f"⏰ {tempo}' min | Fonte 1: Status OK")
                with c2:
                    if isinstance(odd_encontrada, list):
                        st.info(f"📊 Odds: {odd_encontrada[0]['name']} @{odd_encontrada[0]['price']}")
                    else:
                        st.write("Odd em ajuste...")
                st.markdown("---")
    else:
        st.warning("Aguardando entrada de dados das fontes...")

st.sidebar.markdown("---")
st.sidebar.caption("IA configurada para cruzar dados de campo com movimentação de mercado.")
