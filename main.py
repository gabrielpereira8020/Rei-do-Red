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

.main {
    background-color: #0b1020;
}

.block-container {
    padding-top: 1rem;
}

h1, h2, h3 {
    color: white;
}

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

div[data-testid="stSidebar"] {
    background-color: #111827;
}

</style>
""", unsafe_allow_html=True)

# =====================================================
# LIGAS
# =====================================================

LIGAS_ELITE = [71,72,73,39,40,140,141,78,79,135,136,61,62,94]

# =====================================================
# INIT
# =====================================================

@st.cache_resource
def init_services():
    try:
        supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Modelo Flash 1.5 é o segredo para não travar
        model = genai.GenerativeModel("gemini-1.5-flash")
        return supabase, model
    except Exception as e:
        st.error(f"Erro: {e}")
        return None, None

supabase, model = init_services()


API_KEY = st.secrets["API_KEY"]

HEADERS = {
    'x-rapidapi-key': API_KEY,
    'x-rapidapi-host': 'v3.football.api-sports.io'
}

# =====================================================
# API
# =====================================================

@st.cache_data(ttl=60)
def fetch_api(endpoint):

    try:

        url = f"https://v3.football.api-sports.io/{endpoint}"

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        if response.status_code != 200:
            return []

        return response.json().get("response", [])

    except:
        return []

# ==========================================
# TELEGRAM
# ==========================================

def enviar_telegram(msg):

    try:

        url = (
            f"https://api.telegram.org/bot"
            f"{TELEGRAM_TOKEN}/sendMessage"
        )

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg
        }

        requests.post(
            url,
            json=payload,
            timeout=10
        )

    except:
        pass


# ==========================================================
# IA -
# ==========================================================

# 1. FUNÇÃO DA IA (As instruções que o Rei segue)
def analisar_com_ia(dados_do_jogo):
    # Esta função APENAS cria o texto das instruções
    prompt = f"""
    Você é o Analista Senior do 'IA REI DA BOLA PRO'. 
    Sua missão é dar um palpite de alta precisão.
    Analise obrigatoriamente: Gols, Escanteios (Corners) e Cartões.
    
    Responda EXATAMENTE neste formato (não use introduções):

    🎯 **O PALPITE DO REI (A CRAVADA)**
    [Sua melhor entrada entre Gols, Cantos ou Cartões]

    💰 **ALAVANCAGEM (ODD ALTA)**
    [Sugestão de Odd acima de 2.0]

    📈 **RADAR DE TENDÊNCIAS**
    - Escanteios: [Tendência com base na pressão]
    - Cartões: [Tendência de cartões]

    ⚠️ **VEREDITO AO VIVO**
    [ENTRAR AGORA | AGUARDAR ODD | FORA DO RADAR]

    DADOS DO JOGO:
    {dados_do_jogo}
    """
    return prompt
    

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

        st.success(f"{resultado} registrado")

    except Exception as e:

        st.error(f"Erro ao salvar: {e}")

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.title("🏆 REI DA BOLA")
st.sidebar.markdown("Painel Premium")

# =====================================================
# HISTÓRICO
# =====================================================

greens = 0
reds = 0
winrate = 0

try:

    historico = supabase.table("historico").select("*").execute()

    if historico.data:

        df_hist = pd.DataFrame(historico.data)

        greens = len(
            df_hist[df_hist["resultado"] == "GREEN"]
        )

        reds = len(
            df_hist[df_hist["resultado"] == "RED"]
        )

        total = greens + reds

        if total > 0:
            winrate = round(
                (greens / total) * 100,
                1
            )

except:
    pass

st.sidebar.metric("✅ Greens", greens)
st.sidebar.metric("❌ Reds", reds)
st.sidebar.metric("📈 Winrate", f"{winrate}%")

# =====================================================
# HEADER
# =====================================================

TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
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
# AO VIVO
# =====================================================

with aba1:
        st.subheader("🎯 Radar ao Vivo")
        
        jogos = fetch_api("fixtures?live=all")
        elite = [j for j in jogos if j["league"]["id"] in LIGAS_ELITE]
        
        if not elite:
            st.info("Buscando jogos de elite...")
            
        for jogo in elite:
            fixture_id = jogo["fixture"]["id"]
            home = jogo["teams"]["home"]["name"]
            away = jogo["teams"]["away"]["name"]
            gols_home = jogo["goals"]["home"]
            gols_away = jogo["goals"]["away"]
            tempo = jogo["fixture"]["status"]["elapsed"]
            
            with st.expander(f"⏱️ {tempo}' | {home} {gols_home} x {gols_away} {away}"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Mandante", home)
                col2.metric("Placar", f"{gols_home}-{gols_away}")
                col3.metric("Visitante", away)
                
                # BOTÃO DE CONSULTA
                if st.button("Consultar IA", key=f"live_{fixture_id}"):
                    with st.spinner("O Rei está analisando o campo..."):
                        # 1. Pega os dados reais da API
                        stats = fetch_api(f"fixtures/statistics?fixture={fixture_id}")
                        pressao = calcular_pressao(stats)
                        
                        # 2. Prepara o pacote de dados
                        dados_brutos = f"Jogo: {home} x {away}, Minuto: {tempo}, Pressão: {pressao}, Stats: {stats}"
                        
                        # 3. Pega as instruções (Prompt)
                        instrucoes = analisar_com_ia(dados_brutos)
                        
                        try:
                            # 4. AQUI MORA O SEGREDO: Envia para o Google e recebe a resposta
                            resultado_ia = model.generate_content(instrucoes)
                            
                            # 5. MOSTRA A RESPOSTA REAL (response.text)
                            st.markdown("---")
                            st.markdown(resultado_ia.text) # <--- Mostra o palpite, não as instruções
                            st.markdown("---")
                            st.metric("🔥 Pressão Atual", pressao)
                        except Exception as e:
                            st.error(f"Erro na IA: {e}")

                # BOTOES DE RESULTADO (Alinhados fora do IF da IA)
                c1, c2 = st.columns(2)
                if c1.button("✅ GREEN", key=f"green_{fixture_id}"):
                    salvar_resultado(f"{home} x {away}", "GREEN", 100)
                    st.success("Registrado!")
                
                if c2.button("❌ RED", key=f"red_{fixture_id}"):
                    salvar_resultado(f"{home} x {away}", "RED", 0)
                    st.error("Registrado!")
                    
                    
                    

# =====================================================
# PRÉ JOGO
# =====================================================

with aba2:
        st.subheader("📅 Análise Pré-Jogo")
        
        hoje = datetime.now().strftime('%Y-%m-%d')
        with st.spinner("Buscando agenda..."):
            agenda = fetch_api(f"fixtures?date={hoje}")
        
        jogos_pre = [
            j for j in agenda 
            if j["league"]["id"] in LIGAS_ELITE
        ]
        
        if not jogos_pre:
            st.info("Nenhum jogo de elite agendado para hoje.")

        for jogo in jogos_pre:
            home = jogo["teams"]["home"]["name"]
            away = jogo["teams"]["away"]["name"]
            fixture_id = jogo["fixture"]["id"]
            
        with st.expander(f"⚽ {home} x {away}"):
            if st.button("Gerar Análise Real", key=f"pre_{fixture_id}"):
            with st.spinner("O Rei está estudando as equipes..."):
            # 1. Gera as instruções
            prompt_instrucoes = analisar_com_ia(f"Pré-jogo: {home} x {away}")
            
            try:
                # 2. CHAMA A IA DE VERDADE (Essa parte substitui o antigo 'analise')
                response = model.generate_content(prompt_instrucoes)
                
                # 3. MOSTRA O TEXTO QUE A IA ESCREVEU
                st.markdown("---")
                st.markdown(response.text) 
                st.markdown("---")
            except Exception as e:
                st.error(f"Erro na análise: {e}")
                            

# =====================================================
# HISTÓRICO
# =====================================================

with aba3:

    st.subheader("📊 Histórico")

    try:

        historico = supabase.table(
            "historico"
        ).select("*").execute()

        if historico.data:

            df = pd.DataFrame(historico.data)

            st.dataframe(
                df.sort_values(
                    "data",
                    ascending=False
                ),
                use_container_width=True
            )

        else:
            st.info("Sem histórico")

    except Exception as e:

        st.error(f"Erro: {e}")
