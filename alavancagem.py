import streamlit as st
import json
from datetime import datetime
from api_football import buscar_jogos_da_liga
from ia_engine import gerar_analise_pre_jogo
from ligas import LIGAS

# =====================================================
# LIGAS PARA VARREDURA AUTOMÁTICA
# =====================================================
LIGAS_VARREDURA = {
    "Brasileirão Série A": 71,
    "Premier League": 39,
    "LaLiga": 140,
    "Bundesliga": 78,
    "Serie A": 135,
    "Ligue 1": 61,
    "Libertadores": 13,
    "Sudamericana": 11,
    "Champions League": 2,
    "Europa League": 3,
}


# =====================================================
# GERENCIAR ESTADO DA ALAVANCAGEM NO SESSION_STATE
# =====================================================
def init_estado():
    if "alav_banca_inicial" not in st.session_state:
        st.session_state.alav_banca_inicial = 5.0
    if "alav_odd" not in st.session_state:
        st.session_state.alav_odd = 1.5
    if "alav_total_entradas" not in st.session_state:
        st.session_state.alav_total_entradas = 10
    if "alav_entradas" not in st.session_state:
        st.session_state.alav_entradas = []
    if "alav_ativa" not in st.session_state:
        st.session_state.alav_ativa = False
    if "alav_entrada_atual" not in st.session_state:
        st.session_state.alav_entrada_atual = 0


def calcular_tabela(banca_inicial, odd, total_entradas):
    """Gera tabela de alavancagem progressiva."""
    tabela = []
    valor = banca_inicial
    for i in range(1, total_entradas + 1):
        retorno = round(valor * odd, 2)
        lucro = round(retorno - valor, 2)
        tabela.append({
            "entrada": i,
            "valor": round(valor, 2),
            "odd": odd,
            "retorno": retorno,
            "lucro": lucro,
            "status": None,  # None=pendente, True=green, False=red
            "jogo": "",
            "aposta": "",
            "data": ""
        })
        valor = retorno
    return tabela


def cor_status(status):
    if status is True:
        return "#22c55e"
    elif status is False:
        return "#ef4444"
    return "#475569"


def emoji_status(status):
    if status is True:
        return "✅"
    elif status is False:
        return "❌"
    return "⏳"


# =====================================================
# VARREDURA DE JOGOS E SELEÇÃO DA IA
# =====================================================
def varrer_jogos_e_selecionar(odd_min, odd_max, n_entradas):
    """
    Varre todos os jogos do dia nas ligas monitoradas
    e pede para a IA selecionar as melhores entradas.
    """
    from google import genai
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

    todos_jogos = []
    progress = st.progress(0)
    status_text = st.empty()

    ligas_lista = list(LIGAS_VARREDURA.items())
    for i, (nome_liga, league_id) in enumerate(ligas_lista):
        status_text.text(f"🔍 Buscando jogos: {nome_liga}...")
        progress.progress((i + 1) / len(ligas_lista))
        jogos = buscar_jogos_da_liga(league_id)
        for j in jogos:
            j["liga"] = nome_liga
            todos_jogos.append(j)

    progress.empty()
    status_text.empty()

    if not todos_jogos:
        return []

    # Monta resumo dos jogos para a IA
    resumo = f"Jogos disponíveis hoje ({len(todos_jogos)} partidas):\n\n"
    for j in todos_jogos:
        resumo += f"- {j['nome']} | {j['liga']} | ID:{j['id']}\n"

    prompt = f"""
Você é uma IA especialista em apostas esportivas.
Analise os jogos abaixo e selecione as {n_entradas} MELHORES entradas para uma estratégia de alavancagem progressiva.

Critérios obrigatórios:
- Odds entre {odd_min}x e {odd_max}x
- Mercados seguros: Over 0.5 gols HT, Over 1.5 gols FT, Ambos Marcam, Over 3.5 escanteios, Handicap -0.5 do favorito
- Priorize jogos de ligas fortes com histórico de gols
- NUNCA selecione mais de 1 jogo da mesma liga
- Ordene do mais seguro para o menos seguro

{resumo}

Responda EXATAMENTE neste formato JSON, sem markdown, sem explicações:
[
  {{
    "jogo": "Nome do time A x Nome do time B",
    "liga": "Nome da liga",
    "mercado": "Descrição da aposta",
    "odd": 1.65,
    "confianca": 8,
    "motivo": "Motivo em 1 frase"
  }}
]
"""

    try:
        response = client.models.generate_content(
            model="models/gemini-2.0-flash",
            contents=prompt
        )
        texto = response.text.strip()
        # Remove possíveis marcadores de código
        texto = texto.replace("```json", "").replace("```", "").strip()
        selecoes = json.loads(texto)
        return selecoes[:n_entradas]
    except Exception as e:
        st.error(f"Erro na seleção da IA: {e}")
        return []


# =====================================================
# TELA PRINCIPAL DE ALAVANCAGEM
# =====================================================
def tela_alavancagem():
    init_estado()

    st.subheader("🚀 Alavancagem Progressiva")
    st.markdown("A IA varre todos os jogos do dia e monta seu plano de alavancagem automaticamente.")

    # ── CONFIGURAÇÃO ──────────────────────────────
    if not st.session_state.alav_ativa:
        st.markdown("### ⚙️ Configurar Alavancagem")

        col1, col2, col3 = st.columns(3)
        with col1:
            banca = st.number_input(
                "💰 Banca inicial (R$)",
                min_value=1.0, max_value=10000.0,
                value=float(st.session_state.alav_banca_inicial),
                step=1.0
            )
        with col2:
            odd = st.number_input(
                "📈 Odd alvo",
                min_value=1.1, max_value=3.0,
                value=float(st.session_state.alav_odd),
                step=0.05
            )
        with col3:
            total = st.number_input(
                "🎯 Total de entradas",
                min_value=3, max_value=20,
                value=int(st.session_state.alav_total_entradas),
                step=1
            )

        odd_min = st.slider("Odd mínima das apostas", 1.3, 1.8, 1.4, 0.05)
        odd_max = st.slider("Odd máxima das apostas", 1.6, 2.5, 2.0, 0.05)

        # Preview da tabela
        st.markdown("### 👁️ Preview da Progressão")
        preview = calcular_tabela(banca, odd, total)
        cols = st.columns([1, 2, 2, 2, 2])
        cols[0].markdown("**#**")
        cols[1].markdown("**Entrada**")
        cols[2].markdown("**Odd**")
        cols[3].markdown("**Retorno**")
        cols[4].markdown("**Lucro**")
        for row in preview:
            cols = st.columns([1, 2, 2, 2, 2])
            cols[0].markdown(f"**{row['entrada']}**")
            cols[1].markdown(f"R$ {row['valor']:.2f}")
            cols[2].markdown(f"{row['odd']}x")
            cols[3].markdown(f"R$ {row['retorno']:.2f}")
            cols[4].markdown(f"🟢 +R$ {row['lucro']:.2f}")

        lucro_total = round(preview[-1]["retorno"] - preview[0]["valor"], 2)
        st.markdown(f"""
        <div style='background:linear-gradient(135deg,#0a1a0a,#1a3a1a);
        border:2px solid #22c55e;border-radius:16px;padding:20px;margin:16px 0;text-align:center'>
        <p style='color:#94a3b8;margin:0;font-size:0.9rem'>Se acertar todas as {total} entradas</p>
        <p style='color:#22c55e;font-size:2rem;font-weight:800;margin:8px 0'>
        R$ {preview[-1]['retorno']:.2f}</p>
        <p style='color:#4ade80;font-size:0.9rem'>Lucro total: +R$ {lucro_total:.2f}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🤖 INICIAR ALAVANCAGEM — A IA VAI ESCOLHER OS JOGOS", use_container_width=True):
            st.session_state.alav_banca_inicial = banca
            st.session_state.alav_odd = odd
            st.session_state.alav_total_entradas = int(total)

            with st.spinner("🔍 Varrendo todos os jogos do dia e selecionando as melhores entradas..."):
                selecoes = varrer_jogos_e_selecionar(odd_min, odd_max, int(total))

            if not selecoes:
                st.error("Nenhuma entrada encontrada. Tente novamente mais tarde.")
                return

            # Monta a tabela de entradas
            tabela = calcular_tabela(banca, odd, int(total))
            for i, row in enumerate(tabela):
                if i < len(selecoes):
                    sel = selecoes[i]
                    row["jogo"]  = sel.get("jogo", "A definir")
                    row["aposta"] = sel.get("mercado", "A definir")
                    row["odd"]   = sel.get("odd", odd)
                    row["motivo"] = sel.get("motivo", "")
                    row["confianca"] = sel.get("confianca", 0)
                    row["liga"]  = sel.get("liga", "")

            st.session_state.alav_entradas = tabela
            st.session_state.alav_ativa = True
            st.session_state.alav_entrada_atual = 0
            st.rerun()

    # ── ALAVANCAGEM ATIVA ─────────────────────────
    else:
        entradas = st.session_state.alav_entradas
        atual    = st.session_state.alav_entrada_atual

        # Resumo do progresso
        greens = sum(1 for e in entradas if e["status"] is True)
        reds   = sum(1 for e in entradas if e["status"] is False)
        pend   = sum(1 for e in entradas if e["status"] is None)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("✅ Greens", greens)
        col2.metric("❌ Reds", reds)
        col3.metric("⏳ Pendentes", pend)

        # Banca atual
        banca_atual = st.session_state.alav_banca_inicial
        for e in entradas:
            if e["status"] is True:
                banca_atual = e["retorno"]
            elif e["status"] is False:
                banca_atual = 0
                break
        col4.metric("💰 Banca Atual", f"R$ {banca_atual:.2f}")

        st.markdown("---")

        # Tabela de entradas
        st.markdown("### 📋 Suas Entradas")

        for i, entrada in enumerate(entradas):
            status = entrada["status"]
            cor    = cor_status(status)
            emoji  = emoji_status(status)
            is_atual = (i == atual and status is None)

            borda = "2px solid #f59e0b" if is_atual else f"1px solid {cor}"
            bg    = "linear-gradient(135deg,#1a0a2e,#2d1b69)" if is_atual else "#0f172a"

            st.markdown(f"""
            <div style='background:{bg};border:{borda};border-radius:16px;
            padding:16px 20px;margin:8px 0'>
            <div style='display:flex;justify-content:space-between;align-items:center'>
                <span style='color:#94a3b8;font-size:0.85rem'>#{entrada['entrada']} {emoji}</span>
                <span style='color:{cor};font-weight:800;font-size:1.1rem'>R$ {entrada['valor']:.2f}</span>
                <span style='color:#64748b;font-size:0.85rem'>{entrada['odd']}x → R$ {entrada['retorno']:.2f}</span>
            </div>
            <p style='color:#e2e8f0;margin:8px 0 4px;font-weight:600'>{entrada.get('jogo','A definir')}</p>
            <p style='color:#a78bfa;font-size:0.85rem;margin:0'>🎯 {entrada.get('aposta','A definir')}</p>
            {"<p style='color:#fbbf24;font-size:0.8rem;margin:4px 0 0'>⭐ ENTRADA ATUAL</p>" if is_atual else ""}
            {f"<p style='color:#64748b;font-size:0.8rem;margin:4px 0 0'>💡 {entrada.get('motivo','')}</p>" if entrada.get('motivo') else ""}
            </div>
            """, unsafe_allow_html=True)

            # Botões para entrada atual
            if is_atual:
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    if st.button("✅ GREEN — Acertei!", key=f"green_{i}", use_container_width=True):
                        st.session_state.alav_entradas[i]["status"] = True
                        st.session_state.alav_entradas[i]["data"] = datetime.now().strftime("%d/%m %H:%M")
                        # Avança para próxima entrada
                        prox = i + 1
                        while prox < len(entradas) and entradas[prox]["status"] is not None:
                            prox += 1
                        st.session_state.alav_entrada_atual = prox
                        st.rerun()
                with c2:
                    if st.button("❌ RED — Errei", key=f"red_{i}", use_container_width=True):
                        st.session_state.alav_entradas[i]["status"] = False
                        st.session_state.alav_entradas[i]["data"] = datetime.now().strftime("%d/%m %H:%M")
                        st.session_state.alav_entrada_atual = len(entradas)
                        st.rerun()
                with c3:
                    if st.button("↩️", key=f"pular_{i}", help="Pular para depois"):
                        prox = i + 1
                        st.session_state.alav_entrada_atual = prox
                        st.rerun()

        st.markdown("---")

        # Resultado final
        if all(e["status"] is not None for e in entradas):
            if all(e["status"] is True for e in entradas):
                retorno_final = entradas[-1]["retorno"]
                lucro = round(retorno_final - st.session_state.alav_banca_inicial, 2)
                st.markdown(f"""
                <div style='background:linear-gradient(135deg,#0a1a0a,#1a3a1a);
                border:2px solid #22c55e;border-radius:16px;padding:24px;text-align:center;margin:16px 0'>
                <h2 style='color:#22c55e'>🏆 ALAVANCAGEM COMPLETA!</h2>
                <p style='color:#e2e8f0;font-size:1.5rem'>R$ {retorno_final:.2f}</p>
                <p style='color:#4ade80'>Lucro: +R$ {lucro:.2f}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style='background:linear-gradient(135deg,#1a0a0a,#3a1a1a);
                border:2px solid #ef4444;border-radius:16px;padding:24px;text-align:center;margin:16px 0'>
                <h2 style='color:#ef4444'>❌ Alavancagem Encerrada</h2>
                <p style='color:#e2e8f0'>Uma entrada foi perdida. Recomece com a banca inicial.</p>
                </div>
                """, unsafe_allow_html=True)

        # Botão reiniciar
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("🔄 Nova Alavancagem", use_container_width=True):
                st.session_state.alav_ativa = False
                st.session_state.alav_entradas = []
                st.session_state.alav_entrada_atual = 0
                st.rerun()
        with col_r2:
            if st.button("🔍 Buscar Novos Jogos (manter progresso)", use_container_width=True):
                # Substitui apenas as entradas pendentes
                pend_idx = [i for i, e in enumerate(entradas) if e["status"] is None]
                if pend_idx:
                    odd_min = 1.4
                    odd_max = 2.0
                    with st.spinner("Buscando novos jogos..."):
                        novas = varrer_jogos_e_selecionar(odd_min, odd_max, len(pend_idx))
                    for j, idx in enumerate(pend_idx):
                        if j < len(novas):
                            st.session_state.alav_entradas[idx]["jogo"]  = novas[j].get("jogo", "A definir")
                            st.session_state.alav_entradas[idx]["aposta"] = novas[j].get("mercado", "A definir")
                            st.session_state.alav_entradas[idx]["odd"]   = novas[j].get("odd", st.session_state.alav_odd)
                            st.session_state.alav_entradas[idx]["motivo"] = novas[j].get("motivo", "")
                    st.rerun()
