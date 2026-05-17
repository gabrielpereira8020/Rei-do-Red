def buscar_jogos_da_liga(league_id):

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

        jogos.append({
            "nome": f"{casa} x {fora}",
            "id": fixture_id
        })

    return jogos
