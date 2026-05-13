import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# 🔄 Auto-refresh a cada 3 min
st_autorefresh(interval=180000, key="bot_refresh")

# --- CONFIGURAÇÃO DO SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# --- FUNÇÕES DO BANCO DE DADOS (Supabase) ---
def salvar_entrada(jogo, ig, resultado, mercado):
    data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
    supabase.table("historico").insert({
        "data": data_atual,
        "jogo": jogo,
        "ig": ig,
        "resultado": resultado,
        "mercado": mercado
    }).execute()

def carregar_historico():
    res = supabase.table("historico").select("*").order("id", desc=True).execute()
    if res.data:
        return pd.DataFrame(res.data)[["data", "jogo", "ig", "mercado", "resultado"]]
    return pd.DataFrame(columns=["data", "jogo", "ig", "mercado", "resultado"])

def limpar_historico():
    supabase.table("historico").delete().neq("id", 0).execute()

# --- TELEGRAM ---
def enviar_telegram(mensagem):
    token = st.secrets["TELEGRAM_TOKEN"]
    chat_id = st.secrets["CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"})

# --- CACHE DE ESTATÍSTICAS ---
@st.cache_data(ttl=120)
def buscar_stats(id_jogo, api_key):
    url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_jogo}"
    res = requests.get(url, headers={'x-rapidapi-key': api_key}).json()
    return res

@st.cache_data(ttl=120)
def buscar_jogos_ao_vivo(api_key):
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    res = requests.get(url, headers={'x-rapidapi-key': api_key}).json()
    return res

# --- CHAVES ---
API_KEY = st.secrets["API_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["CHAT_ID"]

# --- INTERFACE ---
st.set_page_config(page_title="IA Rei da Bola Pro", layout="wide")
st.title("⚽ IA Rei da Bola + Supabase")

df_hist = carregar_historico()
greens = len(df_hist[df_hist['resultado'] == '✅ GREEN'])
reds = len(df_hist[df_hist['resultado'] == '❌ RED'])
total = greens + reds
acc = (greens / total * 100) if total > 0 else 0

c1, c2, c3 = st.columns(3)
c1.metric("✅ Greens", greens)
c2.metric("❌ Reds", reds)
c3.metric("📈 Assertividade", f"{acc:.1f}%")

tab1, tab2 = st.tabs(["🎯 AO VIVO", "🗄️ HISTÓRICO"])

with tab1:
    res = buscar_jogos_ao_vivo(API_KEY)

    if res.get('response'):
        alertas_enviados = st.session_state.get("alertas_enviados", set())

        for j in res['response']:
            tempo = j['fixture']['status']['elapsed'] or 0
            if tempo < 1:
                continue

            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            id_j = j['fixture']['id']

            s_res = buscar_stats(id_j, API_KEY)

            no_alvo, fora_alvo, ataques_p = 0, 0, 0
            if s_res.get('response'):
                for s in s_res['response']:
                    for stat in s['statistics']:
                        tipo = stat['type']
                        val = stat['value'] if stat['value'] else 0
                        if "Shots on Goal" in tipo:
                            no_alvo += val
                        if "Shots off Goal" in tipo:
                            fora_alvo += val
                        if "Attacks" in tipo:
                            if val > ataques_p:
                                ataques_p = val

            ig = (no_alvo * 6) + (ataques_p * 0.3)
            ic = ((no_alvo + fora_alvo) * 2.5) + (ataques_p * 0.4)

            if ig > 25 or ic > 30:
                mercado = "Gols" if ig > ic else "Cantos"
                indice = ig if mercado == "Gols" else ic

                chave_alerta = f"{id_j}_{mercado}"
                if chave_alerta not in alertas_enviados:
                    msg = (
                        f"🚨 <b>ALERTA IA REI DA BOLA</b>\n"
                        f"🏟️ {casa} x {fora} ({tempo}')\n"
                        f"📊 Mercado: <b>{mercado}</b>\n"
                        f"🎯 Índice: {indice:.1f}\n"
                        f"⚽ Chutes no alvo: {no_alvo} | 🧨 Ataques: {ataques_p}"
                    )
                    enviar_telegram(msg)
                    alertas_enviados.add(chave_alerta)
                    st.session_state["alertas_enviados"] = alertas_enviados

                with st.expander(f"🏟️ {casa} x {fora} ({tempo}') | {mercado} | IG: {ig:.1f} | IC: {ic:.1f}"):
                    st.write(f"🎯 No Alvo: {no_alvo} | 🧨 Ataques: {ataques_p}")
                    st.info(f"📌 Sugestão: **{mercado}**")

                    col_b1, col_b2 = st.columns(2)
                    if col_b1.button(f"✅ Green", key=f"win_{id_j}"):
                        salvar_entrada(f"{casa}x{fora}", ig, "✅ GREEN", mercado)
                        st.rerun()
                    if col_b2.button(f"❌ Red", key=f"loss_{id_j}"):
                        salvar_entrada(f"{casa}x{fora}", ig, "❌ RED", mercado)
                        st.rerun()
    else:
        st.info("Nenhum jogo ao vivo no momento.")

with tab2:
    st.subheader("📊 Histórico Permanente (Supabase)")
    st.dataframe(df_hist, use_container_width=True)

    if st.button("🗑️ Limpar Histórico"):
        limpar_historico()
        st.success("Histórico limpo!")
        st.rerun()
