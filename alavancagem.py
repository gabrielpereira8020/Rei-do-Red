"""
alavancagem.py
==============
Motor principal da Alavancagem Progressiva.

ARQUITETURA INTELIGENTE (LAZY LOADING) — 5 ETAPAS:
  ETAPA 1 — API Football busca a listagem geral de jogos (1 request única)
            ↓
  ETAPA 2 — ranking_engine pontua TODOS os jogos localmente (0 requests)
            ↓
  ETAPA 3 — Paginação em Lotes (Free: Top 10 | Completo: Avança se precisar)
            ↓
  ETAPA 4 — IA analisa o lote e escolhe mercados (Econômico: 1 chamada por lote)
            ↓
  ETAPA 5 — APIs de Odds buscam cotações APENAS dos pré-aprovados e monta o bilhete
"""

import streamlit as st
import json
from datetime import datetime

from odds_engine_alav import buscar_odds_evento_por_nome, buscar_odds_evento
from the_odds_api import (
    buscar_odds_jogo as the_odds_buscar,
    extrair_melhor_odd_mercado,
    montar_texto_odds,
    verificar_cota_restante,
)
from oddspapi_engine import (
    buscar_odds_jogo as oddspapi_buscar,
    extrair_melhor_odd as oddspapi_extrair_odd,
    montar_texto_odds as oddspapi_montar_txt,
)
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
        "alav_modo_operacao": "Free (Econômico)",
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
    Analisa jogos em lotes de 8 para evitar JSON truncado pelo Gemini.
    Cada lote usa stats resumidas (max 200 chars) para manter prompt pequeno.
    """
    from google import genai
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

    TAMANHO_LOTE = 8  # max 8 jogos por chamada — evita truncamento JSON
    todos_resultados = []

    for inicio in range(0, len(jogos), TAMANHO_LOTE):
        lote = jogos[inicio:inicio + TAMANHO_LOTE]
        n = len(lote)

        ctx = ""
        for i, jogo in enumerate(lote):
            # Limita stats a 200 chars para manter prompt compacto
            stats = jogo.get("stats_txt", "Sem dados")[:200]
            ctx += f"JOGO {i+1}: {jogo.get('casa','?')} x {jogo.get('fora','?')} | {jogo.get('liga_nome','')}\n"
            ctx += stats + "\n\n"

        prompt = (
            "Analise os jogos e para CADA UM escolha o mercado mais seguro.\n\n"
            + ctx +
            "MERCADOS: Over 0.5 HT | Over 1.5 FT | Over 2.5 FT | "
"Double Chance 1X | Double Chance X2 | Ambos Marcam Sim | Vitoria Mandante | Vitoria Visitante | Under 4.5 FT\n"
          
            "REGRAS: sem dados=recusar true. confianca<72=recusar true.\n"
            "Responda APENAS o JSON array, sem texto antes ou depois, sem markdown:\n"
            f'[{{"jogo":1,"mercado":"Over 1.5 FT","confianca":82,"motivo":"ok","recusar":false}},...] ({n} objetos)'
        )

        try:
            response = client.models.generate_content(
                model="models/gemini-3.1-flash-lite",
                contents=prompt
            )
            texto = response.text.strip()
            # Limpeza agressiva — remove tudo antes do [ e depois do ]
            inicio_json = texto.find("[")
            fim_json = texto.rfind("]")
            if inicio_json != -1 and fim_json != -1:
                texto = texto[inicio_json:fim_json+1]
            texto = texto.replace("```json","").replace("```","").strip()

            resultados = json.loads(texto)
            if isinstance(resultados, list) and len(resultados) == n:
                todos_resultados.extend(resultados)
            else:
                # Tenta recuperar pelo campo jogo
                mapa = {r.get("jogo", i+1): r for i, r in enumerate(resultados)}
                todos_resultados.extend([
                    mapa.get(i+1, {"recusar": True, "confianca": 0, "motivo": "sem retorno"})
                    for i in range(n)
                ])
        except Exception as e:
            todos_resultados.extend([
                {"mercado": "", "confianca": 0, "motivo": str(e)[:80], "recusar": True}
                for _ in lote
            ])

    return todos_resultados


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
        "3. Simples = 1 jogo com odd já na faixa. Combinada = 2 jogos (MULTIPLICAR as odds: ex 1.18 x 1.28 = 1.51)\n"
        f"4. Odd final DEVE estar entre {odd_min}x e {odd_max}x\n"
        "5. REGRA PRINCIPAL: Se não encontrar 1 jogo com odd na faixa, TENTE COMBINAR 2 jogos com odds menores que se multiplicados atingem a faixa\n"
        "   Exemplo: jogo A @ 1.18 + jogo B @ 1.30 = odd combinada 1.18 * 1.30 = 1.534 (dentro da faixa 1.30-2.00) ✅\n"
        "6. Para combinada, prefira jogos de ligas DIFERENTES com alta confiança\n"
        "7. Se mesmo combinando não atingir a faixa, retorne sem_entrada=true\n\n"
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
# PIPELINE LAZY LOADING EM LOTES (OTIMIZADO)
# ─────────────────────────────────────────────

def executar_pipeline_alavancagem(api_key, odds_api_key, odd_min, odd_max, confianca_min, score_minimo_stats=20, usar_oddspapi=True, usar_the_odds=True, usar_odds_api=True, modo_operacao="Free (Econômico)"):
    """
    Executa o pipeline em lotes locais sob demanda, evitando estourar quotas de API.
    """
    stats_init(api_key)

    # ──────────────────────────────────────────
    # ETAPA 1 — API Football: Busca listagem geral (1 request única)
    # ──────────────────────────────────────────
    etapa1 = st.empty()
    etapa1.info("⚽ **Etapa 1** — Buscando listagem de jogos na API Football (1 request única)...")
    log_etapa("Etapa 1: buscando jogos futuros na API Football")

    jogos_raw = buscar_jogos_futuros_api_football()
    log_etapa(f"Etapa 1: {len(jogos_raw)} jogos encontrados")

    if not jogos_raw:
        etapa1.error("Nenhum jogo encontrado na API Football para hoje/amanhã.")
        return []

    # ──────────────────────────────────────────
    # ETAPA 2 — Pré-Ranking na memória (0 requests adicionais)
    # ──────────────────────────────────────────
    etapa1.info("📊 **Etapa 2** — Ranqueando jogos prioritários locais na memória (0 requests)...")
    log_etapa("Etapa 2: ranqueando jogos brutos por importância de liga")
    
    jogos_ranqueados = ranquear_jogos_por_stats(jogos_raw)
    jogos_elegiveis = [j for j in jogos_ranqueados if j.get("score", 0) >= score_minimo_stats]
    if not jogos_elegiveis:
        jogos_elegiveis = jogos_ranqueados

    # ──────────────────────────────────────────
    # ETAPAS 3, 4 e 5 — Processamento Otimizado por Lotes Sob Demanda
    # ──────────────────────────────────────────
    TAMANHO_BLOCO = 10
    jogos_com_odds = []
    
    log_etapa(f"Iniciando varredura por demanda. Modo: {modo_operacao}")
    
    for indice_bloco, inicio in enumerate(range(0, len(jogos_elegiveis), TAMANHO_BLOCO)):
        bloco_atual = jogos_elegiveis[inicio:inicio + TAMANHO_BLOCO]
        
        etapa1.info(f"🔄 **Processando Bloco {indice_bloco + 1}** — Enriquecendo e analisando lote de {len(bloco_atual)} jogos...")
        log_etapa(f"--- Processando Bloco {indice_bloco + 1} (Jogos {inicio+1} a {inicio+len(bloco_atual)}) ---")
        
        # Enriquecimento estatístico restrito APENAS ao bloco atual de 10 jogos
        prog1 = st.progress(0)
        for i, jogo in enumerate(bloco_atual):
            prog1.progress((i + 1) / max(len(bloco_atual), 1))
            enriquecer_stats_jogo(jogo)
        prog1.empty()

        top_bloco_processado = [j for j in bloco_atual if j.get("score", 0) >= score_minimo_stats]
        if not top_bloco_processado:
            top_bloco_processado = bloco_atual

        # IA analisa o lote compacto atual (1 chamada Gemini apenas)
        log_etapa(f"Chamando Gemini para analisar lote de {len(top_bloco_processado)} jogos")
        resultados_lote = ia_analisar_lote(top_bloco_processado)

        jogos_aprovados_ia = []
        for jogo, resultado_ia in zip(top_bloco_processado, resultados_lote):
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

        # Busca de odds cirúrgica apenas para os sobreviventes aprovados pela IA no bloco
        oddspapi_key = st.secrets.get("ODDSPAPI_KEY", "") if usar_oddspapi else ""
        the_odds_key = st.secrets.get("THE_ODDS_API_KEY", "") if usar_the_odds else ""
        odds_api_key_final = odds_api_key if usar_odds_api else ""

        for jogo in jogos_aprovados_ia:
            melhor_odd = None
            fonte_odd  = ""
            mercado_ia = jogo.get("ia_mercado", "")
            liga_id    = jogo.get("liga_id", 0)
            liga_nome  = jogo.get("liga_nome", "")

            # 1. OddsPapi
            if oddspapi_key and not melhor_odd:
                try:
                    odds_dict = oddspapi_buscar(jogo.get("casa",""), jogo.get("fora",""), liga_id, liga_nome, oddspapi_key, odd_min=1.10, odd_max=odd_max)
                    if odds_dict:
                        odd_val, bm, _ = oddspapi_extrair_odd(odds_dict, mercado_ia, 1.10, odd_max)
                        if odd_val:
                            melhor_odd = odd_val
                            fonte_odd  = "OddsPapi(" + str(bm) + ")"
                            jogo["odds_txt"]  = oddspapi_montar_txt(odds_dict, mercado_ia)
                            jogo["odds_dict"] = odds_dict
                except Exception as e:
                    log_etapa("  OddsPapi erro: " + jogo["nome"] + " — " + str(e)[:60])

            # 2. The Odds API
            if the_odds_key and not melhor_odd:
                try:
                    odds_dict = the_odds_buscar(jogo.get("casa",""), jogo.get("fora",""), liga_id, the_odds_key, odd_min=1.10, odd_max=odd_max)
                    if odds_dict:
                        odd_val, bm = extrair_melhor_odd_mercado(odds_dict, mercado_ia, 1.10, odd_max)
                        if odd_val:
                            melhor_odd = odd_val
                            fonte_odd  = "TheOddsAPI(" + str(bm) + ")"
                            jogo["odds_txt"]  = montar_texto_odds(odds_dict, mercado_ia)
                            jogo["odds_dict"] = odds_dict
                except Exception as e:
                    log_etapa("  TheOddsAPI erro: " + jogo["nome"] + " — " + str(e)[:60])

            # 3. Odds API original
            if odds_api_key_final and not melhor_odd:
                try:
                    odds_txt_raw = buscar_odds_evento_por_nome(jogo.get("casa",""), jogo.get("fora",""), odds_api_key_final)
                    if odds_txt_raw:
                        odd_val = _extrair_melhor_odd(odds_txt_raw, 1.10, odd_max)
                        if odd_val:
                            melhor_odd = odd_val
                            fonte_odd  = "OddsAPI"
                            jogo["odds_txt"] = odds_txt_raw
                except Exception: pass

            if not melhor_odd:
                log_etapa("  sem odds: " + jogo["nome"] + " (liga_id=" + str(liga_id) + ")")
                continue

            jogo["melhor_odd"] = melhor_odd
            jogo["tem_odds"]   = True

            if melhor_odd >= odd_min:
                aprovado, motivo_odd = validar_odd_para_entrada(melhor_odd, odd_min, odd_max, jogo["ia_confianca"])
                if aprovado:
                    jogo["candidato_combinada"] = False
                    jogos_com_odds.append(jogo)
                    log_etapa("  ✅ " + jogo["nome"] + " @ " + str(melhor_odd) + " via " + fonte_odd + " (" + mercado_ia + ")")
                else:
                    log_etapa("  ❌ " + jogo["nome"] + " @ " + str(melhor_odd) + " — " + motivo_odd)
            else:
                if jogo["ia_confianca"] >= confianca_min:
                    jogo["candidato_combinada"] = True
                    jogos_com_odds.append(jogo)
                    log_etapa("  🔗 combinada: " + jogo["nome"] + " @ " + str(melhor_odd) + " via " + fonte_odd)
                else:
                    log_etapa("  ❌ descartado: " + jogo["nome"] + " @ " + str(melhor_odd) + " — odd baixa")

        # Condição de parada inteligente: Se já temos material para a IA montar o bilhete, aborta loops extras
        if len(jogos_com_odds) >= 2:
            log_etapa(f"Sucesso! Temos {len(jogos_com_odds)} oportunidades prontas. Interrompendo varredura para poupar requests.")
            break
            
        # Trava total do Modo Econômico
        if modo_operacao == "Free (Econômico)":
            log_etapa("Modo Free ativo: Análise finalizada estritamente após o primeiro lote de 10.")
            break

    etapa1.empty()
    log_etapa(f"Pipeline concluido: {len(jogos_com_odds)} jogos prontos para o bilhete")
    st.session_state["alav_ultimo_log"] = st.session_state.get("alav_log_etapas", [])
    return jogos_com_odds


def _buscar_no_cache(cache_odds, home, away):
    """
    Busca jogo no cache local (dict retornado por buscar_todos_jogos_odds).
    Usa normalização igual à the_odds_api._norm para casar os nomes.
    Zero requests adicionais.
    """
    import unicodedata

    def _norm(nome):
        nome = str(nome).lower().strip()
        nome = "".join(
            c for c in unicodedata.normalize("NFD", nome)
            if unicodedata.category(c) != "Mn"
        )
        for suf in [" fc"," cf"," sc"," ac"," sk"," fk"," bk"," if"," ff",
                    " united"," city"," athletic"," atletico"," sporting"]:
            nome = nome.replace(suf, "")
        return nome.strip()

    home_n = _norm(home)
    away_n = _norm(away)
    melhor, melhor_sc = None, 0

    for (ch, ca), jogo_dict in cache_odds.items():
        sc = 0
        if home_n == ch or home_n in ch or ch in home_n: sc += 2
        elif set(home_n.split()) & set(ch.split()):       sc += 1
        if away_n == ca or away_n in ca or ca in away_n:  sc += 2
        elif set(away_n.split()) & set(ca.split()):       sc += 1
        if sc > melhor_sc and sc >= 2:
            melhor_sc, melhor = sc, jogo_dict

    return melhor


def _extrair_melhor_odd(odds_txt, odd_min, odd_max):
    """
    Extrai a melhor odd do texto de odds.
    Aceita odds entre ODD_COMBINADA_MIN e odd_max para que jogos
    com odds baixas possam ser combinados e atingir a faixa alvo.
    """
    import re
    ODD_COMBINADA_MIN = 1.10  # aceita odds baixas para montar combinadas
    try:
        matches = re.findall(r'@([\d.]+)', odds_txt)
        odds_validas = []
        for m in matches:
            try:
                v = float(m)
                if ODD_COMBINADA_MIN <= v <= odd_max:
                    odds_validas.append(v)
            except Exception:
                pass
        if odds_validas:
            # Prioriza odds dentro da faixa ideal; se não houver, pega a maior disponível
            odds_na_faixa = [v for v in odds_validas if v >= odd_min]
            if odds_na_faixa:
                centro = (odd_min + odd_max) / 2
                return min(odds_na_faixa, key=lambda x: abs(x - centro))
            # Odds abaixo do mínimo — retorna a maior (candidata para combinada)
            return max(odds_validas)
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
        # Usa ultimo_log que persiste após rerun; alav_log_etapas é zerado a cada execução
        logs = st.session_state.get("alav_ultimo_log") or st.session_state.get("alav_log_etapas", [])
        if logs:
            st.caption(f"📋 {len(logs)} entries no log")
            for linha in logs:
                st.caption(linha)
        else:
            st.info("Nenhum log ainda. Inicie uma alavancagem para ver o passo a passo.")

    with tab1:
        st.subheader("🚀 Alavancagem Progressiva")
        st.markdown(
            "Nova arquitetura inteligente: **API Football (Listagem) → Ranking Memória → "
            "Lazy Loading por Lotes (Filtro IA & Odds) → Bilhete final**"
        )

        if not st.session_state.alav_ativa:
            _tela_configuracao(api_key, odds_api_key, supabase)
        else:
            _tela_execucao(supabase)


# ─────────────────────────────────────────────
# TELA DE CONFIGURAÇÃO
# ─────────────────────────────────────────────

def _tela_configuracao(api_key, odds_api_key, supabase):
    st.markdown("### ⚙️ Configurar Parâmetros")

    # NOVOS CONTROLES DE CONTROLE VISUAL DE TRÁFEGO
    st.markdown("#### ⚡ Arquitetura & Redução de Gargalo")
    c_modo1, c_modo2 = st.columns(2)
    with c_modo1:
        modo_operacao = st.radio(
            "Modo de Operação",
            ["Free (Econômico)", "Completo (Varredura Total)"],
            index=0 if st.session_state.alav_modo_operacao == "Free (Econômico)" else 1,
            help="Modo Free analisa apenas os TOP 10 jogos estatísticos do dia. Modo Completo executa busca continuada por novos blocos caso falte odds."
        )
    with c_modo2:
        st.markdown("<br>", unsafe_allow_html=True)
        if modo_operacao == "Free (Econômico)":
            st.warning("💡 **Modo Free Ativo**: No máximo 10 enriquecimentos de stats e 1 chamada de IA por bilhete!")
        else:
            st.success("🔥 **Modo Completo Ativo**: Fallback automático ligado. Se faltar cotação, ele puxa mais 10.")

    st.markdown("---")

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
    st.markdown("### 👁️ Preview Alvo")
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

    with st.expander("ℹ️ Como funciona o novo pipeline?"):
        st.markdown("""
**Etapa 1 — API Football** busca listagem e monta base local na memória imediata de forma limpa.

**Etapa 2 — Ranking local** organiza por relevância estatística, gerando fila prioritária imediata.

**Etapa 3 — Lazy Loading** extrai o bloco inicial (Top 10), consumindo dados cirurgicamente por lote.

**Etapa 4 — IA & Odds Cascata** processa apenas o bloco ativo em 1 request unificado de IA, puxando cotação dos sobreviventes.
        """)

    # Seleção de APIs
    st.markdown("### 🔌 APIs de Odds")
    st.caption("Selecione quais APIs usar. Desative as de cota limitada para testes.")

    col_api1, col_api2, col_api3 = st.columns(3)
    with col_api1:
        usar_oddspapi_ui = st.checkbox(
            "OddsPapi",
            value=st.session_state.get("alav_usar_oddspapi", True),
            help="250 requests/mês | Pinnacle | 460+ mercados"
        )
        st.caption("250 req/mês · Pinnacle")
    with col_api2:
        usar_the_odds_ui = st.checkbox(
            "The Odds API",
            value=st.session_state.get("alav_usar_the_odds", True),
            help="500 créditos/mês | Bet365, Unibet"
        )
        st.caption("500 req/mês · Bet365")
    with col_api3:
        usar_odds_api_ui = st.checkbox(
            "Odds API (odds-api.io)",
            value=st.session_state.get("alav_usar_odds_api", True),
            help="100 requests/hora | Unibet | Boa para testes"
        )
        st.caption("100 req/hora · Testes ✅")

    if not usar_oddspapi_ui and not usar_the_odds_ui and not usar_odds_api_ui:
        st.warning("⚠️ Selecione pelo menos uma API de odds.")

    if st.button("🚀 INICIAR PIPELINE OTIMIZADO", use_container_width=True):
        if not usar_oddspapi_ui and not usar_the_odds_ui and not usar_odds_api_ui:
            st.error("Selecione pelo menos uma API de odds antes de iniciar.")
            return

        st.session_state.alav_banca_inicial = banca
        st.session_state.alav_odd_alvo = odd
        st.session_state.alav_total_entradas = int(total)
        st.session_state.alav_odd_min = odd_min
        st.session_state.alav_odd_max = odd_max
        st.session_state.alav_confianca_min = confianca_min
        st.session_state.alav_usar_oddspapi = usar_oddspapi_ui
        st.session_state.alav_usar_the_odds = usar_the_odds_ui
        st.session_state.alav_usar_odds_api = usar_odds_api_ui
        st.session_state.alav_modo_operacao = modo_operacao
        st.session_state.alav_log_etapas = []
        st.session_state.alav_ultimo_log = []

        jogos_prontos = executar_pipeline_alavancagem(
            api_key, odds_api_key,
            odd_min, odd_max, confianca_min,
            usar_oddspapi=usar_oddspapi_ui,
            usar_the_odds=usar_the_odds_ui,
            usar_odds_api=usar_odds_api_ui,
            modo_operacao=modo_operacao
        )

        st.session_state.alav_ultimo_log = list(st.session_state.get("alav_log_etapas", []))

        if not jogos_prontos:
            log_txt = "\n".join(st.session_state.alav_ultimo_log)
            if "Bloco" not in log_txt:
                fase = "🔴 **Travou na Etapa 2** — nenhum jogo local encontrado na listagem."
            elif "IA analisando" not in log_txt and "Chamando Gemini" not in log_txt:
                fase = "🔴 **Travou na triagem inicial** — score mínimo muito alto para os dados locais."
            else:
                fase = "🟡 Bloco processado mas nenhuma cotação retornou dentro dos filtros alvos."

            st.error(
                f"❌ Nenhuma oportunidade validada nos blocos de hoje.\n\n"
                f"{fase}\n\n"
                "Verifique os detalhes das etapas abaixo 👇"
            )
            with st.expander("🔍 Log completo do pipeline", expanded=True):
                logs = st.session_state.alav_ultimo_log
                if logs:
                    for linha in logs:
                        st.caption(linha)
                else:
                    st.warning("Log vazio — verifique suas chaves.")
            return

        st.success(f"✅ {len(jogos_prontos)} jogo(s) aprovados e prontos em todas as etapas!")
        st.markdown("**🏆 Jogos prontos para o bilhete:**")
        for j in jogos_prontos:
            st.markdown(
                f"**#{j.get('score', 0)}/100** | {j['nome']} | {j.get('liga_nome', '')} | "
                f"Mercado: **{j.get('ia_mercado', '')}** | "
                f"Confiança IA: {j.get('ia_confianca', 0)}/100 | "
                f"Odd: {j.get('melhor_odd', '?')}"
            )

        tabela = calcular_tabela(banca, odd, int(total))
        st.session_state.alav_entradas = tablea = tabela
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
