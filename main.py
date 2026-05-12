import streamlit as st
import requests

# Puxa a chave dos "Secrets"
API_KEY = st.secrets["API_KEY"]
HEADERS = {'x-rapidapi-key': API_KEY}

st.set_page_config(page_title="IA Pro Stats", page_icon="📈")

st.title("🚀 IA Esportiva: Analisador Pro")

aba_fut, aba_basq = st.tabs(["⚽ Futebol Ao Vivo", "🏀 Basquete (NBA)"])

with aba_fut:
    st.header("Análise de Pressão e Gols")
    if st.button("Buscar Jogos no Mundo"):
        # Agora busca TODOS os jogos ao vivo (live=all)
        url = "https://v3.football.api-sports.io/fixtures?live=all"
        res = requests.get(url, headers=HEADERS).json()
        
        if res['response']:
            for j in res['response']:
                casa = j['teams']['home']['name']
                fora = j['teams']['away']['name']
                placar_casa = j['goals']['home']
                placar_fora = j['goals']['away']
                tempo = j['fixture']['status']['elapsed']
                
                with st.expander(f"{casa} {placar_casa} x {placar_fora} {fora} ({tempo}')"):
                    st.write(f"**Competição:** {j['league']['name']} - {j['league']['country']}")
                    
                    # Lógica simples de IA para pressão
                    eventos = len(j.get('events', []))
                    if eventos > 10:
                        st.success("🔥 CHANCE ALTA DE GOL: Jogo muito movimentado!")
                    elif eventos > 5:
                        st.warning("⚠️ JOGO MORNO: Pouca pressão na área.")
                    else:
                        st.error("❄️ JOGO PARADO: Grande chance de Under (poucos gols).")
        else:
            st.info("Nenhum jogo relevante acontecendo agora.")

with aba_basq:
    st.header("NBA Stats")
    st.write("Dica: Os jogos da NBA geralmente começam à noite!")
