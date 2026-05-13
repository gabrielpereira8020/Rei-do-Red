import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from supabase import create_client, Client
from datetime import datetime
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="IA Rei da Bola: Elite Pro", page_icon="⚽", layout="wide")

# Refresh a cada 5 minutos para economizar API
st_autorefresh(interval=300000, key="global_refresh")

# --- INICIALIZAÇÃO ---
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def init_gemini():
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-1.5-flash')

supabase = init_supabase()
gemini = init_gemini()

class FootballData:
    def __init__(self):
        self.headers = {'x-rapidapi-key': st.secrets["API_KEY"]}

    @st.cache_data(ttl=300) # Cache de 5 min
    def get_live_fixtures(_self):
        url = "https://v3.football.api-sports.io/fixtures?live=all"
        return requests.get(url, headers=_self.headers).json().get('response', [])

    @st.cache_data(ttl=600) # Cache de 10 min
    def get_match_stats(_self, fixture_id):
        url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
        return requests.get(url, headers=_self.headers).json().get('response', [])

    @st.cache_data(ttl=3600) # Cache de 1 hora
    def get_pre_match(_self, date_str):
        url = f"https://v3.football.api-sports.io/fixtures?date={date_str}"
        return requests.get(url, headers=_self.headers).json().get('response', [])

    def get_h2h(self, id1, id2):
        # Chamada direta sem cache para ser usada apenas sob demanda
        url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={id1}-{id2}"
        res = requests.get(url, headers=self.headers).json().get('response', [])
        return res[:5]

# --- FUNÇÕES ---
def gerar_analise_ia(contexto):
    prompt = f"Analise como Trader Sênior: {contexto}. Veredito direto com confiança 0-100%."
    try: return gemini.generate_content(prompt).text
    except: return "🤖 IA em manutenção..."

def db_salvar(jogo, ig, resultado):
    try: supabase.table("historico").insert({"data": datetime.now().isoformat(), "jogo": jogo, "ig": ig, "resultado": resultado}).execute()
    except: pass

# --- UI ---
st.title("⚡ IA REI DA BOLA: SISTEMA DE ELITE")
fd = FootballData()

tab_live, tab_pre, tab_db = st.tabs(["🎯 LIVE RADAR", "🔮 PRÉ-JOGO EXPERT", "📈 PERFORMANCE"])

# --- LIVE ---
with tab_live:
    live = fd.get_live_fixtures()
    if not live: st.info("Buscando oportunidades...")
    else:
        for f in live:
            fid = f['fixture']['id']
            casa, fora = f['teams']['home']['name'], f['teams']['away']['name']
            s = fd.get_stats(fid)
            # Lógica de cálculo simplificada para economizar processamento
            no_alvo = sum([item['value'] or 0 for team in s for item in team['statistics'] if "Shots on Goal" in item['type']]) if s else 0
            atq_p = sum([item['value'] or 0 for team in s for item in team['statistics'] if "Dangerous Attacks" in item['type']]) if s else 0
            ig = (no_alvo * 6) + (atq_p * 0.35)
            
            if ig > 20:
                with st.expander(f"🏟️ {casa} vs {fora} | IG: {ig:.1f}"):
                    if st.button("🧠 Consultar Gemini", key=f"l_{fid}"):
                        st.info(gerar_analise_ia(f"{casa}x{fora}, IG:{ig:.1f}"))
                    if st.button("✅ GREEN", key=f"g_{fid}"):
                        db_salvar(f"{casa}x{fora}", ig, "✅ GREEN")
                        st.rerun()

# --- PRÉ-JOGO (DESTRAVADO) ---
with tab_pre:
    hoje = datetime.now().strftime("%Y-%m-%d")
    pre = fd.get_pre_match(hoje)
    if pre:
        # Filtra jogos que ainda não começaram
        futuros = [j for j in pre if j['fixture']['status']['short'] == "NS"]
        for pf in futuros[:30]:
            fid_p = pf['fixture']['id']
            c, f_n = pf['teams']['home']['name'], pf['teams']['away']['name']
            with st.expander(f"📅 {pf['fixture']['date'][11:16]} | {c} x {f_n}"):
                if st.button(f"🔍 Dossiê de Elite", key=f"p_{fid_p}"):
                    with st.spinner("IA cruzando H2H..."):
                        # Busca H2H apenas no clique do botão para economizar API
                        h = fd.get_h2h(pf['teams']['home']['id'], pf['teams']['away']['id'])
                        h_txt = ", ".join([f"{m['goals']['home']}x{m['goals']['away']}" for m in h])
                        st.markdown(gerar_analise_ia(f"Pré-jogo: {c}x{f_n}. H2H recente: {h_txt}"))
    else: st.error("Limite da API atingido ou sem jogos disponíveis.")

# --- HISTÓRICO ---
with tab_db:
    try:
        res = supabase.table("historico").select("*").execute()
        if res.data: st.dataframe(pd.DataFrame(res.data).sort_values(by='data', ascending=False))
    except: st.error("Erro no banco.")
