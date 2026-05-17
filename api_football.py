import requests
import streamlit as st

API_KEY = st.secrets["API_FOOTBALL_KEY"]

headers = {
    "x-apisports-key": API_KEY
}

def buscar_jogo(nome_jogo):

    url = "https://v3.football.api-sports.io/fixtures"

    params = {
        "search": nome_jogo
    }

    response = requests.get(
        url,
        headers=headers,
        params=params
    )

    return response.json()
