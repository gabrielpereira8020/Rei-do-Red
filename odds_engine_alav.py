import requests
from datetime import datetime, timezone

ODDS_API_BASE = "https://api.odds-api.io/v3"

# Ligas por prioridade
LIGAS_ALTA = ["UEFA Champions League", "Premier League", "La Liga", "Bundesliga",
               "Serie A", "Brasileirao", "Libertadores"]
LIGAS_MEDIA = ["Serie B", "Ligue 1", "Sudamericana", "Europa League"]

# Mercados bloqueados (muito arriscados)
MERCADOS_BLOQUEADOS = [
    "correct score", "placar correto", "exact score",
    "scorecast", "wincast", "first goalscorer",
    "anytime goalscorer"
]

# Faixas de segurança
def classificar_odd(odd):
    try:
        odd = float(odd)
        if odd <= 1.35:
            return "muito_segura"
        elif odd <= 1.55:
            return "segura"
        elif odd <= 1.80:
            return "moderada"
        else:
            return "arriscada"
    except Exception:
        return "desconhecida"

def jogo_e_futuro(horario_str):
    if not horario_str:
        return True
    try:
        horario_str = str(horario_str).replace(" ", "T")
        if not horario_str.endswith("Z") and "+" not in horario_str:
            horario_str += "Z"
        dt = datetime.fromisoformat(horario_str.replace("Z", "+00:00"))
        return dt > datetime.now(timezone.utc)
    except Exception:
        return True

def mercado_e_permitido(nome_mercado):
    nome_lower = str(nome_mercado).lower()
    for bloqueado in MERCADOS_BLOQUEADOS:
        if bloqueado in nome_lower:
            return False
    return True

def buscar_eventos_futuros(odds_api_key):
    """Busca eventos futuros de futebol."""
    try:
        r = requests.get(
            ODDS_API_BASE + "/events",
            params={"apiKey": odds_api_key, "sport": "football",
                    "status": "upcoming", "limit": 100},
            timeout=15
        )
        if r.status_code == 401:
            return None, "invalida"
        if r.status_code != 200:
            return None, "erro_" + str(r.status_code)
        data = r.json()
        eventos = data if isinstance(data, list) else data.get("data", [])
        futuros = [ev for ev in eventos if jogo_e_futuro(
            ev.get("date", ev.get("start_time", ""))
        )]
        return futuros, "ok"
    except Exception as e:
        return None, str(e)

def buscar_odds_evento(event_id, odds_api_key):
    """Busca odds reais filtrando mercados bloqueados."""
    try:
        r = requests.get(
            ODDS_API_BASE + "/odds",
            params={"apiKey": odds_api_key, "eventId": str(event_id),
                    "bookmakers": "Bet365,Unibet"},
            timeout=15
        )
        if r.status_code != 200:
            return ""
        data = r.json()
        bookmakers = data.get("bookmakers", {})
        if not bookmakers:
            return ""

        linhas = []
        for bk_nome, mercados in bookmakers.items():
            if not mercados:
                continue
            for mercado in mercados:
                nome_mercado = mercado.get("name", "")
                if not mercado_e_permitido(nome_mercado):
                    continue
                odds_lista = mercado.get("odds", [])
                if not odds_lista:
                    continue
                odd_vals = odds_lista[0]

                if nome_mercado == "ML":
                    h = odd_vals.get("home", "")
                    d = odd_vals.get("draw", "")
                    a = odd_vals.get("away", "")
                    if h and d and a:
                        faixa_h = classificar_odd(h)
                        linhas.append(f"[{bk_nome}] 1x2: Casa@{h}({faixa_h}) | Empate@{d} | Fora@{a}")

                elif nome_mercado in ["Over/Under", "OU", "Goals", "Total Goals"]:
                    for k, v in odd_vals.items():
                        if v:
                            faixa = classificar_odd(v)
                            linhas.append(f"[{bk_nome}] {nome_mercado} {k}@{v}({faixa})")

                elif nome_mercado in ["BTTS", "Both Teams to Score"]:
                    sim = odd_vals.get("yes", odd_vals.get("Yes", ""))
                    nao = odd_vals.get("no", odd_vals.get("No", ""))
                    if sim and nao:
                        linhas.append(f"[{bk_nome}] Ambos Marcam: Sim@{sim} | Nao@{nao}")

                elif nome_mercado == "DC":
                    x1 = odd_vals.get("1X", "")
                    x12 = odd_vals.get("12", "")
                    x2 = odd_vals.get("X2", "")
                    if x1:
                        faixa = classificar_odd(x1)
                        linhas.append(f"[{bk_nome}] Double Chance: 1X@{x1}({faixa}) | 12@{x12} | X2@{x2}")

                else:
                    partes = [f"{k}@{v}" for k, v in odd_vals.items() if v]
                    if partes:
                        linhas.append(f"[{bk_nome}] {nome_mercado}: " + " | ".join(partes))

            if linhas:
                break

        return "\n".join(linhas[:8])
    except Exception:
        return ""

def buscar_jogos_com_odds(odds_api_key, progress_callback=None):
    """
    Busca todos os jogos futuros com odds reais.
    Retorna apenas jogos com odds confirmadas.
    """
    jogos = []
    eventos, status = buscar_eventos_futuros(odds_api_key)

    if status == "invalida":
        return jogos, "ODDS_API_KEY invalida"
    if eventos is None:
        return jogos, "Erro: " + status
    if not eventos:
        return jogos, "Nenhum evento futuro encontrado"

    total = min(len(eventos), 60)
    for i, ev in enumerate(eventos[:60]):
        if progress_callback:
            progress_callback(i + 1, total, ev.get("home", "") + " x " + ev.get("away", ""))

        event_id = ev.get("id", "")
        home = ev.get("home", ev.get("home_team", ""))
        away = ev.get("away", ev.get("away_team", ""))
        liga_info = ev.get("league", {})
        liga = liga_info.get("name", "Futebol") if isinstance(liga_info, dict) else str(liga_info)
        horario = ev.get("date", ev.get("start_time", ""))

        if not home or not away or not event_id:
            continue

        odds_txt = buscar_odds_evento(event_id, odds_api_key)
        if not odds_txt:
            continue

        # Define prioridade da liga
        prioridade = 3
        for l in LIGAS_ALTA:
            if l.lower() in liga.lower():
                prioridade = 1
                break
        for l in LIGAS_MEDIA:
            if l.lower() in liga.lower():
                prioridade = 2
                break

        jogos.append({
            "nome": str(home) + " x " + str(away),
            "casa": str(home),
            "fora": str(away),
            "liga_nome": str(liga),
            "odds_txt": odds_txt,
            "tem_odds": True,
            "id": str(event_id),
            "horario": str(horario)[:16].replace("T", " ") if horario else "",
            "prioridade": prioridade
        })

    # Ordena por prioridade (ligas melhores primeiro)
    jogos.sort(key=lambda x: x["prioridade"])
    return jogos, "ok"
