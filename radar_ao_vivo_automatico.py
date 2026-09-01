"""
radar_ao_vivo_automatico.py
============================
Robô de monitoramento AO VIVO que roda SOZINHO, sem precisar do app
aberto no navegador. Pensado para ser executado periodicamente (ex: a
cada 5 minutos) via GitHub Actions (ou qualquer agendador tipo cron).

COMO FUNCIONA (2 camadas, para economizar API e IA):

  CAMADA 1 — BARATA (sem IA, sem gastar Gemini):
    A cada execução, busca os jogos ao vivo das ligas monitoradas e
    olha só os números brutos (pressão, escanteios, faltas por
    jogador). Compara com o que foi visto na execução anterior
    (guardado no Supabase). Só passa para a Camada 2 se algo relevante
    mudou.

  CAMADA 2 — CARA (chama a IA e o Telegram):
    Só roda quando a Camada 1 detecta um gatilho:
      - Pressão subiu bastante desde a última checagem
      - Escanteios aumentaram bastante desde a última checagem
      - Algum jogador bateu a 2ª falta (risco de cartão) e ainda não
        tinha sido avisado sobre ele
    Tem um "cooldown" por jogo (padrão 10 min) para não spammar o
    mesmo jogo repetidamente.

REQUISITOS:
  - Uma tabela nova no Supabase chamada "radar_estado" (ver
    RADAR_ESTADO_SQL.txt para o SQL de criação).
  - As mesmas secrets já usadas no app: API_KEY, GEMINI_API_KEY,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SUPABASE_URL, SUPABASE_KEY —
    disponíveis via st.secrets (arquivo .streamlit/secrets.toml).
"""

import json
import time
from datetime import datetime, timezone

import requests
import streamlit as st
from supabase import create_client

from api_football import _get  # reaproveita o rate limiter já configurado
from ia_engine import gerar_analise_ao_vivo


# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────

# Mesmas ligas "elite" do ao_vivo.py — evita gastar IA/API em ligas
# sem cobertura de estatísticas
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
# para começar a olhar detalhes de jogadores (evita gastar chamadas
# extras em jogos mornos)
PRESSAO_MINIMA_PARA_DETALHAR = 25

# Gatilhos de alerta
SALTO_PRESSAO_MINIMO      = 25   # pressão subiu pelo menos isso desde a última checagem
PRESSAO_MINIMA_ALERTA     = 55   # e já está acima disso no total
SALTO_ESCANTEIOS_MINIMO   = 2    # escanteios novos desde a última checagem
FALTAS_PARA_RISCO_CARTAO  = 2    # faltas cometidas = risco de cartão

# Cooldown por jogo, em minutos — não alerta o mesmo jogo de novo antes disso
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


def salvar_estado(supabase, fixture_id, pressao, escanteios, faltas_por_jogador, ultimo_alerta_ts=None):
    """Salva/atualiza o estado atual do jogo para a próxima checagem comparar."""
    dados = {
        "fixture_id": fixture_id,
        "pressao": pressao,
        "escanteios": escanteios,
        "faltas_por_jogador": json.dumps(faltas_por_jogador),
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
    """
    Retorna dict {nome_jogador: faltas_cometidas} para jogadores em campo.
    Usado para detectar risco de cartão (2+ faltas).
    """
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


# ─────────────────────────────────────────────
# DECISÃO DE GATILHO
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


def detectar_gatilho(estado_anterior, pressao_atual, escanteios_atual, faltas_atual):
    """
    Retorna (disparou: bool, motivo: str) comparando o estado atual
    com o que foi visto na última checagem.
    """
    if em_cooldown(estado_anterior):
        return False, ""

    # Primeira vez que vemos esse jogo — só guarda baseline, não alerta
    if estado_anterior is None:
        return False, ""

    pressao_anterior    = estado_anterior.get("pressao", 0) or 0
    escanteios_anterior = estado_anterior.get("escanteios", 0) or 0
    try:
        faltas_anterior = json.loads(estado_anterior.get("faltas_por_jogador") or "{}")
    except Exception:
        faltas_anterior = {}

    # Gatilho 1 — salto de pressão
    if (pressao_atual - pressao_anterior) >= SALTO_PRESSAO_MINIMO and pressao_atual >= PRESSAO_MINIMA_ALERTA:
        return True, f"Pressão subiu de {pressao_anterior} para {pressao_atual}"

    # Gatilho 2 — salto de escanteios
    if (escanteios_atual - escanteios_anterior) >= SALTO_ESCANTEIOS_MINIMO:
        return True, f"Escanteios subiram de {escanteios_anterior} para {escanteios_atual}"

    # Gatilho 3 — jogador cruzou o limite de faltas (novo risco de cartão)
    for jogador, qtd in faltas_atual.items():
        qtd_antes = faltas_anterior.get(jogador, 0)
        if qtd >= FALTAS_PARA_RISCO_CARTAO and qtd_antes < FALTAS_PARA_RISCO_CARTAO:
            return True, f"{jogador} bateu {qtd} faltas — risco de cartão"

    return False, ""


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

        # ── Camada 1 (barata): estatísticas do jogo ──
        stats   = _get(f"fixtures/statistics?fixture={fixture_id}")
        pressao = calcular_pressao(stats)
        escanteios = contar_escanteios(stats)

        # Só busca faltas por jogador se o jogo já estiver minimamente
        # quente — evita gastar chamada extra em jogo morno
        faltas_atual = {}
        if pressao >= PRESSAO_MINIMA_PARA_DETALHAR:
            faltas_atual = buscar_faltas_por_jogador(fixture_id)

        estado_anterior = carregar_estado(supabase, fixture_id)
        disparou, motivo = detectar_gatilho(estado_anterior, pressao, escanteios, faltas_atual)

        log(f"{home} {gols_home}x{gols_away} {away} ({tempo}') | pressão={pressao} escanteios={escanteios} | gatilho={disparou}")

        ultimo_alerta_ts = None

        if disparou:
            log(f"  🔥 Gatilho: {motivo} — chamando IA...")
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
                enviar_telegram(
                    "<b>🤖 RADAR AUTOMÁTICO - REI DA BOLA</b>\n\n"
                    f"⚡ Gatilho: {motivo}\n\n"
                    f"{tempo}' | {home} {gols_home}x{gols_away} {away}\n"
                    f"Liga: {liga}\n"
                    f"Pressão: {pressao}\n\n"
                    f"{resposta[:800]}"
                )
                ultimo_alerta_ts = datetime.now(timezone.utc).isoformat()
                log("  ✅ Alerta enviado pro Telegram.")
            except Exception as e:
                log(f"  ❌ Erro ao gerar análise/enviar alerta: {e}")

        salvar_estado(supabase, fixture_id, pressao, escanteios, faltas_atual, ultimo_alerta_ts)


if __name__ == "__main__":
    rodar_radar()
