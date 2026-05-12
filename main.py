import streamlit as st
import requests

# Configurações de API
API_KEY = st.secrets["API_KEY"]
HEADERS = {'x-rapidapi-key': API_KEY}

st.set_page_config(page_title="IA Futebol Elite", page_icon="⚽", layout="wide")

st.title("⚽ IA Rei da Bola: Analisador Elite")
st.markdown("---")

if st.button("🚀 ESCANEAR OPORTUNIDADES AGORA"):
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url, headers=HEADERS).json()
    
    if res['response']:
        for j in res['response']:
            # Dados básicos
            id_jogo = j['fixture']['id']
            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            p_casa = j['goals']['home']
            p_fora = j['goals']['away']
            tempo = j['fixture']['status']['elapsed']
            liga = j['league']['name']
            
            # 1. RADAR DE ESCANTEIOS E PRESSÃO (Buscando Estatísticas)
            url_stats = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_jogo}"
            s_res = requests.get(url_stats, headers=HEADERS).json()
            
            chutes_alvo = 0
            ataques_perigosos = 0
            
            if s_res['response']:
                for s in s_res['response']:
                    for stat in s['statistics']:
                        if stat['type'] == 'Shots on Goal' and stat['value']:
                            chutes_alvo += stat['value']
                        if stat['type'] == 'Dangerous Attacks' and stat['value']:
                            ataques_perigosos += stat['value']

            # 2. ÍNDICE DE PERIGO (PI) - Cálculo da IA
            # Fórmula: (Chutes no alvo * 2) + (Ataques perigosos / 10)
            indice_perigo = (chutes_alvo * 2) + (ataques_perigosos / 5)
            
            # Criando o Card
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.subheader(f"{casa} {p_casa} x {p_fora} {fora}")
                    st.caption(f"🏆 {liga} • {tempo} min")
                    st.write(f"📊 Pressão: {ataques_perigosos} ataques perigosos")
                
                with col2:
                    # Lógica do Veredito
                    if indice_perigo > 15:
                        st.success(f"🔥 ALTA PRESSÃO (PI: {indice_perigo:.1f})")
                        st.write("Foco: Próximo Gol ou Escanteios")
                    elif indice_perigo > 7:
                        st.warning(f"⚖️ JOGO MOVIMENTADO (PI: {indice_perigo:.1f})")
                    else:
                        st.error(f"❄️ JOGO TRANCADO (PI: {indice_perigo:.1f})")
                
                with col3:
                    # 3. PALPITE DA IA (Veredito Final)
                    if tempo > 75 and abs(p_casa - p_fora) <= 1 and ataques_perigosos > 40:
                        st.button("🚩 Sugestão: Cantos +0.5", key=f"c_{id_jogo}")
                    elif tempo < 35 and indice_perigo > 10:
                        st.button("⚽ Sugestão: Over 0.5 HT", key=f"h_{id_jogo}")
                    else:
                        st.button("🔒 Sem Entrada", key=f"n_{id_jogo}")
                
                st.markdown("---")
    else:
        st.info("Nenhum jogo com estatísticas avançadas no momento.")

st.sidebar.title("🤖 Painel de Controle")
st.sidebar.markdown("""
**Como funciona:**
1. **PI (Índice de Perigo):** Acima de 15 o jogo está fervendo.
2. **Cantos:** Sugestão baseada em pressão final.
3. **Over HT:** Sugestão de gol no 1º tempo.
""")
