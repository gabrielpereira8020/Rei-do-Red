import requests
import streamlit as st
from datetime import datetime


API_KEY = st.secrets["API_KEY"]

HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}


def buscar_jogos_da_liga(league_id):

    try:

        hoje = datetime.now().strftime("%Y-%m-%d")

        url = (
            "https://v3.football.api-sports.io/fixtures"
            f"?league={league_id}"
            f"&season={datetime.now().year}"
            f"&date={hoje}"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        if response.status_code != 200:
            st.error(f"Erro API: {response.status_code}")
            return []

        data = response.json()

        jogos = data.get("response", [])

        resultado = []

        for jogo in jogos:

            fixture_id = jogo["fixture"]["id"]

            home = jogo["teams"]["home"]["name"]
            away = jogo["teams"]["away"]["name"]

            resultado.append({
                "id": fixture_id,
                "nome": f"{home} x {away}",
                "time_casa": home,
                "time_fora": away,
                "liga": jogo["league"]["name"],
                "data": jogo["fixture"]["date"]
            })

        return resultado

    except Exception as e:
        st.error(f"Erro buscar_jogos_da_liga: {e}")
        return []
