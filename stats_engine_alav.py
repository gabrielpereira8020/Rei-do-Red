"""
stats_engine_alav.py
====================
Busca jogos futuros e enriquece com stats reais da API Football.
"""

import requests
import streamlit as st
from datetime import datetime, timedelta

API_KEY = None
HEADERS = {}

# -------------------------------------------
# LIGAS MONITORADAS
# -------------------------------------------

LIGAS_ALTA_IDS = {
    # Brasil
    71,   # Serie A
    # Europa top 5
    39,   # Premier League
    140,  # LaLiga
    135,  # Serie A Italia
    78,   # Bundesliga
    61,   # Ligue 1
    # Europa outras
    94,   # Primeira Liga Portugal
    88,   # Eredivisie Holanda
    144,  # Jupiler Pro League Belgica
    203,  # Super Lig Turquia
    179,  # Premiership Escocia
    207,  # Super League Suica
    # Americas
    128,  # Liga Profesional Argentina
    262,  # Liga MX Mexico
    253,  # MLS EUA
    # Asia
    98,   # J1 League Japao
    307,  # Saudi Pro League
    # Escandinavia
    103,  # Eliteserien Noruega
    113,  # Allsvenskan Suecia
    119,  # Superliga Dinamarca
    # Competicoes internacionais
    1,    # World Cup
    2,    # UEFA Champions League
    3,    # UEFA Europa League
    13,   # CONMEBOL Libertadores
    11,   # CONMEBOL Sudamericana
    15,   # FIFA Club World Cup
    848,  # UEFA Europa Conference League
    16,   # CONCACAF Champions Cup
    17,   # AFC Champions League Elite
    12,   # CAF Champions League
    9,    # International Friendlies (selecoes)
}

LIGAS_MEDIA_IDS = {
    # Brasil
    72,   # Serie B
    73,   # Serie C
    # Europa segunda divisao
    40,   # EFL Championship
    41,   # EFL League One
    42,   # EFL League Two
    141,  # LaLiga 2
    136,  # Serie B Italia
    62,   # Ligue 2
    95,   # Segunda Liga Portugal
    79,   # 2. Bundesliga
    # Americas
    129,  # Primera Nacional Argentina
    130,  # Copa Argentina
    131,  # Primera B Metropolitana Argentina
    132,  # Primera C Argentina
    266,  # Primera B Chile
    268,  # Primera Division Apertura
    269,  # Segunda Division
    299,  # Primera Division
    300,  # Segunda Division
    # Asia e Oriente Medio
    99,   # J2 League Japao
    293,  # K League 2 Coreia
    291,  # K League 1 Coreia
    542,  # Iraqi League
    # Africa
    200,  # Botola Pro Marrocos
    201,  # Botola 2 Marrocos
    411,  # Elite One Camaroes
    # Europa outras
    104,  # 1. Division Dinamarca
    117,  # 1. Division
    223,  # Regionalliga West Alemanha
    277,  # Super League
    316,  # 1st League FBiH Bosnia
    # EUA
    254,  # USL Championship
    909,  # MLS Next Pro
    # Outros
    10,   # Friendlies (clubes)
    667,  # Club Friendlies
    914,  # Tournoi Maurice Revello
}


def init(api_key):
    global API_KEY, HEADERS
    API_KEY = api_key
    HEADERS = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }


def _get(endpoint):
    if not API_KEY:
        return []
    try:
        r = requests.get(
            "https://v3.football.api-sports.io/" + endpoint,
            headers=HEADERS,
            timeout=15
        )
        if r.status_code != 200:
            return []
        data = r.json()
        resp = data.get("response", data)
        return resp if isinstance(resp, list) else [resp]
    except Exception:
        return []


def _get_dict(endpoint):
    result = _get(endpoint)
    if isinstance(result, list) and result:
        return result[0] if isinstance(result[0], dict) else {}
    return {}


# -------------------------------------------
# BUSCAR JOGOS FUTUROS
# -------------------------------------------

def buscar_jogos_futuros_api_football(dias=2):
    """
    Busca todos os jogos de hoje e amanhã.
    Estrategia 1: endpoint por data (uma chamada, retorna tudo).
    Estrategia 2: fallback por liga se a 1 falhar.
    """
    todas_ids = LIGAS_ALTA_IDS | LIGAS_MEDIA_IDS
    jogos_encontrados = []
    ids_vistos = set()

    STATUS_ENCERRADO = {"FT", "AET", "PEN", "AWD", "WO", "CANC", "ABD"}

    datas = [datetime.now().strftime("%Y-%m-%d")]
    if dias >= 2:
        datas.append((datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))

    # Estrategia 1: endpoint por data
    total_e1 = 0
    for data_str in datas:
        fixtures = _get(f"fixtures?date={data_str}")
        if not fixtures:
            fixtures = _get(f"fixtures?date={data_str}&status=NS")

        total_bruto = len(fixtures)
        aceitos = 0
        fora_lista = 0

        for f in fixtures:
            fid = f.get("fixture", {}).get("id")
            if not fid or fid in ids_vistos:
                continue
            status = f.get("fixture", {}).get("status", {}).get("short", "")
            if status in STATUS_ENCERRADO:
                continue
            jogo = _montar_jogo(f)
            if jogo:
                ids_vistos.add(fid)
                jogos_encontrados.append(jogo)
                aceitos += 1
                total_e1 += 1
            else:
                fora_lista += 1

        log_msg = (
            f"Data {data_str}: {total_bruto} brutos | "
            f"{aceitos} aceitos | {fora_lista} sem stats esperados"
        )
        st.caption(log_msg)

    if total_e1 > 0:
        st.info(f"✅ {total_e1} jogos encontrados para analise")
        jogos_encontrados.sort(key=lambda x: x.get("prioridade", 3))
        return jogos_encontrados

    # Estrategia 2: fallback por liga
    st.warning("Endpoint por data retornou vazio — buscando liga por liga...")
    ano = datetime.now().year
    ligas_ordenadas = list(LIGAS_ALTA_IDS) + list(LIGAS_MEDIA_IDS - LIGAS_ALTA_IDS)
    prog = st.progress(0)

    for idx, liga_id in enumerate(ligas_ordenadas):
        prog.progress((idx + 1) / len(ligas_ordenadas))
        for temporada in [ano, ano - 1]:
            for data_str in datas:
                try:
                    fixtures = _get(
                        f"fixtures?league={liga_id}&season={temporada}&date={data_str}"
                    )
                    for f in fixtures:
                        fid = f.get("fixture", {}).get("id")
                        if not fid or fid in ids_vistos:
                            continue
                        status = f.get("fixture", {}).get("status", {}).get("short", "")
                        if status in STATUS_ENCERRADO:
                            continue
                        jogo = _montar_jogo(f)
                        if jogo:
                            ids_vistos.add(fid)
                            jogos_encontrados.append(jogo)
                    if fixtures:
                        break
                except Exception:
                    continue

    prog.empty()
    jogos_encontrados.sort(key=lambda x: x.get("prioridade", 3))
    st.info(f"✅ Fallback: {len(jogos_encontrados)} jogos encontrados")
    return jogos_encontrados


def _montar_jogo(f):
    """Converte fixture em dict padronizado. Aceita qualquer liga."""
    fid = f.get("fixture", {}).get("id")
    if not fid:
        return None

    home = f.get("teams", {}).get("home", {})
    away = f.get("teams", {}).get("away", {})
    league = f.get("league", {})
    liga_id = league.get("id", 0)

    home_name = home.get("name", "")
    away_name = away.get("name", "")
    home_id = home.get("id")
    away_id = away.get("id")

    if not home_name or not away_name or not home_id or not away_id:
        return None

    todas_ids = LIGAS_ALTA_IDS | LIGAS_MEDIA_IDS
    if liga_id in LIGAS_ALTA_IDS:
        prioridade = 1
    elif liga_id in LIGAS_MEDIA_IDS:
        prioridade = 2
    else:
        prioridade = 3  # Liga desconhecida — aceita mas fica por ultimo

    return {
        "id": str(fid),
        "nome": f"{home_name} x {away_name}",
        "casa": home_name,
        "fora": away_name,
        "casa_id": home_id,
        "fora_id": away_id,
        "liga_nome": league.get("name", ""),
        "liga_id": liga_id,
        "data": f.get("fixture", {}).get("date", "")[:16].replace("T", " "),
        "prioridade": prioridade,
        # Stats (preenchidos por enriquecer_stats_jogo)
        "forma_home": "",
        "forma_away": "",
        "aprov_home": 0,
        "aprov_away": 0,
        "gols_marcados_home": 0,
        "gols_sofridos_home": 0,
        "gols_marcados_away": 0,
        "gols_sofridos_away": 0,
        "sequencia_home": "",
        "sequencia_away": "",
        "h2h_home_wins": 0,
        "h2h_total": 0,
        "classificacao_home": {},
        "classificacao_away": {},
        "stats_txt": "",
        # Odds (Etapa 4)
        "odds_txt": "",
        "tem_odds": False,
        "melhor_odd": 0,
        # IA (Etapa 3)
        "ia_mercado": "",
        "ia_confianca": 0,
        "ia_motivo": "",
    }


# -------------------------------------------
# ENRIQUECER JOGO COM STATS REAIS
# -------------------------------------------

def enriquecer_stats_jogo(jogo):
    """
    Busca e preenche stats reais do jogo via API Football.
    Modifica o dict in-place.
    """
    home_id = jogo.get("casa_id")
    away_id = jogo.get("fora_id")
    liga_id = jogo.get("liga_id", 71)
    temporada = datetime.now().year
    casa = jogo.get("casa", "Casa")
    fora = jogo.get("fora", "Fora")

    ctx_lines = [
        f"Jogo: {casa} x {fora} | Liga: {jogo.get('liga_nome','')} | {jogo.get('data','')}"
    ]

    # Stats mandante
    stats_h = _get_dict(
        f"teams/statistics?team={home_id}&league={liga_id}&season={temporada}"
    )
    if not stats_h:
        stats_h = _get_dict(
            f"teams/statistics?team={home_id}&league={liga_id}&season={temporada-1}"
        )
    if stats_h:
        _preencher_stats_time(jogo, stats_h, "home")
        ctx_lines.append(
            f"{casa}: Forma {jogo['forma_home']} | "
            f"Gols {jogo['gols_marcados_home']}/jogo | "
            f"Sofre {jogo['gols_sofridos_home']}/jogo | "
            f"Casa {jogo['aprov_home']}% aprov"
        )

    # Stats visitante
    stats_a = _get_dict(
        f"teams/statistics?team={away_id}&league={liga_id}&season={temporada}"
    )
    if not stats_a:
        stats_a = _get_dict(
            f"teams/statistics?team={away_id}&league={liga_id}&season={temporada-1}"
        )
    if stats_a:
        _preencher_stats_time(jogo, stats_a, "away")
        ctx_lines.append(
            f"{fora}: Forma {jogo['forma_away']} | "
            f"Gols {jogo['gols_marcados_away']}/jogo | "
            f"Sofre {jogo['gols_sofridos_away']}/jogo | "
            f"Fora {jogo['aprov_away']}% aprov"
        )

    # H2H
    h2h = _get(f"fixtures/headtohead?h2h={home_id}-{away_id}&last=5")
    if h2h:
        home_wins = sum(
            1 for j in h2h
            if j.get("teams", {}).get("home", {}).get("id") == home_id
            and (j.get("goals", {}).get("home") or 0) > (j.get("goals", {}).get("away") or 0)
        )
        jogo["h2h_home_wins"] = home_wins
        jogo["h2h_total"] = len(h2h)
        ctx_lines.append(f"H2H: {home_wins} vitórias do mandante em {len(h2h)} jogos")

    # Classificação
    standings = _get(f"standings?league={liga_id}&season={temporada}")
    if standings:
        try:
            tabela = standings[0]["league"]["standings"][0]
            for time in tabela:
                tid = time["team"]["id"]
                if tid in (home_id, away_id):
                    cl = {
                        "posicao": time["rank"],
                        "pontos": time["points"],
                        "jogos": time["all"]["played"],
                        "saldo": time.get("goalsDiff", 0),
                    }
                    nome = time["team"]["name"]
                    if tid == home_id:
                        jogo["classificacao_home"] = cl
                    else:
                        jogo["classificacao_away"] = cl
                    ctx_lines.append(
                        f"{nome}: {cl['posicao']}o lugar | {cl['pontos']}pts | saldo {cl['saldo']}"
                    )
        except Exception:
            pass

    jogo["stats_txt"] = "\n".join(ctx_lines)
    return jogo["stats_txt"]


def _preencher_stats_time(jogo, stats, lado):
    try:
        form_str = stats.get("form", "") or ""
        form = list(form_str[-5:]) if form_str else []
        forma = "".join(form)

        gols = stats.get("goals", {})
        gols_marcados = float(gols.get("for", {}).get("average", {}).get("total", 0) or 0)
        gols_sofridos = float(gols.get("against", {}).get("average", {}).get("total", 0) or 0)

        fixtures = stats.get("fixtures", {})
        if lado == "home":
            wins = fixtures.get("wins", {}).get("home", 0)
            total = max(fixtures.get("played", {}).get("home", 1), 1)
        else:
            wins = fixtures.get("wins", {}).get("away", 0)
            total = max(fixtures.get("played", {}).get("away", 1), 1)
        aprov = round((wins / total) * 100)

        sequencia = ""
        if form:
            ultimo = form[-1]
            count = sum(1 for x in reversed(form) if x == ultimo)
            mapa = {"W": "vitoria(s)", "D": "empate(s)", "L": "derrota(s)"}
            sequencia = f"{count} {mapa.get(ultimo, '')} seguida(s)"

        if lado == "home":
            jogo["forma_home"] = forma
            jogo["aprov_home"] = aprov
            jogo["gols_marcados_home"] = round(gols_marcados, 2)
            jogo["gols_sofridos_home"] = round(gols_sofridos, 2)
            jogo["sequencia_home"] = sequencia
        else:
            jogo["forma_away"] = forma
            jogo["aprov_away"] = aprov
            jogo["gols_marcados_away"] = round(gols_marcados, 2)
            jogo["gols_sofridos_away"] = round(gols_sofridos, 2)
            jogo["sequencia_away"] = sequencia
    except Exception:
        pass


def montar_contexto_stats(jogo):
    """Compat com pre_jogo/ao_vivo."""
    return enriquecer_stats_jogo(jogo)
                      
