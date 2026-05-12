import streamlit as st
import requests

# Puxando as duas chaves
API_KEY = st.secrets["API_KEY"]
ODDS_API_KEY =import streamlit as st
import requests

# Puxando as duas chaves
API_KEY = st.secrets["API_KEY"]
ODDS_API_KEY = d0d406c62c4212e48e29ffa594778d0d["ODDS_API_KEY"]

HEADERS = {'x-rapidapi-key': API_KEY}

st.set_page_config(page_title="IA Rei da Bola: Valor Pro", page_icon="💰", layout="wide")

st.title("💰 IA Rei da Bola: Análise de Valor")
st.sidebar.info("IA comparando Pressão vs Odds")

if st.button("🔍 SCANEAR OPORTUNIDADES COM ODDS"):
    # 1. Busca jogos ao vivo (Stats)
    url_live = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url_live, headers=HEADERS).json()
    
    if res.get('response'):
        for j in res['response']:
            tempo = j['fixture']['status']['elapsed'] if j['fixture']['status']['elapsed'] else 0
            if tempo < 10: continue

            id_jogo = j['fixture']['id']
            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            p_casa = j['goals']['home'] if j['goals']['home'] is not None else 0
            p_fora = j['goals']['away'] if j['goals']['away'] is not None else 0
            
            # --- BUSCA STATS ---
            url_stats = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_jogo}"
            s_res = requests.get(url_stats, headers=HEADERS).json()
            
            no_alvo, fora_alvo, ataques_p = 0, 0, 0
            if s_res.get('response'):
                for s in s_res['response']:
                    for stat in s['statistics']:
                        if stat['type'] == 'Shots on Goal' and stat['value']: no_alvo += stat['value']
                        if stat['type'] == 'Shots off Goal' and stat['value']: fora_alvo += stat['value']
                        if stat['type'] == 'Dangerous Attacks' and stat['value']: ataques_p += stat['value']

            # Índices de Pressão
            ig = (no_alvo * 8) + (ataques_p / 5)
            ic = ((no_alvo + fora_alvo) * 3) + (ataques_p / 3)

            # --- BUSCA ODDS (Simulando Filtro de Valor) ---
            # Aqui a IA analisa se a pressão justifica a entrada
            with st.container():
                c1, c2, c3 = st.columns([2, 1.5, 1])
                with c1:
                    st.subheader(f"{casa} {p_casa} x {p_fora} {fora}")
                    st.caption(f"⏰ {tempo}' min | 🎯 Alvo: {no_alvo}")
                
                with c2:
                    # Lógica de Valor
                    if ig > 45:
                        st.success(f"🔥 PRESSÃO ALTA (IG: {ig:.1f})")
                        st.write("📢 Recomendação: Buscar Odd acima de 1.80")
                    elif ic > 35:
                        st.warning(f"🚩 PRESSÃO CANTOS (IC: {ic:.1f})")
                        st.write("📢 Recomendação: Buscar Odd acima de 1.70")
                    else:
                        st.write("⚖️ Sem valor no momento")

                with c3:
                    if ig > 45 or ic > 40:
                        st.button("💰 ANALISAR ODD", key=f"v_{id_jogo}")
                    else:
                        st.button("👀 AGUARDAR", key=f"n_{id_jogo}")
                st.markdown("---")
    else:
        st.info("Nenhum jogo quente encontrado para análise de valor.")
 ["ODDS_API_KEY"]

HEADERS = {'x-rapidapi-key': API_KEY}

st.set_page_config(page_title="IA Rei da Bola: Valor Pro", page_icon="💰", layout="wide")

st.title("💰 IA Rei da Bola: Análise de Valor")
st.sidebar.info("IA comparando Pressão vs Odds")

if st.button("🔍 SCANEAR OPORTUNIDADES COM ODDS"):
    # 1. Busca jogos ao vivo (Stats)
    url_live = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url_live, headers=HEADERS).json()
    
    if res.get('response'):
        for j in res['response']:
            tempo = j['fixture']['status']['elapsed'] if j['fixture']['status']['elapsed'] else 0
            if tempo < 10: continue

            id_jogo = j['fixture']['id']
            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            p_casa = j['goals']['home'] if j['goals']['home'] is not None else 0
            p_fora = j['goals']['away'] if j['goals']['away'] is not None else 0
            
            # --- BUSCA STATS ---
            url_stats = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_jogo}"
            s_res = requests.get(url_stats, headers=HEADERS).json()
            
            no_alvo, fora_alvo, ataques_p = 0, 0, 0
            if s_res.get('response'):
                for s in s_res['response']:
                    for stat in s['statistics']:
                        if stat['type'] == 'Shots on Goal' and stat['value']: no_alvo += stat['value']
                        if stat['type'] == 'Shots off Goal' and stat['value']: fora_alvo += stat['value']
                        if stat['type'] == 'Dangerous Attacks' and stat['value']: ataques_p += stat['value']

            # Índices de Pressão
            ig = (no_alvo * 8) + (ataques_p / 5)
            ic = ((no_alvo + fora_alvo) * 3) + (ataques_p / 3)

            # --- BUSCA ODDS (Simulando Filtro de Valor) ---
            # Aqui a IA analisa se a pressão justifica a entrada
            with st.container():
                c1, c2, c3 = st.columns([2, 1.5, 1])
                with c1:
                    st.subheader(f"{casa} {p_casa} x {p_fora} {fora}")
                    st.caption(f"⏰ {tempo}' min | 🎯 Alvo: {no_alvo}")
                
                with c2:
                    # Lógica de Valor
                    if ig > 45:
                        st.success(f"🔥 PRESSÃO ALTA (IG: {ig:.1f})")
                        st.write("📢 Recomendação: Buscar Odd acima de 1.80")
                    elif ic > 35:
                        st.warning(f"🚩 PRESSÃO CANTOS (IC: {ic:.1f})")
                        st.write("📢 Recomendação: Buscar Odd acima de 1.70")
                    else:
                        st.write("⚖️ Sem valor no momento")

                with c3:
                    if ig > 45 or ic > 40:
                        st.button("💰 ANALISAR ODD", key=f"v_{id_jogo}")
                    else:
                        st.button("👀 AGUARDAR", key=f"n_{id_jogo}")
                st.markdown("---")
    else:
        st.info("Nenhum jogo quente encontrado para análise de valor.")
