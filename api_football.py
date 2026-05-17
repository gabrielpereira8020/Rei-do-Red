import requests
import streamlit as st

API_KEY = st.secrets["API_FOOTBALL_KEY"]

headers = {
    "x-apisports-key": API_KEY
}

def buscar_estatisticas_jogo(jogo):

    try:

        url = "https://v3.football.api-sports.io/fixtures"

        params = {
            "search": jogo
        }

        response = requests.get(
            url,
            headers=headers,
            params=params
        )

        data = response.json()

        # VOCÊ PODE MELHORAR DEPOIS
        # PEGANDO:
        # - odds
        # - jogadores
        # - cartões
        # - escanteios
        # - últimos jogos

        return data

    except Exception as e:

        return {
            "erro": str(e)
        }
