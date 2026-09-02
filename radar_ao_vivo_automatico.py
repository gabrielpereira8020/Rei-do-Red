"""
radar_ao_vivo_automatico.py
============================
Robô de monitoramento AO VIVO que roda SOZINHO, sem precisar do app
aberto no navegador. Pensado para ser executado periodicamente (ex: a
cada 5 minutos) via GitHub Actions (ou qualquer agendador tipo cron).

COMO FUNCIONA (2 camadas, para economizar API e IA):

  CAMADA 1 — BARATA (sem IA, sem gastar Gemini):
    A cada execução, busca os jogos ao vivo das ligas monitoradas e
    olha os números brutos: pressão, escanteios, faltas por jogador,
    placar (gols), eventos de cartão realmente emitidos, e (para jogos
    já quentes) odds ao vivo. Compara tudo com o que foi visto na
    execução anterior (guardado no Supabase).

  CAMADA 2 — CARA (chama a IA e o Telegram):
    Só roda quando a Camada 1 detecta pelo menos 1 gatilho:
      - GOL (bypassa o cooldown — sempre avisa na hora)
      - Cartão amarelo/vermelho realmente mostrado (bypassa o cooldown)
      - Pressão subiu bastante desde a última checagem
      - Escanteios aumentaram bastante desde a última checagem
      - Algum jogador bateu a 2ª falta (risco de cartão)
      - Odd ao vivo de algum mercado mudou bastante (o mercado "sentiu"
        que algo pode acontecer)
    Gol e cartão emitido são eventos raros e importantes, por isso
    avisam na hora, ignorando o cooldown. Os demais (mais "ruidosos")
    respeitam um cooldown por jogo (padrão 10 min) para não spammar.

REQUISITOS:
  - Tabela "radar_estado" no Supabase (ver RADAR_ESTADO_SQL.txt para
    criar do zero, ou RADAR_ESTADO_ALTER.txt se você já criou a versão
    anterior e só precisa adicionar as colunas novas).
  - As mesmas secrets já usadas no app: API_KEY, GEMINI_API_KEY,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SUPABASE_URL, SUPABASE_KEY —
    disponíveis via st.secrets (arquivo .streamlit/secrets.toml).
"""

import json
from datetime import datetime, timezone

import requests
import streamlit as st
from supabase import create_client

from api_football import _get  # reaproveita o rate limiter já configurado
from ia_engine import gerar_analise_ao_vivo


# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────

LIGAS_ELITE = [
    71, 72, 73,
    39, 40,
    140, 141,
    78, 79,
    135, 136,
    61, 62,
    94,
    13, 11,
    2, 3, 848,
]

# A partir de quanto de pressão o jogo já é "interessante" o suficiente
# para olhar detalhes extras (faltas por jogador, odds ao vivo) —
# evita gastar chamadas extras em jogos mornos
PRESSAO_MINIMA_PARA_DETALHAR = 25

# Gatilhos "ruidosos" (respeitam cooldown)
SALTO_PRESSAO_MINIMO      = 25   # pressão subiu pelo menos isso desde a última checagem
PRESSAO_MINIMA_ALERTA     = 55   # e já está acima disso no total
SALTO_ESCANTEIOS_MINIMO   = 2    # escanteios novos desde a última checagem
FALTAS_PARA_RISCO_CARTAO  = 2    # faltas cometidas = risco de cartão
VARIACAO_ODD_MINIMA_PCT   = 15   # % de mudança na odd para considerar relevante

# Cooldown por jogo, em minutos — só vale para os gatilhos "ruidosos"
# acima. Gol e cartão emitido SEMPRE avisam, sem cooldown.
COOLDOWN_MINUTOS = 10


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ─────────────────────────────────────────────
# TELEGRAM
# ─────────────────────────────────────────────

def enviar_telegram(msg):
    token   = st.secrets["TELEGRAM_TOKEN"]
    chat_id = st.secrets["TELEGRAM_CHAT_ID"]
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        log(f"Erro Telegram: {e}")
        return False


# ─────────────────────────────────────────────
# SUPABASE — memória do que já foi visto
# ─────────────────────────────────────────────

def get_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def carregar_estado(supabase, fixture_id):
    """Busca o último estado salvo desse jogo. None se for a 1ª vez que vemos ele."""
    try:
        r = supabase.table("radar_estado").select("*").eq("fixture_id", fixture_id).execute()
        if r.data:
            return r.data[0]
    except Exception as e:
        log(f"Erro ao carregar estado do jogo {fixture_id}: {e}")
    return None


def salvar_estado(supabase, fixture_id, pressao, escanteios, faltas_por_jogador,
                   gols_home, gols_away, eventos_cartao_vistos, odds_referencia,
                   ultimo_alerta_ts=None):
    """Salva/atualiza o estado atual do jogo para a próxima checagem comparar."""
    dados = {
        "fixture_id": fixture_id,
        "pressao": pressao,
        "escanteios": escanteios,
        "faltas_por_jogador": json.dumps(faltas_por_jogador),
        "gols_home": gols_home,
        "gols_away": gols_away,
        "eventos_cartao_vistos": json.dumps(eventos_cartao_vistos),
        "odds_referencia": json.dumps(odds_referencia),
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }
    if ultimo_alerta_ts is not None:
        dados["ultimo_alerta_ts"] = ultimo_alerta_ts
    try:
        supabase.table("radar_estado").upsert(dados, on_conflict="fixture_id").execute()
    except Exception as e:
        log(f"Erro ao salvar estado do jogo {fixture_id}: {e}")


def limpar_jogos_encerrados(supabase, fixture_ids_ao_vivo_agora):
    """Remove do banco os jogos que não estão mais ao vivo (evita lixo acumulando)."""
    try:
        r = supabase.table("radar_estado").select("fixture_id").execute()
        for row in (r.data or []):
            if row["fixture_id"] not in fixture_ids_ao_vivo_agora:
                supabase.table("radar_estado").delete().eq("fixture_id", row["fixture_id"]).execute()
    except Exception as e:
        log(f"Erro ao limpar jogos encerrados: {e}")


# ─────────────────────────────────────────────
# CÁLCULO DE ESTATÍSTICAS (mesma lógica do ao_vivo.py)
# ─────────────────────────────────────────────

def calcular_pressao(stats):
    if not stats or len(stats) < 2:
        return 0

    def pegar(s, nome):
        for item in s:
            if item["type"] == nome:
                v = item["value"]
                if v is None:
                    return 0
                try:
                    return int(str(v).replace("%", ""))
                except Exception:
                    return 0
        return 0

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]
    ph = pegar(home, "Shots on Goal") * 6 + pegar(home, "Corner Kicks") * 3 + pegar(home, "Total Shots") * 2
    pa = pegar(away, "Shots on Goal") * 6 + pegar(away, "Corner Kicks") * 3 + pegar(away, "Total Shots") * 2
    return max(ph, pa)


def contar_escanteios(stats):
    if not stats or len(stats) < 2:
        return 0

    def pegar(s):
        for item in s:
            if item["type"] == "Corner Kicks":
                v = item["value"]
                try:
                    return int(v) if v is not None else 0
                except Exception:
                    return 0
        return 0

    return pegar(stats[0]["statistics"]) + pegar(stats[1]["statistics"])


def descrever_stats(stats):
    if not stats or len(stats) < 2:
        return "Estatísticas indisponíveis."

    def pegar(s, nome):
        for item in s:
            if item["type"] == nome:
                v = item["value"]
                return v if v is not None else 0
        return 0

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]
    th = stats[0].get("team", {}).get("name", "Casa")
    ta = stats[1].get("team", {}).get("name", "Fora")

    return (
        f"{th}: Chutes {pegar(home,'Total Shots')}, No gol {pegar(home,'Shots on Goal')}, "
        f"Escanteios {pegar(home,'Corner Kicks')}, Posse {pegar(home,'Ball Possession')}%, "
        f"Faltas {pegar(home,'Fouls')}, Cartões A{pegar(home,'Yellow Cards')}/V{pegar(home,'Red Cards')} | "
        f"{ta}: Chutes {pegar(away,'Total Shots')}, No gol {pegar(away,'Shots on Goal')}, "
        f"Escanteios {pegar(away,'Corner Kicks')}, Posse {pegar(away,'Ball Possession')}%, "
        f"Faltas {pegar(away,'Fouls')}, Cartões A{pegar(away,'Yellow Cards')}/V{pegar(away,'Red Cards')}"
    )


def buscar_faltas_por_jogador(fixture_id):
    """Retorna dict {nome_jogador: faltas_cometidas} — usado para risco de cartão."""
    try:
        data = _get(f"fixtures/players?fixture={fixture_id}")
        faltas = {}
        for time_ in data:
            for item in time_.get("players", []):
                p = item.get("player", {})
                s = item.get("statistics", [{}])[0]
                minutos = s.get("games", {}).get("minutes", 0) or 0
                if minutos <= 0:
                    continue
                nome = p.get("name", "?")
                qtd_faltas = s.get("fouls", {}).get("committed", 0) or 0
                faltas[nome] = qtd_faltas
        return faltas
    except Exception as e:
        log(f"Erro ao buscar faltas por jogador (fixture {fixture_id}): {e}")
        return {}


def buscar_eventos_cartao(fixture_id):
    """
    Retorna lista de cartões AMARELO/VERMELHO já mostrados no jogo,
    cada um com uma chave única (para saber se já avisamos ou não) e
    um texto pronto pra mandar no alerta.
    """
    try:
        data = _get(f"fixtures/events?fixture={fixture_id}")
        cartoes = []
        for ev in data:
            if ev.get("type") != "Card":
                continue
            minuto    = ev.get("time", {}).get("elapsed", "?")
            jogador   = ev.get("player", {}).get("name", "?")
            time_nome = ev.get("team", {}).get("name", "?")
            detalhe   = ev.get("detail", "")
            emoji = "🟨" if detalhe == "Yellow Card" else "🟥"
            key = f"{jogador}_{minuto}_{detalhe}"
            texto = f"{emoji} Cartão {detalhe} para {jogador} ({time_nome}) aos {minuto}'"
            cartoes.append({"key": key, "texto": texto})
        return cartoes
    except Exception as e:
        log(f"Erro ao buscar eventos de cartão (fixture {fixture_id}): {e}")
        return []


def buscar_odds_ao_vivo_dict(fixture_id):
    """
    Retorna um dict {"mercado:opcao": preco} com as primeiras odds ao
    vivo disponíveis, para comparar a variação entre execuções.
    """
    try:
        data = _get(f"odds/live?fixture={fixture_id}")
        odds_dict = {}
        if not data:
            return odds_dict
        item = data[0]
        for bet in item.get("bets", [])[:5]:
            nome_mercado = bet.get("name", "")
            valores = bet.get("values", [])
            if valores:
                primeiro = valores[0]
                try:
                    chave = f"{nome_mercado}:{primeiro.get('value','')}"
                    odds_dict[chave] = float(primeiro.get("odd", 0))
                except Exception:
                    pass
        return odds_dict
    except Exception as e:
        log(f"Erro ao buscar odds ao vivo (fixture {fixture_id}): {e}")
        return {}


# ─────────────────────────────────────────────
# DECISÃO DE GATILHOS
# ─────────────────────────────────────────────

def em_cooldown(estado_anterior):
    if not estado_anterior or not estado_anterior.get("ultimo_alerta_ts"):
        return False
    try:
        ultimo = datetime.fromisoformat(estado_anterior["ultimo_alerta_ts"])
        agora = datetime.now(timezone.utc)
        minutos_passados = (agora - ultimo).total_seconds() / 60
        return minutos_passados < COOLDOWN_MINUTOS
    except Exception:
        return False


def detectar_gatilhos(estado_anterior, home, away, pressao_atual, escanteios_atual,
                       faltas_atual, gols_home_atual, gols_away_atual,
                       cartoes_atual, odds_atual):
    """
    Retorna a lista de motivos que dispararam (pode ser mais de 1 ao
    mesmo tempo, ex: gol + pressão alta juntos).
    """
    motivos = []

    # Primeira vez que vemos esse jogo — só guarda baseline, não alerta
    if estado_anterior is None:
        return motivos

    gols_home_anterior = estado_anterior.get("gols_home", 0) or 0
    gols_away_anterior = estado_anterior.get("gols_away", 0) or 0
    try:
        cartoes_vistos_anterior = json.loads(estado_anterior.get("eventos_cartao_vistos") or "[]")
    except Exception:
        cartoes_vistos_anterior = []

    # ── GATILHO: GOL (sempre avisa, sem cooldown) ──
    if gols_home_atual > gols_home_anterior:
        motivos.append(f"⚽ GOL do {home}! Placar agora: {gols_home_atual}x{gols_away_atual}")
    if gols_away_atual > gols_away_anterior:
        motivos.append(f"⚽ GOL do {away}! Placar agora: {gols_home_atual}x{gols_away_atual}")

    # ── GATILHO: CARTÃO EMITIDO (sempre avisa, sem cooldown) ──
    for c in cartoes_atual:
        if c["key"] not in cartoes_vistos_anterior:
            motivos.append(c["texto"])

    # ── Gatilhos "ruidosos" — só se não estiver em cooldown ──
    if not em_cooldown(estado_anterior):
        pressao_anterior    = estado_anterior.get("pressao", 0) or 0
        escanteios_anterior = estado_anterior.get("escanteios", 0) or 0
        try:
            faltas_anterior = json.loads(estado_anterior.get("faltas_por_jogador") or "{}")
        except Exception:
            faltas_anterior = {}
        try:
            odds_anterior = json.loads(estado_anterior.get("odds_referencia") or "{}")
        except Exception:
            odds_anterior = {}

        if (pressao_atual - pressao_anterior) >= SALTO_PRESSAO_MINIMO and pressao_atual >= PRESSAO_MINIMA_ALERTA:
            motivos.append(f"🔥 Pressão subiu de {pressao_anterior} para {pressao_atual}")

        if (escanteios_atual - escanteios_anterior) >= SALTO_ESCANTEIOS_MINIMO:
            motivos.append(f"🚩 Escanteios subiram de {escanteios_anterior} para {escanteios_atual}")

        for jogador, qtd in faltas_atual.items():
            qtd_antes = faltas_anterior.get(jogador, 0)
            if qtd >= FALTAS_PARA_RISCO_CARTAO and qtd_antes < FALTAS_PARA_RISCO_CARTAO:
                motivos.append(f"⚠️ {jogador} bateu {qtd} faltas — risco de cartão")

        for mercado, preco_atual in odds_atual.items():
            preco_antigo = odds_anterior.get(mercado)
            if preco_antigo and preco_antigo > 0:
                variacao_pct = abs(preco_atual - preco_antigo) / preco_antigo * 100
                if variacao_pct >= VARIACAO_ODD_MINIMA_PCT:
                    motivos.append(
                        f"💹 Odd '{mercado}' mudou de {preco_antigo} para {preco_atual} ({variacao_pct:.0f}%)"
                    )

    return motivos


# ─────────────────────────────────────────────
# LOOP PRINCIPAL — 1 execução completa do radar
# ─────────────────────────────────────────────

def rodar_radar():
    supabase = get_supabase()

    log("Buscando jogos ao vivo...")
    todos_live = _get("fixtures?live=all")

    if not todos_live:
        log("Nenhum jogo ao vivo no momento.")
        return

    elite_live = [j for j in todos_live if j["league"]["id"] in LIGAS_ELITE]
    log(f"{len(elite_live)} jogo(s) ao vivo nas ligas monitoradas.")

    fixture_ids_agora = [j["fixture"]["id"] for j in elite_live]
    limpar_jogos_encerrados(supabase, fixture_ids_agora)

    for jogo in elite_live:
        fixture_id = jogo["fixture"]["id"]
        home       = jogo["teams"]["home"]["name"]
        away       = jogo["teams"]["away"]["name"]
        home_id    = jogo["teams"]["home"]["id"]
        away_id    = jogo["teams"]["away"]["id"]
        gols_home  = jogo["goals"]["home"] or 0
        gols_away  = jogo["goals"]["away"] or 0
        tempo      = jogo["fixture"]["status"]["elapsed"] or "?"
        liga       = jogo["league"]["name"]

        # ── Camada 1 (barata) ──
        stats      = _get(f"fixtures/statistics?fixture={fixture_id}")
        pressao    = calcular_pressao(stats)
        escanteios = contar_escanteios(stats)
        cartoes    = buscar_eventos_cartao(fixture_id)  # sempre checa — gol/cartão importam mesmo em jogo morno

        faltas_atual = {}
        odds_atual   = {}
        if pressao >= PRESSAO_MINIMA_PARA_DETALHAR:
            faltas_atual = buscar_faltas_por_jogador(fixture_id)
            odds_atual   = buscar_odds_ao_vivo_dict(fixture_id)

        estado_anterior = carregar_estado(supabase, fixture_id)
        motivos = detectar_gatilhos(
            estado_anterior, home, away, pressao, escanteios,
            faltas_atual, gols_home, gols_away, cartoes, odds_atual
        )

        log(f"{home} {gols_home}x{gols_away} {away} ({tempo}') | pressão={pressao} escanteios={escanteios} | gatilhos={len(motivos)}")

        ultimo_alerta_ts = None

        if motivos:
            log(f"  gatilhos: {' | '.join(motivos)} — chamando IA...")
            stats_texto = descrever_stats(stats)

            jogo_info = {
                "id":        fixture_id,
                "casa":      home,
                "fora":      away,
                "casa_id":   home_id,
                "fora_id":   away_id,
                "minuto":    str(tempo),
                "placar":    f"{home} {gols_home} x {gols_away} {away}",
                "stats":     stats_texto,
                "stats_raw": stats,
                "pressao":   pressao,
            }

            try:
                resposta = gerar_analise_ao_vivo(jogo_info)
                texto_gatilhos = "\n".join(f"- {m}" for m in motivos)
                enviar_telegram(
                    "<b>Radar Automatico - Rei da Bola</b>\n\n"
                    f"{texto_gatilhos}\n\n"
                    f"{tempo}' | {home} {gols_home}x{gols_away} {away}\n"
                    f"Liga: {liga}\n"
                    f"Pressao: {pressao}\n\n"
                    f"{resposta[:800]}"
                )
                ultimo_alerta_ts = datetime.now(timezone.utc).isoformat()
                log("  alerta enviado pro Telegram.")
            except Exception as e:
                log(f"  erro ao gerar analise/enviar alerta: {e}")

        # Junta os cartões já vistos antes com os novos, pra nunca mais
        # re-avisar do mesmo cartão
        cartoes_vistos_anterior = []
        if estado_anterior:
            try:
                cartoes_vistos_anterior = json.loads(estado_anterior.get("eventos_cartao_vistos") or "[]")
            except Exception:
                pass
        cartoes_vistos_atualizados = list(set(cartoes_vistos_anterior + [c["key"] for c in cartoes]))

        salvar_estado(
            supabase, fixture_id, pressao, escanteios, faltas_atual,
            gols_home, gols_away, cartoes_vistos_atualizados, odds_atual,
            ultimo_alerta_ts
        )


if __name__ == "__main__":
    rodar_radar()
