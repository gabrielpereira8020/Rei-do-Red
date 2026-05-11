import streamlit as st
import requests
import pandas as pd

# Puxa a chave dos "Secrets" do Streamlit
API_KEY = st.secrets["API_KEY"]
HEADERS = {'x-rapidapi-key': API_KEY}

st.set_page_config(page_title="IA Pro Stats", page_icon="📈", layout="wide")

st.title("🚀 IA Esportiva: Analisador Pro")

aba_fut, aba_basq = st.tabs(["⚽ Futebol (Série A)", "🏀 Basquete (NBA)"])

with aba_fut:
    st.header("Análise de Jogos e Escalações")
    if st.button("Atualizar Futebol"):
        url = "https://v3.football.api-sports.io/fixtures?live=all&league=71"
        res = requests.get(url, headers=HEADERS).json()
        
        if res['response']:
            for j in res['response']:
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.subheader(f"{j['teams']['home']['name']} {j['goals']['home']} x {j['goals']['away']} {j['teams']['away']['name']}")
                    st.write(f"Tempo de jogo: {j['fixture']['status']['elapsed']}'")
                
                with col2:
                    # Botão para analisar jogadores desse jogo específico
                    if st.button(f"Analisar Elenco", key=j['fixture']['id']):
                        st.info("Buscando performance dos jogadores...")
                        # Aqui chamamos a função de scouting que testamos no Colab
        else:
            st.warning("Nenhum jogo do Brasileirão ao vivo agora.")

with aba_basq:
    st.header("NBA Analytics")
    st.info("Esta aba mostrará a probabilidade de Over/Under de pontos por jogador.")
    # Adicionaremos a lógica de NBA aqui na próxima etapa
  
