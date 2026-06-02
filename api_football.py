import requests
import streamlit as st
from datetime import datetime, timedelta

API_KEY = st.secrets["API_KEY"]
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

def _get(endpoint):
    try:
        url = "https://v3.football.api-sports.io/" + endpoint
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        return r.json().get("response", [])
    except Exception:
        return []


# =====================================================
# BUSCAR JOGOS DA LIGA (hoje + amanhã)
# =====================================================
def buscar_jogos_da_liga(league_id):
    try:
        temporadas = [2025, 2026, 2027]
        datas = [datetime.now(), datetime.now() + timedelta(days=1)]
        jogos_formatados = []

        for season in temporadas:
            for data_ref in datas:
                data_str = data_ref.strftime("%Y-%m-%d")
                jogos = _get(f"fixtures?league={league_id}&season={season}&date={data_str}")

                for jogo in jogos:
                    fixture_id = jogo["fixture"]["id"]
                    if any(j["id"] == fixture_id for j in jogos_formatados):
                        continue

                    home    = jogo["teams"]["home"]["name"]
                    away    = jogo["teams"]["away"]["name"]
                    home_id = jogo["teams"]["home"]["id"]
                    away_id = jogo["teams"]["away"]["id"]

                    jogos_formatados.append({
                        "id":       fixture_id,
                        "nome":     f"{home} x {away}",
                        "casa":     home,
                        "fora":     away,
                        "casa_id":  home_id,
                        "fora_id":  away_id,
                        "liga":     jogo["league"]["name"],
                        "liga_id":  league_id,
                        "season":   season,
                        "data":     jogo["fixture"]["date"]
                    })

        return jogos_formatados

    except Exception as e:
        st.error(f"Erro buscar_jogos_da_liga: {e}")
        return []


# =====================================================
# BUSCAR TOP JOGADORES DA TEMPORADA
# =====================================================
def buscar_top_jogadores(team_id, league_id, season):
    """
    Busca estatísticas dos jogadores do time na temporada.
    Retorna os top 5 por minutos jogados com gols, assistências,
    chutes, cartões e avaliação média.
    """
    try:
        data = _get(f"players?team={team_id}&league={league_id}&season={season}")
        jogadores = []

        for item in data:
            p = item.get("player", {})
            stats = item.get("statistics", [{}])[0]

            nome     = p.get("name", "?")
            pos      = stats.get("games", {}).get("position", "?")
            minutos  = stats.get("games", {}).get("minutes", 0) or 0
            jogos    = stats.get("games", {}).get("appearences", 0) or 0
            gols     = stats.get("goals", {}).get("total", 0) or 0
            assists  = stats.get("goals", {}).get("assists", 0) or 0
            chutes   = stats.get("shots", {}).get("total", 0) or 0
            amarelos = stats.get("cards", {}).get("yellow", 0) or 0
            vermelhos= stats.get("cards", {}).get("red", 0) or 0
            rating   = stats.get("games", {}).get("rating", None)

            if minutos > 0:
                jogadores.append({
                    "nome":      nome,
                    "pos":       pos,
                    "minutos":   minutos,
                    "jogos":     jogos,
                    "gols":      gols,
                    "assists":   assists,
                    "chutes":    chutes,
                    "amarelos":  amarelos,
                    "vermelhos": vermelhos,
                    "rating":    round(float(rating), 2) if rating else 0.0
                })

        # Ordena por minutos jogados e pega top 5
        jogadores.sort(key=lambda x: x["minutos"], reverse=True)
        return jogadores[:5]

    except Exception:
        return []


# =====================================================
# BUSCAR ESTATÍSTICAS AO VIVO POR JOGADOR
# =====================================================
def buscar_stats_jogadores_ao_vivo(fixture_id):
    """
    Busca estatísticas individuais dos jogadores durante o jogo ao vivo.
    Retorna os destaques: quem chutou mais, tomou cartão, fez gol, etc.
    """
    try:
        data = _get(f"fixtures/players?fixture={fixture_id}")
        destaques = []

        for time in data:
            nome_time = time.get("team", {}).get("name", "?")
            jogadores  = time.get("players", [])

            for item in jogadores:
                p     = item.get("player", {})
                stats = item.get("statistics", [{}])[0]

                nome     = p.get("name", "?")
                minutos  = stats.get("games", {}).get("minutes", 0) or 0
                gols     = stats.get("goals", {}).get("total", 0) or 0
                assists  = stats.get("goals", {}).get("assists", 0) or 0
                chutes   = stats.get("shots", {}).get("total", 0) or 0
                no_gol   = stats.get("shots", {}).get("on", 0) or 0
                amarelo  = stats.get("cards", {}).get("yellow", 0) or 0
                vermelho = stats.get("cards", {}).get("red", 0) or 0
                rating   = stats.get("games", {}).get("rating", None)

                # Só inclui jogadores que estão em campo
                if minutos and minutos > 0:
                    destaques.append({
                        "time":     nome_time,
                        "nome":     nome,
                        "minutos":  minutos,
                        "gols":     gols,
                        "assists":  assists,
                        "chutes":   chutes,
                        "no_gol":   no_gol,
                        "amarelo":  amarelo,
                        "vermelho": vermelho,
                        "rating":   round(float(rating), 2) if rating else 0.0
                    })

        # Ordena por rating e chutes
        destaques.sort(key=lambda x: (x["rating"], x["chutes"]), reverse=True)
        return destaques[:10]  # Top 10 jogadores em campo

    except Exception:
        return []


# =====================================================
# CONTEXTO COMPLETO PRÉ-JOGO
# =====================================================
def buscar_contexto_completo(jogo):
    """
    Monta contexto rico com classificação, H2H, forma recente
    e top jogadores da temporada para o prompt da IA.
    """
    casa      = jogo["casa"]
    fora      = jogo["fora"]
    home_id   = jogo.get("casa_id")
    away_id   = jogo.get("fora_id")
    league_id = jogo.get("liga_id")
    season    = jogo.get("season", 2025)

    contexto = f"Jogo: {casa} x {fora}\nLiga: {jogo['liga']}\nData: {jogo['data'][:10]}\n\n"

    # --- CLASSIFICAÇÃO ---
    try:
        standings = _get(f"standings?league={league_id}&season={season}")
        if standings:
            tabela = standings[0]["league"]["standings"][0]
            contexto += "📊 CLASSIFICAÇÃO:\n"
            for time in tabela:
                nome = time["team"]["name"]
                if nome in [casa, fora]:
                    pos   = time["rank"]
                    pts   = time["points"]
                    pg    = time["all"]["played"]
                    vit   = time["all"]["win"]
                    emp   = time["all"]["draw"]
                    der   = time["all"]["lose"]
                    gp    = time["all"]["goals"]["for"]
                    gc    = time["all"]["goals"]["against"]
                    forma = time.get("form", "N/A")
                    contexto += f"  {nome}: {pos}º | {pts}pts | {pg}J {vit}V {emp}E {der}D | Gols: {gp}/{gc} | Forma recente: {forma}\n"
            contexto += "\n"
    except Exception:
        pass

    # --- H2H ---
    try:
        h2h = _get(f"fixtures/headtohead?h2h={home_id}-{away_id}&last=5")
        if h2h:
            contexto += "⚔️ ÚLTIMOS CONFRONTOS (H2H):\n"
            for j in h2h[:5]:
                dh = j["teams"]["home"]["name"]
                da = j["teams"]["away"]["name"]
                gh = j["goals"]["home"]
                ga = j["goals"]["away"]
                dt = j["fixture"]["date"][:10]
                contexto += f"  {dt}: {dh} {gh} x {ga} {da}\n"
            contexto += "\n"
    except Exception:
        pass

    # --- FORMA RECENTE ---
    try:
        for time_id, time_nome in [(home_id, casa), (away_id, fora)]:
            ultimos = _get(f"fixtures?team={time_id}&last=5")
            if ultimos:
                contexto += f"📈 ÚLTIMOS 5 JOGOS - {time_nome}:\n"
                for j in ultimos:
                    dh = j["teams"]["home"]["name"]
                    da = j["teams"]["away"]["name"]
                    gh = j["goals"]["home"]
                    ga = j["goals"]["away"]
                    dt = j["fixture"]["date"][:10]
                    contexto += f"  {dt}: {dh} {gh} x {ga} {da}\n"
                contexto += "\n"
    except Exception:
        pass

    # --- TOP JOGADORES ---
    try:
        for time_id, time_nome in [(home_id, casa), (away_id, fora)]:
            jogadores = buscar_top_jogadores(time_id, league_id, season)
            if jogadores:
                contexto += f"🌟 TOP JOGADORES - {time_nome} (temporada):\n"
                for j in jogadores:
                    contexto += (
                        f"  {j['nome']} ({j['pos']}) | "
                        f"{j['jogos']} jogos | "
                        f"⚽{j['gols']} 🅰️{j['assists']} "
                        f"🎯{j['chutes']} chutes | "
                        f"🟨{j['amarelos']} 🟥{j['vermelhos']} | "
                        f"Nota: {j['rating']}\n"
                    )
                contexto += "\n"
    except Exception:
        pass

    return contexto


# =====================================================
# CONTEXTO AO VIVO COM JOGADORES
# =====================================================
def buscar_contexto_ao_vivo(jogo, fixture_id):
    """
    Monta contexto ao vivo com estatísticas individuais dos jogadores.
    """
    casa    = jogo["casa"]
    fora    = jogo["fora"]
    minuto  = jogo.get("minuto", "?")
    placar  = jogo.get("placar", "0 x 0")
    pressao = jogo.get("pressao", 0)
    stats   = jogo.get("stats", "indisponível")

    contexto = (
        f"Jogo: {casa} x {fora}\n"
        f"Minuto: {minuto}'\n"
        f"Placar: {placar}\n"
        f"Índice de Pressão: {pressao}\n"
        f"Estatísticas do jogo: {stats}\n\n"
    )

    # Estatísticas individuais ao vivo
    try:
        jogadores = buscar_stats_jogadores_ao_vivo(fixture_id)
        if jogadores:
            contexto += "🔥 DESTAQUES AO VIVO (top 10 jogadores em campo):\n"
            for j in jogadores:
                linha = f"  [{j['time']}] {j['nome']} | {j['minutos']}min"
                if j['gols']:    linha += f" | ⚽{j['gols']} gol(s)"
                if j['assists']: linha += f" | 🅰️{j['assists']} assist"
                if j['chutes']:  linha += f" | 🎯{j['chutes']} chutes ({j['no_gol']} no gol)"
                if j['amarelo']: linha += f" | 🟨 AMARELO"
                if j['vermelho']:linha += f" | 🟥 VERMELHO"
                if j['rating']:  linha += f" | Nota: {j['rating']}"
                contexto += linha + "\n"
    except Exception:
        pass

    return contexto
    
