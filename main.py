import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

st_autorefresh(interval=180000, key="bot_refresh")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

def salvar_entrada(jogo, ig, resultado, mercado):
    supabase.table("historico").insert({
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "jogo": jogo, "ig": ig, "resultado": resultado, "mercado": mercado
    }).execute()

def carregar_historico():
    res = supabase.table("historico").select("*").order("id", desc=True).execute()
    if res.data:
        return pd.DataFrame(res.data)[["data", "jogo", "ig", "mercado", "resultado"]]
    return pd.DataFrame(columns=["data", "jogo", "ig", "mercado", "resultado"])

def limpar_historico():
    supabase.table("historico").delete().neq("id", 0).execute()

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{st.secrets['TELEGRAM_TOKEN']}/sendMessage"
    requests.post(url, data={"chat_id": st.secrets["CHAT_ID"], "text": mensagem, "parse_mode": "HTML"})

@st.cache_data(ttl=120)
def buscar_jogos_ao_vivo(api_key):
    return requests.get("https://v3.football.api-sports.io/fixtures?live=all", headers={'x-rapidapi-key': api_key}).json()

@st.cache_data(ttl=120)
def buscar_stats(id_jogo, api_key):
    return requests.get(f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_jogo}", headers={'x-rapidapi-key': api_key}).json()

@st.cache_data(ttl=300)
def buscar_lesoes(team_id, sm_key):
    try:
        res = requests.get("https://api.sportmonks.com/v3/football/injuries",
            params={"api_token": sm_key, "filters": f"teamId:{team_id}", "include": "player"}).json()
        lesoes = [f"🚑 {i.get('player',{}).get('display_name','?')} - {i.get('type','Lesão')}" for i in res.get("data", [])[:5]]
        return lesoes if lesoes else ["✅ Sem lesões registradas"]
    except:
        return ["⚠️ Dados indisponíveis"]

@st.cache_data(ttl=300)
def buscar_escalacao(fixture_id, sm_key):
    try:
        res = requests.get(f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}",
            params={"api_token": sm_key, "include": "lineups.player"}).json()
        titulares = {"casa": [], "fora": []}
        if res.get("data") and res["data"].get("lineups"):
            times = {}
            for p in res["data"]["lineups"]:
                if p.get("type_id") == 11:
                    tid = p.get("team_id")
                    times.setdefault(tid, []).append(p.get("player", {}).get("display_name", "?"))
            ids = list(times.keys())
            if len(ids) >= 2:
                titulares["casa"] = times[ids[0]][:11]
                titulares["fora"] = times[ids[1]][:11]
        return titulares
    except:
        return {"casa": [], "fora": []}

API_KEY = st.secrets["API_KEY"]
SM_KEY = st.secrets["SPORTMONKS_KEY"]

st.set_page_config(page_title="IA Rei da Bola Pro", layout="wide")
st.title("⚽ IA Rei da Bola Pro")

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
            if tempo < 1: continue
            casa = j['teams']['home']['name']
            fora = j['teams']['away']['name']
            id_j = j['fixture']['id']
            id_casa = j['teams']['home']['id']
            id_fora = j['teams']['away']['id']
            s_res = buscar_stats(id_j, API_KEY)
            no_alvo, fora_alvo, ataques_p = 0, 0, 0
            if s_res.get('response'):
                for s in s_res['response']:
                    for stat in s['statistics']:
                        val = stat['value'] if stat['value'] else 0
                        if "Shots on Goal" in stat['type']: no_alvo += val
                        if "Shots off Goal" in stat['type']: fora_alvo += val
                        if "Attacks" in stat['type'] and val > ataques_p: ataques_p = val
            ig = (no_alvo * 6) + (ataques_p * 0.3)
            ic = ((no_alvo + fora_alvo) * 2.5) + (ataques_p * 0.4)
            if ig > 25 or ic > 30:
                mercado = "Gols" if ig > ic else "Cantos"
                indice = ig if mercado == "Gols" else ic
                chave_alerta = f"{id_j}_{mercado}"
                if chave_alerta not in alertas_enviados:
                    enviar_telegram(f"🚨 <b>ALERTA IA REI DA BOLA</b>\n🏟️ {casa} x {fora} ({tempo}')\n📊 Mercado: <b>{mercado}</b>\n🎯 Índice: {indice:.1f}\n⚽ Chutes: {no_alvo} | 🧨 Ataques: {ataques_p}")
                    alertas_enviados.add(chave_alerta)
                    st.session_state["alertas_enviados"] = alertas_enviados
                with st.expander(f"🏟️ {casa} x {fora} ({tempo}') | {mercado} | IG: {ig:.1f} | IC: {ic:.1f}"):
                    st.write(f"🎯 Chutes no Alvo: {no_alvo} | 🧨 Ataques: {ataques_p}")
                    st.info(f"📌 Sugestão: **{mercado}**")
                    st.markdown("---")
                    col_l1, col_l2 = st.columns(2)
                    with col_l1:
                        st.markdown(f"**🏥 Lesões — {casa}**")
                        for l in buscar_lesoes(id_casa, SM_KEY): st.write(l)
                    with col_l2:
                        st.markdown(f"**🏥 Lesões — {fora}**")
                        for l in buscar_lesoes(id_fora, SM_KEY): st.write(l)
                    st.markdown("---")
                    esc = buscar_escalacao(id_j, SM_KEY)
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        st.markdown(f"**📋 Escalação — {casa}**")
                        for p in esc["casa"]: st.write(f"👤 {p}")
                        if not esc["casa"]: st.write("⏳ Ainda não divulgada")
                    with col_e2:
                        st.markdown(f"**📋 Escalação — {fora}**")
                        for p in esc["fora"]: st.write(f"👤 {p}")
                        if not esc["fora"]: st.write("⏳ Ainda não divulgada")
                    st.markdown("---")
                    col_b1, col_b2 = st.columns(2)
                    if col_b1.button("✅ Green", key=f"win_{id_j}"):
                        salvar_entrada(f"{casa}x{fora}", ig, "✅ GREEN", mercado)
                        st.rerun()
                    if col_b2.button("❌ Red", key=f"loss_{id_j}"):
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
