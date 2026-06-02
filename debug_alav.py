import streamlit as st
import requests
from api_football import buscar_jogos_da_liga

st.title("DEBUG - Alavancagem")

api_key = st.secrets["API_KEY"]
headers = {
    "x-rapidapi-key": api_key,
    "x-rapidapi-host": "v3.football.api-sports.io"
}

LIGAS_TESTE = {
    "Brasileirao Serie A": 71,
    "Brasileirao Serie B": 72,
    "Champions League": 2,
}

if st.button("TESTAR AGORA"):

    # 1. Testa busca de jogos
    st.subheader("1. Jogos encontrados")
    todos = []
    for nome, lid in LIGAS_TESTE.items():
        jogos = buscar_jogos_da_liga(lid)
        st.write(f"{nome}: {len(jogos)} jogos")
        for j in jogos:
            st.write(f"  - {j['nome']} | ID: {j['id']}")
            todos.append(j)

    if not todos:
        st.error("NENHUM JOGO ENCONTRADO! Problema na busca de jogos.")
        st.stop()

    # 2. Testa odds do primeiro jogo
    st.subheader("2. Teste de odds")
    jogo_teste = todos[0]
    st.write(f"Testando odds para: {jogo_teste['nome']} (ID: {jogo_teste['id']})")

    bookmakers = [6, 5, 7, 4, 8, 11, 1, 3, 16, 18]
    for bk in bookmakers:
        url = f"https://v3.football.api-sports.io/odds?fixture={jogo_teste['id']}&bookmaker={bk}"
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        resp = data.get("response", [])
        erros = data.get("errors", [])
        st.write(f"Bookmaker {bk}: status={r.status_code} | response={len(resp)} itens | errors={erros}")
        if resp:
            st.success(f"✅ Bookmaker {bk} funcionou!")
            # Mostra mercados disponíveis
            for item in resp[:1]:
                for bkm in item.get("bookmakers", [])[:1]:
                    bets = bkm.get("bets", [])
                    st.write(f"Mercados disponíveis: {[b['name'] for b in bets]}")
            break

    # 3. Testa odds sem bookmaker específico
    st.subheader("3. Odds sem filtro de bookmaker")
    url2 = f"https://v3.football.api-sports.io/odds?fixture={jogo_teste['id']}"
    r2 = requests.get(url2, headers=headers, timeout=15)
    data2 = r2.json()
    resp2 = data2.get("response", [])
    st.write(f"Sem filtro: {len(resp2)} bookmakers retornados")
    if resp2:
        for item in resp2[:1]:
            for bkm in item.get("bookmakers", [])[:3]:
                st.write(f"  Bookmaker: {bkm.get('name')} (ID: {bkm.get('id')})")
    else:
        st.error("Sem odds mesmo sem filtro de bookmaker!")
        st.json(data2)
        
