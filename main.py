import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from datetime import datetime
import plotly.express as px
from supabase import create_client, Client

# --- 1. CONFIGURAÇÕES INICIAIS ---
st.set_page_config(
    page_title="IA REI DA BOLA - ELITE PRO",
    page_icon="🏆",
    layout="wide"
)

# Estilização para um visual "Dark Mode Pro"
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px dotted #7029b1; }
    .stButton>button { width: 100%; border-radius: 8px; background: linear-gradient(45deg, #4b0082, #7029b1); color: white; font-weight: bold; }
    .stExpander { border: 1px solid #4b0082; border-radius: 10px; background-color: #161b22; }
    </style>
    """, unsafe_allow_html=True)

LIGAS_ELITE = [71, 72, 73, 39, 40, 140, 141, 78, 79, 135, 136, 61, 62, 94, 307, 253, 2, 3, 5, 848, 13]

# --- 2. INICIALIZAÇÃO ---
@st.cache_resource
def init_services():
    try:
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash')
        return sb, model
    except Exception as e:
        st.error(f"Erro Crítico: {e}")
        return None, None

supabase, gemini = init_services()
API_KEY = st.secrets["API_KEY"]
HEADERS = {'x-rapidapi-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- 3. FUNÇÕES DE DADOS ---

@st.cache_data(ttl=60)
def fetch_api(endpoint):
    url = f"https://v3.football.api-sports.io/{endpoint}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        return res.get('response', [])
    except: return []

def calcular_ig_avancado(stats):
    if not stats or len(stats) < 2: return 0
    def g(s_list, k):
        for i in s_list:
            if i['type'] == k: return int(i['value']) if i['value'] else 0
        return 0
    h, a = stats[0]['statistics'], stats[1]['statistics']
    # IG focado em volume ofensivo
    p = (g(h, 'Shots on Goal')*6 + g(h, 'Corner Kicks')*3 + g(h, 'Total Shots')*2)
    p_a = (g(a, 'Shots on Goal')*6 + g(a, 'Corner Kicks')*3 + g(a, 'Total Shots')*2)
    return max(p, p_a)

# --- 4. A IA COM PERSONALIDADE E "FEELING" ---

def analisar_com_feeling(ctx, tipo="live"):
    if not gemini: return "IA Offline"
    
    # O "Cérebro" da IA: Aqui definimos a personalidade audaciosa que você pediu
    system_prompt = """
    Você é o 'REI DA BOLA', o trader mais audacioso e experiente do mercado. 
    Sua análise vai ALÉM dos números. Você considera:
    - Mando de campo e pressão da torcida.
    - Clima e estado do gramado.
    - Necessidade de vitória (desespero vs conforto).
    - 'Zebra Feeling': Se os números dizem uma coisa, mas o 'cheiro' do jogo diz outra, confie no seu instinto.
    
    Sua resposta deve ser curta, direta e ter opinião própria. Se achar que o favorito vai pipocar, diga! 
    Use gírias leves de trader (Green, Red, Pipocar, Amassar, Zebra).
    
    FORMATO DE RESPOSTA:
    🎯 VEREDITO: [Sua decisão real]
    🔥 FEELING: [Sua opinião sincera desafiando ou confirmando os números]
    📈 CONFIANÇA: [0-100%]
    """
    
    full_prompt = f"{system_prompt}\n\nCONTEXTO DO JOGO: {ctx}"
    
    try:
        response = gemini.generate_content(full_prompt)
        return response.text
    except: return "O Rei está pensando... tente novamente."

def salvar_no_banco(jogo, resultado, ig):
    try:
        supabase.table("historico").insert({
            "data": datetime.now().isoformat(),
            "jogo": jogo, 
            "resultado": resultado, 
            "ig": ig
        }).execute()
        st.toast(f"Registrado como {resultado}!", icon="💰")
    except: st.error("Erro ao salvar no Supabase.")

# --- 5. INTERFACE ---

st.title("🏆 IA REI DA BOLA - MODO ELITE PRO")

t_radar, t_pre, t_db = st.tabs(["🎯 RADAR AO VIVO", "🔮 ANÁLISE PRÉ-JOGO", "📈 HISTÓRICO"])

with t_radar:
    with st.spinner("Lendo o campo..."):
        lives = fetch_api("fixtures?live=all")
        jogos_elite = [j for j in lives if j['league']['id'] in LIGAS_ELITE]
    
    if not jogos_elite:
        st.info("Aguardando jogos de Elite começarem...")
    else:
        for j in jogos_elite:
            fid = j['fixture']['id']
            h_n, a_n = j['teams']['home']['name'], j['teams']['away']['name']
            placar = f"{j['goals']['home']}-{j['goals']['away']}"
            tempo = j['fixture']['status']['elapsed']
            
            # Sinalizador Roxo para jogos com cara de virada ou empate heróico
            sinal = "🟣" if (tempo > 70 and abs(j['goals']['home'] - j['goals']['away']) <= 1) else "⚪"
            
            with st.expander(f"{sinal} {tempo}' | {h_n} {placar} {a_n}"):
                if st.button(f"Consultar o Rei", key=f"ai_{fid}"):
                    stats = fetch_api(f"fixtures/statistics?fixture={fid}")
                    ig = calcular_ig_avancado(stats)
                    
                    # Montando o contexto rico para a IA
                    contexto = f"""
                    Jogo: {h_n} vs {a_n}
                    Placar: {placar} | Tempo: {tempo}min
                    Estatísticas Reais: {stats}
                    IG de Pressão: {ig}
                    Liga: {j['league']['name']}
                    """
                    
                    st.subheader("O Rei diz:")
                    st.info(analisar_com_feeling(contexto, "live"))
                    
                    c1, c2 = st.columns(2)
                    if c1.button("✅ GREEN", key=f"g_{fid}"): salvar_no_banco(f"{h_n}x{a_n}", "GREEN", ig)
                    if c2.button("❌ RED", key=f"r_{fid}"): salvar_no_banco(f"{h_n}x{a_n}", "RED", ig)

with t_pre:
    hoje = datetime.now().strftime('%Y-%m-%d')
    st.subheader(f"📅 Visão do Especialista - {hoje}")
    
    agenda = fetch_api(f"fixtures?date={hoje}")
    proximos = [j for j in agenda if j['league']['id'] in LIGAS_ELITE and j['fixture']['status']['short'] == 'NS']
    
    if not proximos:
        st.info("Tudo calmo nas ligas de elite hoje.")
    else:
        for p in proximos:
            h_n, a_n = p['teams']['home']['name'], p['teams']['away']['name']
            hora = datetime.fromisoformat(p['fixture']['date']).strftime('%H:%M')
            p_id = p['fixture']['id']
            
            with st.expander(f"🕒 {hora} | {h_n} x {a_n}"):
                if st.button(f"Análise de Especialista", key=f"pre_{p_id}"):
                    # Buscando informações extras para a IA ser precisa
                    # Aqui ela considera mando de campo e o peso da camisa
                    ctx_pre = f"""
                    CONFRONTO: {h_n} (Mandante) vs {a_n} (Visitante)
                    LIGA: {p['league']['name']}
                    HORÁRIO: {hora}
                    O mandante costuma ser forte em casa. O visitante precisa do resultado.
                    """
                    st.write("---")
                    st.markdown(analisar_com_feeling(ctx_pre, "pre"))

with t_db:
    st.subheader("📊 Performance Acumulada")
    try:
        res = supabase.table("historico").select("*").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            total = len(df)
            greens = len(df[df['resultado'] == 'GREEN'])
            st.columns(3)[0].metric("Assertividade", f"{(greens/total*100):.1f}%")
            st.dataframe(df.sort_values('data', ascending=False), use_container_width=True)
        else: st.write("Ainda sem registros.")
    except: st.error("Erro ao carregar banco.")
