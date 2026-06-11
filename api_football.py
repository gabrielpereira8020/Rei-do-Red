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
# BUSCAR EVENTOS DO JOGO AO VIVO
# =====================================================
def buscar_eventos_ao_vivo(fixture_id):
    """
    Busca eventos do jogo: gols, cartões, substituições com minuto exato.
    """
    try:
        data = _get(f"fixtures/events?fixture={fixture_id}")
        eventos = []
        for ev in data:
            tipo      = ev.get("type", "")
            detalhe   = ev.get("detail", "")
            minuto    = ev.get("time", {}).get("elapsed", "?")
            extra     = ev.get("time", {}).get("extra", None)
            time_nome = ev.get("team", {}).get("name", "?")
            jogador   = ev.get("player", {}).get("name", "?")
            assist    = ev.get("assist", {}).get("name", "")

            min_str = f"{minuto}" + (f"+{extra}" if extra else "") + "'"

            if tipo == "Goal":
                linha = f"  ⚽ {min_str} | {time_nome} | {jogador}"
                if assist:
                    linha += f" (assist: {assist})"
                if detalhe in ["Own Goal"]:
                    linha += " (GOL CONTRA)"
                elif detalhe == "Penalty":
                    linha += " (PÊNALTI)"
                eventos.append(linha)
            elif tipo == "Card":
                emoji = "🟨" if detalhe == "Yellow Card" else "🟥"
                eventos.append(f"  {emoji} {min_str} | {time_nome} | {jogador}")
            elif tipo == "subst":
                eventos.append(f"  🔄 {min_str} | {time_nome} | ↑{jogador} ↓{assist}")

        return eventos
    except Exception:
        return []


# =====================================================
# BUSCAR ODDS AO VIVO
# =====================================================
def buscar_odds_ao_vivo(fixture_id):
    """
    Busca odds ao vivo do fixture se disponível.
    """
    try:
        data = _get(f"odds/live?fixture={fixture_id}")
        if not data:
            return ""
        linhas = ["📊 ODDS AO VIVO:"]
        for item in data[:1]:  # Primeiro bookmaker
            bk = item.get("bookmaker", {}).get("name", "?")
            for bet in item.get("bets", [])[:3]:  # Primeiros 3 mercados
                nome_mercado = bet.get("name", "")
                valores = bet.get("values", [])
                odds_str = " | ".join([f"{v.get('value','')}@{v.get('odd','')}" for v in valores])
                linhas.append(f"  [{bk}] {nome_mercado}: {odds_str}")
        return "\n".join(linhas)
    except Exception:
        return ""


# =====================================================
# CONTEXTO AO VIVO COMPLETO
# =====================================================
def buscar_contexto_ao_vivo(jogo, fixture_id):
    """
    Monta contexto ao vivo COMPLETO com:
    - Stats do jogo (passes, precisão, chutes bloqueados, ataques perigosos)
    - Eventos (gols, cartões, subs com minuto exato)
    - Odds ao vivo
    - Stats individuais dos jogadores
    - Faltas por jogador (risco de cartão)
    """
    casa    = jogo["casa"]
    fora    = jogo["fora"]
    minuto  = jogo.get("minuto", "?")
    placar  = jogo.get("placar", "0 x 0")
    pressao = jogo.get("pressao", 0)

    contexto = (
        f"Jogo: {casa} x {fora}\n"
        f"Minuto: {minuto}'\n"
        f"Placar: {placar}\n"
        f"Índice de Pressão: {pressao}\n\n"
    )

    # ── Stats completas do jogo ──────────────────────
    stats_raw = jogo.get("stats_raw", [])
    if stats_raw and len(stats_raw) >= 2:
        def pegar_stat(s, nome):
            for item in s:
                if item["type"] == nome:
                    v = item["value"]
                    return v if v is not None else 0
            return 0

        home_s = stats_raw[0]["statistics"]
        away_s = stats_raw[1]["statistics"]
        th = stats_raw[0].get("team", {}).get("name", casa)
        ta = stats_raw[1].get("team", {}).get("name", fora)

        contexto += f"📊 ESTATÍSTICAS COMPLETAS DO JOGO:\n"
        stats_campos = [
            ("Total Shots",       "Chutes Totais"),
            ("Shots on Goal",     "Chutes no Gol"),
            ("Shots off Goal",    "Chutes Fora"),
            ("Blocked Shots",     "Chutes Bloqueados"),
            ("Ball Possession",   "Posse de Bola"),
            ("Corner Kicks",      "Escanteios"),
            ("Fouls",             "Faltas"),
            ("Yellow Cards",      "Cartões Amarelos"),
            ("Red Cards",         "Cartões Vermelhos"),
            ("Offsides",          "Impedimentos"),
            ("Goalkeeper Saves",  "Defesas do Goleiro"),
            ("Total passes",      "Passes Totais"),
            ("Passes accurate",   "Passes Certos"),
            ("Passes %",          "Precisão Passes"),
        ]
        contexto += f"  {'Estatística':<25} {th:<20} {ta}\n"
        contexto += "  " + "-"*55 + "\n"
        for campo, nome_pt in stats_campos:
            vh = pegar_stat(home_s, campo)
            va = pegar_stat(away_s, campo)
            if vh or va:
                contexto += f"  {nome_pt:<25} {str(vh):<20} {va}\n"
        contexto += "\n"
    else:
        # Fallback para texto simples
        stats_txt = jogo.get("stats", "indisponível")
        contexto += f"Estatísticas: {stats_txt}\n\n"

    # ── Eventos do jogo ─────────────────────────────
    try:
        eventos = buscar_eventos_ao_vivo(fixture_id)
        if eventos:
            contexto += "📋 EVENTOS DO JOGO:\n"
            contexto += "\n".join(eventos) + "\n\n"
    except Exception:
        pass

    # ── Odds ao vivo ────────────────────────────────
    try:
        odds_live = buscar_odds_ao_vivo(fixture_id)
        if odds_live:
            contexto += odds_live + "\n\n"
    except Exception:
        pass

    # ── Stats individuais dos jogadores ─────────────
    try:
        jogadores = buscar_stats_jogadores_ao_vivo(fixture_id)
        if jogadores:
            contexto += "🔥 DESTAQUES AO VIVO (top 10 jogadores):\n"
            for j in jogadores:
                linha = f"  [{j['time']}] {j['nome']} | {j['minutos']}min"
                if j['gols']:    linha += f" | ⚽{j['gols']} gol(s)"
                if j['assists']: linha += f" | 🅰️{j['assists']} assist"
                if j['chutes']:  linha += f" | 🎯{j['chutes']} chutes ({j['no_gol']} no gol)"
                if j['amarelo']: linha += f" | 🟨 AMARELO"
                if j['vermelho']:linha += f" | 🟥 VERMELHO"
                if j['rating']:  linha += f" | Nota: {j['rating']}"
                contexto += linha + "\n"
            contexto += "\n"
    except Exception:
        pass

    # ── Jogadores em risco de cartão (mais faltas) ───
    try:
        data_players = _get(f"fixtures/players?fixture={fixture_id}")
        em_risco = []
        for time in data_players:
            nome_time = time.get("team", {}).get("name", "?")
            for item in time.get("players", []):
                p = item.get("player", {})
                s = item.get("statistics", [{}])[0]
                faltas   = s.get("fouls", {}).get("committed", 0) or 0
                amarelo  = s.get("cards", {}).get("yellow", 0) or 0
                minutos  = s.get("games", {}).get("minutes", 0) or 0
                if faltas >= 2 and minutos > 0:
                    em_risco.append({
                        "time": nome_time,
                        "nome": p.get("name", "?"),
                        "faltas": faltas,
                        "amarelo": amarelo
                    })
        if em_risco:
            em_risco.sort(key=lambda x: x["faltas"], reverse=True)
            contexto += "⚠️ JOGADORES EM RISCO DE CARTÃO (≥2 faltas):\n"
            for j in em_risco[:5]:
                ja = " 🟨JÁ AMARELADO" if j["amarelo"] else ""
                contexto += f"  {j['time']} | {j['nome']} | {j['faltas']} faltas{ja}\n"
            contexto += "\n"
    except Exception:
        pass

    return contexto

    
