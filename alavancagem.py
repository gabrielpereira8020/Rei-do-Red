import streamlit as st
import json
import requests
from datetime import datetime
from api_football import buscar_jogos_da_liga

LIGAS_VARREDURA = {
    "Brasileirao Serie A": 71,
    "Brasileirao Serie B": 72,
    "Premier League": 39,
    "LaLiga": 140,
    "Bundesliga": 78,
    "Serie A Italia": 135,
    "Ligue 1": 61,
    "Libertadores": 13,
    "Sudamericana": 11,
    "Champions League": 2,
    "Europa League": 3,
    "Amistosos Selecoes": 9,
    "Copa do Mundo": 1,
}

ODDS_API_BASE = "https://api.odds-api.io/v3"
BOOKMAKERS = "Bet365,Unibet,SingBet"


def init_estado():
    defaults = {
        "alav_banca_inicial": 10.0,
        "alav_odd_alvo": 1.5,
        "alav_total_entradas": 10,
        "alav_entradas": [],
        "alav_ativa": False,
        "alav_entrada_atual": 0,
        "alav_odd_min": 1.3,
        "alav_odd_max": 2.0,
        "alav_jogos": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def calcular_tabela(banca, odd, total):
    tabela = []
    valor = banca
    for i in range(1, total + 1):
        retorno = round(valor * odd, 2)
        tabela.append({
            "entrada": i,
            "valor": round(valor, 2),
            "odd": odd,
            "retorno": retorno,
            "lucro": round(retorno - valor, 2),
            "status": None,
            "bilhete": [],
            "tipo": "",
            "confianca": 0,
            "data": "",
        })
        valor = retorno
    return tabela


def buscar_eventos(odds_api_key):
    """Busca todos os eventos de futebol disponíveis."""
    try:
        r = requests.get(
            ODDS_API_BASE + "/events",
            params={
                "apiKey": odds_api_key,
                "sport": "football",
                "limit": 100
            },
            timeout=15
        )
        if r.status_code == 401:
            return None, "invalida"
        if r.status_code != 200:
            return None, "erro_" + str(r.status_code)
        data = r.json()
        if isinstance(data, list):
            return data, "ok"
        return data.get("data", []), "ok"
    except Exception as e:
        return None, str(e)


def buscar_odds_evento(event_id, odds_api_key):
    """
    Busca odds de um evento.
    Retorno da API:
    {
      "bookmakers": {
        "Bet365": [{"name": "ML", "odds": [{"home": "2.10", "draw": "3.40", "away": "3.20"}]}]
      }
    }
    """
    try:
        r = requests.get(
            ODDS_API_BASE + "/odds",
            params={
                "apiKey": odds_api_key,
                "eventId": str(event_id),
                "bookmakers": BOOKMAKERS
            },
            timeout=15
        )
        if r.status_code != 200:
            return ""

        data = r.json()
        bookmakers = data.get("bookmakers", {})
        if not bookmakers:
            return ""

        linhas = []
        # Pega do primeiro bookmaker disponível
        for bk_nome, mercados in bookmakers.items():
            if not mercados:
                continue
            for mercado in mercados:
                nome_mercado = mercado.get("name", "")
                odds_lista = mercado.get("odds", [])
                if not odds_lista:
                    continue
                odd_vals = odds_lista[0]  # Pega primeiro conjunto de odds

                if nome_mercado == "ML":
                    linha = (
                        "[" + bk_nome + "] 1x2: " +
                        "Casa @ " + str(odd_vals.get("home", "")) + " | " +
                        "Empate @ " + str(odd_vals.get("draw", "")) + " | " +
                        "Fora @ " + str(odd_vals.get("away", ""))
                    )
                    linhas.append(linha)

                elif nome_mercado in ["Over/Under", "OU", "Goals"]:
                    for k, v in odd_vals.items():
                        linhas.append("[" + bk_nome + "] " + nome_mercado + " " + str(k) + " @ " + str(v))

                elif nome_mercado in ["BTTS", "Both Teams to Score"]:
                    linha = (
                        "[" + bk_nome + "] Ambos Marcam: " +
                        "Sim @ " + str(odd_vals.get("yes", odd_vals.get("Sim", ""))) + " | " +
                        "Nao @ " + str(odd_vals.get("no", odd_vals.get("Nao", "")))
                    )
                    linhas.append(linha)

                elif nome_mercado == "DC":
                    linha = (
                        "[" + bk_nome + "] Double Chance: " +
                        "1X @ " + str(odd_vals.get("1X", "")) + " | " +
                        "12 @ " + str(odd_vals.get("12", "")) + " | " +
                        "X2 @ " + str(odd_vals.get("X2", ""))
                    )
                    linhas.append(linha)

                else:
                    # Formato genérico
                    linha = "[" + bk_nome + "] " + nome_mercado + ": "
                    linha += " | ".join(str(k) + " @ " + str(v) for k, v in odd_vals.items())
                    linhas.append(linha)

            if linhas:
                break  # Apenas 1 bookmaker é suficiente

        return "\n".join(linhas[:6])
    except Exception:
        return ""


def buscar_todos_jogos_com_odds(odds_api_key):
    """Busca eventos e odds reais da odds-api.io."""
    jogos = []

    # 1. Busca eventos
    eventos, status = buscar_eventos(odds_api_key)

    if status == "invalida":
        st.error("ODDS_API_KEY invalida! Verifique nos Secrets do Streamlit.")
        return jogos
    if eventos is None:
        st.warning("Erro ao conectar na Odds API: " + status)
        return jogos
    if not eventos:
        st.warning("Nenhum evento retornado pela Odds API.")
        return jogos

    st.info("Odds API: " + str(len(eventos)) + " eventos encontrados. Buscando odds...")

    # 2. Busca odds para cada evento
    prog = st.progress(0)
    txt = st.empty()
    total = min(len(eventos), 50)

    for i, ev in enumerate(eventos[:50]):
        prog.progress((i + 1) / total)

        event_id = ev.get("id", "")
        home = ev.get("home", ev.get("home_team", ""))
        away = ev.get("away", ev.get("away_team", ""))
        liga_info = ev.get("league", {})
        liga = liga_info.get("name", "Futebol") if isinstance(liga_info, dict) else str(liga_info)
        horario = ev.get("date", ev.get("start_time", ""))

        if not home or not away:
            continue

        nome_jogo = str(home) + " x " + str(away)
        txt.text("Odds: " + nome_jogo)

        odds_txt = buscar_odds_evento(event_id, odds_api_key) if event_id else ""

        jogos.append({
            "nome": nome_jogo,
            "liga_nome": str(liga),
            "odds_txt": odds_txt,
            "tem_odds": bool(odds_txt),
            "id": str(event_id),
            "horario": str(horario)[:16].replace("T", " ") if horario else ""
        })

    prog.empty()
    txt.empty()

    com_odds = sum(1 for j in jogos if j["tem_odds"])
    st.success(
        "Odds API: " + str(len(jogos)) + " jogos | " +
        str(com_odds) + " com odds reais | " +
        str(len(jogos) - com_odds) + " sem odds"
    )
    return jogos


def varrer_jogos_api_football(api_key):
    """Busca jogos adicionais via API Football."""
    todos = []
    prog = st.progress(0)
    txt = st.empty()
    ligas = list(LIGAS_VARREDURA.items())
    for i, (nome, league_id) in enumerate(ligas):
        txt.text("Buscando " + nome + "...")
        prog.progress((i + 1) / len(ligas))
        try:
            jogos = buscar_jogos_da_liga(league_id)
            for j in jogos:
                j["liga_nome"] = nome
                j["tem_odds"] = False
                j["odds_txt"] = ""
            todos.extend(jogos)
        except Exception:
            pass
    prog.empty()
    txt.empty()
    return todos


def ia_proxima_entrada(jogos, odd_min, odd_max, num_entrada, banca, historico):
    from google import genai
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

    com_odds = [j for j in jogos if j.get("tem_odds")]
    sem_odds = [j for j in jogos if not j.get("tem_odds")]

    ctx_jogos = ""
    if com_odds:
        ctx_jogos += "JOGOS COM ODDS REAIS (" + str(len(com_odds)) + " jogos):\n"
        for j in com_odds[:25]:
            ctx_jogos += "\nJogo: " + j.get("nome", "")
            ctx_jogos += " | Liga: " + j.get("liga_nome", "")
            if j.get("horario"):
                ctx_jogos += " | " + j.get("horario", "")
            ctx_jogos += "\n" + j.get("odds_txt", "") + "\n"

    ctx_jogos += "\nOUTROS JOGOS - estime as odds (" + str(len(sem_odds)) + "):\n"
    for j in sem_odds[:10]:
        ctx_jogos += "- " + j.get("nome", "") + " | " + j.get("liga_nome", "") + "\n"

    ctx_hist = ""
    if historico:
        ctx_hist = "\nHistorico:\n"
        for h in historico:
            s = "GREEN" if h["status"] is True else "RED"
            for b in h.get("bilhete", []):
                ctx_hist += s + " | " + b.get("jogo", "") + " - " + b.get("mercado", "") + "\n"

    prompt = (
        "Voce e uma IA especialista em apostas esportivas para alavancagem progressiva segura.\n\n"
        "SITUACAO:\n"
        "Entrada #" + str(num_entrada) + "\n"
        "Banca: R$ " + str(round(banca, 2)) + "\n"
        "Odd alvo: entre " + str(odd_min) + "x e " + str(odd_max) + "x\n"
        + ctx_hist + "\n"
        + ctx_jogos + "\n"
        "INSTRUCOES:\n"
        "1. Selecione: simples (1 jogo) ou combinada (2 jogos de ligas diferentes)\n"
        "2. Odd final entre " + str(odd_min) + "x e " + str(odd_max) + "x\n"
        "3. Para jogos com odds reais: use os valores EXATOS da lista\n"
        "4. Para jogos sem odds: estime com seu conhecimento\n"
        "5. Prefira: Over 1.5 FT, Double Chance, Ambos Marcam, favorito\n"
        "6. Retorne sem_entrada=true SOMENTE se genuinamente nao tiver confianca\n\n"
        "Responda SOMENTE JSON sem markdown:\n"
        "{\"sem_entrada\": false, \"tipo\": \"simples\", \"odd_total\": 1.55, \"confianca\": 8, "
        "\"motivo_recusa\": \"\", "
        "\"bilhete\": [{\"jogo\": \"Time A x Time B\", \"liga\": \"Liga X\", "
        "\"mercado\": \"Over 1.5 gols FT\", \"odd\": 1.55, \"motivo\": \"Motivo curto\"}]}"
    )

    try:
        response = client.models.generate_content(
            model="models/gemini-3.1-flash-lite",
            contents=prompt
        )
        texto = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(texto)
    except Exception as e:
        return {"sem_entrada": True, "motivo": "Erro: " + str(e)}


def tela_alavancagem():
    init_estado()
    api_key = st.secrets["API_KEY"]
    odds_api_key = st.secrets.get("ODDS_API_KEY", "")

    st.subheader("Alavancagem Progressiva")
    st.markdown("IA analisa 1 entrada por vez com odds reais de Bet365, Unibet e mais.")

    if not st.session_state.alav_ativa:

        st.markdown("### Configurar")
        col1, col2, col3 = st.columns(3)
        with col1:
            banca = st.number_input("Banca inicial (R$)", min_value=1.0,
                                     max_value=10000.0,
                                     value=float(st.session_state.alav_banca_inicial), step=1.0)
        with col2:
            odd = st.number_input("Odd alvo", min_value=1.1, max_value=3.0,
                                   value=float(st.session_state.alav_odd_alvo), step=0.05)
        with col3:
            total = st.number_input("Total de entradas", min_value=3, max_value=20,
                                     value=int(st.session_state.alav_total_entradas), step=1)

        col4, col5 = st.columns(2)
        with col4:
            odd_min = st.slider("Odd minima", 1.2, 1.8,
                                float(st.session_state.alav_odd_min), 0.05)
        with col5:
            odd_max = st.slider("Odd maxima", 1.5, 2.5,
                                float(st.session_state.alav_odd_max), 0.05)

        st.markdown("### Preview")
        preview = calcular_tabela(banca, odd, int(total))
        cols = st.columns([1, 2, 2, 2, 2])
        for h, c in zip(["#", "Entrada", "Odd", "Retorno", "Lucro"], cols):
            c.markdown("**" + h + "**")
        for row in preview:
            cols = st.columns([1, 2, 2, 2, 2])
            cols[0].write(str(row["entrada"]))
            cols[1].write("R$ " + str(row["valor"]))
            cols[2].write(str(row["odd"]) + "x")
            cols[3].write("R$ " + str(row["retorno"]))
            cols[4].write("+R$ " + str(row["lucro"]))

        lucro_total = round(preview[-1]["retorno"] - banca, 2)
        st.success("Acertando tudo: R$ " + str(preview[-1]["retorno"]) +
                   " | Lucro: +R$ " + str(lucro_total))

        st.markdown("---")
        if st.button("INICIAR", use_container_width=True):
            st.session_state.alav_banca_inicial = banca
            st.session_state.alav_odd_alvo = odd
            st.session_state.alav_total_entradas = int(total)
            st.session_state.alav_odd_min = odd_min
            st.session_state.alav_odd_max = odd_max

            todos_jogos = []

            if odds_api_key:
                jogos_odds = buscar_todos_jogos_com_odds(odds_api_key)
                todos_jogos.extend(jogos_odds)
            else:
                st.warning("ODDS_API_KEY nao configurada nos Secrets.")

            with st.spinner("Buscando jogos adicionais via API Football..."):
                jogos_af = varrer_jogos_api_football(api_key)
                nomes_ja = {j.get("nome", "") for j in todos_jogos}
                novos = [j for j in jogos_af if j.get("nome", "") not in nomes_ja]
                todos_jogos.extend(novos)

            if not todos_jogos:
                st.error("Nenhum jogo encontrado.")
                return

            com_odds = sum(1 for j in todos_jogos if j.get("tem_odds"))
            st.success(str(len(todos_jogos)) + " jogos no total | " +
                       str(com_odds) + " com odds reais")

            st.session_state.alav_jogos = todos_jogos
            tabela = calcular_tabela(banca, odd, int(total))
            st.session_state.alav_entradas = tabela
            st.session_state.alav_ativa = True
            st.session_state.alav_entrada_atual = 0
            st.rerun()

    else:
        entradas = st.session_state.alav_entradas
        atual = st.session_state.alav_entrada_atual
        jogos = st.session_state.alav_jogos

        greens = sum(1 for e in entradas if e["status"] is True)
        reds = sum(1 for e in entradas if e["status"] is False)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Greens", greens)
        col2.metric("Reds", reds)
        col3.metric("Pendentes", sum(1 for e in entradas if e["status"] is None))

        banca_atual = st.session_state.alav_banca_inicial
        for e in entradas:
            if e["status"] is True:
                banca_atual = e["retorno"]
            elif e["status"] is False:
                banca_atual = 0
                break
        col4.metric("Banca Atual", "R$ " + str(round(banca_atual, 2)))

        st.markdown("---")

        if atual < len(entradas) and entradas[atual]["status"] is None:
            entrada_info = entradas[atual]

            if not entrada_info.get("bilhete"):
                with st.spinner("IA analisando odds e escolhendo entrada #" + str(atual + 1) + "..."):
                    historico = [e for e in entradas if e["status"] is not None]
                    resultado = ia_proxima_entrada(
                        jogos,
                        st.session_state.alav_odd_min,
                        st.session_state.alav_odd_max,
                        atual + 1,
                        entrada_info["valor"],
                        historico
                    )

                if resultado.get("sem_entrada"):
                    st.warning("**Sem entrada com confianca suficiente**")
                    motivo = resultado.get("motivo_recusa") or resultado.get("motivo", "")
                    if motivo:
                        st.info("Motivo: " + motivo)
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Tentar novamente", use_container_width=True):
                            st.rerun()
                    with c2:
                        if st.button("Nova Alavancagem", key="nova_sem", use_container_width=True):
                            for k in ["alav_ativa", "alav_entradas", "alav_entrada_atual", "alav_jogos"]:
                                st.session_state.pop(k, None)
                            st.rerun()
                    return

                odd_total = float(resultado.get("odd_total", st.session_state.alav_odd_alvo))
                retorno = round(entrada_info["valor"] * odd_total, 2)
                st.session_state.alav_entradas[atual]["bilhete"] = resultado.get("bilhete", [])
                st.session_state.alav_entradas[atual]["odd"] = odd_total
                st.session_state.alav_entradas[atual]["retorno"] = retorno
                st.session_state.alav_entradas[atual]["lucro"] = round(retorno - entrada_info["valor"], 2)
                st.session_state.alav_entradas[atual]["confianca"] = resultado.get("confianca", 0)
                st.session_state.alav_entradas[atual]["tipo"] = resultado.get("tipo", "simples")
                st.rerun()

            entrada_info = entradas[atual]
            tipo = entrada_info.get("tipo", "simples")
            conf = entrada_info.get("confianca", 0)

            st.markdown("#### Entrada #" + str(entrada_info["entrada"]) +
                        " — " + ("Combinada 2 jogos" if tipo == "combinada" else "Simples"))
            st.markdown(
                "**R$ " + str(entrada_info["valor"]) + "** @ **" +
                str(entrada_info["odd"]) + "x** → **R$ " +
                str(entrada_info["retorno"]) + "**" +
                "  |  Confianca: " + str(conf) + "/10"
            )

            for b in entrada_info.get("bilhete", []):
                st.info(
                    "**" + b.get("jogo", "") + "**  |  " + b.get("liga", "") + "\n\n" +
                    "Aposta: **" + b.get("mercado", "") + "** @ " + str(b.get("odd", "")) + "\n\n" +
                    "Motivo: " + b.get("motivo", "")
                )

            c1, c2 = st.columns(2)
            with c1:
                if st.button("GREEN - Acertei!", key="green_" + str(atual), use_container_width=True):
                    st.session_state.alav_entradas[atual]["status"] = True
                    st.session_state.alav_entradas[atual]["data"] = datetime.now().strftime("%d/%m %H:%M")
                    st.session_state.alav_entrada_atual = atual + 1
                    st.rerun()
            with c2:
                if st.button("RED - Errei", key="red_" + str(atual), use_container_width=True):
                    st.session_state.alav_entradas[atual]["status"] = False
                    st.session_state.alav_entradas[atual]["data"] = datetime.now().strftime("%d/%m %H:%M")
                    st.session_state.alav_entrada_atual = len(entradas)
                    st.rerun()

        st.markdown("---")
        st.markdown("### Historico")

        for entrada in entradas:
            if entrada["status"] is None:
                continue
            linha = "#" + str(entrada["entrada"]) + " | R$ " + str(entrada["valor"]) + " -> R$ " + str(entrada["retorno"])
            for b in entrada.get("bilhete", []):
                linha += " | " + b.get("jogo", "") + " - " + b.get("mercado", "")
            if entrada["status"] is True:
                st.success(linha)
            else:
                st.error(linha)

        if atual >= len(entradas):
            if all(e["status"] is True for e in entradas):
                retorno_final = entradas[-1]["retorno"]
                lucro = round(retorno_final - st.session_state.alav_banca_inicial, 2)
  
