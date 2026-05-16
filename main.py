import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from datetime import datetime
from supabase import create_client
import time

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="IA REI DA BOLA PRO",
    page_icon="🏆",
    layout="wide"
)

# =====================================================
# CSS PREMIUM
# =====================================================
st.markdown("""
<style>
.main { background-color: #0b1020; }
.block-container { padding-top: 1rem; }
h1, h2, h3 { color: white; }
.stMetric {
    background: linear-gradient(145deg,#141b2d,#1d2840);
    border-radius: 15px;
    padding: 15px;
    border: 1px solid #7a3cff;
}
.stButton>button {
    width: 100%;
    border-radius: 10px;
    background: linear-gradient(90deg,#7a3cff,#4f46e5);
    color: white;
    font-weight: bold;
    border: none;
    padding: 12px;
}
.stExpander {
    border: 1px solid #252f48;
    border-radius: 15px;
    background: #121a2b;
}
div[data-testid="stSidebar"] { background-color: #111827; }

/* Caixa de Cravo */
.cravo-box {
    background: linear-gradient(135deg, #1a0a2e, #2d1b69);
    border: 2px solid #f59e0b;
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
}
.cravo-box h3 { color: #f59e0b !important; font-size: 1.4rem; }

/* Caixa de Oportunidade */
.oportunidade-box {
    background: linear-gradient(135deg, #0a1a0a, #1a3a1a);
    border: 2px solid #22c55e;
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
}
.oportunidade-box h3 { color: #22c55e !important; }

/* Caixa de Confiança */
.confianca-box {
    background: linear-gradient(135deg, #0a0a2e, #0a1a3a);
    border: 2px solid #38bdf8;
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
}
.confianca-box h3 { color: #38bdf8 !important; }

/* Barra de confiança */
.progress-bar {
    background: #1e293b;
    border-radius: 999px;
    height: 20px;
    width: 100%;
    margin-top: 8px;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #38bdf8, #7a3cff);
    transition: width 0.5s ease;
}

/* Caixa AO VIVO - entrada */
.entrada-box {
    background: linear-gradient(135deg, #1a0a0a, #3a1a1a);
    border: 2px solid #ef4444;
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
}
.entrada-box h3 { color: #ef4444 !important; }

/* API Counter */
.api-counter {
    background: linear-gradient(135deg, #1a1a0a, #2a2a1a);
    border: 1px solid #eab308;
    border-radius: 12px;
    padding: 10px 16px;
    text-align: center;
    margin: 6px 0;
}
.api-counter span { color: #eab308; font-weight: bold; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# =====================================================
# LIGAS
# =====================================================
LIGAS_ELITE = [71, 72, 73, 39, 40, 140, 141, 78, 79, 135, 136, 61, 62, 94]

# =====================================================
# CONTROLE DE CHAMADAS DE API (contador diário)
# =====================================================
def get_api_usage_key():
    return f"api_calls_{datetime.now().strftime('%Y-%m-%d')}"

def registrar_chamada_api():
    key = get_api_usage_key()
    if key not in st.session_state:
        st.session_state[key] = 0
    st.session_state[key] += 1

def get_chamadas_hoje():
    key = get_api_usage_key()
    return st.session_state.get(key, 0)

LIMITE_DIARIO_API = 100  # ajuste conforme seu plano

# =====================================================
# INIT SERVICES
# =====================================================
@st.cache_resource
def init_services():
    try:
        supabase = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"]
        )

        client = genai.Client(
            api_key=st.secrets["GEMINI_API_KEY"]
        )

        modelos_disponiveis = []

        for m in client.models.list():
            modelos_disponiveis.append(m.name)

        modelo_escolhido = "gemini-2.5-flash-lite"

        st.success(f"Modelo carregado: {modelo_escolhido}")

        return supabase, client

    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None, None

supabase, gemini = init_services()
API_KEY = st.secrets["API_KEY"]
HEADERS = {
    'x-rapidapi-key': API_KEY,
    'x-rapidapi-host': 'v3.football.api-sports.io'
}

# =====================================================
# API FOOTBALL
# =====================================================
@st.cache_data(ttl=60)
def fetch_api(endpoint):
    try:
        url = f"https://v3.football.api-sports.io/{endpoint}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        registrar_chamada_api()
        if response.status_code != 200:
            return []
        return response.json().get("response", [])
    except:
        return []

def fetch_api_com_status(endpoint):
    """Busca e também retorna os headers de uso da API."""
    try:
        url = f"https://v3.football.api-sports.io/{endpoint}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        registrar_chamada_api()
        remaining = response.headers.get("x-ratelimit-requests-remaining", None)
        limit = response.headers.get("x-ratelimit-requests-limit", None)
        data = response.json().get("response", []) if response.status_code == 200 else []
        return data, remaining, limit
    except:
        return [], None, None

# =====================================================
# TELEGRAM
# =====================================================
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

def enviar_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except:
        return False

# =====================================================
# IA - PRÉ-JOGO (prompt detalhado)
# =====================================================
def analisar_pre_jogo(contexto):
    try:
        prompt = f"""
Você é o REI DA BOLA — o maior analista de apostas esportivas do Brasil.
Analise o jogo abaixo como um trader profissional com anos de experiência.

CONTEXTO DO JOGO:
{contexto}

Retorne EXATAMENTE neste formato (sem markdown extra fora das seções):

🎯 VEREDITO:
[Dê sua opinião geral sobre o jogo. Quem tem vantagem e por quê.]

🏆 CRAVO:
[Aqui você coloca O SEU MELHOR PALPITE — aquilo que você CRAVO que vai acontecer.
Seja específico: pode ser vitória de um time, placar, gols (over/under), escanteios,
cartões, chutes, gol ou assistência de um jogador específico, falta sofrida, etc.
Exemplo: "CRAVO vitória do Goiás. Meu pick principal: Over 1.5 gols. Apoio forte."]

💰 OPORTUNIDADE:
[Liste 2 a 3 mercados que têm valor mas você NÃO cravar com certeza.
São oportunidades secundárias interessantes pelo contexto do jogo.
Exemplo: escanteios acima de X, cartão para jogador Y, gol no segundo tempo.]

📈 CONFIANÇA:
[Dê uma porcentagem de 0% a 100% de confiança no seu CRAVO principal.
Depois explique brevemente o motivo.
Formato: CONFIANÇA: XX%
Explicação: ...]

🔥 FEELING:
[Seu feeling como Rei da Bola — o "instinto" além dos números.]
"""
        resposta = gemini.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents=prompt
)

    return resposta.text if resposta.text else "IA sem resposta"
    except Exception as e:
        return f"ERRO DA IA: {str(e)}"

# =====================================================
# IA - AO VIVO (prompt focado em entrada)
# =====================================================
def analisar_ao_vivo(contexto_ao_vivo):
    try:
        prompt = f"""
Você é o REI DA BOLA — especialista em trading ao vivo.
Analise o momento atual do jogo e diga O QUE FAZER AGORA.

CONTEXTO AO VIVO:
{contexto_ao_vivo}

Retorne EXATAMENTE neste formato:

⚡ ENTRADA RECOMENDADA:
[Diga claramente: PODE ENTRAR AGORA em [mercado específico]?
Seja direto: entrar em vitória, empate, gols, escanteios, cartões, etc.
Se o jogo está movimentado, diga em qual mercado entrar agora.
Exemplo: "ENTRA AGORA — Over 2.5 gols. Jogo aberto, placar 1x1, muita pressão."]

🎯 CRAVO AO VIVO:
[Seu melhor palpite para os próximos minutos ou para o resultado final.
Pode ser: virada, mais um gol, escanteio, cartão, chute a gol de alguém.]

📈 CONFIANÇA:
[Porcentagem de confiança na entrada recomendada.
Formato: CONFIANÇA: XX%]

⚠️ RISCOS:
[Aponte 1 ou 2 riscos principais desta entrada.]

🔥 FEELING AO VIVO:
[Seu instinto neste momento do jogo.]
"""
        resposta = gemini.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents=prompt
)

return resposta.text if resposta.text else "IA sem resposta"
        return "IA sem resposta"
    except Exception as e:
        return f"ERRO DA IA: {str(e)}"

# =====================================================
# RENDERIZAR ANÁLISE FORMATADA
# =====================================================
def renderizar_analise(texto, modo="pre"):
    """
    Renderiza a análise da IA em caixas visuais formatadas.
    modo: 'pre' para pré-jogo, 'live' para ao vivo.
    """
    if not texto or texto.startswith("ERRO"):
        st.error(texto)
        return

    secoes = {
        "🎯 VEREDITO": ("", "#7a3cff"),
        "🏆 CRAVO": ("cravo-box", "#f59e0b"),
        "⚡ ENTRADA RECOMENDADA": ("entrada-box", "#ef4444"),
        "🎯 CRAVO AO VIVO": ("cravo-box", "#f59e0b"),
        "💰 OPORTUNIDADE": ("oportunidade-box", "#22c55e"),
        "📈 CONFIANÇA": ("confianca-box", "#38bdf8"),
        "🔥 FEELING": ("", "#a78bfa"),
        "🔥 FEELING AO VIVO": ("", "#a78bfa"),
        "⚠️ RISCOS": ("", "#f87171"),
    }

    # Parse por seção
    linhas = texto.split("\n")
    secao_atual = None
    conteudo_atual = []
    blocos = []

    for linha in linhas:
        linha_strip = linha.strip()
        encontrou = False
        for chave in secoes:
            if linha_strip.startswith(chave):
                if secao_atual:
                    blocos.append((secao_atual, "\n".join(conteudo_atual).strip()))
                secao_atual = chave
                conteudo_atual = [linha_strip[len(chave):].lstrip(":").strip()]
                encontrou = True
                break
        if not encontrou and secao_atual:
            conteudo_atual.append(linha)

    if secao_atual:
        blocos.append((secao_atual, "\n".join(conteudo_atual).strip()))

    # Renderizar blocos
    for titulo, conteudo in blocos:
        css_class, cor = secoes.get(titulo, ("", "#fff"))

        # Extrai % de confiança se for seção de confiança
        if "CONFIANÇA" in titulo and "%" in conteudo:
            import re
            match = re.search(r"(\d+)%", conteudo)
            pct = int(match.group(1)) if match else 0

            st.markdown(f"""
            <div class="confianca-box">
                <h3>{titulo}</h3>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:{pct}%"></div>
                </div>
                <p style="color:#38bdf8; font-size:1.3rem; font-weight:bold; margin-top:8px;">{pct}%</p>
                <p style="color:#94a3b8;">{conteudo.replace(f"CONFIANÇA: {pct}%", "").strip()}</p>
            </div>
            """, unsafe_allow_html=True)

        elif css_class:
            st.markdown(f"""
            <div class="{css_class}">
                <h3>{titulo}</h3>
                <p style="color:#e2e8f0; line-height:1.7; white-space:pre-line;">{conteudo}</p>
            </div>
            """, unsafe_allow_html=True)

        else:
            st.markdown(f"**{titulo}**")
            st.markdown(f"<p style='color:#cbd5e1; line-height:1.7; white-space:pre-line;'>{conteudo}</p>", unsafe_allow_html=True)

# =====================================================
# PRESSÃO
# =====================================================
def calcular_pressao(stats):
    if not stats or len(stats) < 2:
        return 0

    def pegar(stats_list, nome):
        for item in stats_list:
            if item["type"] == nome:
                valor = item["value"]
                if valor is None:
                    return 0
                try:
                    return int(str(valor).replace("%", ""))
                except:
                    return 0
        return 0

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]
    pontos_home = (
        pegar(home, "Shots on Goal") * 6 +
        pegar(home, "Corner Kicks") * 3 +
        pegar(home, "Total Shots") * 2
    )
    pontos_away = (
        pegar(away, "Shots on Goal") * 6 +
        pegar(away, "Corner Kicks") * 3 +
        pegar(away, "Total Shots") * 2
    )
    return max(pontos_home, pontos_away)

def descrever_stats(stats):
    """Converte as stats em texto para o contexto da IA."""
    if not stats or len(stats) < 2:
        return "Estatísticas indisponíveis."

    def pegar(stats_list, nome):
        for item in stats_list:
            if item["type"] == nome:
                v = item["value"]
                return v if v is not None else 0
        return 0

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]
    time_home = stats[0].get("team", {}).get("name", "Casa")
    time_away = stats[1].get("team", {}).get("name", "Fora")

    return (
        f"{time_home}: Chutes {pegar(home,'Total Shots')}, No gol {pegar(home,'Shots on Goal')}, "
        f"Escanteios {pegar(home,'Corner Kicks')}, Posse {pegar(home,'Ball Possession')}%, "
        f"Faltas {pegar(home,'Fouls')}, Cartões A {pegar(home,'Yellow Cards')}/V {pegar(home,'Red Cards')} | "
        f"{time_away}: Chutes {pegar(away,'Total Shots')}, No gol {pegar(away,'Shots on Goal')}, "
        f"Escanteios {pegar(away,'Corner Kicks')}, Posse {pegar(away,'Ball Possession')}%, "
        f"Faltas {pegar(away,'Fouls')}, Cartões A {pegar(away,'Yellow Cards')}/V {pegar(away,'Red Cards')}"
    )

# =====================================================
# BANCO
# =====================================================
def salvar_resultado(jogo, resultado, confianca):
    try:
        supabase.table("historico").insert({
            "data": datetime.now().isoformat(),
            "jogo": jogo,
            "resultado": resultado,
            "confianca": confianca
        }).execute()
        st.success(f"✅ {resultado} registrado com sucesso!")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.title("🏆 REI DA BOLA")
st.sidebar.markdown("**Painel Premium**")
st.sidebar.markdown("---")

# ---- CONTADOR DE API ----
st.sidebar.markdown("### 🔑 Uso da API Hoje")
chamadas_hoje = get_chamadas_hoje()
restantes = max(0, LIMITE_DIARIO_API - chamadas_hoje)
pct_uso = min(100, int((chamadas_hoje / LIMITE_DIARIO_API) * 100))

st.sidebar.markdown(f"""
<div class="api-counter">
    <span>⚡ {restantes} chamadas restantes</span><br>
    <small style="color:#94a3b8;">Usadas: {chamadas_hoje} / {LIMITE_DIARIO_API}</small>
    <div class="progress-bar" style="margin-top:6px;">
        <div class="progress-fill" style="width:{pct_uso}%; background: linear-gradient(90deg,#22c55e,#ef4444);"></div>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

# ---- HISTÓRICO ----
greens = 0
reds = 0
winrate = 0
try:
    historico = supabase.table("historico").select("*").execute()
    if historico.data:
        df_hist = pd.DataFrame(historico.data)
        greens = len(df_hist[df_hist["resultado"] == "GREEN"])
        reds = len(df_hist[df_hist["resultado"] == "RED"])
        total = greens + reds
        if total > 0:
            winrate = round((greens / total) * 100, 1)
except:
    pass

st.sidebar.metric("✅ Greens", greens)
st.sidebar.metric("❌ Reds", reds)
st.sidebar.metric("📈 Winrate", f"{winrate}%")

# ---- TESTE TELEGRAM ----
st.sidebar.markdown("---")
if st.sidebar.button("Testar Telegram"):
    ok = enviar_telegram("<b>REI DA BOLA</b> - Telegram funcionando!")
    if ok:
        st.sidebar.success("Telegram OK!")
    else:
        st.sidebar.error("Falha no Telegram. Verifique TOKEN e CHAT_ID.")

# =====================================================
# HEADER
# =====================================================
st.title("🏆 IA REI DA BOLA PRO")
st.caption("Radar inteligente para traders esportivos")

# =====================================================
# TABS
# =====================================================
aba1, aba2, aba3 = st.tabs([
    "🎯 AO VIVO",
    "🔮 PRÉ-JOGO",
    "📊 HISTÓRICO"
])

# =====================================================
# ABA 1 - AO VIVO
# =====================================================
with aba1:
    st.subheader("🎯 Radar ao Vivo")

    col_refresh, col_info = st.columns([1, 3])
    with col_refresh:
        atualizar = st.button("🔄 Atualizar jogos")

    with st.spinner("Buscando jogos ao vivo..."):
        jogos_live = fetch_api("fixtures?live=all")
        elite_live = [j for j in jogos_live if j["league"]["id"] in LIGAS_ELITE]

    if not elite_live:
        st.info("⏳ Nenhum jogo ao vivo nas ligas monitoradas no momento.")
    else:
        st.success(f"✅ {len(elite_live)} jogo(s) ao vivo encontrado(s)")

    for jogo in elite_live:
        fixture_id = jogo["fixture"]["id"]
        home = jogo["teams"]["home"]["name"]
        away = jogo["teams"]["away"]["name"]
        gols_home = jogo["goals"]["home"] or 0
        gols_away = jogo["goals"]["away"] or 0
        tempo = jogo["fixture"]["status"]["elapsed"] or "?"
        liga = jogo["league"]["name"]

        with st.expander(f"⏱️ {tempo}' | {liga} | {home} {gols_home}x{gols_away} {away}"):
            col1, col2, col3 = st.columns(3)
            col1.metric("🏠 Mandante", home)
            col2.metric("⚽ Placar", f"{gols_home} - {gols_away}")
            col3.metric("✈️ Visitante", away)

            if st.button("🤖 Consultar IA ao Vivo", key=f"live_{fixture_id}"):
                with st.spinner("Analisando jogo ao vivo..."):
                    stats = fetch_api(f"fixtures/statistics?fixture={fixture_id}")
                    pressao = calcular_pressao(stats)
                    stats_texto = descrever_stats(stats)

                    contexto_ao_vivo = (
                        f"Jogo: {home} x {away}\n"
                        f"Minuto: {tempo}'\n"
                        f"Placar: {home} {gols_home} x {gols_away} {away}\n"
                        f"Liga: {liga}\n"
                        f"Índice de Pressão: {pressao}\n"
                        f"Estatísticas: {stats_texto}"
                    )

                    col_p1, col_p2 = st.columns(2)
                    col_p1.metric("🔥 Pressão", pressao)

                    analise = analisar_ao_vivo(contexto_ao_vivo)
                    renderizar_analise(analise, modo="live")

                    # Enviar ao Telegram
                    msg_telegram = (
                        f"🎯 <b>AO VIVO — REI DA BOLA</b>\n\n"
                        f"⏱️ {tempo}' | {home} {gols_home}x{gols_away} {away}\n"
                        f"Liga: {liga}\n"
                        f"Pressão: {pressao}\n\n"
                        f"{analise[:1000]}"
                    )
                    ok = enviar_telegram(msg_telegram)
                    if ok:
                        st.success("Sinal enviado ao Telegram!")
                    else:
                        st.warning("Analise gerada mas Telegram falhou. Verifique TOKEN/CHAT_ID.")

 
