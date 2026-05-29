import streamlit as st
import json
from datetime import datetime
from api_football import buscar_jogos_da_liga
from ligas import LIGAS

# =====================================================
# LIGAS PARA VARREDURA
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

# Bookmaker padrão: bet365 = 6
BOOKMAKER_ID = 6

# =====================================================
# BUSCAR ODDS REAIS DA API FOOTBALL
# =====================================================
def buscar_odds_jogo(fixture_id, headers):
    try:
        import requests
        url = f"https://v3.football.api-sports.io/odds?fixture={fixture_id}&bookmaker={BOOKMAKER_ID}"
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return {}
        data = r.json().get("response", [])
        if not data:
            return {}

        odds_formatadas = {}
        for item in data:
            for bookmaker in item.get("bookmakers", []):
                for bet in bookmaker.get("bets", []):
                    nome_mercado = bet.get("name", "")
                    valores = bet.get("values", [])
                    odds_formatadas[nome_mercado] = {
                        v.get("value", ""): float(v.get("odd", 0))
                        for v in valores
                    }
        return odds_formatadas
    except Exception:
        return {}


def formatar_odds_para_ia(odds_dict):
    """Formata as odds em texto legível para o prompt da IA."""
    if not odds_dict:
        return "Odds indisponíveis"
    linhas = []
    mercados_interesse = [
        "Match Winner", "Goals Over/Under", "Both Teams Score",
        "Double Chance", "Asian Handicap", "First Half Goals",
        "Corners Over Under", "Cards Over Under"
    ]
    for mercado in mercados_interesse:
        if mercado in odds_dict:
            vals = odds_dict[mercado]
            linha = f"  {mercado}: " + " | ".join([f"{k}: {v}" for k, v in vals.items()])
            linhas.append(linha)
    return "\n".join(linhas) if linhas else "Odds indisponíveis para mercados principais"


# =====================================================
# ESTADO DA ALAVANCAGEM
# =====================================================
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
        "alav_jogos_disponiveis": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def calcular_tabela(banca_inicial, odd, total):
    tabela = []
    valor = banca_inicial
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
            "data": "",
        })
        valor = retorno
    return tabela


# =====================================================
# VARREDURA DE JOGOS COM ODDS REAIS
# =====================================================
def varrer_jogos_com_odds(headers):
    todos = []
    progress = st.progress(0)
    status_txt = st.empty()
    ligas = list(LIGAS_VARREDURA.items())

    for i, (nome_liga, league_id) in enumerate(ligas):
        status_txt.text(f"🔍 Buscando: {nome_liga}...")
        progress.progress((i + 1) / len(ligas))
        jogos = buscar_jogos_da_liga(league_id)
        for j in jogos:
            j["liga"] = nome_liga
            todos.append(j)

    progress.empty()
    status_txt.empty()
    return todos


# =====================================================
# IA SELECIONA PRÓXIMA ENTRADA
# =====================================================
def ia_selecionar_proxima_entrada(jogos_com_odds, odd_min, odd_max, entrada_num, banca, historico):
    from google import genai
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

    # Monta contexto dos jogos
    contexto_jogos = ""
    for j in jogos_com_odds[:30]:  # Limita para não estourar tokens
        contexto_jogos += f"\n🏟️ {j['nome']} | {j['liga']}\n"
        contexto_jogos += f"   Odds disponíveis:\n{j.get('odds_texto', 'Sem odds')}\n"

    # Histórico de entradas anteriores
    hist_txt = ""
    if historico:
        hist_txt = "\nEntradas já realizadas nessa alavancagem:\n"
        for h in historico:
            status = "✅ GREEN" if h["status"] is True else "❌ RED" if h["status"] is False else "⏳"
            for b in h.get("bilhete", []):
                hist_txt += f"  {status} #{h['entrada']}: {b.get('jogo','')} — {b.get('mercado','')} @ {b.get('odd','')}\n"

    prompt = f"""
Você é uma IA especialista em apostas esportivas com foco em alavancagem progressiva segura.

SITUAÇÃO ATUAL:
- Entrada #{entrada_num} da alavancagem
- Banca disponível: R$ {banca:.2f}
- Odd alvo do bilhete: entre {odd_min}x e {odd_max}x
{hist_txt}

JOGOS DISPONÍVEIS HOJE COM ODDS REAIS:
{contexto_jogos}

SUA TAREFA:
Selecione O MELHOR BILHETE para essa entrada. Pode ser:
- 1 jogo simples com odd entre {odd_min}x e {odd_max}x, OU
- Combinada de 2 jogos onde a odd COMBINADA (multiplicada) fique entre {odd_min}x e {odd_max}x

CRITÉRIOS OBRIGATÓRIOS:
- Use APENAS odds reais dos jogos listados acima
- Priorize mercados seguros: Over 0.5 gols HT, Over 1.5 gols FT, Ambos Marcam Sim, Double Chance
- Para combinadas: escolha jogos de ligas DIFERENTES
- Odd combinada final deve estar entre {odd_min}x e {odd_max}x
- Se NÃO houver nenhuma entrada segura hoje, responda com {{"sem_entrada": true, "motivo": "explicação"}}

Responda SOMENTE com JSON válido, sem markdown:
{{
  "sem_entrada": false,
  "tipo": "simples" ou "combinada",
  "odd_total": 1.65,
  "confianca": 8,
  "bilhete": [
    {{
      "jogo": "Time A x Time B",
      "liga": "Nome da liga",
      "mercado": "Over 1.5 gols FT",
      "odd": 1.65,
      "motivo": "Motivo em 1 frase"
    }}
  ]
}}
"""

    try:
        response = client.models.generate_content(
            model="models/gemini-3.1-flash-lite",
            contents=prompt
        )
        texto = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(texto)
    except Exception as e:
        return {"sem_entrada": True, "motivo": f"Erro na IA: {str(e)}"}


# =====================================================
# TELA PRINCIPAL
# =====================================================
def tela_alavancagem():
    init_estado()

    # Pega headers do main via secrets
    import requests as req
    headers = {
        "x-rapidapi-key": st.secrets["API_KEY"],
        "x-rapidapi-host": "v3.football.api-sports.io"
    }

    st.subheader("🚀 Alavancagem Progressiva")
    st.markdown("A IA analisa **1 entrada por vez** com odds reais, usando bilhetes simples ou combinados de 2 jogos.")

    # ── CONFIGURAÇÃO ──────────────────────────────
    if not st.session_state.alav_ativa:
        st.markdown("### ⚙️ Configurar")

        col1, col2, col3 = st.columns(3)
        with col1:
            banca = st.number_input("💰 Banca inicial (R$)", min_value=1.0, max_value=10000.0,
                                     value=float(st.session_state.alav_banca_inicial), step=1.0)
        with col2:
            odd = st.number_input("📈 Odd alvo do bilhete", min_value=1.1, max_value=3.0,
                                   value=float(st.session_state.alav_odd_alvo), step=0.05)
        with col3:
            total = st.number_input("🎯 Total de entradas", min_value=3, max_value=20,
                                     value=int(st.session_state.alav_total_entradas), step=1)

        col4, col5 = st.columns(2)
        with col4:
            odd_min = st.slider("Odd mínima", 1.2, 1.8, float(st.session_state.alav_odd_min), 0.05)
        with col5:
            odd_max = st.slider("Odd máxima", 1.5, 2.5, float(st.session_state.alav_odd_max), 0.05)

        # Preview progressão
        st.markdown("### 👁️ Preview da Progressão")
        preview = calcular_tabela(banca, odd, int(total))

        col_h = st.columns([1, 2, 2, 2, 2])
        for txt, c in zip(["#", "Entrada", "Odd", "Retorno", "Lucro"], col_h):
            c.markdown(f"**{txt}**")

        for row in preview:
            cols = st.columns([1, 2, 2, 2, 2])
            cols[0].markdown(f"**{row['entrada']}**")
            cols[1].markdown(f"R$ {row['valor']:.2f}")
            cols[2].markdown(f"{row['odd']}x")
            cols[3].markdown(f"R$ {row['retorno']:.2f}")
            cols[4].markdown(f"🟢 +R$ {row['lucro']:.2f}")

        lucro_total = round(preview[-1]["retorno"] - banca, 2)
        st.markdown(f"""
        <div style='background:linear-gradient(135deg,#0a1a0a,#1a3a1a);
        border:2px solid #22c55e;border-radius:16px;padding:20px;text-align:center;margin:16px 0'>
        <p style='color:#94a3b8;margin:0'>Se acertar todas as {int(total)} entradas</p>
        <p style='color:#22c55e;font-size:2rem;font-weight:800;margin:8px 0'>R$ {preview[-1]['retorno']:.2f}</p>
        <p style='color:#4ade80'>Lucro total: +R$ {lucro_total:.2f}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        if st.button("🤖 INICIAR — Buscar jogos e primeira entrada", use_container_width=True):
            st.session_state.alav_banca_inicial = banca
            st.session_state.alav_odd_alvo = odd
            st.session_state.alav_total_entradas = int(total)
            st.session_state.alav_odd_min = odd_min
            st.session_state.alav_odd_max = odd_max

            with st.spinner("🔍 Varrendo jogos e buscando odds reais..."):
                jogos = varrer_jogos_com_odds(headers)

                # Busca odds reais para cada jogo
                jogos_com_odds = []
                for j in jogos[:40]:  # Limita chamadas
                    odds = buscar_odds_jogo(j["id"], headers)
                    j["odds_texto"] = formatar_odds_para_ia(odds)
                    j["odds_dict"] = odds
                    jogos_com_odds.append(j)

                st.session_state.alav_jogos_disponiveis = jogos_com_odds

            # Monta tabela base
            tabela = calcular_tabela(banca, odd, int(total))
            st.session_state.alav_entradas = tabela
            st.session_state.alav_ativa = True
            st.session_state.alav_entrada_atual = 0
            st.rerun()

    # ── ALAVANCAGEM ATIVA ─────────────────────────
    else:
        entradas = st.session_state.alav_entradas
        atual    = st.session_state.alav_entrada_atual
        jogos    = st.session_state.alav_jogos_disponiveis

        # Métricas
        greens = sum(1 for e in entradas if e["status"] is True)
        reds   = sum(1 for e in entradas if e["status"] is False)
        pend   = sum(1 for e in entradas if e["status"] is None)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("✅ Greens", greens)
        col2.metric("❌ Reds", reds)
        col3.metric("⏳ Pendentes", pend)

        banca_atual = st.session_state.alav_banca_inicial
        for e in entradas:
            if e["status"] is True:
                banca_atual = e["retorno"]
            elif e["status"] is False:
                banca_atual = 0
                break
        col4.metric("💰 Banca Atual", f"R$ {banca_atual:.2f}")

        st.markdown("---")

        # Entrada atual — busca IA
        if atual < len(entradas) and entradas[atual]["status"] is None:
            entrada_info = entradas[atual]

            # Se o bilhete ainda não foi gerado pela IA
            if not entrada_info.get("bilhete"):
                with st.spinner(f"🤖 IA analisando melhor entrada #{atual + 1}..."):
                    historico = [e for e in entradas if e["status"] is not None]
                    resultado = ia_selecionar_proxima_entrada(
                        jogos,
                        st.session_state.alav_odd_min,
                        st.session_state.alav_odd_max,
                        atual + 1,
                        entrada_info["valor"],
                        historico
                    )

                if resultado.get("sem_entrada"):
                    st.markdown(f"""
                    <div style='background:linear-gradient(135deg,#1a1000,#2a1500);
                    border:2px solid #f59e0b;border-radius:16px;padding:24px;text-align:center;margin:16px 0'>
                    <h2 style='color:#f59e0b'>⛔ Sem entrada segura hoje</h2>
                    <p style='color:#e2e8f0'>{resultado.get('motivo', 'A IA não encontrou jogos seguros no momento.')}</p>
                    <p style='color:#94a3b8;font-size:0.9rem'>Recomendação: Pause hoje e volte amanhã.</p>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button("🔄 Tentar novamente mais tarde"):
                        # Limpa bilhete para tentar de novo
                        st.rerun()
                    return

                # Salva bilhete gerado
                odd_total = resultado.get("odd_total", st.session_state.alav_odd_alvo)
                retorno = round(entrada_info["valor"] * odd_total, 2)
                st.session_state.alav_entradas[atual]["bilhete"] = resultado.get("bilhete", [])
                st.session_state.alav_entradas[atual]["odd"] = odd_total
                st.session_state.alav_entradas[atual]["retorno"] = retorno
                st.session_state.alav_entradas[atual]["lucro"] = round(retorno - entrada_info["valor"], 2)
                st.session_state.alav_entradas[atual]["confianca"] = resultado.get("confianca", 0)
                st.session_state.alav_entradas[atual]["tipo"] = resultado.get("tipo", "simples")
                st.rerun()

            # Exibe entrada atual
            entrada_info = entradas[atual]
            tipo = entrada_info.get("tipo", "simples")
            confianca = entrada_info.get("confianca", 0)
            cor_conf = "#22c55e" if confianca >= 8 else "#f59e0b" if confianca >= 6 else "#ef4444"

            st.markdown(f"""
            <div style='background:linear-gradient(135deg,#1a0a2e,#2d1b69);
            border:2px solid #f59e0b;border-radius:16px;padding:20px;margin:10px 0'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>
                <span style='color:#f59e0b;font-size:1.2rem;font-weight:800'>⭐ ENTRADA #{entrada_info['entrada']}</span>
                <span style='color:#e2e8f0;font-size:1rem'>R$ {entrada_info['valor']:.2f} → R$ {entrada_info['retorno']:.2f}</span>
            </div>
            <div style='display:flex;gap:12px;margin-bottom:12px'>
                <span style='background:#1e293b;padding:4px 12px;border-radius:999px;color:#a78bfa;font-size:0.85rem'>
                {"🎯 Combinada 2 jogos" if tipo == "combinada" else "🎲 Simples"}</span>
                <span style='background:#1e293b;padding:4px 12px;border-radius:999px;color:#38bdf8;font-size:0.85rem'>
                Odd: {entrada_info['odd']}x</span>
                <span style='background:#1e293b;padding:4px 12px;border-radius:999px;color:{cor_conf};font-size:0.85rem'>
                Confiança: {confianca}/10</span>
            </div>
            </div>
            """, unsafe_allow_html=True)

            # Jogos do bilhete
            for b in entrada_info.get("bilhete", []):
                st.markdown(f"""
                <div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:16px;margin:8px 0'>
                <p style='color:#e2e8f0;font-weight:600;margin:0 0 4px'>{b.get('jogo','')}</p>
                <p style='color:#94a3b8;font-size:0.8rem;margin:0 0 4px'>{b.get('liga','')}</p>
                <p style='color:#a78bfa;margin:0 0 4px'>🎯 {b.get('mercado','')} <span style='color:#38bdf8;font-weight:700'>@ {b.get('odd','')}</span></p>
                <p style='color:#64748b;font-size:0.85rem;margin:0'>💡 {b.get('motivo','')}</p>
                </div>
                """, unsafe_allow_html=True)

            # Botões resultado
            st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ GREEN — Acertei!", key=f"green_{atual}", use_container_width=True):
                    st.session_state.alav_entradas[atual]["status"] = True
                    st.session_state.alav_entradas[atual]["data"] = datetime.now().strftime("%d/%m %H:%M")
                    st.session_state.alav_entrada_atual = atual + 1
                    st.rerun()
            with c2:
                if st.button("❌ RED — Errei", key=f"red_{atual}", use_container_width=True):
                    st.session_state.alav_entradas[atual]["status"] = False
                    st.session_state.alav_entradas[atual]["data"] = datetime.now().strftime("%d/%m %H:%M")
                    st.session_state.alav_entrada_atual = len(entradas)
                    st.rerun()

        st.markdown("---")
        st.markdown("### 📋 Histórico das Entradas")

        # Histórico de entradas anteriores
        for i, entrada in enumerate(entradas):
            if entrada["status"] is None and i >= atual:
                continue  # Não mostra futuras

            status = entrada["status"]
            if status is True:
                cor, emoji = "#22c55e", "✅"
            elif status is False:
                cor, emoji = "#ef4444", "❌"
            else:
                continue

            st.markdown(f"""
            <div style='background:#0f172a;border:1px solid {cor};border-radius:12px;padding:14px;margin:6px 0'>
            <div style='display:flex;justify-content:space-between'>
                <span style='color:{cor};font-weight:700'>{emoji} #{entrada['entrada']}</span>
                <span style='color:#e2e8f0'>R$ {entrada['valor']:.2f} → R$ {entrada['retorno']:.2f}</span>
                <span style='color:#64748b;font-size:0.8rem'>{entrada.get('data','')}</span>
            </div>
            {"".join([f"<p style='color:#94a3b8;font-size:0.85rem;margin:4px 0 0'>{b.get('jogo','')} — {b.get('mercado','')} @ {b.get('odd','')}</p>" for b in entrada.get('bilhete',[])])}
            </div>
            """, unsafe_allow_html=True)

        # Resultado final
        if atual >= len(entradas):
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

        if st.button("Entrar"):
    st.write("clicou")
