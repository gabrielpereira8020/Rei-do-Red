import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time
import re

# Importacoes com tratamento de erro claro
try:
    import google.generativeai as genai
except ImportError:
    st.error("Pacote google-generativeai nao instalado. Verifique o requirements.txt")
    st.stop()

try:
    from supabase import create_client
except ImportError:
    st.error("Pacote supabase nao instalado. Verifique o requirements.txt")
    st.stop()

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="IA REI DA BOLA PRO",
    page_icon="",
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
.cravo-box {
    background: linear-gradient(135deg, #1a0a2e, #2d1b69);
    border: 2px solid #f59e0b;
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
}
.cravo-box h3 { color: #f59e0b !important; font-size: 1.4rem; }
.oportunidade-box {
    background: linear-gradient(135deg, #0a1a0a, #1a3a1a);
    border: 2px solid #22c55e;
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
}
.oportunidade-box h3 { color: #22c55e !important; }
.confianca-box {
    background: linear-gradient(135deg, #0a0a2e, #0a1a3a);
    border: 2px solid #38bdf8;
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
}
.confianca-box h3 { color: #38bdf8 !important; }
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
}
.entrada-box {
    background: linear-gradient(135deg, #1a0a0a, #3a1a1a);
    border: 2px solid #ef4444;
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
}
.entrada-box h3 { color: #ef4444 !important; }
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
# LIGAS MONITORADAS
# =====================================================
LIGAS_ELITE = [71, 72, 73, 39, 40, 140, 141, 78, 79, 135, 136, 61, 62, 94]

# =====================================================
# CONTADOR DE CHAMADAS DE API
# =====================================================
LIMITE_DIARIO_API = 100

def get_api_usage_key():
    return "api_calls_" + datetime.now().strftime("%Y-%m-%d")

def registrar_chamada_api():
    key = get_api_usage_key()
    if key not in st.session_state:
        st.session_state[key] = 0
    st.session_state[key] += 1

def get_chamadas_hoje():
    key = get_api_usage_key()
    return st.session_state.get(key, 0)

# =====================================================
# INICIALIZAR SERVICOS
# =====================================================
@st.cache_resource
def init_services():
    try:
        supabase = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"]
        )

        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

        modelos_disponiveis = []
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                modelos_disponiveis.append(m.name)

        if modelos_disponiveis:
            escolhido = next(
                (x for x in modelos_disponiveis if "flash" in x),
                modelos_disponiveis[0]
            )
            model = genai.GenerativeModel(escolhido)
            return supabase, model, escolhido
        else:
            return None, None, None

    except Exception as e:
        st.error("Erro ao iniciar servicos: " + str(e))
        return None, None, None

supabase, gemini, modelo_nome = init_services()

API_KEY = st.secrets["API_KEY"]
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# =====================================================
# FUNCOES DE API FOOTBALL
# =====================================================
@st.cache_data(ttl=60)
def fetch_api(endpoint):
    try:
        url = "https://v3.football.api-sports.io/" + endpoint
        response = requests.get(url, headers=HEADERS, timeout=15)
        registrar_chamada_api()
        if response.status_code != 200:
            return []
        return response.json().get("response", [])
    except Exception:
        return []

# =====================================================
# TELEGRAM
# =====================================================
def enviar_telegram(msg):
    try:
        url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

# =====================================================
# IA - PRE-JOGO
# =====================================================
def analisar_pre_jogo(contexto):
    if not gemini:
        return "ERRO: IA nao inicializada. Verifique a chave GEMINI_API_KEY."
    try:
        prompt = (
            "Voce e o REI DA BOLA, o maior analista de apostas esportivas do Brasil.\n"
            "Analise o jogo abaixo como trader profissional.\n\n"
            "CONTEXTO DO JOGO:\n"
            + contexto +
            "\n\nRetorne EXATAMENTE neste formato:\n\n"
            "VEREDITO:\n"
            "[Opiniao geral sobre o jogo. Quem tem vantagem e por que.]\n\n"
            "CRAVO:\n"
            "[SEU MELHOR PALPITE que voce CRAVO. Seja especifico: vitoria, placar, "
            "gols over/under, escanteios, cartoes, gol de jogador, falta sofrida, etc. "
            "Exemplo: CRAVO vitoria do time X. Pick principal: Over 1.5 gols.]\n\n"
            "OPORTUNIDADE:\n"
            "[2 a 3 mercados secundarios com valor mas sem certeza total. "
            "Ex: escanteios acima de X, cartao para jogador Y, gol no segundo tempo.]\n\n"
            "CONFIANCA:\n"
            "[Porcentagem de 0 a 100 de confianca no CRAVO. "
            "Formato: CONFIANCA: XX% | Motivo: explicacao curta.]\n\n"
            "FEELING:\n"
            "[Seu instinto alem dos numeros como Rei da Bola.]"
        )
        resposta = gemini.generate_content(prompt)
        if hasattr(resposta, "text"):
            return resposta.text
        return "IA sem resposta"
    except Exception as e:
        return "ERRO DA IA: " + str(e)

# =====================================================
# IA - AO VIVO
# =====================================================
def analisar_ao_vivo(contexto_ao_vivo):
    if not gemini:
        return "ERRO: IA nao inicializada. Verifique a chave GEMINI_API_KEY."
    try:
        prompt = (
            "Voce e o REI DA BOLA, especialista em trading ao vivo.\n"
            "Analise o momento atual do jogo e diga O QUE FAZER AGORA.\n\n"
            "CONTEXTO AO VIVO:\n"
            + contexto_ao_vivo +
            "\n\nRetorne EXATAMENTE neste formato:\n\n"
            "ENTRADA RECOMENDADA:\n"
            "[PODE ENTRAR AGORA em qual mercado? Seja direto: vitoria, empate, gols, "
            "escanteios, cartoes. Ex: ENTRA AGORA em Over 2.5 gols. Jogo aberto, muito movimento.]\n\n"
            "CRAVO AO VIVO:\n"
            "[Melhor palpite para os proximos minutos ou resultado final. "
            "Pode ser virada, mais um gol, escanteio, cartao, chute a gol.]\n\n"
            "CONFIANCA:\n"
            "[Porcentagem de confianca. Formato: CONFIANCA: XX%]\n\n"
            "RISCOS:\n"
            "[1 ou 2 riscos principais desta entrada.]\n\n"
            "FEELING AO VIVO:\n"
            "[Seu instinto neste momento do jogo.]"
        )
        resposta = gemini.generate_content(prompt)
        if hasattr(resposta, "text"):
            return resposta.text
        return "IA sem resposta"
    except Exception as e:
        return "ERRO DA IA: " + str(e)

# =====================================================
# RENDERIZAR ANALISE COM CAIXAS VISUAIS
# =====================================================
def renderizar_analise(texto):
    if not texto or texto.startswith("ERRO"):
        st.error(texto)
        return

    mapa_secoes = {
        "VEREDITO": ("", "#7a3cff"),
        "CRAVO": ("cravo-box", "#f59e0b"),
        "ENTRADA RECOMENDADA": ("entrada-box", "#ef4444"),
        "CRAVO AO VIVO": ("cravo-box", "#f59e0b"),
        "OPORTUNIDADE": ("oportunidade-box", "#22c55e"),
        "CONFIANCA": ("confianca-box", "#38bdf8"),
        "FEELING": ("", "#a78bfa"),
        "FEELING AO VIVO": ("", "#a78bfa"),
        "RISCOS": ("", "#f87171"),
    }

    linhas = texto.split("\n")
    secao_atual = None
    conteudo_atual = []
    blocos = []

    for linha in linhas:
        linha_strip = linha.strip()
        encontrou = False
        for chave in mapa_secoes:
            if linha_strip.upper().startswith(chave + ":") or linha_strip.upper() == chave + ":":
                if secao_atual:
                    blocos.append((secao_atual, "\n".join(conteudo_atual).strip()))
                secao_atual = chave
                resto = linha_strip[len(chave):].lstrip(":").strip()
                conteudo_atual = [resto] if resto else []
                encontrou = True
                break
        if not encontrou and secao_atual is not None:
            conteudo_atual.append(linha)

    if secao_atual:
        blocos.append((secao_atual, "\n".join(conteudo_atual).strip()))

    if not blocos:
        st.markdown(texto)
        return

    for titulo, conteudo in blocos:
        css_class, cor = mapa_secoes.get(titulo, ("", "#fff"))

        if "CONFIANCA" in titulo and "%" in conteudo:
            match = re.search(r"(\d+)%", conteudo)
            pct = int(match.group(1)) if match else 0
            explicacao = conteudo.replace("CONFIANCA: " + str(pct) + "%", "").replace("Motivo:", "").strip()
            st.markdown(
                "<div class='confianca-box'>"
                "<h3>CONFIANCA</h3>"
                "<div class='progress-bar'>"
                "<div class='progress-fill' style='width:" + str(pct) + "%'></div>"
                "</div>"
                "<p style='color:#38bdf8;font-size:1.3rem;font-weight:bold;margin-top:8px;'>"
                + str(pct) + "%</p>"
                "<p style='color:#94a3b8;'>" + explicacao + "</p>"
                "</div>",
                unsafe_allow_html=True
            )
        elif css_class:
            st.markdown(
                "<div class='" + css_class + "'>"
                "<h3>" + titulo + "</h3>"
                "<p style='color:#e2e8f0;line-height:1.7;white-space:pre-line;'>"
                + conteudo + "</p>"
                "</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown("**" + titulo + "**")
            st.markdown(
                "<p style='color:#cbd5e1;line-height:1.7;white-space:pre-line;'>"
                + conteudo + "</p>",
                unsafe_allow_html=True
            )

# =====================================================
# CALCULAR PRESSAO
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
                except Exception:
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
    if not stats or len(stats) < 2:
        return "Estatisticas indisponiveis."

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
        time_home + ": Chutes " + str(pegar(home, "Total Shots")) +
        ", No gol " + str(pegar(home, "Shots on Goal")) +
        ", Escanteios " + str(pegar(home, "Corner Kicks")) +
        ", Posse " + str(pegar(home, "Ball Possession")) + "%" +
        ", Faltas " + str(pegar(home, "Fouls")) +
        ", Cartoes A" + str(pegar(home, "Yellow Cards")) +
        "/V" + str(pegar(home, "Red Cards")) +
        " | " +
        time_away + ": Chutes " + str(pegar(away, "Total Shots")) +
        ", No gol " + str(pegar(away, "Shots on Goal")) +
        ", Escanteios " + str(pegar(away, "Corner Kicks")) +
        ", Posse " + str(pegar(away, "Ball Possession")) + "%" +
        ", Faltas " + str(pegar(away, "Fouls")) +
        ", Cartoes A" + str(pegar(away, "Yellow Cards")) +
        "/V" + str(pegar(away, "Red Cards"))
    )

# =====================================================
# SALVAR RESULTADO
# =====================================================
def salvar_resultado(jogo, resultado, confianca):
    try:
        supabase.table("historico").insert({
            "data": datetime.now().isoformat(),
            "jogo": jogo,
            "resultado": resultado,
            "confianca": confianca
        }).execute()
        st.success(resultado + " registrado com sucesso!")
    except Exception as e:
        st.error("Erro ao salvar: " + str(e))

# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.title("REI DA BOLA")
st.sidebar.markdown("**Painel Premium**")
if modelo_nome:
    st.sidebar.caption("Modelo: " + modelo_nome)
st.sidebar.markdown("---")

# Contador de API
st.sidebar.markdown("### Uso da API Hoje")
chamadas_hoje = get_chamadas_hoje()
restantes = max(0, LIMITE_DIARIO_API - chamadas_hoje)
pct_uso = min(100, int((chamadas_hoje / LIMITE_DIARIO_API) * 100))

st.sidebar.markdown(
    "<div class='api-counter'>"
    "<span>" + str(restantes) + " chamadas restantes</span><br>"
    "<small style='color:#94a3b8;'>Usadas: " + str(chamadas_hoje) + " / " + str(LIMITE_DIARIO_API) + "</small>"
    "<div class='progress-bar' style='margin-top:6px;'>"
    "<div class='progress-fill' style='width:" + str(pct_uso) + "%;background:linear-gradient(90deg,#22c55e,#ef4444);'></div>"
    "</div>"
    "</div>",
    unsafe_allow_html=True
)
st.sidebar.markdown("---")

# Historico sidebar
greens = 0
reds = 0
winrate = 0
try:
    historico_data = supabase.table("historico").select("*").execute()
    if historico_data.data:
        df_hist = pd.DataFrame(historico_data.data)
        greens = len(df_hist[df_hist["resultado"] == "GREEN"])
        reds = len(df_hist[df_hist["resultado"] == "RED"])
        total = greens + reds
        if total > 0:
            winrate = round((greens / total) * 100, 1)
except Exception:
    pass

st.sidebar.metric("Greens", greens)
st.sidebar.metric("Reds", reds)
st.sidebar.metric("Winrate", str(winrate) + "%")

st.sidebar.markdown("---")
if st.sidebar.button("Testar Telegram"):
    ok = enviar_telegram("<b>REI DA BOLA</b> - Telegram funcionando!")
    if ok:
        st.sidebar.success("Telegram OK!")
    else:
        st.sidebar.error("Falha. Verifique TOKEN e CHAT_ID.")

# =====================================================
# HEADER
# =====================================================
st.title("IA REI DA BOLA PRO")
st.caption("Radar inteligente para traders esportivos")

# =====================================================
# TABS
# =====================================================
aba1, aba2, aba3 = st.tabs(["AO VIVO", "PRE-JOGO", "HISTORICO"])

# =====================================================
# ABA 1 - AO VIVO
# =====================================================
with aba1:
    st.subheader("Radar ao Vivo")

    if st.button("Atualizar jogos"):
        st.cache_data.clear()

    with st.spinner("Buscando jogos ao vivo..."):
        jogos_live = fetch_api("fixtures?live=all")
        elite_live = [j for j in jogos_live if j["league"]["id"] in LIGAS_ELITE]

    if not elite_live:
        st.info("Nenhum jogo ao vivo nas ligas monitoradas no momento.")
    else:
        st.success(str(len(elite_live)) + " jogo(s) ao vivo encontrado(s)")

    for jogo in elite_live:
        fixture_id = jogo["fixture"]["id"]
        home = jogo["teams"]["home"]["name"]
        away = jogo["teams"]["away"]["name"]
        gols_home = jogo["goals"]["home"] or 0
        gols_away = jogo["goals"]["away"] or 0
        tempo = jogo["fixture"]["status"]["elapsed"] or "?"
        liga = jogo["league"]["name"]

        with st.expander(str(tempo) + "' | " + liga + " | " + home + " " + str(gols_home) + "x" + str(gols_away) + " " + away):
            col1, col2, col3 = st.columns(3)
            col1.metric("Mandante", home)
            col2.metric("Placar", str(gols_home) + " - " + str(gols_away))
            col3.metric("Visitante", away)

            if st.button("Consultar IA ao Vivo", key="live_" + str(fixture_id)):
                with st.spinner("Analisando jogo ao vivo..."):
                    stats = fetch_api("fixtures/statistics?fixture=" + str(fixture_id))
                    pressao = calcular_pressao(stats)
                    stats_texto = descrever_stats(stats)

                    contexto_ao_vivo = (
                        "Jogo: " + home + " x " + away + "\n"
                        "Minuto: " + str(tempo) + "\n"
                        "Placar: " + home + " " + str(gols_home) + " x " + str(gols_away) + " " + away + "\n"
                        "Liga: " + liga + "\n"
                        "Indice de Pressao: " + str(pressao) + "\n"
                        "Estatisticas: " + stats_texto
                    )

                    st.metric("Pressao", pressao)

                    analise = analisar_ao_vivo(contexto_ao_vivo)
                    renderizar_analise(analise)

                    msg_telegram = (
                        "<b>AO VIVO - REI DA BOLA</b>\n\n"
                        + str(tempo) + "' | " + home + " " + str(gols_home) + "x" + str(gols_away) + " " + away + "\n"
                        "Liga: " + liga + "\n"
                        "Pressao: " + str(pressao) + "\n\n"
                        + analise[:1000]
                    )
                    ok = enviar_telegram(msg_telegram)
            
