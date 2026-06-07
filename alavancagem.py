"""
alavancagem.py
==============
Motor principal da Alavancagem Progressiva.

NOVA ARQUITETURA — 4 ETAPAS:

  ETAPA 1 — API Football busca jogos + stats reais
            ↓
  ETAPA 2 — ranking_engine pontua por estatísticas (sem odds)
            ↓
  ETAPA 3 — IA escolhe mercado ideal para cada jogo aprovado
            ↓
  ETAPA 4 — Odds API busca odds APENAS dos jogos aprovados pela IA
            ↓
  ETAPA 5 — IA valida a odd real e monta o bilhete final

Correções aplicadas:
  - Debug prints removidos
  - supabase passado corretamente
  - Contagem real de chamadas de API
  - Score mínimo configurável com aviso explicativo
"""

import streamlit as st
import json
from datetime import datetime

from odds_engine_alav import buscar_odds_evento_por_nome, buscar_odds_evento
from stats_engine_alav import init as stats_init, buscar_jogos_futuros_api_football, enriquecer_stats_jogo
from ranking_engine_alav import ranquear_jogos_por_stats, filtrar_top_para_ia, validar_odd_para_entrada
from historico_engine_alav import salvar_entrada, exibir_painel_aprendizado


# ─────────────────────────────────────────────
# ESTADO
# ─────────────────────────────────────────────

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
        "alav_confianca_min": 65,
        "alav_log_etapas": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def log_etapa(msg):
    if "alav_log_etapas" not in st.session_state:
        st.session_state["alav_log_etapas"] = []
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state["alav_log_etapas"].append(f"[{ts}] {msg}")


# ─────────────────────────────────────────────
# TABELA DE ALAVANCAGEM
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# ETAPA 2 — IA ESCOLHE MERCADO (sem odds ainda)
# ─────────────────────────────────────────────

def ia_analisar_lote(jogos):
    """
    Analisa todos os jogos em UMA unica chamada Gemini.
    Respeita o limite de 20 chamadas/min e compara jogos entre si.
    """
    from google import genai
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

    ctx = ""
    for i, jogo in enumerate(jogos):
        stats = jogo.get("stats_txt", "Sem dados")[:400]
        ctx += "JOGO " + str(i+1) + ": " + jogo.get("casa","?") + " x " + jogo.get("fora","?")
        ctx += " | " + jogo.get("liga_nome","") + "\n"
        ctx += stats + "\n\n"

    n = len(jogos)
    prompt = (
        "Voce e um analista esportivo especialista em apostas seguras. "
        "Analise os jogos abaixo e para CADA UM escolha o mercado mais seguro. "
        "Compare os jogos entre si e priorize os que tem dados mais confiaveis.\n\n"
        + ctx +
        "MERCADOS PERMITIDOS: Over 0.5 HT | Over 1.5 FT | Over 2.5 FT | "
        "Double Chance 1X | Double Chance X2 | Ambos Marcam Sim | Vitoria Mandante | Under 4.5 FT\n\n"
        "REGRAS: 1) Sem dados suficientes = recusar true. "
        "2) Confianca abaixo de 72 = recusar true. "
        "3) Prefira mercados com odds entre 1.20 e 2.00.\n\n"
        "Responda SOMENTE JSON array com " + str(n) + " objetos na mesma ordem sem markdown: "
        '[{"jogo":1,"mercado":"Over 1.5 FT","confianca":82,"motivo":"mandante ofensivo","recusar":false}]'
    )

    try:
        response = client.models.generate_content(
            model="models/gemini-3.1-flash-lite",
            contents=prompt
        )
        texto = response.text.strip().replace("```json", "").replace("```", "").strip()
        resultados = json.loads(texto)
        if isinstance(resultados, list) and len(resultados) == n:
            return resultados
        mapa = {r.get("jogo", i+1): r for i, r in enumerate(resultados)}
        return [mapa.get(i+1, {"recusar": True, "confianca": 0, "motivo": "sem retorno"}) for i in range(n)]
    except Exception as e:
        return [{"mercado": "", "confianca": 0, "motivo": str(e), "recusar": True} for _ in jogos]



# ─────────────────────────────────────────────
# ETAPA 5 — IA MONTA BILHETE FINAL
# ─────────────────────────────────────────────

def ia_montar_bilhete_final(jogos_aprovados, odd_min, odd_max, num_entrada, banca, historico):
    """
    Recebe jogos que passaram em todas as etapas (stats + IA + odds confirmadas).
    Monta o bilhete final: simples ou combinada.
    """
    from google import genai
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

    if not jogos_aprovados:
        return {"sem_entrada": True, "motivo": "Nenhum jogo passou por todas as etapas."}

    ctx = "JOGOS APROVADOS (stats + IA + odds confirmadas):\n\n"
    for j in jogos_aprovados:
        ctx += (
            f"#{j.get('score', 0)}/100 | {j['nome']} | {j.get('liga_nome', '')}\n"
            f"Mercado IA: {j.get('ia_mercado', '')} | Confiança IA: {j.get('ia_confianca', 0)}/100\n"
            f"Odd real confirmada: {j.get('melhor_odd', '?')}\n"
            f"Motivo IA: {j.get('ia_motivo', '')}\n"
            f"{j.get('stats_txt', '')[:300]}\n\n"
        )

    hist_txt = ""
    if historico:
        hist_txt = "HISTÓRICO DESTA ALAVANCAGEM:\n"
        for h in historico:
            s = "GREEN" if h["status"] is True else "RED"
            for b in h.get("bilhete", []):
                hist_txt += f"  {s} | {b.get('jogo','')} — {b.get('mercado','')} @ {b.get('odd','')}\n"

    prompt = (
        "Você é um especialista em alavancagem progressiva esportiva.\n\n"
        "SITUAÇÃO:\n"
        f"Entrada #{num_entrada} | Banca: R$ {round(banca, 2)}\n"
        f"Odd alvo: entre {odd_min}x e {odd_max}x\n\n"
        + hist_txt + "\n"
        + ctx
        + "INSTRUÇÕES:\n"
        "1. Use SOMENTE os jogos listados acima — todos têm odds confirmadas\n"
        "2. Use as odds EXATAS da lista — NUNCA invente valores\n"
        "3. Simples = 1 jogo. Combinada = 2 jogos de ligas DIFERENTES\n"
        f"4. Odd final DEVE estar entre {odd_min}x e {odd_max}x\n"
        "5. Priorize jogos com maior confiança IA\n"
        "6. Se nenhum bilhete atingir a faixa de odd, retorne sem_entrada=true\n\n"
        "Responda SOMENTE JSON sem markdown:\n"
        "{\"sem_entrada\": false, \"tipo\": \"simples\", \"odd_total\": 1.45, "
        "\"confianca\": 85, \"motivo_recusa\": \"\", "
        "\"bilhete\": [{\"jogo\": \"Time A x Time B\", \"liga\": \"Liga X\", "
        "\"mercado\": \"Over 1.5 FT\", \"odd\": 1.45, "
        "\"motivo\": \"mandante marca muito em casa\"}]}"
    )

    try:
        response = client.models.generate_content(
            model="models/gemini-3.1-flash-lite",
            contents=prompt
        )
        texto = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(texto)
    except Exception as e:
        return {"sem_entrada": True, "motivo": f"Erro IA bilhete: {e}"}


# ─────────────────────────────────────────────
# PIPELINE COMPLETO DAS 4 ETAPAS
# ─────────────────────────────────────────────

def executar_pipeline_alavancagem(api_key, odds_api_key, odd_min, odd_max, confianca_min, score_minimo_stats=20):
    """
    Executa as 4 etapas e retorna jogos prontos para o bilhete.
    """
    stats_init(api_key)

    # ──────────────────────────────────────────
    # ETAPA 1 — API Football: jogos + stats reais
    # ──────────────────────────────────────────
    etapa1 = st.empty()
    etapa1.info("⚽ **Etapa 1/4** — Buscando jogos e estatísticas na API Football...")
    log_etapa("Etapa 1: buscando jogos futuros na API Football")

    jogos_raw = buscar_jogos_futuros_api_football()
    log_etapa(f"Etapa 1: {len(jogos_raw)} jogos encontrados")

    if not jogos_raw:
        etapa1.error("Nenhum jogo encontrado na API Football para hoje/amanhã.")
        return []

    # Enriquece os top 50 jogos por prioridade (ligas top primeiro)
    jogos_para_enriquecer = jogos_raw[:50]
    log_etapa(f"Etapa 1: enriquecendo stats de {len(jogos_para_enriquecer)} jogos prioritarios")

    prog1 = st.progress(0)
    stats_ok = 0
    for i, jogo in enumerate(jogos_para_enriquecer):
        prog1.progress((i + 1) / max(len(jogos_para_enriquecer), 1))
        enriquecer_stats_jogo(jogo)
        if jogo.get("forma_home") or jogo.get("aprov_home", 0) > 0:
            stats_ok += 1
    prog1.empty()

    jogos_raw = jogos_para_enriquecer + jogos_raw[50:]
    log_etapa(f"Etapa 1: {stats_ok}/{len(jogos_para_enriquecer)} com stats reais | {len(jogos_para_enriquecer)-stats_ok} sem stats")

    # DEBUG: mostra aproveitamento dos primeiros jogos para confirmar stats
    com_stats = [j for j in jogos_para_enriquecer if j.get("aprov_home", 0) > 0]
    sem_stats = [j for j in jogos_para_enriquecer if j.get("aprov_home", 0) == 0]
    if sem_stats:
        log_etapa(f"ATENCAO: {len(sem_stats)} jogos sem stats — podem ser ligas sem dados na API")

    # ──────────────────────────────────────────
    # ETAPA 2 — Ranking por estatísticas
    # ──────────────────────────────────────────
    etapa1.info("📊 **Etapa 2/4** — Ranqueando jogos por estatísticas (sem odds ainda)...")
    log_etapa("Etapa 2: ranqueando por stats")

    jogos_ranqueados = ranquear_jogos_por_stats(jogos_raw)
    top_jogos = filtrar_top_para_ia(jogos_ranqueados, top_n=20, score_minimo=score_minimo_stats)
    log_etapa(f"Etapa 2: {len(top_jogos)} jogos passaram pelo filtro de stats (score ≥ {score_minimo_stats})")

    if not top_jogos:
        etapa1.warning(
            f"⚠️ Nenhum jogo atingiu score ≥ {score_minimo_stats} na análise estatística.\n\n"
            "Isso pode acontecer quando as ligas não têm dados suficientes na temporada atual. "
            "Tente reduzir o score mínimo ou aguardar mais jogos da temporada."
        )
        return []

    # ──────────────────────────────────────────
    # ETAPA 3 — IA escolhe mercado (sem odds)
    # ──────────────────────────────────────────
    etapa1.info(f"🤖 **Etapa 3/4** — IA analisando {len(top_jogos)} jogos e escolhendo mercados...")
    log_etapa(f"Etapa 3: IA analisando {len(top_jogos)} jogos")

    jogos_aprovados_ia = []

    with st.spinner("Analisando " + str(len(top_jogos)) + " jogos em lote - 1 chamada Gemini..."):
        resultados_lote = ia_analisar_lote(top_jogos)

    for jogo, resultado_ia in zip(top_jogos, resultados_lote):
        conf_ia = resultado_ia.get("confianca", 0)
        recusar = resultado_ia.get("recusar", True)

        if not recusar and conf_ia >= confianca_min:
            jogo["ia_mercado"] = resultado_ia.get("mercado", "")
            jogo["ia_confianca"] = conf_ia
            jogo["ia_motivo"] = resultado_ia.get("motivo", "")
            jogos_aprovados_ia.append(jogo)
            log_etapa("  ✅ " + jogo["nome"] + " -> " + str(jogo["ia_mercado"]) + " (" + str(conf_ia) + "/100)")
        else:
            motivo = resultado_ia.get("motivo", "confianca insuficiente")
            log_etapa("  RECUSADO: " + jogo["nome"] + " (" + str(conf_ia) + "/100) - " + str(motivo))

    log_etapa("Etapa 3: " + str(len(jogos_aprovados_ia)) + " jogos aprovados pela IA")

    if not jogos_aprovados_ia:
        etapa1.warning(
            f"⚠️ A IA não aprovou nenhum jogo com confiança ≥ {confianca_min}.\n\n"
            "Tente reduzir o score mínimo de confiança ou aguardar novos jogos."
        )
        return []

    # ──────────────────────────────────────────
    # ETAPA 4 — Odds API apenas para jogos aprovados
    # ──────────────────────────────────────────
    etapa1.info(
        f"💰 **Etapa 4/4** — Buscando odds APENAS para os {len(jogos_aprovados_ia)} jogos aprovados..."
    )
    log_etapa(f"Etapa 4: buscando odds para {len(jogos_aprovados_ia)} jogos")

    jogos_com_odds = []
    prog4 = st.progress(0)
    for i, jogo in enumerate(jogos_aprovados_ia):
        prog4.progress((i + 1) / max(len(jogos_aprovados_ia), 1))

        odds_txt = buscar_odds_evento_por_nome(
            jogo.get("casa", ""),
            jogo.get("fora", ""),
            odds_api_key
        )

        if not odds_txt:
            log_etapa(f"  ⚠️ Sem odds para: {jogo['nome']}")
            continue

        jogo["odds_txt"] = odds_txt
        jogo["tem_odds"] = True

        # Valida se a odd do mercado escolhido está na faixa
        melhor_odd = _extrair_melhor_odd(odds_txt, odd_min, odd_max)
        if melhor_odd:
            aprovado, motivo_odd = validar_odd_para_entrada(melhor_odd, odd_min, odd_max, jogo["ia_confianca"])
            jogo["melhor_odd"] = melhor_odd
            if aprovado:
                jogos_com_odds.append(jogo)
                log_etapa(f"  ✅ Odd aprovada: {jogo['nome']} @ {melhor_odd}")
            else:
                log_etapa(f"  ❌ Odd recusada: {jogo['nome']} — {motivo_odd}")
        else:
            log_etapa(f"  ⚠️ Nenhuma odd na faixa {odd_min}-{odd_max} para: {jogo['nome']}")

    prog4.empty()
    etapa1.empty()

    log_etapa(f"Pipeline concluído: {len(jogos_com_odds)} jogos prontos para o bilhete")
    return jogos_com_odds


def _extrair_melhor_odd(odds_txt, odd_min, odd_max):
    """Extrai a melhor odd dentro da faixa do texto de odds."""
    import re
    try:
        matches = re.findall(r'@([\d.]+)', odds_txt)
        odds_na_faixa = []
        for m in matches:
            try:
                v = float(m)
                if odd_min <= v <= odd_max:
                    odds_na_faixa.append(v)
            except Exception:
                pass
        if odds_na_faixa:
            centro = (odd_min + odd_max) / 2
            return min(odds_na_faixa, key=lambda x: abs(x - centro))
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────
# TELA PRINCIPAL
# ─────────────────────────────────────────────

def tela_alavancagem(supabase=None):
    init_estado()
    api_key = st.secrets["API_KEY"]
    odds_api_key = st.secrets.get("ODDS_API_KEY", "")

    tab1, tab2, tab3 = st.tabs(["🚀 Alavancagem", "📊 Painel de Aprendizado", "🔍 Log de Etapas"])

    with tab2:
        if supabase:
            exibir_painel_aprendizado(supabase)
        else:
            st.info("Conecte o Supabase para ver o painel de aprendizado.")

    with tab3:
        st.markdown("### 🔍 Log de Etapas")
        logs = st.session_state.get("alav_log_etapas", [])
        if logs:
            for linha in logs:
                st.caption(linha)
        else:
            st.info("Nenhum log ainda. Inicie uma alavancagem para ver o passo a passo.")

    with tab1:
        st.subheader("🚀 Alavancagem Progressiva")
        st.markdown(
            "Nova arquitetura: **API Football → Ranking Stats → IA escolhe mercado → "
            "Odds API valida → Bilhete final**"
        )

        if not st.session_state.alav_ativa:
            _tela_configuracao(api_key, odds_api_key, supabase)
        else:
            _tela_execucao(supabase)


# ─────────────────────────────────────────────
# TELA DE CONFIGURAÇÃO
# ─────────────────────────────────────────────

def _tela_configuracao(api_key, odds_api_key, supabase):
    st.markdown("### ⚙️ Configurar")

    col1, col2, col3 = st.columns(3)
    with col1:
        banca = st.number_input("Banca inicial (R$)", min_value=1.0, max_value=10000.0,
                                value=float(st.session_state.alav_banca_inicial), step=1.0)
    with col2:
        odd = st.number_input("Odd alvo", min_value=1.1, max_value=3.0,
                              value=float(st.session_state.alav_odd_alvo), step=0.05)
    with col3:
        total = st.number_input("Total de entradas", min_value=3, max_value=20,
                                value=int(st.session_state.alav_total_entradas), step=1)

    col4, col5, col6 = st.columns(3)
    with col4:
        odd_min = st.slider("Odd mínima", 1.10, 1.80, float(st.session_state.alav_odd_min), 0.05)
    with col5:
        odd_max = st.slider("Odd máxima", 1.50, 2.50, float(st.session_state.alav_odd_max), 0.05)
    with col6:
        confianca_min = st.slider("Confiança mínima da IA (0-100)", 30, 95,
                                  int(st.session_state.alav_confianca_min), 5)
        if confianca_min <= 40:
            st.caption("⚠️ Confiança baixa — mais jogos mas menos seletivo")
        elif confianca_min >= 80:
            st.caption("🎯 Alta seletividade — poucos jogos mas mais seguros")
        else:
            st.caption("Abaixo disso, a IA descarta o jogo")

    # Preview
    st.markdown("### 👁️ Preview")
    preview = calcular_tabela(banca, odd, int(total))
    cols = st.columns([1, 2, 2, 2, 2])
    for h, c in zip(["#", "Entrada", "Odd", "Retorno", "Lucro"], cols):
        c.markdown(f"**{h}**")
    for row in preview:
        cols = st.columns([1, 2, 2, 2, 2])
        cols[0].write(str(row["entrada"]))
        cols[1].write(f"R$ {row['valor']}")
        cols[2].write(f"{row['odd']}x")
        cols[3].write(f"R$ {row['retorno']}")
        cols[4].write(f"+R$ {row['lucro']}")

    lucro_total = round(preview[-1]["retorno"] - banca, 2)
    st.success(f"Acertando tudo: R$ {preview[-1]['retorno']} | Lucro: +R$ {lucro_total}")

    st.markdown("---")

    # Explica o novo fluxo
    with st.expander("ℹ️ Como funciona o novo pipeline?"):
        st.markdown("""
**Etapa 1 — API Football** busca jogos de hoje/amanhã e coleta estatísticas reais:
forma dos últimos 5 jogos, média de gols, aproveitamento em casa/fora, H2H, classificação.

**Etapa 2 — Ranking por stats** pontua cada jogo de 0 a 100 usando somente dados estatísticos.
Somente os melhores 20 avançam. *Ainda sem olhar odds.*

**Etapa 3 — IA escolhe o mercado** ideal para cada jogo (Over 1.5, Double Chance, etc.)
e dá uma confiança de 0-100. Jogos com confiança abaixo do mínimo são descartados.

**Etapa 4 — Odds API** busca odds *apenas* para os jogos aprovados pela IA.
A odd real é validada contra a faixa configurada.

**Resultado:** bilhete montado com jogos que passaram em todas as etapas.
        """)

    if st.button("🚀 INICIAR PIPELINE — Buscar, analisar e ranquear", use_container_width=True):
        if not odds_api_key:
            st.error("ODDS_API_KEY não configurada nos Secrets.")
            return

        st.session_state.alav_banca_inicial = banca
        st.session_state.alav_odd_alvo = odd
        st.session_state.alav_total_entradas = int(total)
        st.session_state.alav_odd_min = odd_min
        st.session_state.alav_odd_max = odd_max
        st.session_state.alav_confianca_min = confianca_min
        st.session_state.alav_log_etapas = []

        jogos_prontos = executar_pipeline_alavancagem(
            api_key, odds_api_key,
            odd_min, odd_max, confianca_min
        )

        if not jogos_prontos:
            st.error(
                "❌ Nenhum jogo passou por todas as etapas do pipeline.\n\n"
                "Verifique a aba **Log de Etapas** para entender onde os jogos foram bloqueados."
            )
            return

        st.success(f"✅ {len(jogos_prontos)} jogo(s) aprovados em todas as etapas!")
        st.markdown("**🏆 Jogos prontos para o bilhete:**")
        for j in jogos_prontos:
            st.markdown(
                f"**#{j.get('score', 0)}/100** | {j['nome']} | {j.get('liga_nome', '')} | "
                f"Mercado: **{j.get('ia_mercado', '')}** | "
                f"Confiança IA: {j.get('ia_confianca', 0)}/100 | "
                f"Odd: {j.get('melhor_odd', '?')}"
            )

        tabela = calcular_tabela(banca, odd, int(total))
        st.session_state.alav_entradas = tabela
        st.session_state.alav_jogos = jogos_prontos
        st.session_state.alav_ativa = True
        st.session_state.alav_entrada_atual = 0
        st.rerun()


# ─────────────────────────────────────────────
# TELA DE EXECUÇÃO
# ─────────────────────────────────────────────

def _tela_execucao(supabase):
    entradas = st.session_state.alav_entradas
    atual = st.session_state.alav_entrada_atual
    jogos = st.session_state.alav_jogos

    greens   = sum(1 for e in entradas if e["status"] is True)
    reds     = sum(1 for e in entradas if e["status"] is False)
    pendentes = sum(1 for e in entradas if e["status"] is None)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ Greens", greens)
    col2.metric("❌ Reds", reds)
    col3.metric("⏳ Pendentes", pendentes)

    banca_atual = st.session_state.alav_banca_inicial
    for e in entradas:
        if e["status"] is True:
            banca_atual = e["retorno"]
        elif e["status"] is False:
            banca_atual = 0
            break
    col4.metric("💰 Banca Atual", f"R$ {round(banca_atual, 2)}")

    st.markdown("---")

    # Entrada atual pendente
    if atual < len(entradas) and entradas[atual]["status"] is None:
        entrada_info = entradas[atual]

        if not entrada_info.get("bilhete"):
            st.info(f"🤖 Montando bilhete para entrada #{atual + 1} com {len(jogos)} jogos disponíveis...")
            with st.spinner("IA analisando e escolhendo a melhor aposta..."):
                historico = [e for e in entradas if e["status"] is not None]
                try:
                    resultado = ia_montar_bilhete_final(
                        jogos,
                        st.session_state.alav_odd_min,
                        st.session_state.alav_odd_max,
                        atual + 1,
                        entrada_info["valor"],
                        historico
                    )
                except Exception as err:
                    st.error(f"Erro ao montar bilhete: {err}")
                    if st.button("Tentar novamente", use_container_width=True):
                        st.rerun()
                    return

            # Mostra resultado bruto para debug
            with st.expander("🔬 Resposta bruta da IA", expanded=False):
                st.json(resultado)

            if resultado.get("sem_entrada"):
                st.warning("**IA não encontrou entrada segura neste momento**")
                motivo = resultado.get("motivo_recusa") or resultado.get("motivo", "sem motivo")
                st.info(f"Motivo: {motivo}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Tentar novamente", use_container_width=True):
                        st.rerun()
                with c2:
                    if st.button("Nova Alavancagem", key="nova_sem", use_container_width=True):
                        _resetar_alavancagem()
                        st.rerun()
                return

            odd_total = float(resultado.get("odd_total", st.session_state.alav_odd_alvo))
            retorno   = round(entrada_info["valor"] * odd_total, 2)
            st.session_state.alav_entradas[atual]["bilhete"]   = resultado.get("bilhete", [])
            st.session_state.alav_entradas[atual]["odd"]       = odd_total
            st.session_state.alav_entradas[atual]["retorno"]   = retorno
            st.session_state.alav_entradas[atual]["lucro"]     = round(retorno - entrada_info["valor"], 2)
            st.session_state.alav_entradas[atual]["confianca"] = resultado.get("confianca", 0)
            st.session_state.alav_entradas[atual]["tipo"]      = resultado.get("tipo", "simples")
            st.rerun()

        # Exibe bilhete da entrada atual
        entrada_info = entradas[atual]
        tipo  = entrada_info.get("tipo", "simples")
        conf  = entrada_info.get("confianca", 0)
        cor   = "#22c55e" if conf >= 80 else "#f59e0b" if conf >= 65 else "#ef4444"

        st.markdown(
            f"#### Entrada #{entrada_info['entrada']} — "
            f"{'Combinada 2 jogos' if tipo == 'combinada' else 'Simples'}"
        )
        st.markdown(
            f"**R$ {entrada_info['valor']}** @ **{entrada_info['odd']}x** "
            f"→ **R$ {entrada_info['retorno']}**"
        )
        st.markdown(
            f"<span style='color:{cor};font-weight:700'>Score de confiança: {conf}/100</span>",
            unsafe_allow_html=True
        )

        for b in entrada_info.get("bilhete", []):
            st.info(
                f"**{b.get('jogo', '')}** | {b.get('liga', '')}\n\n"
                f"Aposta: **{b.get('mercado', '')}** @ {b.get('odd', '')}\n\n"
                f"Motivo: {b.get('motivo', '')}"
            )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ GREEN - Acertei!", key=f"green_{atual}", use_container_width=True):
                st.session_state.alav_entradas[atual]["status"] = True
                st.session_state.alav_entradas[atual]["data"]   = datetime.now().strftime("%d/%m %H:%M")
                st.session_state.alav_entrada_atual = atual + 1
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
            if st.button("❌ RED - Errei", key=f"red_{atual}", use_container_width=True):
                st.session_state.alav_entradas[atual]["status"] = False
                st.session_state.alav_entradas[atual]["data"]   = datetime.now().strftime("%d/%m %H:%M")
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

    # Histórico
    st.markdown("---")
    st.markdown("### 📋 Histórico desta alavancagem")
    for entrada in entradas:
        if entrada["status"] is None:
            continue
        linha = f"#{entrada['entrada']} | R$ {entrada['valor']} → R$ {entrada['retorno']}"
        for b in entrada.get("bilhete", []):
            linha += f" | {b.get('jogo', '')} — {b.get('mercado', '')}"
        if entrada["status"] is True:
            st.success(linha)
        else:
            st.error(linha)

    # Finalização
    if atual >= len(entradas):
        if all(e["status"] is True for e in entradas):
            retorno_final = entradas[-1]["retorno"]
            lucro = round(retorno_final - st.session_state.alav_banca_inicial, 2)
            st.success(f"🏆 COMPLETO! R$ {retorno_final} | Lucro: +R$ {lucro}")
        else:
            st.error("❌ Alavancagem encerrada com RED. Recomece com a banca inicial.")

    if st.button("🔄 Nova Alavancagem", use_container_width=True):
        _resetar_alavancagem()
        st.rerun()


def _resetar_alavancagem():
    for k in ["alav_ativa", "alav_entradas", "alav_entrada_atual", "alav_jogos", "alav_log_etapas"]:
        st.session_state.pop(k, None)
 
