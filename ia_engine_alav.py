import requests
import streamlit as st

API_KEY = None

def init(api_key):
    global API_KEY
    API_KEY = api_key

def _get(endpoint):
    try:
        r = requests.get(
            "https://v3.football.api-sports.io/" + endpoint,
            headers={
                "x-rapidapi-key": API_KEY,
                "x-rapidapi-host": "v3.football.api-sports.io"
            },
            timeout=15
        )
        if r.status_code != 200:
            return []
        return r.json().get("response", [])
    except Exception:
        return []

def buscar_stats_time(team_id, league_id, season=2025):
    """Busca forma recente, média de gols, aproveitamento mandante/visitante."""
    try:
        data = _get(f"teams/statistics?team={team_id}&league={league_id}&season={season}")
        if not data:
            return {}

        stats = data if isinstance(data, dict) else data[0] if data else {}

        # Forma recente
        form_str = stats.get("form", "")
        form = list(form_str[-5:]) if form_str else []
        vit = form.count("W")
        emp = form.count("D")
        der = form.count("L")

        # Gols
        all_stats = stats.get("goals", {})
        gols_marcados = all_stats.get("for", {}).get("average", {}).get("total", "0")
        gols_sofridos = all_stats.get("against", {}).get("average", {}).get("total", "0")

        # Mandante/Visitante
        fixtures = stats.get("fixtures", {})
        home_wins = fixtures.get("wins", {}).get("home", 0)
        home_total = fixtures.get("played", {}).get("home", 1)
        away_wins = fixtures.get("wins", {}).get("away", 0)
        away_total = fixtures.get("played", {}).get("away", 1)

        aprov_home = round((home_wins / max(home_total, 1)) * 100)
        aprov_away = round((away_wins / max(away_total, 1)) * 100)

        # Sequência atual
        sequencia = ""
        if form:
            ultimo = form[-1]
            count = 0
            for f in reversed(form):
                if f == ultimo:
                    count += 1
                else:
                    break
            if ultimo == "W":
                sequencia = str(count) + " vitoria(s) seguida(s)"
            elif ultimo == "L":
                sequencia = str(count) + " derrota(s) seguida(s)"
            else:
                sequencia = str(count) + " empate(s) seguido(s)"

        return {
            "form": "".join(form),
            "vit": vit, "emp": emp, "der": der,
            "gols_marcados": gols_marcados,
            "gols_sofridos": gols_sofridos,
            "aprov_home": aprov_home,
            "aprov_away": aprov_away,
            "sequencia": sequencia
        }
    except Exception:
        return {}

def buscar_h2h(home_id, away_id):
    """Busca últimos 5 confrontos diretos."""
    try:
        data = _get(f"fixtures/headtohead?h2h={home_id}-{away_id}&last=5")
        if not data:
            return []
        resultados = []
        for j in data[:5]:
            home_nome = j["teams"]["home"]["name"]
            away_nome = j["teams"]["away"]["name"]
            gh = j["goals"]["home"] or 0
            ga = j["goals"]["away"] or 0
            data_jogo = j["fixture"]["date"][:10]
            resultados.append(f"{data_jogo}: {home_nome} {gh} x {ga} {away_nome}")
        return resultados
    except Exception:
        return []

def buscar_classificacao(team_id, league_id, season=2025):
    """Busca posição, pontos e saldo na tabela."""
    try:
        data = _get(f"standings?league={league_id}&season={season}")
        if not data:
            return {}
        tabela = data[0]["league"]["standings"][0]
        for time in tabela:
            if time["team"]["id"] == team_id:
                return {
                    "posicao": time["rank"],
                    "pontos": time["points"],
                    "jogos": time["all"]["played"],
                    "saldo": time["goalsDiff"],
                    "forma_tabela": time.get("form", "")
                }
        return {}
    except Exception:
        return {}

def montar_contexto_stats(jogo):
    """
    Monta o contexto completo de estatísticas para um jogo.
    Retorna texto formatado para o prompt da IA.
    """
    home_id = jogo.get("casa_id")
    away_id = jogo.get("fora_id")
    league_id = jogo.get("liga_id", 71)
    casa = jogo.get("casa", "Casa")
    fora = jogo.get("fora", "Fora")

    if not home_id or not away_id:
        return ""

    ctx = "\n--- ESTATISTICAS REAIS ---\n"

    # Stats dos times
    stats_home = buscar_stats_time(home_id, league_id)
    stats_away = buscar_stats_time(away_id, league_id)

    if stats_home:
        ctx += f"\n{casa}:\n"
        ctx += f"  Forma recente: {stats_home.get('form','N/A')} ({stats_home.get('vit',0)}V {stats_home.get('emp',0)}E {stats_home.get('der',0)}D)\n"
        ctx += f"  Media gols: {stats_home.get('gols_marcados','?')} marcados | {stats_home.get('gols_sofridos','?')} sofridos\n"
        ctx += f"  Aproveitamento em casa: {stats_home.get('aprov_home','?')}%\n"
        ctx += f"  Sequencia atual: {stats_home.get('sequencia','N/A')}\n"

    if stats_away:
        ctx += f"\n{fora}:\n"
        ctx += f"  Forma recente: {stats_away.get('form','N/A')} ({stats_away.get('vit',0)}V {stats_away.get('emp',0)}E {stats_away.get('der',0)}D)\n"
        ctx += f"  Media gols: {stats_away.get('gols_marcados','?')} marcados | {stats_away.get('gols_sofridos','?')} sofridos\n"
        ctx += f"  Aproveitamento fora: {stats_away.get('aprov_away','?')}%\n"
        ctx += f"  Sequencia atual: {stats_away.get('sequencia','N/A')}\n"

    # H2H
    h2h = buscar_h2h(home_id, away_id)
    if h2h:
        ctx += "\nUltimos confrontos (H2H):\n"
        for r in h2h:
            ctx += f"  {r}\n"

    # Classificação
    class_home = buscar_classificacao(home_id, league_id)
    class_away = buscar_classificacao(away_id, league_id)
    if class_home or class_away:
        ctx += "\nClassificacao:\n"
        if class_home:
            ctx += f"  {casa}: {class_home.get('posicao','?')}o lugar | {class_home.get('pontos','?')} pts | Saldo {class_home.get('saldo','?')}\n"
        if class_away:
            ctx += f"  {fora}: {class_away.get('posicao','?')}o lugar | {class_away.get('pontos','?')} pts | Saldo {class_away.get('saldo','?')}\n"

    return ctx
EOF
python3 -c "import ast; ast.parse(open('/mnt/user-data/outputs/stats_engine.py').read()); print('stats_engine OK')"
