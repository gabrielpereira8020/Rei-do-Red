import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from supabase import create_client, Client
from datetime import datetime, timedelta
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURAÇÕES DE INTERFACE ---
st.set_page_config(
    page_title="IA Rei da Bola: Ultimate Pro",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo Dark Mode Profissional
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 10px; }
    .stExpander { border: 1px solid #30363d; background-color: #0d1117; }
    </style>
    """, unsafe_allow_html=True)

# Auto-refresh do Radar a cada 2 minutos
st_autorefresh(interval=120000, key="global_refresh")

# --- 2. INICIALIZAÇÃO DE SERVIÇOS (7 CHAVES) ---
@st.cache_resource
def init_supabase() -> Client:
    # Usa chaves: SUPABASE_URL e SUPABASE_KEY
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def init_gemini():
    # Usa chave: GEMINI_API_KEY
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-1.5-flash')

supabase = init_supabase()
gemini = init_gemini()

# --- 3. CLASSE DE DADOS (API-FOOTBALL + SPORTMONKS) ---
class FootballData:
    def __init__(self):
        # Usa chaves: API_KEY e SPORTMONKS_KEY
        self.headers = {'x-rapidapi-key': st.secrets["API_KEY"]}
        self.sm_token = st.secrets["SPORTMONKS_KEY"]

    @st.cache_data(ttl=120)
    def get_live(_self):
        url = "https://v3.football.api-sports.io/fixtures?live=all"
        return requests.get(url, headers=_self.headers).json().get('response', [])

    @st.cache_data(ttl=60)
    def get_stats(_self, fid):
        url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fid}"
        return requests.get(url, headers=_self.headers).json().get('response', [])

    @st.cache_data(ttl=3600)
    def get_pre_match(_self, date_str):
        url = f"https://v3.football.api-sports.io/fixtures?date={date_str}"
        return requests.get(url, headers=_self.headers).json().get('response', [])

# --- 4. FUNÇÕES DE SUPORTE ---
def gerar_analise_ia(contexto, tipo="live"):
    prompt = f"""
    Aja como um Trader Esportivo Sênior. 
    Contexto do Jogo: {contexto}
    Tipo de Análise: {tipo.upper()}
    Dê um veredito direto: Vale a entrada? Qual o risco? Confiança de 0-100%.
    """
    try:
        return gemini.generate_content(prompt).text
    except:
        return "⚠️ O cérebro da IA está pensando... tente em instantes."

def salvar_no_db(jogo, ig, resultado, mercado):
    # Salva no histórico do Supabase
    try:
        supabase.table("historico").insert({
            "data": datetime.now().isoformat(),
            "jogo": jogo, 
            "ig": ig, 
            "resultado": resultado, 
            "mercado": mercado
        }).execute()
    except:
        st.error("Erro ao salvar no banco de dados.")

# --- 5. INTERFACE PRINCIPAL ---
st.title("⚡ IA REI DA BOLA PRO")
fd = FootballData()

# Sidebar: Performance e Alertas (Usa TELEGRAM_TOKEN e CHAT_ID se necessário)
with st.sidebar:
    st.header("📊 Performance Real")
    try:
        data = supabase.table("historico").select("*").execute()
        df_side = pd.DataFrame(data.data)
        if not df_side.empty:
            greens = len(df_side[df_side['resultado'].str.contains("GREEN")])
            reds = len(df_side[df_side['resultado'].str.contains("RED")])
            total = greens + reds
            acc = (greens / total * 100) if total > 0 else 0
            st.metric("Assertividade", f"{acc:.1f}%")
            st.write(f"✅ {greens} Greens | ❌ {reds} Reds")
    except:
        st.write("Sem dados para exibir.")

tab_live, tab_pre, tab_db = st.tabs(["🎯 RADAR AO VIVO", "🔮 ANÁLISE PRÉ-JOGO", "📈 HISTÓRICO"])

# --- ABA 1: AO VIVO ---
with tab_live:
    live_fixtures = fd.get_live()
    if not live_fixtures:
        st.info("Nenhum jogo com volume estatístico no momento.")
    else:
        for f in live_fixtures:
            fid = f['fixture']['id']
            casa, fora = f['teams']['home']['name'], f['teams']['away']['name']
            placar = f"{f['goals']['home']}x{f['goals']['away']}"
            tempo = f['fixture']['status']['elapsed'] or 0
            
            # Busca Estatísticas Detalhadas
            s_data = fd.get_stats(fid)
            no_alvo, f_alvo, ataques_p, cantos = 0, 0, 0, 0
            if s_data:
                for team_stats in s_data:
                    for s in team_stats['statistics']:
                        v = s['value'] or 0
                        t = s['type']
                        if "Shots on Goal" in t: no_alvo += v
                        if "Shots off Goal" in t: f_alvo += v
                        if "Dangerous Attacks" in t: ataques_p += v
                        if "Corner Kicks" in t: cantos += v

            # Cálculo de Índices Rei da Bola
            ig = (no_alvo * 6) + (ataques_p * 0.35) + (cantos * 2)
            
            # Filtro de Exibição (Só jogos interessantes)
            if ig > 20:
                with st.expander(f"🏟️ {casa} {placar} {fora} ({tempo}') | IG: {ig:.1f}"):
                    col_info, col_ai = st.columns([1, 1.5])
                    with col_info:
                        st.write(f"🎯 No Alvo: {no_alvo}")
                        st.write(f"🧨 Atq. Perigosos: {ataques_p}")
                        st.write(f"🚩 Escanteios: {cantos}")
                    
                    with col_ai:
                        if st.button(f"🧠 Consultar Gemini", key=f"ai_live_{fid}"):
                            with st.spinner("Analisando pressão tática..."):
                                res = gerar_analise_ia(f"{casa}x{fora}, {tempo}min, Placar: {placar}, IG:{ig:.1f}")
                                st.info(res)
                    
                    st.divider()
                    b1, b2 = st.columns(2)
                    if b1.button("✅ REGISTRAR GREEN", key=f"win_{fid}"):
                        salvar_no_db(f"{casa}x{fora}", ig, "✅ GREEN", "Live")
                        st.success("Salvo!")
                        st.rerun()
                    if b2.button("❌ REGISTRAR RED", key=f"loss_{fid}"):
                        salvar_no_db(f"{casa}x{fora}", ig, "❌ RED", "Live")
                        st.error("Salvo.")
                        st.rerun()

# --- ABA 2: PRÉ-JOGO ---
with tab_pre:
    st.subheader("🔮 Prognósticos para as próximas 24h")
    hoje = datetime.now().strftime("%Y-%m-%d")
    pre_fixtures = fd.get_pre_match(hoje)
    
    if pre_fixtures:
        # Mostra os 30 primeiros jogos do dia
        for pf in pre_fixtures[:30]:
            id_pf = pf['fixture']['id']
            c_name, f_name = pf['teams']['home']['name'], pf['teams']['away']['name']
            liga = pf['league']['name']
            hora = pf['fixture']['date'][11:16]
            
            with st.expander(f"📅 {hora} | {liga}: {c_name} x {f_name}"):
                if st.button(f"🔍 Gerar Dossiê de Valor", key=f"pre_ia_{id_pf}"):
                    with st.spinner("IA estudando o confronto..."):
                        analise_pre = gerar_analise_ia(f"Pré-jogo: {c_name} x {f_name} ({liga})", tipo="pre-jogo")
                        st.markdown(f"### 🤖 Parecer da IA:\n{analise_pre}")
    else:
        st.warning("Não foi possível carregar a lista de jogos para hoje.")

# --- ABA 3: HISTÓRICO ---
with tab_db:
    st.subheader("📈 Gestão de Performance")
    try:
        res_db = supabase.table("historico").select("*").execute()
        if res_db.data:
            df_hist = pd.DataFrame(res_db.data)
            df_hist = df_hist.sort_values(by='data', ascending=False)
            
            # Gráfico de Resultados
            fig = px.pie(df_hist, names="resultado", title="Distribuição de Resultados", 
                         color="resultado", color_discrete_map={"✅ GREEN": "#2ecc71", "❌ RED": "#e74c3c"})
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(df_hist[["data", "jogo", "ig", "mercado", "resultado"]], use_container_width=True)
        else:
            st.info("O banco de dados ainda está vazio. Registre entradas no Radar Live!")
    except:
        st.error("Erro ao conectar com o Supabase. Verifique suas chaves URL e KEY.")
