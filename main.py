import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from supabase import create_client, Client
from datetime import datetime, timedelta
import plotly.express as px # Para gráficos de performance
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURAÇÕES DE INTERFACE ---
st.set_page_config(
    page_title="IA Rei da Bola: Ultimate Pro",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS Customizado para parecer um Terminal de Trading
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 10px; }
    .stExpander { border: 1px solid #30363d; background-color: #0d1117; }
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE SERVIÇOS ---

@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def init_gemini():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-1.5-flash')

supabase = init_supabase()
gemini = init_gemini()
st_autorefresh(interval=120000, key="global_refresh")

# --- CORE LOGIC: API WRAPPERS ---

class FootballData:
    def __init__(self):
        self.api_key = st.secrets["API_KEY"]
        self.sm_key = st.secrets["SPORTMONKS_KEY"]
        self.headers = {'x-rapidapi-key': self.api_key}

    @st.cache_data(ttl=120)
    def get_live_fixtures(_self):
        url = "https://v3.football.api-sports.io/fixtures?live=all"
        return requests.get(url, headers=_self.headers).json().get('response', [])

    @st.cache_data(ttl=60)
    def get_match_stats(_self, fixture_id):
        url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
        return requests.get(url, headers=_self.headers).json().get('response', [])

    @st.cache_data(ttl=3600)
    def get_h2h(_self, id1, id2):
        url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={id1}-{id2}"
        res = requests.get(url, headers=_self.headers).json().get('response', [])
        return res[:5] # Últimos 5 jogos

    def get_injuries(self, team_id):
        # Integração com Sportmonks para lesões
        try:
            url = f"https://api.sportmonks.com/v3/football/injuries/teams/{team_id}?api_token={self.sm_key}"
            res = requests.get(url).json().get('data', [])
            return res
        except: return []

# --- CORE LOGIC: IA ANALYST ---

def gerar_analise_ia(contexto, tipo="live"):
    prompt = f"""
    Aja como um Senior Football Analyst & Professional Bettor.
    CONTEXTO: {contexto}
    TIPO DE ANÁLISE: {tipo.upper()}
    
    TAREFA:
    1. Avalie se a pressão estatística condiz com o momento do jogo.
    2. Identifique anomalias (ex: muito IG mas poucos chutes reais).
    3. Dê uma recomendação de entrada (Back, Lay, Over, Under ou Cantos).
    4. Atribua um índice de confiança de 0 a 100%.
    
    Seja cético. Se o jogo estiver 'morno', diga para não entrar.
    """
    try:
        response = gemini.generate_content(prompt)
        return response.text
    except: return "🤖 IA temporariamente indisponível."

# --- DATABASE OPS ---

def db_salvar_entrada(jogo, ig, resultado, mercado, lucro=0):
    supabase.table("historico").insert({
        "data": datetime.now().isoformat(),
        "jogo": jogo,
        "ig": ig,
        "resultado": resultado,
        "mercado": mercado,
        "lucro": lucro
    }).execute()

# --- INTERFACE: SIDEBAR (STATS GERAIS) ---

with st.sidebar:
    st.header("📊 Global Performance")
    try:
        res = supabase.table("historico").select("*").execute()
        df_stats = pd.DataFrame(res.data)
        if not df_stats.empty:
            greens = len(df_stats[df_stats['resultado'].str.contains("GREEN")])
            reds = len(df_stats[df_stats['resultado'].str.contains("RED")])
            st.metric("Win Rate", f"{(greens/(greens+reds)*100):.1f}%")
            st.metric("Total de Entradas", len(df_stats))
    except: st.write("Aguardando primeiras entradas...")

# --- INTERFACE: MAIN TABS ---

tab_live, tab_pre, tab_db = st.tabs(["🔥 LIVE RADAR", "🔮 PRE-MATCH AI", "📈 HISTORY & ANALYTICS"])
fd = FootballData()

# --- TAB 1: AO VIVO ---
with tab_live:
    fixtures = fd.get_live_fixtures()
    if not fixtures:
        st.info("Nenhum jogo relevante ao vivo agora.")
    else:
        for f in fixtures:
            id_j = f['fixture']['id']
            casa = f['teams']['home']['name']
            fora = f['teams']['away']['name']
            placar = f"{f['goals']['home']}x{f['goals']['away']}"
            tempo = f['fixture']['status']['elapsed']
            
            # Cálculo de Pressão Real
            stats = fd.get_match_stats(id_j)
            no_alvo, fora_alvo, ataques_p, escanteios = 0, 0, 0, 0
            
            if stats:
                for s in stats:
                    for item in s['statistics']:
                        val = item['value'] or 0
                        t = item['type']
                        if "Shots on Goal" in t: no_alvo += val
                        if "Shots off Goal" in t: fora_alvo += val
                        if "Dangerous Attacks" in t: ataques_p += val
                        if "Corner Kicks" in t: escanteios += val

            # Fórmulas de Elite
            ig = (no_alvo * 6) + (ataques_p * 0.35) + (escanteios * 2)
            ic = ((no_alvo + fora_alvo) * 3) + (ataques_p * 0.45)

            if ig > 20 or ic > 25:
                with st.expander(f"🏟️ {casa} {placar} {fora} ({tempo}') | IG: {ig:.1f}"):
                    c1, c2, c3 = st.columns([1, 1, 2])
                    with c1:
                        st.write("**Estatísticas Brutas**")
                        st.write(f"🎯 Alvo: {no_alvo}")
                        st.write(f"🧨 Atq. Perigosos: {ataques_p}")
                        st.write(f"🚩 Cantos: {escanteios}")
                    with c2:
                        st.write("**Índices de Pressão**")
                        st.metric("Índice Gols", f"{ig:.1f}")
                        st.metric("Índice Cantos", f"{ic:.1f}")
                    with c3:
                        if st.button(f"🧠 Gemini Master Analysis", key=f"gem_{id_j}"):
                            with st.spinner("IA processando comportamento tático..."):
                                ctx = f"{casa}x{fora}, {tempo}min, Placar: {placar}, IG:{ig}, Cantos:{escanteios}"
                                st.info(gerar_analise_ia(ctx))

                    st.divider()
                    cb1, cb2, cb3 = st.columns(3)
                    if cb1.button("✅ GREEN", key=f"win_{id_j}"):
                        db_salvar_entrada(f"{casa}x{fora}", ig, "✅ GREEN", "Live")
                        st.rerun()
                    if cb2.button("❌ RED", key=f"red_{id_j}"):
                        db_salvar_entrada(f"{casa}x{fora}", ig, "❌ RED", "Live")
                        st.rerun()

# --- TAB 2: PRÉ-JOGO ---
tab_pre:
    st.subheader("🔮 Prognósticos IA para as próximas 24h")
    # Busca jogos de amanhã
    amanha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    url_pre = f"https://v3.football.api-sports.io/fixtures?date={amanha}"
    pre_fixtures = requests.get(url_pre, headers=fd.headers).json().get('response', [])
    
    # Filtro de Ligas Principais (Brasil, Euro, Libertadores)
    ligas_permitidas = [13, 71, 39, 140, 135, 78, 61]
    
    for pf in pre_fixtures:
        if pf['league']['id'] in ligas_permitidas:
            id_pf = pf['fixture']['id']
            t_casa = pf['teams']['home']
            t_fora = pf['teams']['away']
            
            with st.expander(f"📅 {pf['fixture']['date'][11:16]} | {pf['league']['name']}: {t_casa['name']} vs {t_fora['name']}"):
                col_pre1, col_pre2 = st.columns([1, 1])
                
                if st.button(f"🔍 Gerar Dossiê Completo", key=f"dossie_{id_pf}"):
                    with st.spinner("Cruzando H2H e Dados Históricos..."):
                        h2h = fd.get_h2h(t_casa['id'], t_fora['id'])
                        h2h_str = "\n".join([f"{m['fixture']['date'][:10]}: {m['goals']['home']}x{m['goals']['away']}" for m in h2h])
                        
                        ctx_pre = f"""
                        Jogo: {t_casa['name']} x {t_fora['name']}
                        Liga: {pf['league']['name']}
                        H2H Recente: {h2h_str}
                        """
                        analise_pre = gerar_analise_ia(ctx_pre, tipo="pre-jogo")
                        st.markdown(f"### 🤖 Parecer Especialista:\n{analise_pre}

# --- TAB 3: PERFORMANCE & ANALYTICS ---
with tab_db:
    st.subheader("📈 Gestão de Banca e Performance")
    res_db = supabase.table("historico").select("*").execute()
    if res_db.data:
        df_final = pd.DataFrame(res_db.data)
        
        # Gráfico de Evolução (Exemplo simples)
        df_final['data'] = pd.to_datetime(df_final['data'])
        fig = px.line(df_final, x="data", y="ig", title="Oscilação de IG das Entradas", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(df_final.sort_values(by='data', ascending=False), use_container_width=True)
    else:
        st.info("Nenhuma entrada registrada no histórico.")
