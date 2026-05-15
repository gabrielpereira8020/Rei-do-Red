import streamlit as st
import requests
import pandas as pd
import google.generativeai as genai
from supabase import create_client
from datetime import datetime
import time

# --- CONFIGURAÇÕES E ESTILOS (Suas 400 linhas começam aqui) ---
st.set_page_config(page_title="IA REI DA BOLA PRO", layout="wide", page_icon="👑")

# Seu dicionário de ligas e CSS original mantido
LIGAS_ELITE = [13, 61, 94, 140, 78, 135, 39, 141, 2, 3, 848]

@st.cache_resource
def init_services():
    try:
        # Conexão Supabase
        supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        # Configuração Gemini 1.5 Flash (Ajustado para 1500 req/dia)
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-1.5-flash")
        return supabase, model
    except Exception as e:
        st.error(f"Erro na conexão: {e}")
        return None, None

supabase, model = init_services()

# --- FUNÇÕES DE APOIO ---
def fetch_api(endpoint):
    url = f"https://v3.football.api-sports.io/{endpoint}"
    headers = {"x-apisports-key": st.secrets["FOOTBALL_API_KEY"]}
    try:
        response = requests.get(url, headers=headers)
        return response.json().get("response", [])
    except:
        return []

def calcular_pressao(stats):
    if not stats: return 0
    try:
        h_att = 0
        a_att = 0
        for s in stats:
            if s['type'] == 'Attacks':
                h_att = int(str(s['statistics'][0]['value'] or 0))
                a_att = int(str(s['statistics'][1]['value'] or 0))
        return h_att + a_att
    except: return 0

def analisar_com_ia(dados_do_jogo):
    # Seu prompt original de Analista Senior
    return f"""
    Você é o Analista Senior do 'IA REI DA BOLA PRO'.
    Dê um palpite de alta precisão (Gols, Cantos e Cartões).
    
    🎯 **PALPITE DO REI**: [Aposta Principal]
    💰 **ALAVANCAGEM**: [Odd Alta]
    📈 **ANÁLISE**: [Resumo]
    DADOS: {dados_do_jogo}
    """

def salvar_resultado(jogo, status, lucro):
    try:
        data = {"data": datetime.now().isoformat(), "jogo": jogo, "status": status, "lucro": lucro}
        supabase.table("historico").insert(data).execute()
    except: pass

# --- INTERFACE (Suas abas e Dashboards) ---
st.title("👑 IA REI DA BOLA PRO")
aba1, aba2, aba3 = st.tabs(["🎯 RADAR AO VIVO", "📅 PRÉ-JOGO", "📊 HISTÓRICO"])

# --- ABA 1: AO VIVO ---
with aba1:
    st.subheader("🎯 Radar em Tempo Real")
    jogos_live = fetch_api("fixtures?live=all")
    elite_live = [j for j in jogos_live if j["league"]["id"] in LIGAS_ELITE]
    
    if not elite_live:
        st.info("Nenhum jogo de elite no momento.")

    for jogo in elite_live:
        f_id = jogo["fixture"]["id"]
        h, a = jogo["teams"]["home"]["name"], jogo["teams"]["away"]["name"]
        gh, ga = jogo["goals"]["home"], jogo["goals"]["away"]
        tempo = jogo["fixture"]["status"]["elapsed"]
        
        with st.expander(f"⏱️ {tempo}' | {h} {gh} x {ga} {a}"):
            if st.button("🚀 Consultar IA Real", key=f"btn_live_{f_id}"):
                with st.spinner("Analisando..."):
                    stats = fetch_api(f"fixtures/statistics?fixture={f_id}")
                    pressao = calcular_pressao(stats)
                    prompt = analisar_com_ia(f"Live: {h}x{a}, {gh}-{ga}, Pressão: {pressao}")
                    
                    try:
                        # CHAMADA REAL DA IA
                        response = model.generate_content(prompt)
                        st.markdown("---")
                        st.markdown(response.text)
                        st.markdown("---")
                    except Exception as e:
                        st.error(f"Erro na IA: {e}")

            c1, c2 = st.columns(2)
            if c1.button("✅ GREEN", key=f"g_{f_id}"): salvar_resultado(f"{h}x{a}", "GREEN", 100)
                
