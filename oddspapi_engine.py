"""
oddspapi_engine.py
==================
Integração com OddsPapi (https://oddspapi.io)
350+ bookmakers | 460+ mercados | Pinnacle incluso

Plano gratuito: 250 requests/mês
1 request = retorna todos os bookmakers de uma vez

MERCADOS MAPEADOS (market IDs):
  101 — Full Time Result (1x2)
  104 — Both Teams To Score (Ambos marcam)
  106 — Over/Under Full Time
  109 — Double Chance
  (mais mercados carregados dinamicamente)

secrets.toml:
  ODDSPAPI_KEY = "sua_chave_aqui"
"""

import requests
import unicodedata
import re
from datetime import datetime, timezone

BASE_URL = "https://api.oddspapi.io/v4"
SPORT_ID = 10  # Futebol

# ─────────────────────────────────────────────
# IDs de mercado fixos (documentação OddsPapi)
# ─────────────────────────────────────────────
MARKET_FULL_TIME_RESULT  = 101   # 1x2: outcome 101=home, 102=draw, 103=away
MARKET_BTTS              = 104   # Ambos marcam: 104=Yes, 105=No
MARKET_OVER_UNDER        = 106   # Over/Under FT (vários handicaps)
MARKET_DOUBLE_CHANCE     = 109   # Double Chance: 1X, 12, X2

# Bookmaker preferido (Pinnacle = melhor cobertura)
BOOKMAKER_PRINCIPAL = "pinnacle"
BOOKMAKER_FALLBACK  = "unibet"

# ─────────────────────────────────────────────
# MAPEAMENTO liga_id (API Football) → tournament_id (OddsPapi)
# Busca dinâmica caso não encontre aqui
# ─────────────────────────────────────────────
LIGA_PARA_TOURNAMENT = {
    # ── BRASIL ──────────────────────────────
    71:  None,   # Brasileirão Série A  (busca por nome)
    72:  None,   # Brasileirão Série B
    73:  None,   # Brasileirão Série C
    # ── INTERNACIONAIS ──────────────────────
    1:   None,   # FIFA World Cup
    2:   None,   # UEFA Champions League
    3:   None,   # UEFA Europa League
    9:   None,   # Amistosos internacionais
    10:  None,   # Amistosos internacionais
    13:  None,   # Libertadores
    11:  None,   # Sudamericana
    # ── LIGAS TOP ───────────────────────────
    39:  None,   # Premier League
    78:  None,   # Bundesliga
    135: None,   # Serie A
    140: None,   # La Liga
    61:  None,   # Ligue 1
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _norm(nome):
    """Normaliza nome de time: minúsculo, sem acento, sem sufixos."""
    nome = str(nome).lower().strip()
    nome = "".join(
        c for c in unicodedata.normalize("NFD", nome)
        if unicodedata.category(c) != "Mn"
    )
    for suf in [" fc", " cf", " sc", " ac", " sk", " fk", " bk",
                " united", " city", " athletic", " atletico", " sporting"]:
        nome = nome.replace(suf, "")
    return nome.strip()


def _score_match(home_api, away_api, home_ev, away_ev):
    """Pontuação de similaridade entre dois pares de nomes."""
    h1, h2 = _norm(home_api), _norm(home_ev)
    a1, a2 = _norm(away_api), _norm(away_ev)
    sc = 0
    if h1 == h2 or h1 in h2 or h2 in h1: sc += 2
    elif set(h1.split()) & set(h2.split()): sc += 1
    if a1 == a2 or a1 in a2 or a2 in a1: sc += 2
    elif set(a1.split()) & set(a2.split()): sc += 1
    return sc


def _extrair_preco(bookmaker_odds, market_id, outcome_id, handicap=None):
    """
    Extrai preço de um mercado/outcome específico.
    bookmaker_odds = dados de um bookmaker dentro de fixture['bookmakerOdds']
    """
    try:
        market = bookmaker_odds.get("markets", {}).get(str(market_id), {})
        outcome = market.get("outcomes", {}).get(str(outcome_id), {})
        players = outcome.get("players", {})
        if not players:
            return None
        # Pega o primeiro player ativo
        for p in players.values():
            if p.get("active", True):
                price = p.get("price")
                if price and float(price) > 1.0:
                    return float(price)
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────
# BUSCA DE TORNEIOS (cache simples em memória)
# ─────────────────────────────────────────────
_cache_torneios = None

def _get_torneios(api_key):
    global _cache_torneios
    if _cache_torneios is not None:
        return _cache_torneios
    try:
        r = requests.get(
            f"{BASE_URL}/tournaments",
            params={"apiKey": api_key, "sportId": SPORT_ID},
            timeout=15
        )
        if r.status_code == 200:
            _cache_torneios = r.json()
            return _cache_torneios
    except Exception:
        pass
    return []


def _encontrar_tournament_id(liga_nome, api_key):
    """Busca tournament_id pelo nome da liga."""
    torneios = _get_torneios(api_key)
    liga_n = _norm(liga_nome)
    melhor, melhor_sc = None, 0
    for t in torneios:
        nome_t = _norm(t.get("tournamentName", ""))
        cat_t  = _norm(t.get("categoryName", ""))
        sc = 0
        if liga_n == nome_t or liga_n in nome_t or nome_t in liga_n:
            sc += 2
        elif set(liga_n.split()) & set(nome_t.split()):
            sc += 1
        if sc > melhor_sc:
            melhor_sc = sc
            melhor = t.get("tournamentId")
    return melhor if melhor_sc >= 1 else None


# ─────────────────────────────────────────────
# BUSCA PRINCIPAL — por nome do jogo
# ─────────────────────────────────────────────

def buscar_odds_jogo(home, away, liga_id, liga_nome, api_key, odd_min=1.10, odd_max=2.50):
    """
    Busca odds de um jogo específico na OddsPapi.

    Fluxo:
      1. Descobre tournament_id pelo liga_id ou nome da liga
      2. Busca fixtures desse torneio com odds do Pinnacle
      3. Casa o jogo pelo nome (fuzzy match)
      4. Extrai todos os mercados relevantes

    Retorna dict com odds formatadas ou None se não encontrar.
    """
    if not api_key:
        return None

    # Descobre tournament_id
    tournament_id = LIGA_PARA_TOURNAMENT.get(liga_id)
    if not tournament_id and liga_nome:
        tournament_id = _encontrar_tournament_id(liga_nome, api_key)
    if not tournament_id:
        return None

    # Tenta Pinnacle primeiro, depois fallback
    for bookmaker in [BOOKMAKER_PRINCIPAL, BOOKMAKER_FALLBACK]:
        try:
            r = requests.get(
                f"{BASE_URL}/odds-by-tournaments",
                params={
                    "apiKey": api_key,
                    "bookmaker": bookmaker,
                    "tournamentIds": str(tournament_id),
                    "oddsFormat": "decimal",
                },
                timeout=15
            )
            if r.status_code != 200:
                continue

            fixtures = r.json()
            if not isinstance(fixtures, list):
                continue

            # Casa o jogo pelo nome dos participantes
            melhor_fixture = None
            melhor_sc = 0

            for fix in fixtures:
                # OddsPapi usa participant IDs, precisa buscar nomes
                p1 = str(fix.get("participant1Id", ""))
                p2 = str(fix.get("participant2Id", ""))
                # Tenta pelo campo nome se disponível
                nome1 = fix.get("participant1Name", fix.get("home", ""))
                nome2 = fix.get("participant2Name", fix.get("away", ""))

                if not nome1 or not nome2:
                    continue

                sc = _score_match(home, away, nome1, nome2)
                if sc > melhor_sc and sc >= 2:
                    melhor_sc = sc
                    melhor_fixture = fix

            if melhor_fixture:
                return _processar_fixture(melhor_fixture, bookmaker, odd_min, odd_max, home, away)

        except Exception:
            continue

    return None


# ─────────────────────────────────────────────
# BUSCA EM LOTE — para múltiplos jogos de uma vez
# ─────────────────────────────────────────────

def buscar_odds_lote(jogos_aprovados, api_key, odd_min=1.10, odd_max=2.50):
    """
    Busca odds de vários jogos com o mínimo de requests.

    Estratégia:
      - Agrupa jogos por tournament_id
      - 1 request por torneio (economiza cota)
      - Casa cada jogo no resultado

    Retorna dict {nome_jogo: odds_dict}
    """
    if not api_key or not jogos_aprovados:
        return {}

    # Monta mapa tournament_id → lista de jogos
    torneios_map = {}
    jogos_sem_torneio = []

    for jogo in jogos_aprovados:
        liga_id   = jogo.get("liga_id", 0)
        liga_nome = jogo.get("liga_nome", "")
        tid = LIGA_PARA_TOURNAMENT.get(liga_id)
        if not tid and liga_nome:
            tid = _encontrar_tournament_id(liga_nome, api_key)
        if tid:
            torneios_map.setdefault(tid, []).append(jogo)
        else:
            jogos_sem_torneio.append(jogo)

    resultado = {}

    # Busca por torneio (1 request por torneio)
    for tid, jogos_do_torneio in torneios_map.items():
        for bookmaker in [BOOKMAKER_PRINCIPAL, BOOKMAKER_FALLBACK]:
            try:
                r = requests.get(
                    f"{BASE_URL}/odds-by-tournaments",
                    params={
                        "apiKey": api_key,
                        "bookmaker": bookmaker,
                        "tournamentIds": str(tid),
                        "oddsFormat": "decimal",
                    },
                    timeout=15
                )
                if r.status_code != 200:
                    continue

                fixtures = r.json()
                if not isinstance(fixtures, list):
                    continue

                # Casa cada jogo aprovado com os fixtures retornados
                for jogo in jogos_do_torneio:
                    if jogo["nome"] in resultado:
                        continue  # já encontrou

                    melhor_fix, melhor_sc = None, 0
                    for fix in fixtures:
                        nome1 = fix.get("participant1Name", fix.get("home", ""))
                        nome2 = fix.get("participant2Name", fix.get("away", ""))
                        if not nome1 or not nome2:
                            continue
                        sc = _score_match(jogo.get("casa",""), jogo.get("fora",""), nome1, nome2)
                        if sc > melhor_sc and sc >= 2:
                            melhor_sc = sc
                            melhor_fix = fix

                    if melhor_fix:
                        odds = _processar_fixture(
                            melhor_fix, bookmaker, odd_min, odd_max,
                            jogo.get("casa",""), jogo.get("fora","")
                        )
                        if odds:
                            resultado[jogo["nome"]] = odds

                break  # se Pinnacle funcionou, não precisa tentar Unibet

            except Exception:
                continue

    return resultado


# ─────────────────────────────────────────────
# PROCESSAMENTO DE FIXTURE
# ─────────────────────────────────────────────

def _processar_fixture(fixture, bookmaker, odd_min, odd_max, home_orig, away_orig):
    """
    Extrai todos os mercados relevantes de um fixture e retorna dict formatado.
    """
    bm_odds = fixture.get("bookmakerOdds", {}).get(bookmaker, {})
    if not bm_odds:
        return None

    markets = bm_odds.get("markets", {})
    if not markets:
        return None

    nome1 = fixture.get("participant1Name", home_orig)
    nome2 = fixture.get("participant2Name", away_orig)

    resultado = {
        "home":       nome1,
        "away":       nome2,
        "bookmaker":  bookmaker,
        "fixture_id": fixture.get("fixtureId", ""),
        "mercados":   {},
        "odds_txt":   "",
    }

    linhas = [f"Odds [{bookmaker}]: {nome1} x {nome2}"]

    # ── 1x2 (Full Time Result) ──────────────
    home_price = _extrair_preco(bm_odds, MARKET_FULL_TIME_RESULT, 101)
    draw_price = _extrair_preco(bm_odds, MARKET_FULL_TIME_RESULT, 102)
    away_price = _extrair_preco(bm_odds, MARKET_FULL_TIME_RESULT, 103)

    if home_price:
        resultado["mercados"]["vitoria_mandante"] = home_price
        linhas.append(f"  1x2: Mandante@{home_price} | Empate@{draw_price} | Visitante@{away_price}")

    # ── Double Chance ───────────────────────
    dc_1x = _extrair_preco(bm_odds, MARKET_DOUBLE_CHANCE, 110)   # 1X
    dc_12 = _extrair_preco(bm_odds, MARKET_DOUBLE_CHANCE, 111)   # 12
    dc_x2 = _extrair_preco(bm_odds, MARKET_DOUBLE_CHANCE, 112)   # X2

    if dc_1x:
        resultado["mercados"]["double_chance_1x"] = dc_1x
        resultado["mercados"]["double_chance_12"] = dc_12
        resultado["mercados"]["double_chance_x2"] = dc_x2
        linhas.append(f"  Double Chance: 1X@{dc_1x} | 12@{dc_12} | X2@{dc_x2}")

    # ── Both Teams To Score ─────────────────
    btts_sim = _extrair_preco(bm_odds, MARKET_BTTS, 104)
    btts_nao = _extrair_preco(bm_odds, MARKET_BTTS, 105)

    if btts_sim:
        resultado["mercados"]["btts_sim"] = btts_sim
        resultado["mercados"]["btts_nao"] = btts_nao
        linhas.append(f"  Ambos Marcam: Sim@{btts_sim} | Nao@{btts_nao}")

    # ── Over/Under (vários handicaps) ───────
    # Handicaps comuns: 0.5, 1.5, 2.5, 3.5, 4.5
    # OddsPapi usa market_id diferente por handicap — varre todos
    ou_encontrados = []
    for market_id_str, market_data in markets.items():
        try:
            mid = int(market_id_str)
        except Exception:
            continue

        outcomes = market_data.get("outcomes", {})
        # Over/Under tem 2 outcomes (over e under)
        if len(outcomes) == 2:
            over_val = under_val = handicap = None
            for oid_str, outcome_data in outcomes.items():
                players = outcome_data.get("players", {})
                for p in players.values():
                    if not p.get("active", True):
                        continue
                    price = p.get("price")
                    outcome_id = int(oid_str)
                    # Detecta over/under pelo bookmakerOutcomeId
                    boid = str(p.get("bookmakerOutcomeId", "")).lower()
                    if "over" in boid or outcome_id % 2 == 0:
                        over_val = float(price) if price else None
                    elif "under" in boid or outcome_id % 2 == 1:
                        under_val = float(price) if price else None

            if over_val and under_val:
                # Tenta extrair handicap do market_id (aproximação)
                # handicaps comuns: 106=0.5, ~110=1.5, ~114=2.5, ~118=3.5, ~122=4.5
                handicap_est = round(0.5 + ((mid - 106) / 4) * 1.0, 1) if mid >= 106 else None
                if handicap_est and 0.5 <= handicap_est <= 5.5:
                    key = f"over_{handicap_est}"
                    resultado["mercados"][key] = over_val
                    resultado["mercados"][f"under_{handicap_est}"] = under_val
                    ou_encontrados.append(f"Over {handicap_est}@{over_val} | Under {handicap_est}@{under_val}")

    if ou_encontrados:
        linhas.append("  Over/Under: " + " | ".join(ou_encontrados[:4]))

    resultado["odds_txt"] = "\n".join(linhas)
    return resultado if len(resultado["mercados"]) > 0 else None


# ─────────────────────────────────────────────
# EXTRAIR ODD PARA MERCADO DA IA
# ─────────────────────────────────────────────

def extrair_odd_para_mercado(odds_dict, mercado_ia, odd_min=1.10, odd_max=2.50):
    """
    Dado o dict de odds e o mercado sugerido pela IA,
    retorna a odd mais adequada.
    """
    if not odds_dict:
        return None

    mercados = odds_dict.get("mercados", {})
    m = mercado_ia.lower().strip()

    # Vitória mandante
    if "mandante" in m or "home win" in m:
        v = mercados.get("vitoria_mandante")
        if v and odd_min <= v <= odd_max:
            return v

    # Vitória visitante
    if "visitante" in m or "away win" in m:
        v = mercados.get("vitoria_visitante")
        if v and odd_min <= v <= odd_max:
            return v

    # Double Chance 1X
    if "1x" in m:
        v = mercados.get("double_chance_1x")
        if v and odd_min <= v <= odd_max:
            return v

    # Double Chance X2
    if "x2" in m:
        v = mercados.get("double_chance_x2")
        if v and odd_min <= v <= odd_max:
            return v

    # Double Chance 12
    if "12" in m and "double" in m:
        v = mercados.get("double_chance_12")
        if v and odd_min <= v <= odd_max:
            return v

    # Ambos marcam
    if "ambos" in m or "btts" in m:
        v = mercados.get("btts_sim")
        if v and odd_min <= v <= odd_max:
            return v

    # Over X.X
    over_match = re.search(r"over\s*([\d.]+)", m)
    if over_match:
        handicap = float(over_match.group(1))
        v = mercados.get(f"over_{handicap}")
        if v and odd_min <= v <= odd_max:
            return v
        # Tenta handicaps próximos
        for key, val in mercados.items():
            if key.startswith("over_") and val and odd_min <= val <= odd_max:
                return val

    # Under X.X
    under_match = re.search(r"under\s*([\d.]+)", m)
    if under_match:
        handicap = float(under_match.group(1))
        v = mercados.get(f"under_{handicap}")
        if v and odd_min <= v <= odd_max:
            return v

    # Fallback: melhor odd disponível na faixa
    melhor = None
    centro = (odd_min + odd_max) / 2
    for key, val in mercados.items():
        if val and odd_min <= val <= odd_max:
            if melhor is None or abs(val - centro) < abs(melhor - centro):
                melhor = val

    # Se nada na faixa, tenta abaixo do mínimo (candidato combinada)
    if not melhor:
        for key, val in mercados.items():
            if val and 1.10 <= val < odd_min:
                if melhor is None or val > melhor:
                    melhor = val

    return melhor


# ─────────────────────────────────────────────
# MONTAR TEXTO DE ODDS (para passar à IA)
# ─────────────────────────────────────────────

def montar_texto_odds(odds_dict, mercado_ia=""):
    """Retorna texto resumido das odds para a IA processar."""
    if not odds_dict:
        return ""
    return odds_dict.get("odds_txt", "")


# ─────────────────────────────────────────────
# ALIAS para compatibilidade com alavancagem.py
# ─────────────────────────────────────────────

def extrair_melhor_odd(odds_dict, mercado_ia, odd_min=1.10, odd_max=2.50):
    """
    Alias de extrair_odd_para_mercado.
    Retorna (odd_valor, bookmaker, mercado_usado) para compatibilidade.
    """
    odd_val = extrair_odd_para_mercado(odds_dict, mercado_ia, odd_min, odd_max)
    bookmaker = odds_dict.get("bookmaker", "") if odds_dict else ""
    return odd_val, bookmaker, mercado_ia


# ─────────────────────────────────────────────
# VERIFICAR COTA RESTANTE
# ─────────────────────────────────────────────

def verificar_cota_restante(api_key):
    """Retorna uso da conta OddsPapi."""
    try:
        r = requests.get(
            f"{BASE_URL}/account",
            params={"apiKey": api_key},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            usado = data.get("requestsUsed", data.get("used", "?"))
            total = data.get("requestsLimit", data.get("limit", 250))
            return {"restantes": total - usado if isinstance(usado, int) else "?", "usadas": usado}
    except Exception:
        pass
    return {"restantes": "?", "usadas": "?"}
          
