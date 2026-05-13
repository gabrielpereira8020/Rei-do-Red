import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from supabase import create_client, Client
from datetime import datetime, timedelta
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURAÇÕES DE ELITE ---
st.set_page_config(page_title="IA Rei da Bola: Ultimate Pro", page_icon="⚽", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 10px; }
    .stExpander { border: 1px solid #30363d; background-color: #0d1117; }
    </style>
    """, unsafe_allow_html=True)

st_autorefresh(interval=120000, key="global_refresh")

# --- INICIALIZAÇÃO DE SERVIÇOS ---
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def init_gemini():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-1.5-flash')

supabase = init_supabase()
gemini = init_gemini()

# --- CLASSE DE DADOS (ARQUITETURA COMPLEXA) ---
class FootballData:
    def __init__(self):
        self.headers = {'x-rapidapi-key': st.secrets["API_KEY"]}
        self.sm_key = st.secrets["SPORTMONKS_KEY"]

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
        return res[:5]

    @st.cache_data(ttl=1800)
    def get_all_day_fixtures(_self, date_str):
        # BUSCA AMPLA: Sem filtros de liga para garantir que nada escape
        url = f"https://v3.football.api-sports.io/fixtures?date={date_str}"
        return requests.get(url, headers=_self.headers).json().get('response', [])

# --- CORE LOGIC: IA ANALYST ---
def gerar_analise_ia(contexto, tipo="live"):
    prompt = f"""
    Aja como um Senior Football Analyst & Professional Trader.
    CONTEXTO: {contexto}
    TIPO: {tipo.upper()}
    
    REGRAS DE OURO:
    1. Analise se a pressão (IG) é condizente com a realidade.
    2. No Pré-jogo, use seu conhecimento sobre a força das ligas.
    3. Dê uma recomendação: 'ENTRADA SUGERIDA' ou 'FIQUE DE FORA'.
    4. Confiança de 0-100%. Seja crítico.
    """
    try:
        return gemini.generate_content(prompt).text
    except: return "🤖 IA recalculando... tente em instantes."

# --- DATABASE ---
def db_salvar(jogo, ig, resultado, mercado):
    supabase.table("historico").insert({
        "data": datetime.now().isoformat(),
        "jogo": jogo, "ig": ig, "resultado": resultado, "mercado": mercado
    }).execute()

# --- INTERFACE PRINCIPAL ---
st.title("⚡ IA REI DA BOLA: SISTEMA DE ELITE")
fd = FootballData()

# Sidebar Performance
with st.sidebar:
    st.header("📊 Global Performance")
    try:
        res = supabase.table("historico").select("*").execute()
        df_stats = pd.DataFrame(res.data)
        if not df_stats.empty:
            greens = len(df_stats[df_stats['resultado'].str.contains("GREEN")])
            reds = len(df_stats[df_stats['resultado'].str.contains("RED")])
            st.metric("Win Rate", f"{(greens/(greens+reds)*100):.1f}%" if (greens+reds)>0 else "0%")
    except: st.write("Banco sincronizado.")

tab_live, tab_pre, tab_db = st.tabs(["🎯 LIVE RADAR", "🔮 PRÉ-JOGO EXPERT", "📈 PERFORMANCE"])

# --- TAB 1: AO VIVO (COM RAIO-X) ---
with tab_live:
    fixtures = fd.get_live_fixtures()
    if not fixtures:
        st.info("Varrendo ligas em busca de oportunidades...")
    else:
        for f in fixtures:
            id_j = f['fixture']['id']
            casa, fora = f['teams']['home']['name'], f['teams']['away']['name']
            tempo = f['fixture']['status']['elapsed'] or 0
            placar = f"{f['goals']['home']}x{f['goals']['away']}"
            
            # Stats em tempo real
            s_res = fd.get_match_stats(id_j)
            no_alvo, atq_p, cantos = 0, 0, 0
            if s_res:
                for s in s_res:
                    for item in s['statistics']:
                        v = item['value'] or 0
                        if "Shots on Goal" in item['type']: no_alvo += v
                        if "Dangerous Attacks" in item['type']: atq_p += v
                        if "Corner Kicks" in item['type']: cantos += v

            ig = (no_alvo * 6) + (atq_p * 0.35) + (cantos * 2)
            
            if ig > 20:
                with st.expander(f"🏟️ {casa} {placar} {fora} ({tempo}') | IG: {ig:.1f}"):
                    c1, c2, c3 = st.columns([1, 1, 2])
                    with c1:
                        st.write(f"🎯 Alvo: {no_alvo}\n🧨 Atq.P: {atq_p}")
                    with c2:
                        st.metric("Índice Gols", f"{ig:.1f}")
                    with c3:
                        if st.button("🧠 Consultar Gemini", key=f"btn_{id_j}"):
                            st.info(gerar_analise_ia(f"{casa}x{fora}, {tempo}', IG:{ig:.1f}"))
                    
                    st.divider()
                    cb1, cb2 = st.columns(2)
                    if cb1.button("✅ GREEN", key=f"win_{id_j}"):
                        db_salvar(f"{casa}x{fora}", ig, "✅ GREEN", "Live")
                        st.rerun()
                    if cb2.button("❌ RED", key=f"red_{id_j}"):
                        db_salvar(f"{casa}x{fora}", ig, "❌ RED", "Live")
                        st.rerun()

# --- TAB 2: PRÉ-JOGO (COMPLEXO + FIX DE VISIBILIDADE) ---
with tab_pre:
    st.subheader("🔮 Prognósticos Master - Próximas 24h")
    hoje_str = datetime.now().strftime("%Y-%m-%d")
    pre_fixtures = fd.get_all_day_fixtures(hoje_str)
    
    if pre_fixtures:
        # NS = Not Started (Jogos que vão começar)
        jogos_futuros = [pf for pf in pre_fixtures if pf['fixture']['status']['short'] == "NS"]
        
        if not jogos_futuros:
            st.warning("Os principais jogos de hoje já estão em andamento (veja no Radar Live).")
        else:
            for pf in jogos_futuros[:40]: # Mostra os 40 principais
                id_pf = pf['fixture']['id']
                c_n, f_n = pf['teams']['home']['name'], pf['teams']['away']['name']
                liga = pf['league']['name']
                hora = pf['fixture']['date'][11:16]
                
                with st.expander(f"📅 {hora} | {liga}: {c_n} x {f_n}"):
                    if st.button(f"🔍 Gerar Dossiê de Elite", key=f"pre_{id_pf}"):
                        with st.spinner("IA cruzando H2H e tendências..."):
                            h2h = fd.get_h2h(pf['teams']['home']['id'], pf['teams']['away']['id'])
                            h2h_txt = "\n".join([f"{m['fixture']['date'][:10]}: {m['goals']['home']}x{m['goals']['away']}" for m in h2h])
                            
                            ctx = f"Jogo: {c_n}x{f_n}\nLiga: {liga}\nH2H Recente:\n{h2h_txt}"
                            st.markdown(f"### 🤖 Veredito:\n{gerar_analise_ia(ctx, 'pre-jogo')}")
    else:
        st.error("Erro ao carregar lista de jogos. Verifique o limite da API.")

# --- TAB 3: PERFORMANCE ---
with tab_db:
    try:
        data = supabase.table("historico").select("*").execute()
        if data.data:
            df = pd.DataFrame(data.data).sort_values(by='data', ascending=False)
            st.plotly_chart(px.pie(df, names="resultado", color="resultado", 
                                   color_discrete_map={"✅ GREEN": "#2ecc71", "❌ RED": "#e74c3c"}))
            st.dataframe(df, use_container_width=True)
    except: st.error("Banco de dados não encontrado.")
