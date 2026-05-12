import streamlit as st
import requests

# Puxa a chave dos "Secrets"
API_KEY = st.secrets["API_KEY"]
HEADERS = {'x-rapidapi-key': API_KEY}

st.set_page_config(page_title="IA Pro Stats", page_icon="💰", layout="wide")

st.title("💰 IA Esportiva: Analisador Pro + Odds")

aba_fut, aba_basq = st.tabs(["⚽ Futebol Ao Vivo", "🏀 Basquete (NBA)"])

with aba_fut:
    st.header("Análise de Valor em Tempo Real")
    if st.button("Analisar Oportunidades"):
        url = "https://v3.football.api-sports.io/fixtures?live=all"
        res = requests.get(url, headers=HEADERS).json()
        
        if res['response']:
            for j in res['response']:
                casa = j['teams']['home']['name']
                fora = j['teams']['away']['name']
                p_casa = j['goals']['home']
                p_fora = j['goals']['away']
                tempo = j['fixture']['status']['elapsed']
                
                # Criando o card do jogo
                with st.container():
                    st.markdown(f"---")
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.subheader(f"{casa} {p_casa} x {p_fora} {fora}")
                        st.caption(f"Liga: {j['league']['name']} ({tempo}')")
                    
                    with col2:
                        # Lógica de Inteligência de Valor
                        chutes_total = 0 # Simulação se não houver stats detalhadas
                        if tempo > 70 and (p_casa + p_fora) == 0:
                            st.error("🎯 Alerta: Under 0.5/1.5")
                        elif tempo < 30 and (p_casa + p_fora) >= 2:
                            st.success("🔥 Alerta: Over Gols!")
                        else:
                            st.info("⚖️ Jogo Equilibrado")

        else:
            st.info("Nenhum jogo ao vivo encontrado agora.")

with aba_basq:
    st.header("NBA - Projeções")
    st.write("Aguardando jogos da noite para análise de cestas.")
    
