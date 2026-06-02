"""
stats_engine_alav.py
====================
ETAPA 1 da nova arquitetura:
  - Busca jogos futuros diretamente na API Football (hoje + amanhã)
  - Coleta stats reais: forma, gols, aproveitamento, H2H, classificação
  - Já embute os dados no objeto do jogo para o ranking_engine pontuar
  - Retorna jogos com campos padronizados prontos para ranquear

NÃO depende de odds nessa etapa.
"""

import requests
import streamlit as st
from datetime import datetime, timedelta
from ligas import LIGAS, COMPETICOES_INTERNACIONAIS

API_KEY = None
HEADERS = {}

# Monta os sets de IDs direto do ligas.py — sem duplicar nada
def _todos_ids():
    ids = set()
    for pais in LIGAS.values():
        for lid in pais.values():
            ids.add(lid)
    for lid in COMPETICOES_INTERNACIONAIS.values():
        ids.add(lid)
    return ids

# Ligas de alto valor para prioridade 1
LIGAS_ALTA_IDS = {
    39, 61, 71, 78, 94, 135, 140, 848,  # ligas nacionais top
    2, 3, 13, 11, 15, 1, 16, 17, 12     # competicoes internacionais
}
# Tudo mais do ligas.py recebe prioridade 2
LIGAS_MEDIA_IDS = _todos_ids() - LIGAS_ALTA_IDS


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
        # A API retorna dict com "response" ou às vezes o dict diretamente
        resp = data.get("response", data)
        return resp if isinstance(resp, list) else [resp]
    except Exception:
        return []


def _get_dict(endpoint):
    """Versão que retorna o primeiro item como dict (para statistics)."""
    result = _get(endpoint)
    if isinstance(result, list) and result:
        return result[0] if isinstance(result[0], dict) else {}
    return {}


# ---------------------------------------------
# BUSCAR JOGOS FUTUROS DA API FOOTBALL
# ---------------------------------------------

def buscar_jogos_futuros_api_football(ligas_ids=None, dias=2):
    """
    Busca jogos de hoje e amanhã para as ligas monitoradas.
    Retorna lista de jogos formatados com IDs dos times para buscar stats.
    """
    if ligas_ids is None:
        ligas_ids = list(LIGAS_ALTA_IDS | LIGAS_MEDIA_IDS)

    jogos_encontrados = []
    ids_vistos = set()

    datas = [
        datetime.now().strftime("%Y-%m-%d"),
        (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    ]

    temporada = datetime.now().year

    for liga_id in ligas_ids:
        for data_str in datas[:dias]:
            try:
                fixtures = _get(
                    f"fixtures?league={liga_id}&season={temporada}&date={data_str}"
                )
                # Tenta também ano anterior se não achar nada
                if not fixtures:
                    fixtures = _get(
                        f"fixtures?league={liga_id}&season={temporada - 1}&date={data_str}"
                    )

                for f in fixtures:
                    fid = f.get("fixture", {}).get("id")
                    if not fid or fid in ids_vistos:
                        continue
                    ids_vistos.add(fid)

                    home = f.get("teams", {}).get("home", {})
                    away = f.get("teams", {}).get("away", {})
                    league = f.get("league", {})

                    home_name = home.get("name", "")
                    away_name = away.get("name", "")
                    home_id = home.get("id")
                    away_id = away.get("id")

                    if not home_name or not away_name or not home_id or not away_id:
                        continue

                    # Prioridade da liga
                    if liga_id in LIGAS_ALTA_IDS:
                        prioridade = 1
                    elif liga_id in LIGAS_MEDIA_IDS:
                        prioridade = 2
                    else:
                        prioridade = 3

                    jogos_encontrados.append({
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
                        # Campos de stats (preenchidos depois)
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
                        # Campos de odds (preenchidos na Etapa 3)
                        "odds_txt": "",
                        "tem_odds": False,
                        "melhor_odd": 0,
                        "faixa_odd": "",
                        # Campos da IA (preenchidos na Etapa 2)
                        "ia_mercado": "",
                        "ia_confianca": 0,
                        "ia_motivo": "",
                    })
            except Exception:
                continue

    return jogos_encontrados


# ---------------------------------------------
# ENRIQUECER JOGO COM STATS REAIS
# ---------------------------------------------

def enriquecer_stats_jogo(jogo):
    """
    Busca e preenche todos os campos de stats de um jogo.
    Modifica o dict in-place e também retorna o texto formatado.
    """
    home_id = jogo.get("casa_id")
    away_id = jogo.get("fora_id")
    liga_id = jogo.get("liga_id", 71)
    temporada = datetime.now().year
    casa = jogo.get("casa", "Casa")
    fora = jogo.get("fora", "Fora")

    ctx_lines = [f"Jogo: {casa} x {fora} | Liga: {jogo.get('liga_nome','')} | {jogo.get('data','')}"]

    # -- Stats mandante --------------------------
    stats_h = _get_dict(f"teams/statistics?team={home_id}&league={liga_id}&season={temporada}")
    if not stats_h:
        stats_h = _get_dict(f"teams/statistics?team={home_id}&league={liga_id}&season={temporada-1}")

    if stats_h:
        _preencher_stats_time(jogo, stats_h, "home")
        ctx_lines.append(
            f"{casa}: Forma {jogo['forma_home']} | "
            f"Gols {jogo['gols_marcados_home']}/jogo | "
            f"Sofre {jogo['gols_sofridos_home']}/jogo | "
            f"Casa {jogo['aprov_home']}% aproveit. | "
            f"Seq: {jogo['sequencia_home']}"
        )

    # -- Stats visitante --------------------------
    stats_a = _get_dict(f"teams/statistics?team={away_id}&league={liga_id}&season={temporada}")
    if not stats_a:
        stats_a = _get_dict(f"teams/statistics?team={away_id}&league={liga_id}&season={temporada-1}")

    if stats_a:
        _preencher_stats_time(jogo, stats_a, "away")
        ctx_lines.append(
            f"{fora}: Forma {jogo['forma_away']} | "
            f"Gols {jogo['gols_marcados_away']}/jogo | "
            f"Sofre {jogo['gols_sofridos_away']}/jogo | "
            f"Fora {jogo['aprov_away']}% aproveit. | "
            f"Seq: {jogo['sequencia_away']}"
        )

    # -- H2H --------------------------------------
    h2h = _get(f"fixtures/headtohead?h2h={home_id}-{away_id}&last=5")
    if h2h:
        home_wins = sum(
            1 for j in h2h
            if j.get("teams", {}).get("home", {}).get("id") == home_id
            and (j.get("goals", {}).get("home") or 0) > (j.get("goals", {}).get("away") or 0)
        )
        jogo["h2h_home_wins"] = home_wins
        jogo["h2h_total"] = len(h2h)
        h2h_lines = []
        for j in h2h[:5]:
            dh = j.get("teams", {}).get("home", {}).get("name", "")
            da = j.get("teams", {}).get("away", {}).get("name", "")
            gh = j.get("goals", {}).get("home", 0) or 0
            ga = j.get("goals", {}).get("away", 0) or 0
            dt = j.get("fixture", {}).get("date", "")[:10]
            h2h_lines.append(f"  {dt}: {dh} {gh}x{ga} {da}")
        ctx_lines.append(f"H2H (últimos {len(h2h)}): {home_wins} vitórias do mandante")
        ctx_lines.extend(h2h_lines)

    # -- Classificação ----------------------------
    standings = _get(f"standings?league={liga_id}&season={temporada}")
    if standings:
        try:
            tabela = standings[0]["league"]["standings"][0]
            for time in tabela:
                nome = time["team"]["name"]
                tid = time["team"]["id"]
                if tid in (home_id, away_id):
                    cl = {
                        "posicao": time["rank"],
                        "pontos": time["points"],
                        "jogos": time["all"]["played"],
                        "saldo": time.get("goalsDiff", 0),
                        "forma": time.get("form", "")
                    }
                    if tid == home_id:
                        jogo["classificacao_home"] = cl
                        ctx_lines.append(
                            f"{casa} na tabela: {cl['posicao']}º | {cl['pontos']}pts | "
                            f"{cl['jogos']}J | Saldo {cl['saldo']}"
                        )
                    else:
                        jogo["classificacao_away"] = cl
                        ctx_lines.append(
                            f"{fora} na tabela: {cl['posicao']}º | {cl['pontos']}pts | "
                            f"{cl['jogos']}J | Saldo {cl['saldo']}"
                        )
        except Exception:
            pass

    stats_txt = "\n".join(ctx_lines)
    jogo["stats_txt"] = stats_txt
    return stats_txt


def _preencher_stats_time(jogo, stats, lado):
    """Preenche campos do jogo com stats de um lado (home/away)."""
    try:
        form_str = stats.get("form", "") or ""
        form = list(form_str[-5:]) if form_str else []
        vit = form.count("W")
        emp = form.count("D")
        der = form.count("L")
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

        # Sequência
        sequencia = ""
        if form:
            ultimo = form[-1]
            count = sum(1 for f in reversed(form) if f == ultimo)
            mapa = {"W": "vitória(s)", "D": "empate(s)", "L": "derrota(s)"}
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


# ---------------------------------------------
# CONTEXTO ANTIGO (compatibilidade com pre_jogo / ao_vivo)
# ---------------------------------------------

def montar_contexto_stats(jogo):
    """Compat: chamado pela alavancagem antiga. Usa enriquecer_stats_jogo."""
    return enriquecer_stats_jogo(jogo)
      
