import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from datetime import datetime
import time
from supabase import create_client, Client

# --- 1. CONFIGURAÇÕES DE INTERFACE ---
st.set_page_config(page_title="IA REI DA BOLA - ELITE PRO", page_icon="🏆", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #7029b1; }
    .stButton>button { width: 100%; border-radius: 8px; background: linear-gradient(45deg, #4b0082, #7029b1); color: white; font-weight: bold; }
    .stExpander { border: 1px solid #4b0082; border-radius: 10px; background-color: #161b22; }
    </style>
    """, unsafe_allow_html=True)

LIGAS_ELITE = [71, 72, 73, 39, 40, 140, 141, 78, 79, 135, 136, 61, 62, 94, 307, 253, 2, 3, 5, 848, 13]

# --- 2. INICIALIZAÇÃO DE SERVIÇOS (IA E BANCO) ---
@st.cache_resource
def init_services():
    try:
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # Configuração para a IA não censurar termos de futebol (evita o erro da imagem)
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)
        return sb, model
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None, None

supabase, gemini = init_services()
API_KEY = st.secrets["API_KEY"]
HEADERS = {'x-rapidapi-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# --- 3. FUNÇÕES DE SUPORTE ---

@st.cache_data(ttl=60)
def fetch_api(endpoint):
    try:
        url = f"https://v3.football.api-sports.io/{endpoint}"
        res = requests.get(url, headers=HEADERS, timeout=12).json()
        return res.get('response', [])
    except:
        return []

def calcular_ig_avancado(stats):
    if not stats or len(stats) < 2: return 0
    def g(s_list, k):
        for i in s_list:
            if i['type'] == k: 
                val = i['value']
                return int(val) if val and str(val).isdigit() else 0
        return 0
    h, a = stats[0]['statistics'], stats[1]['statistics']
    p_h = (g(h, 'Shots on Goal')*6 + g(h, 'Corner Kicks')*3 + g(h, 'Total Shots')*2)
    p_a = (g(a, 'Shots on Goal')*6 + g(a, 'Corner Kicks')*3 + g(a, 'Total Shots')*2)
    return max(p_h, p_a)

def analisar_com_feeling(ctx):
    if not gemini: return "IA fora de campo."
    
    prompt = f"""
    Aja como o 'REI DA BOLA', trader esportivo experiente e audacioso.
    Sua análise vai ALÉM das estatísticas. Se os números dizem uma coisa, mas seu 'feeling' diz que vai dar zebra, mande a real.
    Considere: clima, mando de campo, desespero por pontos e histórico.
    Seja direto e use termos de trader.

    CONTEXTO: {ctx}

    FORMATO:
    🎯 VEREDITO: [Sua decisão]
    🔥 FEELING DO REI: [Sua opinião sincera desafiando ou confirmando os números]
    📈 CONFIANÇA: [0-100]%
    """
    try:
        response = gemini.generate_content(prompt)
        return response.text if response.text else "O Rei preferiu não opinar nessa. VAR em dúvida!"
    except Exception as e:
        if "429" in str(e): return "Muita calma! O Rei está sem fôlego. Espere 10s."
        return "O Rei está pensando... tente novamente em instantes."

def salvar_resultado(jogo, resultado, ig):
    try:
        supabase.table("historico").insert({
            "data": datetime.now().isoformat(),
            "jogo": jogo, "resultado": resultado, "ig": ig
        }).execute()
        st.toast(f"Registrado: {resultado}", icon="💰")
    except:
        st.error("Erro ao salvar no banco.")

# --- 4. INTERFACE PRINCIPAL ---
st.title("🏆 IA REI DA BOLA - ELITE PRO")

tab_radar, tab_pre, tab_db = st.tabs(["🎯 RADAR AO VIVO", "🔮 ANÁLISE PRÉ-JOGO", "📈 HISTÓRICO"])

# --- ABA 1: RADAR ---
with tab_radar:
    with st.spinner("Buscando jogos..."):
        lives = fetch_api("fixtures?live=all")
        jogos_elite = [j for j in lives if j['league']['id'] in LIGAS_ELITE]
    
    if not jogos_elite:
        st.info("Aguardando jogos de Elite...")
    else:
        for j in jogos_elite:
            fid = j['fixture']['id']
            h_n, a_n = j['teams']['home']['name'], j['teams']['away']['name']
            placar = f"{j['goals']['home']}-{j['goals']['away']}"
            tempo = j['fixture']['status']['elapsed']
            sinal = "🟣" if (tempo > 65 and j['goals']['home'] == j['goals']['away']) else "⚪"
            
            with st.expander(f"{sinal} {tempo}' | {h_n} {placar} {a_n}"):
                if st.button(f"Consultar o Rei", key=f"live_{fid}"):
                    stats = fetch_api(f"fixtures/statistics?fixture={fid}")
                    ig = calcular_ig_avancado(stats)
                    st.metric("Índice de Pressão (IG)", ig)
                    st.markdown(analisar_com_feeling(f"LIVE: {h_n}x{a_n}, {tempo}', IG:{ig}, Placar:{placar}"))
                    
                    c1, c2 = st.columns(2)
                    if c1.button("✅ GREEN", key=f"g_{fid}"): salvar_resultado(f"{h_n}x{a_n}", "GREEN", ig)
                    if c2.button("❌ RED", key=f"r_{fid}"): salvar_resultado(f"{h_n}x{a_n}", "RED", ig)

# --- ABA 2: PRÉ-JOGO ---
with tab_pre:
    hoje = datetime.now().strftime('%Y-%m-%d')
    st.subheader(f"📅 Visão do Especialista - {hoje}")
    agenda = fetch_api(f"fixtures?date={hoje}")
    proximos = [j for j in agenda if j['league']['id'] in LIGAS_ELITE and j['fixture']['status']['short'] == 'NS']
    
    if not proximos:
        st.info("Sem jogos de elite restantes hoje.")
    else:
        for p in proximos:
            h_n, a_n = p['teams']['home']['name'], p['teams']['away']['name']
            hora = datetime.fromisoformat(p['fixture']['date']).strftime('%H:%M')
            p_id = p['fixture']['id']
            
            with st.expander(f"🕒 {hora} | {h_n} x {a_n}"):
                if st.button(f"Análise de Especialista", key=f"pre_{p_id}"):
                    with st.spinner("Analisando..."):
                        time.sleep(0.5) # Evita erro 429
                        res = analisar_com_feeling(f"PRÉ-JOGO: {h_n} (Mandante) x {a_n} (Visitante). Liga: {p['league']['name']}")
                        st.markdown(res)

# --- ABA 3: HISTÓRICO ---
with tab_db:
    try:
        res = supabase.table("historico").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            st.metric("Winrate", f"{(len(df[df['resultado']=='GREEN'])/len(df)*100):.1f}%")
            st.dataframe(df.sort_values('data', ascending=False), use_container_width=True)
    except:
        st.write("Histórico indisponível.")
