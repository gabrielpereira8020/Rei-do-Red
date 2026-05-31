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

# IDs dos esportes de futebol na odds-api.io
FOOTBALL_SPORT_IDS = [1]  # 1 = Soccer/Football


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


def buscar_jogos_odds_api(odds_api_key):
    """
    Busca jogos de futebol com odds reais via odds-api.io
    """
    jogos = []
    headers = {"Authorization": "Bearer " + odds_api_key}

    try:
        # Busca eventos de futebol
        url = ODDS_API_BASE + "/events?sport_id=1&status=upcoming"
        r = requests.get(url, headers=headers, timeout=15)

        if r.status_code == 401:
            st.error("Chave ODDS_API_KEY invalida. Verifique nos Secrets.")
            return []

        if r.status_code != 200:
            # Tenta endpoint alternativo
            url2 = ODDS_API_BASE + "/sports/1/events"
            r = requests.get(url2, headers=headers, timeout=15)
            if r.status_code != 200:
                return []

        data = r.json()

        # Pode vir como lista ou dict com 'data'
        eventos = data if isinstance(data, list) else data.get("data", data.get("events", []))

        for ev in eventos[:50]:
            home = ev.get("home_team", ev.get("home", ev.get("home_name", "")))
            away = ev.get("away_team", ev.get("away", ev.get("away_name", "")))
            if not home or not away:
                continue

            nome_jogo = str(home) + " x " + str(away)
            liga = ev.get("league", ev.get("competition", ev.get("league_name", "Futebol")))
            if isinstance(liga, dict):
                liga = liga.get("name", "Futebol")

            # Pega odds
            odds_raw = ev.get("odds", ev.get("markets", []))
            odds_texto = ""

            if isinstance(odds_raw, dict):
                # Formato dict de mercados
                for mercado, valores in odds_raw.items():
                    if mercado in ["1x2", "h2h", "match_winner", "over_under", "btts", "both_teams_score"]:
                        if isinstance(valores, dict):
                            linha = mercado + ": "
                            linha += " | ".join(str(k) + " @ " + str(v) for k, v in valores.items())
                            odds_texto += linha + "\n"
                        elif isinstance(valores, list):
                            linha = mercado + ": "
                            for v in valores[:3]:
                                if isinstance(v, dict):
                                    nome = v.get("name", v.get("outcome", ""))
                                    odd = v.get("odd", v.get("price", v.get("odds", "")))
                                    linha += str(nome) + " @ " + str(odd) + " | "
                            odds_texto += linha.rstrip(" | ") + "\n"

            elif isinstance(odds_raw, list):
                for market in odds_raw[:5]:
                    if isinstance(market, dict):
                        m_nome = market.get("name", market.get("key", ""))
                        outcomes = market.get("outcomes", market.get("values", []))
                        if outcomes:
                            linha = str(m_nome) + ": "
                            for o in outcomes[:3]:
                                if isinstance(o, dict):
                                    n = o.get("name", o.get("outcome", ""))
                                    p = o.get("price", o.get("odd", o.get("odds", "")))
                                    linha += str(n) + " @ " + str(p) + " | "
                            odds_texto += linha.rstrip(" | ") + "\n"

            jogos.append({
                "nome": nome_jogo,
                "liga_nome": str(liga),
                "odds_txt": odds_texto.strip() if odds_texto else "",
                "tem_odds": bool(odds_texto.strip()),
                "id": ev.get("id", 0),
                "horario": str(ev.get("start_time", ev.get("commence_time", "")))[:16]
            })

    except Exception as e:
        st.warning("Erro ao buscar odds: " + str(e))

    return jogos


def varrer_jogos_api_football(api_key):
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

    if sem_odds:
        ctx_jogos += "\nOUTROS JOGOS (" + str(len(sem_odds)) + " jogos - estime as odds):\n"
        for j in sem_odds[:15]:
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
        "1. Analise TODOS os jogos listados\n"
        "2. Escolha: simples (1 jogo) ou combinada (2 jogos de ligas diferentes)\n"
        "3. Odd final entre " + str(odd_min) + "x e " + str(odd_max) + "x\n"
        "4. Para jogos com odds reais: use os valores exatos\n"
        "5. Para jogos sem odds: estime baseado no seu conhecimento\n"
        "6. Prefira: Over 0.5 HT, Over 1.5 FT, Double Chance, Ambos Marcam\n"
        "7. Retorne sem_entrada=true SOMENTE se genuinamente nao tiver confianca\n\n"
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
    st.markdown("IA analisa 1 entrada por vez com odds reais de 250+ casas de apostas.")

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
                with st.spinner("Buscando odds reais de 250+ casas de apostas..."):
                    jogos_odds = buscar_jogos_odds_api(odds_api_key)
                    todos_jogos.extend(jogos_odds)
                    com = sum(1 for j in jogos_odds if j.get("tem_odds"))
                    st.info("Odds API: " + str(len(jogos_odds)) + " jogos | " +
                            str(com) + " com odds reais")
            else:
                st.warning("ODDS_API_KEY nao encontrada nos Secrets.")

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
                with st.spinner("IA analisando odds e escolhendo melhor entrada #" + str(atual + 1) + "..."):
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
                    st.caption("A IA analisou todos os jogos e nao encontrou valor. Recomendacao: pause hoje.")
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
                st.success("COMPLETO! R$ " + str(retorno_final) + " | Lucro: +R$ " + str(lucro))
            else:
                st.error("Encerrada. Recomece com a banca inicial.")

        if st.button("Nova Alavancagem", use_container_width=True):
            for k in ["alav_ativa", "alav_entradas", "alav_entrada_atual", "alav_jogos"]:
                st.session_state.pop(k, None)
            st.rerun()
