import streamlit as st
import json
from datetime import datetime

from odds_engine import buscar_jogos_com_odds
from stats_engine import init as stats_init, montar_contexto_stats
from ranking_engine import ranquear_jogos, filtrar_por_confianca
from historico_engine import salvar_entrada, exibir_painel_aprendizado


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
        "alav_confianca_min": 70,
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


def ia_proxima_entrada(jogos_ranqueados, odd_min, odd_max, num_entrada, banca, historico):
    from google import genai
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

    if not jogos_ranqueados:
        return {"sem_entrada": True, "motivo": "Nenhum jogo passou pelo filtro de confianca minima."}

    # Monta contexto com os top 20 jogos ranqueados
    ctx = "TOP JOGOS RANQUEADOS (odds reais + estatisticas + score de confianca):\n"
    for j in jogos_ranqueados[:20]:
        ctx += f"\n#{j['score']}/100 | {j['nome']} | {j['liga_nome']}"
        if j.get("horario"):
            ctx += f" | {j['horario']}"
        ctx += f"\nOdds reais: {j.get('odds_txt','')}"
        if j.get("detalhes_score"):
            ctx += f"\nMotivos do score: {', '.join(j['detalhes_score'][:3])}"
        # Adiciona stats se disponíveis
        stats_txt = j.get("stats_txt", "")
        if stats_txt:
            ctx += f"\n{stats_txt}"
        ctx += "\n"

    ctx_hist = ""
    if historico:
        ctx_hist = "\nHistorico desta alavancagem:\n"
        for h in historico:
            s = "GREEN" if h["status"] is True else "RED"
            for b in h.get("bilhete", []):
                ctx_hist += f"  {s} | {b.get('jogo','')} - {b.get('mercado','')} @ {b.get('odd','')}\n"

    prompt = (
        "Voce e uma IA especialista em apostas esportivas para alavancagem progressiva segura.\n\n"
        "SITUACAO:\n"
        f"Entrada #{num_entrada}\n"
        f"Banca: R$ {round(banca, 2)}\n"
        f"Odd alvo: entre {odd_min}x e {odd_max}x\n"
        + ctx_hist + "\n"
        + ctx + "\n"
        "INSTRUCOES OBRIGATORIAS:\n"
        "1. Use APENAS os jogos listados acima - todos tem odds reais confirmadas\n"
        "2. Use as odds EXATAS da lista - NUNCA invente valores\n"
        "3. Selecione: simples (1 jogo) ou combinada (2 jogos de ligas DIFERENTES)\n"
        f"4. Odd final DEVE estar entre {odd_min}x e {odd_max}x\n"
        "5. Priorize jogos com score mais alto (maior confianca)\n"
        "6. Prefira mercados: Double Chance, Over 0.5 HT, Over 1.5 FT, favorito claro\n"
        "7. EVITE: Placar correto, Handicap agressivo\n"
        "8. Retorne sem_entrada=true SOMENTE se nenhum jogo tiver confianca real\n\n"
        "Responda SOMENTE JSON sem markdown:\n"
        "{\"sem_entrada\": false, \"tipo\": \"simples\", \"odd_total\": 1.45, \"confianca\": 85, "
        "\"motivo_recusa\": \"\", "
        "\"bilhete\": [{\"jogo\": \"Time A x Time B\", \"liga\": \"Liga X\", "
        "\"mercado\": \"Double Chance 1X\", \"odd\": 1.45, \"motivo\": \"Score 88/100, mandante forte em casa\"}]}"
    )

    try:
        response = client.models.generate_content(
            model="models/gemini-3.1-flash-lite",
            contents=prompt
        )
        texto = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(texto)
    except Exception as e:
        return {"sem_entrada": True, "motivo": "Erro IA: " + str(e)}


def tela_alavancagem(supabase=None):
    init_estado()
    api_key = st.secrets["API_KEY"]
    odds_api_key = st.secrets.get("ODDS_API_KEY", "")

    # Inicializa stats engine com a chave da API Football
    stats_init(api_key)

    tab1, tab2 = st.tabs(["🚀 Alavancagem", "📊 Painel de Aprendizado"])

    with tab2:
        if supabase:
            exibir_painel_aprendizado(supabase)
        else:
            st.info("Conecte o Supabase para ver o painel de aprendizado.")

    with tab1:
        st.subheader("Alavancagem Progressiva")
        st.markdown("IA usa **odds reais + estatísticas + ranking de confiança**. Apenas jogos futuros com odds confirmadas.")

        if not st.session_state.alav_ativa:

            st.markdown("### ⚙️ Configurar")
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

            col4, col5, col6 = st.columns(3)
            with col4:
                odd_min = st.slider("Odd minima", 1.2, 1.8,
                                    float(st.session_state.alav_odd_min), 0.05)
            with col5:
                odd_max = st.slider("Odd maxima", 1.5, 2.5,
                                    float(st.session_state.alav_odd_max), 0.05)
            with col6:
                confianca_min = st.slider("Score minimo (0-100)", 50, 95,
                                          int(st.session_state.alav_confianca_min), 5)
                st.caption("Bloqueia jogos com score abaixo desse valor")

            st.markdown("### 👁️ Preview")
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
            if st.button("🚀 INICIAR — Buscar jogos e ranquear", use_container_width=True):
                if not odds_api_key:
                    st.error("ODDS_API_KEY nao configurada nos Secrets.")
                    return

                st.session_state.alav_banca_inicial = banca
                st.session_state.alav_odd_alvo = odd
                st.session_state.alav_total_entradas = int(total)
                st.session_state.alav_odd_min = odd_min
                st.session_state.alav_odd_max = odd_max
                st.session_state.alav_confianca_min = confianca_min

                # PASSO 1: Busca jogos com odds reais
                prog = st.progress(0)
                txt = st.empty()

                def update_progress(i, total_ev, nome):
                    prog.progress(i / total_ev)
                    txt.text("Buscando odds: " + nome)

                jogos, status = buscar_jogos_com_odds(odds_api_key, update_progress)
                prog.empty()
                txt.empty()

                if status != "ok" and not jogos:
                    st.error("Erro: " + status)
                    return

                st.info("Odds reais: " + str(len(jogos)) + " jogos encontrados")

                # PASSO 2: Busca estatísticas para cada jogo
                st.write("📊 Buscando estatísticas dos times...")
                prog2 = st.progress(0)
                for i, jogo in enumerate(jogos):
                    prog2.progress((i + 1) / max(len(jogos), 1))
                    stats_txt = montar_contexto_stats(jogo)
                    jogo["stats_txt"] = stats_txt
                prog2.empty()

                # PASSO 3: Rankeia os jogos
                jogos_ranqueados = ranquear_jogos(jogos, odd_min, odd_max)
                jogos_filtrados = filtrar_por_confianca(jogos_ranqueados, confianca_min)

                st.success(
                    str(len(jogos_ranqueados)) + " jogos ranqueados | " +
                    str(len(jogos_filtrados)) + " acima do score minimo (" + str(confianca_min) + ")"
                )

                # Mostra top 5 ranqueados
                if jogos_filtrados:
                    st.markdown("**🏆 Top jogos selecionados:**")
                    for j in jogos_filtrados[:5]:
                        st.markdown(
                            f"**#{j['score']}/100** | {j['nome']} | {j['liga_nome']} | "
                            f"Melhor odd: {j.get('melhor_odd','?')} ({j.get('faixa_odd','?')})"
                        )

                if not jogos_filtrados:
                    st.warning("Nenhum jogo passou pelo filtro de confianca (" + str(confianca_min) + "). "
                               "Tente reduzir o score minimo.")
                    return

                st.session_state.alav_jogos = jogos_filtrados
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
            col1.metric("✅ Greens", greens)
            col2.metric("❌ Reds", reds)
            col3.metric("⏳ Pendentes", sum(1 for e in entradas if e["status"] is None))

            banca_atual = st.session_state.alav_banca_inicial
            for e in entradas:
                if e["status"] is True:
                    banca_atual = e["retorno"]
                elif e["status"] is False:
                    banca_atual = 0
                    break
            col4.metric("💰 Banca Atual", "R$ " + str(round(banca_atual, 2)))

            st.markdown("---")

            if atual < len(entradas) and entradas[atual]["status"] is None:
                entrada_info = entradas[atual]

                if not entrada_info.get("bilhete"):
                    with st.spinner("IA analisando ranking e escolhendo entrada #" + str(atual + 1) + "..."):
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
                cor_conf = "#22c55e" if conf >= 80 else "#f59e0b" if conf >= 65 else "#ef4444"

                st.markdown("#### Entrada #" + str(entrada_info["entrada"]) +
                            " — " + ("Combinada 2 jogos" if tipo == "combinada" else "Simples"))
                st.markdown(
                    "**R$ " + str(entrada_info["valor"]) + "** @ **" +
                    str(entrada_info["odd"]) + "x** → **R$ " +
                    str(entrada_info["retorno"]) + "**"
                )
                st.markdown(
                    f"<span style='color:{cor_conf};font-weight:700'>Score de confianca: {conf}/100</span>",
                    unsafe_allow_html=True
                )

                for b in entrada_info.get("bilhete", []):
                    st.info(
                        "**" + b.get("jogo", "") + "** | " + b.get("liga", "") + "\n\n" +
                        "Aposta: **" + b.get("mercado", "") + "** @ " + str(b.get("odd", "")) + "\n\n" +
                        "Motivo: " + b.get("motivo", "")
                    )

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ GREEN - Acertei!", key="green_" + str(atual), use_container_width=True):
                        st.session_state.alav_entradas[atual]["status"] = True
                        st.session_state.alav_entradas[atual]["data"] = datetime.now().strftime("%d/%m %H:%M")
                        st.session_state.alav_entrada_atual = atual + 1
                        # Salva no histórico
                        if supabase:
                            for b in entrada_info.get("bilhete", []):
                                salvar_entrada(supabase, {
                                    "entrada": entrada_info["entrada"],
                                    "jogo": b.get("jogo", ""),
                                    "mercado": b.get("mercado", ""),
                                    "odd": b.get("odd", 0),
                                    "liga": b.get("liga", ""),
                                    "resultado": "GREEN",
                                    "valor": entrada_info["valor"],
                                    "retorno": entrada_info["retorno"],
                                    "confianca": conf,
                                })
                        st.rerun()
                with c2:
                    if st.button("❌ RED - Errei", key="red_" + str(atual), use_container_width=True):
                        st.session_state.alav_entradas[atual]["status"] = False
                        st.session_state.alav_entradas[atual]["data"] = datetime.now().strftime("%d/%m %H:%M")
                        st.session_state.alav_entrada_atual = len(entradas)
                        if supabase:
                            for b in entrada_info.get("bilhete", []):
                                salvar_entrada(supabase, {
                                    "entrada": entrada_info["entrada"],
                                    "jogo": b.get("jogo", ""),
                                    "mercado": b.get("mercado", ""),
                                    "odd": b.get("odd", 0),
                                    "liga": b.get("liga", ""),
                                    "resultado": "RED",
                                    "valor": entrada_info["valor"],
                                    "retorno": 0,
                                    "confianca": conf,
                                })
                        st.rerun()

            st.markdown("---")
            st.markdown("### 📋 Histórico desta alavancagem")

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
                    st.success("🏆 COMPLETO! R$ " + str(retorno_final) + " | Lucro: +R$ " + str(lucro))
                else:
                    st.error("❌ Encerrada. Recomece com a banca inicial.")

            if st.button("🔄 Nova Alavancagem", use_container_width=True):
                for k in ["alav_ativa", "alav_entradas", "alav_entrada_atual", "alav_jogos"]:
                    st.session_state.pop(k, None)
                st.rerun()
                
