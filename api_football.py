import requests
import streamlit as st
from datetime import datetime, timedelta


API_KEY = st.secrets["API_KEY"]

HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}


def buscar_jogos_da_liga(league_id):

    try:

        ano_atual = datetime.now().year

        datas = [
            datetime.now(),
            datetime.now() + timedelta(days=1)
        ]

        jogos_formatados = []

        for data_ref in datas:

            data_str = data_ref.strftime("%Y-%m-%d")

            url = (
                "https://v3.football.api-sports.io/fixtures"
                f"?league={league_id}"
                f"&season={ano_atual}"
                f"&date={data_str}"
            )

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=15
            )

            if response.status_code != 200:
                continue

            data = response.json()

            jogos = data.get("response", [])

            for jogo in jogos:

                fixture_id = jogo["fixture"]["id"]

                home = jogo["teams"]["home"]["name"]
                away = jogo["teams"]["away"]["name"]

                jogo_formatado = {
                    "id": fixture_id,
                    "nome": f"{home} x {away}",
                    "time_casa": home,
                    "time_fora": away,
                    "liga": jogo["league"]["name"],
                    "data": jogo["fixture"]["date"]
                }

                # evita duplicados
                if not any(j["id"] == fixture_id for j in jogos_formatados):
                    jogos_formatados.append(jogo_formatado)

        return jogos_formatados

    except Exception as e:
        st.error(f"Erro buscar_jogos_da_liga: {e}")
        return []
