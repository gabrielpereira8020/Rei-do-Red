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


def buscar_odds_fixture(fixture_id, api_key):
    """Busca odds tentando varios bookmakers."""
    # Tenta vários bookmakers: bet365=6, Unibet=5, William Hill=7, Bwin=4
    bookmakers = [6, 5, 7, 4, 8, 11]
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }
    mercados_ok = [
        "Match Winner", "Goals Over/Under", "Both Teams Score",
        "Double Chance", "First Half Goals", "Asian Handicap",
        "Goals Over/Under First Half"
    ]

    for bk_id in bookmakers:
        try:
            url = "https://v3.football.api-sports.io/odds?fixture=" + str(fixture_id) + "&bookmaker=" + str(bk_id)
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json().get("response", [])
            if not data:
                continue

            linhas = []
            for item in data:
                for bk in item.get("bookmakers", []):
                    for bet in bk.get("bets", []):
                        nome = bet.get("name", "")
                        if nome in mercados_ok:
                            vals = bet.get("values", [])
                            linha = nome + ": " + " | ".join(
                                str(v.get("value", "")) + " @ " + str(v.get("odd", ""))
                                for v in vals
                            )
                            linhas.append(linha)

            if linhas:
                return "\n".join(linhas[:10])
        except Exception:
            continue

    return ""


def varrer_jogos(api_key):
    todos = []
    ligas = list(LIGAS_VARREDURA.items())
    prog = st.progress(0)
    txt = st.empty()
    for i, (nome, league_id) in enumerate(ligas):
        txt.text("Buscando " + nome + "...")
        prog.progress((i + 1) / len(ligas))
        try:
            jogos = buscar_jogos_da_liga(league_id)
            for j in jogos:
                j["liga_nome"] = nome
                todos.append(j)
        except Exception:
            pass
    prog.empty()
    txt.empty()
    return todos


def buscar_odds_todos(jogos, api_key):
    resultado = []
    total = min(len(jogos), 50)
    if total == 0:
        return resultado

    prog = st.progress(0)
    txt = st.empty()

    for i, j in enumerate(jogos[:50]):
        txt.text("Buscando odds: " + j.get("nome", "") + "...")
        prog.progress((i + 1) / total)
        odds_txt = buscar_odds_fixture(j["id"], api_key)
        j["odds_txt"] = odds_txt if odds_txt else "Sem odds - usar conhecimento geral"
        resultado.append(j)

    prog.empty()
    txt.empty()
    return resultado


def ia_proxima_entrada(jogos, odd_min, odd_max, num_entrada, banca, historico):
    from google import genai
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

    # Separa jogos com e sem odds
    com_odds = [j for j in jogos if "Sem odds" not in j.get("odds_txt", "Sem odds")]
    sem_odds = [j for j in jogos if "Sem odds" in j.get("odds_txt", "Sem odds")]

    ctx_jogos = ""
    for j in com_odds[:20]:
        ctx_jogos += "\nJogo: " + j.get("nome", "") + " | Liga: " + j.get("liga_nome", "") + "\n"
        ctx_jogos += j.get("odds_txt", "") + "\n"

    if sem_odds and len(com_odds) < 5:
        ctx_jogos += "\nJogos sem odds na API (use seu conhecimento para estimar):\n"
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
        "JOGOS DISPONIVEIS:\n"
        + ctx_jogos + "\n"
        "INSTRUCOES:\n"
        "- Selecione 1 bilhete: simples (1 jogo) ou combinada (2 jogos de ligas diferentes)\n"
        "- Odd combinada deve ficar entre " + str(odd_min) + "x e " + str(odd_max) + "x\n"
        "- Para jogos com odds reais: use exatamente os valores listados\n"
        "- Para jogos sem odds: estime com base no seu conhecimento\n"
        "- Prefira: Over 0.5 HT, Over 1.5 FT, Double Chance, Ambos Marcam\n"
        "- Se realmente nao houver nenhuma opcao segura, retorne sem_entrada true\n\n"
        "Responda SOMENTE JSON sem markdown:\n"
        "{\"sem_entrada\": false, \"tipo\": \"simples\", \"odd_total\": 1.55, \"confianca\": 8, "
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

    st.subheader("Alavancagem Progressiva")
    st.markdown("IA analisa 1 entrada por vez com odds reais. Bilhetes simples ou combinados de 2 jogos.")

    if not st.session_state.alav_ativa:

        st.markdown("### Configurar")
        col1, col2, col3 = st.columns(3)
        with col1:
            banca = st.number_input("Banca inicial (R$)", min_value=1.0,
                                     max_value=10000.0, value=float(st.session_state.alav_banca_inicial), step=1.0)
        with col2:
            odd = st.number_input("Odd alvo", min_value=1.1, max_value=3.0,
                                   value=float(st.session_state.alav_odd_alvo), step=0.05)
        with col3:
            total = st.number_input("Total de entradas", min_value=3, max_value=20,
                                     value=int(st.session_state.alav_total_entradas), step=1)

        col4, col5 = st.columns(2)
        with col4:
            odd_min = st.slider("Odd minima", 1.2, 1.8, float(st.session_state.alav_odd_min), 0.05)
        with col5:
            odd_max = st.slider("Odd maxima", 1.5, 2.5, float(st.session_state.alav_odd_max), 0.05)

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
        st.success(
            "Acertando tudo: R$ " + str(preview[-1]["retorno"]) +
            " | Lucro: +R$ " + str(lucro_total)
        )

        st.markdown("---")
        if st.button("INICIAR", use_container_width=True):
            st.session_state.alav_banca_inicial = banca
            st.session_state.alav_odd_alvo = odd
            st.session_state.alav_total_entradas = int(total)
            st.session_state.alav_odd_min = odd_min
            st.session_state.alav_odd_max = odd_max

            with st.spinner("Varrendo jogos e buscando odds..."):
                jogos = varrer_jogos(api_key)
                if not jogos:
                    st.error("Nenhum jogo encontrado hoje.")
                    return
                jogos_com_odds = buscar_odds_todos(jogos, api_key)
                st.session_state.alav_jogos = jogos_com_odds

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

        # Entrada atual
        if atual < len(entradas) and entradas[atual]["status"] is None:
            entrada_info = entradas[atual]

            if not entrada_info.get("bilhete"):
                with st.spinner("IA analisando entrada #" + str(atual + 1) + "..."):
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
                    st.warning("**Sem entrada segura agora**")
                    st.info(resultado.get("motivo", "Nenhum jogo adequado encontrado."))
                    st.caption("Recomendacao: Pause e tente mais tarde ou amanha.")
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        if st.button("Tentar novamente", use_container_width=True):
                            st.rerun()
                    with col_t2:
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

            st.markdown(
                "#### Entrada #" + str(entrada_info["entrada"]) +
                " — " + ("Combinada 2 jogos" if tipo == "combinada" else "Simples")
            )
            st.markdown(
                "**R$ " + str(entrada_info["valor"]) + "** @ **" +
                str(entrada_info["odd"]) + "x** → **R$ " + str(entrada_info["retorno"]) + "**" +
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
