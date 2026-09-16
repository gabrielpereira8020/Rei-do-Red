"""
poisson_model.py
=================
Modelo estatistico (Distribuicao de Poisson) para estimar
probabilidades REAIS de gols, escanteios e cartoes - complementando
a opiniao da IA de texto com matematica de verdade.

POR QUE ISSO IMPORTA (leia antes de usar):
  Uma IA de texto (Gemini) "opina" sobre os dados, mas isso nao e um
  modelo de probabilidade calibrado - quando ela diz "85% de
  confianca", isso nao passou por nenhuma validacao estatistica.

  A Distribuicao de Poisson e o padrao classico da industria de
  apostas pra estimar quantos eventos (gols, escanteios, cartoes)
  devem acontecer numa partida, a partir da MEDIA historica de cada
  time. Isso da uma probabilidade matematica real pra "Over 2.5 gols"
  por exemplo, em vez de uma impressao de texto.

LIMITACOES HONESTAS (isso nao e perfeito):
  - E uma aproximacao simplificada (nao e o modelo completo tipo
    Dixon-Coles, que tambem ajusta for a interdependencia entre
    ataque e defesa e correlacao entre os times).
  - Escanteios e cartoes nao seguem Poisson tao perfeitamente quanto
    gols (sao mais dependentes do estilo/arbitro do jogo), mas ainda
    e uma aproximacao usada na industria e MELHOR do que nao ter
    nenhum numero matematico de referencia.
  - Depende da qualidade dos dados de entrada (jogos recentes,
    tamanho da amostra). Poucos jogos = media pouco confiavel.
"""

import math
from api_football import _get


def _poisson_pmf(k, lam):
    """P(X = k) para uma distribuicao Poisson com media lam."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def probabilidade_over(media_esperada, linha):
    """
    Retorna a probabilidade (0 a 1) de o total ficar ACIMA da linha.
    Ex: linha=2.5 -> probabilidade de 3 ou mais eventos.
    """
    limite = math.floor(linha)
    prob_acumulada_até_limite = sum(_poisson_pmf(k, media_esperada) for k in range(0, limite + 1))
    return max(0.0, min(1.0, 1 - prob_acumulada_até_limite))


def probabilidade_under(media_esperada, linha):
    """Retorna a probabilidade (0 a 1) de o total ficar ABAIXO da linha."""
    return 1 - probabilidade_over(media_esperada, linha)


# ─────────────────────────────────────────────
# MÉDIAS DOS TIMES (gols) — via endpoint agregado da API-Football
# ─────────────────────────────────────────────

def buscar_media_gols_time(team_id, league_id, season):
    """
    Retorna dict com médias de gols marcados/sofridos do time,
    separado por casa/fora, usando o endpoint agregado da temporada
    (1 request só, dados já calculados pela própria API-Football).
    """
    try:
        data = _get(f"teams/statistics?team={team_id}&league={league_id}&season={season}")
        if not data:
            return None

        gols_for = data.get("goals", {}).get("for", {}).get("average", {})
        gols_against = data.get("goals", {}).get("against", {}).get("average", {})

        def _to_float(v):
            try:
                return float(v)
            except Exception:
                return 0.0

        return {
            "marcados_casa":  _to_float(gols_for.get("home", 0)),
            "marcados_fora":  _to_float(gols_for.get("away", 0)),
            "sofridos_casa":  _to_float(gols_against.get("home", 0)),
            "sofridos_fora":  _to_float(gols_against.get("away", 0)),
        }
    except Exception:
        return None


# ─────────────────────────────────────────────
# MÉDIAS DOS TIMES (escanteios e cartões) — via últimos 5 jogos
# (a API-Football não tem endpoint agregado pra isso, então
# calculamos manualmente a partir das estatísticas de cada jogo)
# ─────────────────────────────────────────────

def buscar_media_escanteios_cartoes_time(team_id, ultimos_n=5):
    """
    Retorna dict {"escanteios": media, "cartoes": media} calculado a
    partir dos últimos N jogos do time. Custa N+1 requests (1 pra
    listar os jogos, N pra buscar a estatística de cada um).
    """
    try:
        fixtures = _get(f"fixtures?team={team_id}&last={ultimos_n}")
        if not fixtures:
            return {"escanteios": 0.0, "cartoes": 0.0, "amostra": 0}

        total_escanteios = 0
        total_cartoes = 0
        amostra = 0

        for fx in fixtures:
            fixture_id = fx["fixture"]["id"]
            time_casa_id = fx["teams"]["home"]["id"]
            stats = _get(f"fixtures/statistics?fixture={fixture_id}")
            if not stats or len(stats) < 2:
                continue

            # Descobre qual dos 2 blocos de stats é do nosso time
            bloco = None
            for s in stats:
                if s.get("team", {}).get("id") == team_id:
                    bloco = s.get("statistics", [])
                    break
            if bloco is None:
                continue

            def pegar(nome):
                for item in bloco:
                    if item["type"] == nome:
                        v = item["value"]
                        try:
                            return int(v) if v is not None else 0
                        except Exception:
                            return 0
                return 0

            total_escanteios += pegar("Corner Kicks")
            total_cartoes += pegar("Yellow Cards") + pegar("Red Cards")
            amostra += 1

        if amostra == 0:
            return {"escanteios": 0.0, "cartoes": 0.0, "amostra": 0}

        return {
            "escanteios": round(total_escanteios / amostra, 2),
            "cartoes": round(total_cartoes / amostra, 2),
            "amostra": amostra,
        }
    except Exception:
        return {"escanteios": 0.0, "cartoes": 0.0, "amostra": 0}


# ─────────────────────────────────────────────
# CÁLCULO DAS EXPECTATIVAS DO JOGO
# ─────────────────────────────────────────────

def calcular_expectativas_jogo(home_id, away_id, league_id, season, ultimos_n=5):
    """
    Combina as médias dos 2 times pra estimar quantos gols,
    escanteios e cartões devem sair NO JOGO (não por time isolado).

    Gols: usa o endpoint agregado da temporada (mais amostra, mais
    confiável). Escanteios/cartões: usa média dos últimos N jogos de
    cada time (a API não tem agregado pra isso).

    Retorna None se não conseguir dados suficientes.
    """
    medias_gols_home = buscar_media_gols_time(home_id, league_id, season)
    medias_gols_away = buscar_media_gols_time(away_id, league_id, season)

    if not medias_gols_home or not medias_gols_away:
        return None

    # Expectativa de gols do mandante = média do que ele marca em casa
    # combinada com média do que o visitante sofre fora (e vice-versa)
    esperado_gols_casa = (medias_gols_home["marcados_casa"] + medias_gols_away["sofridos_fora"]) / 2
    esperado_gols_fora = (medias_gols_away["marcados_fora"] + medias_gols_home["sofridos_casa"]) / 2
    esperado_gols_total = esperado_gols_casa + esperado_gols_fora

    stats_home = buscar_media_escanteios_cartoes_time(home_id, ultimos_n)
    stats_away = buscar_media_escanteios_cartoes_time(away_id, ultimos_n)

    esperado_escanteios_total = stats_home["escanteios"] + stats_away["escanteios"]
    esperado_cartoes_total = stats_home["cartoes"] + stats_away["cartoes"]

    amostra_minima = min(stats_home["amostra"], stats_away["amostra"])

    return {
        "gols_total_esperado": round(esperado_gols_total, 2),
        "escanteios_total_esperado": round(esperado_escanteios_total, 2),
        "cartoes_total_esperado": round(esperado_cartoes_total, 2),
        "amostra_escanteios_cartoes": amostra_minima,  # quantos jogos deram base pra essa média
    }


# ─────────────────────────────────────────────
# ESCANEAR VÁRIAS LINHAS E ACHAR ONDE HÁ VALOR
# ─────────────────────────────────────────────

LINHAS_GOLS       = [0.5, 1.5, 2.5, 3.5, 4.5]
LINHAS_ESCANTEIOS = [6.5, 7.5, 8.5, 9.5, 10.5, 11.5]
LINHAS_CARTOES    = [1.5, 2.5, 3.5, 4.5, 5.5]


def escanear_linhas(media_esperada, linhas, rotulo):
    """
    Para cada linha (ex: 2.5, 3.5...), calcula a probabilidade real
    (Poisson) de Over e Under. Retorna lista de dicts, ordenada da
    probabilidade mais alta pra mais baixa — ou seja, primeiro vêm as
    apostas em que o modelo tem MAIS certeza (não necessariamente as
    de maior valor contra o mercado, isso é calculado depois).
    """
    resultados = []
    for linha in linhas:
        p_over = probabilidade_over(media_esperada, linha)
        p_under = 1 - p_over
        resultados.append({
            "mercado": f"Over {linha} {rotulo}",
            "probabilidade_pct": round(p_over * 100, 1),
        })
        resultados.append({
            "mercado": f"Under {linha} {rotulo}",
            "probabilidade_pct": round(p_under * 100, 1),
        })
    resultados.sort(key=lambda r: r["probabilidade_pct"], reverse=True)
    return resultados
