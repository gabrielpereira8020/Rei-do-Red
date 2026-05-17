import requests
import streamlit as st

API_KEY = st.secrets.get("API_FOOTBALL_KEY")

headers = {
    "x-apisports-key": API_KEY
}

def buscar_jogos_da_liga(...)

    url = "https://v3.football.api-sports.io/fixtures"

    params = {
        "league": league_id,
        "season": 2025,
        "next": 20
    }

    response = requests.get(
        url,
        headers=headers,
        params=params
    )

    data = response.json()

    jogos = []

    for jogo in data["response"]:

        casa = jogo["teams"]["home"]["name"]

        fora = jogo["teams"]["away"]["name"]

        fixture_id = jogo["fixture"]["id"]

        data_jogo = jogo["fixture"]["date"]

        jogos.append({

            "nome": f"{casa} x {fora}",

            "id": fixture_id,

            "casa": casa,

            "fora": fora,

            "data": data_jogo
        })

    return jogos
