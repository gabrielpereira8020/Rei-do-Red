"""
the_odds_api.py
===============
Integracao com The Odds API (https://the-odds-api.com)

Como usar no secrets.toml:
  THE_ODDS_API_KEY = "sua_chave_aqui"
"""

import requests
import unicodedata
from datetime import datetime

BASE_URL = "https://api.the-odds-api.com/v4"
REGIOES  = "eu,us,uk,au"
MERCADOS = "h2h,totals"

# -------------------------------------------
# MAPEAMENTO COMPLETO: liga_id → sport_key
# Todas as ligas do stats_engine_alav.py
# -------------------------------------------
LIGA_PARA_SPORT_KEY = {
    # ── BRASIL ──────────────────────────────
    71:  "soccer_brazil_campeonato",
    72:  "soccer_brazil_serie_b",
    73:  "soccer_brazil_serie_c",
    76:  "soccer_brazil_serie_d",

    # ── INGLATERRA ──────────────────────────
    39:  "soccer_epl",
    40:  "soccer_england_championship",
    41:  "soccer_england_league1",
    42:  "soccer_england_league2",

    # ── ESPANHA ─────────────────────────────
    140: "soccer_spain_la_liga",
    141: "soccer_spain_segunda_division",

    # ── ITALIA ──────────────────────────────
    135: "soccer_italy_serie_a",
    136: "soccer_italy_serie_b",

    # ── ALEMANHA ────────────────────────────
    78:  "soccer_germany_bundesliga",
    79:  "soccer_germany_bundesliga2",

    # ── FRANCA ──────────────────────────────
    61:  "soccer_france_ligue_one",
    62:  "soccer_france_ligue_two",

    # ── PORTUGAL ────────────────────────────
    94:  "soccer_portugal_primeira_liga",
    95:  "soccer_portugal_segunda_liga",

    # ── HOLANDA ─────────────────────────────
    88:  "soccer_netherlands_eredivisie",

    # ── BELGICA ─────────────────────────────
    144: "soccer_belgium_first_div",

    # ── TURQUIA ─────────────────────────────
    203: "soccer_turkey_super_league",

    # ── ESCOCIA ─────────────────────────────
    179: "soccer_scotland_premiership",

    # ── SUICA ───────────────────────────────
    207: "soccer_switzerland_superleague",

    # ── ESCANDINAVIA ────────────────────────
    103: "soccer_norway_eliteserien",
    113: "soccer_sweden_allsvenskan",
    119: "soccer_denmark_superliga",
    104: "soccer_denmark_1st_division",

    # ── AMERICAS ────────────────────────────
    128: "soccer_argentina_primera_division",
    129: "soccer_argentina_nacional_b",
    130: "soccer_argentina_copa",
    131: "soccer_argentina_primera_b",
    132: "soccer_argentina_primera_c",
    262: "soccer_mexico_ligamx",
    253: "soccer_usa_mls",
    254: "soccer_usa_usl_championship",
    909: "soccer_usa_mls_next_pro",
    266: "soccer_chile_primera_division",
    268: "soccer_colombia_primera_a",
    269: "soccer_colombia_primera_b",
    299: "soccer_peru_primera_division",
    300: "soccer_venezuela_primera_pro",

    # ── ASIA ────────────────────────────────
    98:  "soccer_japan_j_league",
    99:  "soccer_japan_j_league",
    291: "soccer_korea_kleague1",
    293: "soccer_korea_kleague2",
    307: "soccer_saudi_arabia_yelo",
    340: "soccer_vietnam_v_league_1",
    542: "soccer_iraq_super_league",

    # ── AFRICA ──────────────────────────────
    200: "soccer_morocco_botola_pro",
    201: "soccer_morocco_botola_pro",
    411: "soccer_cameroon_elite_one",

    # ── EUROPA OUTRAS ───────────────────────
    117: "soccer_finland_veikkausliiga",
    277: "soccer_greece_super_league",
    316: "soccer_bosnia_premier_league",
    223: "soccer_germany_liga3",

    # ── COMPETICOES INTERNACIONAIS ──────────
    1:   "soccer_fifa_world_cup",
    2:   "soccer_uefa_champs_league",
    3:   "soccer_uefa_europa_league",
    848: "soccer_uefa_europa_conference_league",
    13:  "soccer_conmebol_libertadores",
    11:  "soccer_conmebol_sudamericana",
    15:  "soccer_fifa_world_cup",
    16:  "soccer_concacaf_champions_cup",
    17:  "soccer_afc_champions_league",
    12:  "soccer_caf_champions_league",

    # ── AMISTOSOS ───────────────────────────
    9:   "soccer_international",
    10:  "soccer_international",
    667: "soccer_international_clubs",
    914: "soccer_international",
}


# -------------------------------------------
# BUSCA PRINCIPAL
# -------------------------------------------

def buscar_odds_jogo(home, away, liga_id, api_key, odd_min=1.10, odd_max=2.50):
    """
    Busca odds de um jogo na The Odds API.
    Tenta o sport_key da liga primeiro, depois fallback generico.
    """
    if not api_key:
        return None

    sport_key = LIGA_PARA_SPORT_KEY.get(liga_id, "soccer_international")
    sport_keys_tentar = list(dict.fromkeys([sport_key, "soccer_international"]))

    for sk in sport_keys_tentar:
        try:
            r = requests.get(
                f"{BASE_URL}/sports/{sk}/odds",
                params={
                    "apiKey":      api_key,
                    "regions":     REGIOES,
                    "markets":     MERCADOS,
                    "oddsFormat":  "decimal",
                    "dateFormat":  "iso",
                },
                timeout=15
            )
            if r.status_code not in (200, 422):
                continue
            if r.status_code == 422:
                continue

            jogos = r.json()
            if not jogos:
                continue

            jogo_match = _encontrar_jogo(jogos, home, away)
            if jogo_match:
                return _extrair_odds(jogo_match, odd_min, odd_max)

        except Exception:
            continue

    return None


def buscar_todos_jogos_odds(api_key, ligas_ids=None):
    """
    Busca jogos com odds em lote por sport_key unico.
    Retorna dict {(home_norm, away_norm): jogo_dict}
    """
    if not api_key:
        return {}

    if ligas_ids is None:
        ligas_ids = list(LIGA_PARA_SPORT_KEY.keys())

    sport_keys = list(dict.fromkeys(
        LIGA_PARA_SPORT_KEY[lid]
        for lid in ligas_ids
        if lid in LIGA_PARA_SPORT_KEY
    ))

    todos = {}
    for sk in sport_keys:
        try:
            r = requests.get(
                f"{BASE_URL}/sports/{sk}/odds",
                params={
                    "apiKey":     api_key,
                    "regions":    REGIOES,
                    "markets":    MERCADOS,
                    "oddsFormat": "decimal",
                    "dateFormat": "iso",
                },
                timeout=15
            )
            if r.status_code != 200:
                continue
            for jogo in r.json():
                h = _norm(jogo.get("home_team", ""))
                a = _norm(jogo.get("away_team", ""))
                if h and a:
                    todos[(h, a)] = jogo
        except Exception:
            continue

    return todos


def extrair_melhor_odd_mercado(odds_dict, mercado_ia, odd_min, odd_max):
    """
    Extrai a odd correta para o mercado sugerido pela IA.
    Retorna (odd_valor, bookmaker) ou (None, None).
    """
    if not odds_dict:
        return None, None

    mercado_lower = mercado_ia.lower().strip()
    home_team = _norm(odds_dict.get("home_team", ""))
    away_team = _norm(odds_dict.get("away_team", ""))

    melhor_odd = None
    melhor_bm  = None

    for bm in odds_dict.get("bookmakers", []):
        for market in bm.get("markets", []):
            key      = market.get("key", "")
            outcomes = market.get("outcomes", [])
            odd_val  = None

            # Over / Under
            if "over" in mercado_lower or "under" in mercado_lower:
                if key == "totals":
                    direcao = "over" if "over" in mercado_lower else "under"
                    ponto   = _extrair_numero(mercado_lower)
                    for o in outcomes:
                        if (o.get("name","").lower() == direcao
                                and o.get("point") == ponto):
                            odd_val = float(o.get("price", 0))

            # Vitoria mandante
            elif "vitoria mandante" in mercado_lower or "home win" in mercado_lower:
                if key == "h2h":
                    for o in outcomes:
                        if _norm(o.get("name","")) == home_team:
                            odd_val = float(o.get("price", 0))

            # Vitoria visitante
            elif "vitoria visitante" in mercado_lower:
                if key == "h2h":
                    for o in outcomes:
                        if _norm(o.get("name","")) == away_team:
                            odd_val = float(o.get("price", 0))

            # Double Chance 1X
            elif "1x" in mercado_lower or "double chance 1" in mercado_lower:
                if key == "h2h":
                    # melhor odd entre home e draw
                    odds_hd = []
                    for o in outcomes:
                        n = _norm(o.get("name",""))
                        if n == home_team or n == "draw":
                            odds_hd.append(float(o.get("price", 0)))
                    if odds_hd:
                        odd_val = min(odds_hd)

            # Double Chance X2
            elif "x2" in mercado_lower or "double chance x" in mercado_lower:
                if key == "h2h":
                    odds_ad = []
                    for o in outcomes:
                        n = _norm(o.get("name",""))
                        if n == away_team or n == "draw":
                            odds_ad.append(float(o.get("price", 0)))
                    if odds_ad:
                        odd_val = min(odds_ad)

            # Ambos marcam
            elif "ambos" in mercado_lower or "btts" in mercado_lower:
                if key == "btts":
                    for o in outcomes:
                        if o.get("name","").lower() == "yes":
                            odd_val = float(o.get("price", 0))

            # Fallback: melhor h2h na faixa
            else:
                if key == "h2h":
                    for o in outcomes:
                        v = float(o.get("price", 0))
                        if odd_min <= v <= odd_max:
                            odd_val = v

            if odd_val and odd_min <= odd_val <= odd_max:
                if melhor_odd is None or odd_val < melhor_odd:
                    melhor_odd = odd_val
                    melhor_bm  = bm.get("title", "")

    return melhor_odd, melhor_bm


def montar_texto_odds(odds_dict, mercado_ia=""):
    """Texto resumido das odds para passar à IA."""
    if not odds_dict:
        return ""
    linhas = [f"Odds: {odds_dict.get('home_team')} x {odds_dict.get('away_team')}"]
    for bm in odds_dict.get("bookmakers", [])[:2]:
        for market in bm.get("markets", []):
            for o in market.get("outcomes", []):
                pt = f" {o['point']}" if o.get("point") else ""
                linhas.append(f"  {bm['title']} | {o['name']}{pt} @ {o['price']}")
    return "\n".join(linhas)


def verificar_cota_restante(api_key):
    """Retorna requests restantes e usadas do plano."""
    try:
        r = requests.get(
            f"{BASE_URL}/sports",
            params={"apiKey": api_key},
            timeout=10
        )
        return {
            "restantes": r.headers.get("x-requests-remaining", "?"),
            "usadas":    r.headers.get("x-requests-used", "?"),
        }
    except Exception:
        return {"restantes": "?", "usadas": "?"}


# -------------------------------------------
# HELPERS
# -------------------------------------------

def _norm(nome):
    nome = str(nome).lower().strip()
    nome = "".join(
        c for c in unicodedata.normalize("NFD", nome)
        if unicodedata.category(c) != "Mn"
    )
    for suf in [" fc"," cf"," sc"," ac"," sk"," fk"," bk"," if"," ff",
                " united"," city"," athletic"," atletico"," sporting"]:
        nome = nome.replace(suf, "")
    return nome.strip()


def _encontrar_jogo(jogos, home, away):
    home_n = _norm(home)
    away_n = _norm(away)
    melhor, melhor_sc = None, 0
    for jogo in jogos:
        jh = _norm(jogo.get("home_team", ""))
        ja = _norm(jogo.get("away_team", ""))
        sc = 0
        if home_n == jh or home_n in jh or jh in home_n: sc += 2
        elif set(home_n.split()) & set(jh.split()):        sc += 1
        if away_n == ja or away_n in ja or ja in away_n:  sc += 2
        elif set(away_n.split()) & set(ja.split()):        sc += 1
        if sc > melhor_sc and sc >= 2:
            melhor_sc, melhor = sc, jogo
    return melhor


def _extrair_odds(jogo, odd_min, odd_max):
    return {
        "home_team":      jogo.get("home_team"),
        "away_team":      jogo.get("away_team"),
        "commence_time":  jogo.get("commence_time"),
        "bookmakers":     jogo.get("bookmakers", []),
        "odd_min":        odd_min,
        "odd_max":        odd_max,
    }


def _extrair_numero(texto):
    """Extrai numero float de string como 'over 1.5 ft' → 1.5"""
    import re
    m = re.search(r"(\d+\.?\d*)", texto)
    return float(m.group(1)) if m else 1.5
      
