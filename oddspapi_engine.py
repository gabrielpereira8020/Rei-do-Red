"""
oddspapi_engine.py
==================
Integracao com OddsPapi (https://oddspapi.com)

Vantagens:
  - 350+ bookmakers (incluindo Pinnacle)
  - 460+ mercados
  - 1 request retorna tudo de uma vez
  - 1.000 requests/mes gratis

Como usar no secrets.toml:
  ODDSPAPI_KEY = "sua_chave_aqui"

Documentacao: https://oddspapi.com/docs
"""

import requests
import unicodedata
import re
from datetime import datetime

BASE_URL = "https://api.oddspapi.com"

# -------------------------------------------
# MAPEAMENTO: liga_id API Football → sport/league OddsPapi
# -------------------------------------------
LIGA_PARA_ODDSPAPI = {
    # BRASIL
    71:  {"sport": "football", "league": "brazil_serie_a"},
    72:  {"sport": "football", "league": "brazil_serie_b"},
    73:  {"sport": "football", "league": "brazil_serie_c"},

    # INGLATERRA
    39:  {"sport": "football", "league": "england_premier_league"},
    40:  {"sport": "football", "league": "england_championship"},
    41:  {"sport": "football", "league": "england_league_one"},
    42:  {"sport": "football", "league": "england_league_two"},

    # ESPANHA
    140: {"sport": "football", "league": "spain_la_liga"},
    141: {"sport": "football", "league": "spain_segunda_division"},

    # ITALIA
    135: {"sport": "football", "league": "italy_serie_a"},
    136: {"sport": "football", "league": "italy_serie_b"},

    # ALEMANHA
    78:  {"sport": "football", "league": "germany_bundesliga"},
    79:  {"sport": "football", "league": "germany_2_bundesliga"},

    # FRANCA
    61:  {"sport": "football", "league": "france_ligue_1"},
    62:  {"sport": "football", "league": "france_ligue_2"},

    # PORTUGAL
    94:  {"sport": "football", "league": "portugal_primeira_liga"},
    95:  {"sport": "football", "league": "portugal_segunda_liga"},

    # HOLANDA
    88:  {"sport": "football", "league": "netherlands_eredivisie"},

    # BELGICA
    144: {"sport": "football", "league": "belgium_first_division_a"},

    # TURQUIA
    203: {"sport": "football", "league": "turkey_super_lig"},

    # ESCOCIA
    179: {"sport": "football", "league": "scotland_premiership"},

    # SUICA
    207: {"sport": "football", "league": "switzerland_super_league"},

    # ESCANDINAVIA
    103: {"sport": "football", "league": "norway_eliteserien"},
    113: {"sport": "football", "league": "sweden_allsvenskan"},
    119: {"sport": "football", "league": "denmark_superliga"},

    # AMERICAS
    128: {"sport": "football", "league": "argentina_primera_division"},
    129: {"sport": "football", "league": "argentina_primera_nacional"},
    262: {"sport": "football", "league": "mexico_liga_mx"},
    253: {"sport": "football", "league": "usa_mls"},
    254: {"sport": "football", "league": "usa_usl_championship"},
    266: {"sport": "football", "league": "chile_primera_division"},
    268: {"sport": "football", "league": "colombia_primera_a"},
    299: {"sport": "football", "league": "peru_primera_division"},

    # ASIA
    98:  {"sport": "football", "league": "japan_j1_league"},
    99:  {"sport": "football", "league": "japan_j2_league"},
    291: {"sport": "football", "league": "south_korea_k_league_1"},
    293: {"sport": "football", "league": "south_korea_k_league_2"},
    307: {"sport": "football", "league": "saudi_arabia_pro_league"},

    # COMPETICOES INTERNACIONAIS
    2:   {"sport": "football", "league": "uefa_champions_league"},
    3:   {"sport": "football", "league": "uefa_europa_league"},
    848: {"sport": "football", "league": "uefa_conference_league"},
    13:  {"sport": "football", "league": "conmebol_libertadores"},
    11:  {"sport": "football", "league": "conmebol_sudamericana"},
    1:   {"sport": "football", "league": "fifa_world_cup"},
    15:  {"sport": "football", "league": "fifa_club_world_cup"},
    16:  {"sport": "football", "league": "concacaf_champions_cup"},

    # AMISTOSOS
    9:   {"sport": "football", "league": "international_friendlies"},
    10:  {"sport": "football", "league": "international_friendlies"},
    667: {"sport": "football", "league": "club_friendlies"},
}

# Mercados suportados pelo OddsPapi
MERCADOS_ODDSPAPI = {
    "vitoria mandante":  "1x2",
    "vitoria visitante": "1x2",
    "empate":            "1x2",
    "double chance 1x":  "double_chance",
    "double chance x2":  "double_chance",
    "over 0.5 ht":       "totals",
    "over 1.5 ft":       "totals",
    "over 2.5 ft":       "totals",
    "over 3.5 ft":       "totals",
    "under 4.5 ft":      "totals",
    "ambos marcam sim":  "btts",
    "ambos marcam nao":  "btts",
}


# -------------------------------------------
# BUSCA PRINCIPAL
# -------------------------------------------

def buscar_odds_jogo(home, away, liga_id, api_key, odd_min=1.10, odd_max=2.50):
    """
    Busca odds de um jogo especifico no OddsPapi.
    Retorna dict com odds ou None se nao encontrar.
    """
    if not api_key:
        return None

    config = LIGA_PARA_ODDSPAPI.get(liga_id)
    sport  = config["sport"]  if config else "football"
    league = config["league"] if config else None

    try:
        params = {
            "apiKey": api_key,
            "sport":  sport,
        }
        if league:
            params["league"] = league

        r = requests.get(
            f"{BASE_URL}/odds",
            params=params,
            timeout=15
        )

        if r.status_code != 200:
            return None

        data  = r.json()
        jogos = data.get("data", data) if isinstance(data, dict) else data

        if not isinstance(jogos, list):
            return None

        jogo_match = _encontrar_jogo(jogos, home, away)
        if not jogo_match:
            return None

        return jogo_match

    except Exception:
        return None


def buscar_odds_em_lote(api_key, liga_id):
    """
    Busca TODOS os jogos de uma liga de uma vez.
    1 request = todos os jogos da liga. Muito economico.
    Retorna lista de jogos com odds.
    """
    if not api_key:
        return []

    config = LIGA_PARA_ODDSPAPI.get(liga_id)
    sport  = config["sport"]  if config else "football"
    league = config["league"] if config else None

    try:
        params = {"apiKey": api_key, "sport": sport}
        if league:
            params["league"] = league

        r = requests.get(f"{BASE_URL}/odds", params=params, timeout=15)
        if r.status_code != 200:
            return []

        data = r.json()
        return data.get("data", data) if isinstance(data, dict) else data

    except Exception:
        return []


def extrair_melhor_odd(jogo_dict, mercado_ia, odd_min, odd_max):
    """
    Extrai a melhor odd para o mercado sugerido pela IA.
    Retorna (odd_valor, bookmaker, mercado_txt) ou (None, None, None).
    """
    if not jogo_dict:
        return None, None, None

    mercado_lower = mercado_ia.lower().strip()
    home_n = _norm(jogo_dict.get("home_team", jogo_dict.get("home", "")))
    away_n = _norm(jogo_dict.get("away_team", jogo_dict.get("away", "")))

    melhor_odd = None
    melhor_bm  = None
    melhor_txt = None

    # Bookmakers podem estar em varios formatos
    bookmakers = (
        jogo_dict.get("bookmakers", []) or
        jogo_dict.get("odds", []) or
        []
    )

    for bm in bookmakers:
        bm_nome  = bm.get("name", bm.get("title", bm.get("bookmaker", "")))
        mercados = bm.get("markets", bm.get("odds", []))

        for market in mercados:
            market_key = market.get("key", market.get("market", market.get("name", ""))).lower()
            outcomes   = market.get("outcomes", market.get("selections", []))

            odd_val = None
            odd_txt = ""

            # --- Over / Under ---
            if "over" in mercado_lower or "under" in mercado_lower:
                direcao = "over" if "over" in mercado_lower else "under"
                ponto   = _extrair_numero(mercado_lower)
                if "total" in market_key or "goal" in market_key or "over" in market_key:
                    for o in outcomes:
                        nome_o = str(o.get("name", o.get("label", ""))).lower()
                        pt     = o.get("point", o.get("handicap", o.get("line", None)))
                        preco  = _preco(o)
                        if direcao in nome_o and (pt is None or float(pt) == ponto):
                            odd_val = preco
                            odd_txt = f"Over {ponto}"

            # --- Vitoria mandante ---
            elif "vitoria mandante" in mercado_lower or "home" in mercado_lower:
                if "1x2" in market_key or "match" in market_key or "winner" in market_key:
                    for o in outcomes:
                        nome_o = _norm(str(o.get("name", o.get("label", ""))))
                        preco  = _preco(o)
                        if nome_o == home_n or nome_o in ("1", "home"):
                            odd_val = preco
                            odd_txt = "Vitoria Mandante"

            # --- Vitoria visitante ---
            elif "vitoria visitante" in mercado_lower:
                if "1x2" in market_key or "match" in market_key or "winner" in market_key:
                    for o in outcomes:
                        nome_o = _norm(str(o.get("name", o.get("label", ""))))
                        preco  = _preco(o)
                        if nome_o == away_n or nome_o in ("2", "away"):
                            odd_val = preco
                            odd_txt = "Vitoria Visitante"

            # --- Double Chance 1X ---
            elif "1x" in mercado_lower:
                if "double" in market_key or "chance" in market_key or "dc" in market_key:
                    for o in outcomes:
                        nome_o = str(o.get("name", o.get("label", ""))).upper()
                        if "1X" in nome_o or "HOME OR DRAW" in nome_o:
                            odd_val = _preco(o)
                            odd_txt = "Double Chance 1X"

            # --- Double Chance X2 ---
            elif "x2" in mercado_lower:
                if "double" in market_key or "chance" in market_key or "dc" in market_key:
                    for o in outcomes:
                        nome_o = str(o.get("name", o.get("label", ""))).upper()
                        if "X2" in nome_o or "DRAW OR AWAY" in nome_o:
                            odd_val = _preco(o)
                            odd_txt = "Double Chance X2"

            # --- Ambos Marcam ---
            elif "ambos" in mercado_lower or "btts" in mercado_lower:
                if "btts" in market_key or "both" in market_key or "score" in market_key:
                    for o in outcomes:
                        nome_o = str(o.get("name", o.get("label", ""))).lower()
                        if "yes" in nome_o or "sim" in nome_o:
                            odd_val = _preco(o)
                            odd_txt = "Ambos Marcam Sim"

            # Valida se a odd esta na faixa
            if odd_val and odd_min <= odd_val <= odd_max:
                if melhor_odd is None or odd_val < melhor_odd:
                    melhor_odd = odd_val
                    melhor_bm  = bm_nome
                    melhor_txt = odd_txt

    return melhor_odd, melhor_bm, melhor_txt


def montar_texto_odds(jogo_dict):
    """Formata odds para enviar ao contexto da IA."""
    if not jogo_dict:
        return ""
    home = jogo_dict.get("home_team", jogo_dict.get("home", "Casa"))
    away = jogo_dict.get("away_team", jogo_dict.get("away", "Fora"))
    linhas = [f"Odds disponiveis: {home} x {away}"]
    for bm in jogo_dict.get("bookmakers", [])[:2]:
        nome = bm.get("name", bm.get("title", ""))
        for market in bm.get("markets", [])[:3]:
            for o in market.get("outcomes", [])[:4]:
                label = o.get("name", o.get("label", ""))
                preco = _preco(o)
                pt    = o.get("point", "")
                pt_txt = f" {pt}" if pt else ""
                linhas.append(f"  {nome} | {label}{pt_txt} @ {preco}")
    return "\n".join(linhas)


def verificar_cota(api_key):
    """Verifica cota restante da API."""
    try:
        r = requests.get(
            f"{BASE_URL}/sports",
            params={"apiKey": api_key},
            timeout=10
        )
        headers = r.headers
        return {
            "restantes": headers.get("x-requests-remaining", "?"),
            "usadas":    headers.get("x-requests-used", "?"),
            "limite":    headers.get("x-requests-limit", "?"),
        }
    except Exception:
        return {"restantes": "?", "usadas": "?", "limite": "?"}


# -------------------------------------------
# HELPERS
# -------------------------------------------

def _norm(nome):
    """Normaliza nome de time para comparacao."""
    nome = str(nome).lower().strip()
    nome = "".join(
        c for c in unicodedata.normalize("NFD", nome)
        if unicodedata.category(c) != "Mn"
    )
    for suf in [" fc"," cf"," sc"," ac"," sk"," fk"," bk"," if"," ff",
                " united"," city"," athletic"," atletico"," sporting"," club"]:
        nome = nome.replace(suf, "")
    return nome.strip()


def _encontrar_jogo(jogos, home, away):
    """Fuzzy match para encontrar o jogo na lista."""
    home_n = _norm(home)
    away_n = _norm(away)
    melhor, melhor_sc = None, 0

    for jogo in jogos:
        jh = _norm(jogo.get("home_team", jogo.get("home", "")))
        ja = _norm(jogo.get("away_team", jogo.get("away", "")))

        sc = 0
        if home_n == jh or home_n in jh or jh in home_n: sc += 2
        elif set(home_n.split()) & set(jh.split()):        sc += 1
        if away_n == ja or away_n in ja or ja in away_n:  sc += 2
        elif set(away_n.split()) & set(ja.split()):        sc += 1

        if sc > melhor_sc and sc >= 2:
            melhor_sc, melhor = sc, jogo

    return melhor


def _preco(outcome):
    """Extrai preco/odd de um outcome em varios formatos."""
    for campo in ("price", "odd", "odds", "value", "decimal"):
        v = outcome.get(campo)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    return 0.0


def _extrair_numero(texto):
    """Extrai numero float de string como 'over 1.5 ft' -> 1.5"""
    m = re.search(r"(\d+\.?\d*)", texto)
    return float(m.group(1)) if m else 1.5

