"""
bilhete_especial.py
====================
Tela "Bilhete Especial do Dia" - versao visual das melhores entradas
do dia, no estilo dos apps de tipster profissionais (cartao bonito,
odd em destaque, selo de oportunidade).

O QUE ELA FAZ DE VERDADE (sem papo de marketing):

  1. Reaproveita o pipeline que ja existe em alavancagem.py (Etapas
     1-5: busca jogos, ranking local, IA analisa em lote, busca odds
     reais) para achar jogos aprovados com odd confirmada.

  2. Para cada jogo aprovado, calcula se a odd oferecida pelo mercado
     esta "descontada" em relacao a confianca da nossa propria IA -
     ou seja, se o mercado esta pagando mais do que a nossa
     probabilidade estimada sugere que deveria pagar.

  3. Mostra os melhores achados num cartao estilizado. NAO tem botao
     de "adicionar direto na casa de apostas" - isso nao e possivel
     tecnicamente pra terceiros (nenhuma casa de apostas oferece API
     publica pra isso).

SOBRE A "PROBABILIDADE JUSTA" USADA AQUI - LEIA ISSO:
  Usamos a confianca que a nossa propria IA (Gemini) da pra cada
  entrada como proxy de probabilidade real. Isso e util, mas NAO tem
  o mesmo rigor de um modelo estatistico dedicado (tipo Poisson) nem
  da odd "de-vigada" da Pinnacle (que e uma fonte mais robusta de
  probabilidade real, ja que Pinnacle e a casa mais eficiente do
  mercado). Deixamos essa troca preparada como proxima melhoria: no
  lugar de comparar contra "confianca da IA", dá pra comparar contra
  a probabilidade implicita da Pinnacle (ja temos ela disponivel via
  oddspapi_engine.py, que usa BOOKMAKER_PRINCIPAL = "pinnacle").
"""

import re
import streamlit as st

from alavancagem import executar_pipeline_alavancagem
from poisson_model import (
    calcular_expectativas_jogo,
    probabilidade_over,
    escanear_linhas,
    LINHAS_GOLS,
    LINHAS_ESCANTEIOS,
    LINHAS_CARTOES,
)


def calcular_valor(odd, confianca_ia_pct):
    """
    Compara a "probabilidade implicita" da odd do mercado com a
    confianca que a nossa IA deu pra entrada.

    - probabilidade_implicita = 1 / odd  (o que o mercado acha
      provavel, sem contar a margem da casa)
    - Se a confianca da nossa IA for MAIOR que essa probabilidade
      implicita, a odd esta "generosa" em relacao ao que a gente
      acredita ser a chance real -> valor positivo.

    Retorna (valor_pct, eh_valor): valor_pct e a diferenca em pontos
    percentuais entre nossa confianca e a probabilidade do mercado.
    """
    if not odd or odd <= 1.0:
        return 0.0, False

    probabilidade_implicita_pct = (1 / odd) * 100
    valor_pct = confianca_ia_pct - probabilidade_implicita_pct
    eh_valor = valor_pct >= 5  # pelo menos 5 pontos percentuais de folga

    return round(valor_pct, 1), eh_valor


CSS_BILHETE = """
<style>
.bilhete-card {
    background: linear-gradient(145deg, #0d0a1f, #1a1030);
    border: 1px solid #7a3cff;
    border-radius: 18px;
    padding: 22px;
    margin-bottom: 18px;
    box-shadow: 0 0 25px rgba(122,60,255,0.25);
}
.bilhete-tag {
    display: inline-block;
    background: linear-gradient(90deg,#7a3cff,#4f46e5);
    color: white;
    font-weight: 700;
    font-size: 0.75rem;
    padding: 4px 12px;
    border-radius: 999px;
    margin-bottom: 10px;
    letter-spacing: 0.5px;
}
.bilhete-jogo {
    color: white;
    font-size: 1.3rem;
    font-weight: 800;
    margin-bottom: 4px;
}
.bilhete-liga {
    color: #94a3b8;
    font-size: 0.85rem;
    margin-bottom: 14px;
}
.bilhete-mercado {
    color: #e2e8f0;
    font-size: 1rem;
    margin-bottom: 10px;
}
.bilhete-odd {
    display: inline-block;
    background: #16a34a;
    color: white;
    font-weight: 800;
    font-size: 1.4rem;
    padding: 6px 18px;
    border-radius: 10px;
    margin-right: 10px;
}
.bilhete-valor {
    display: inline-block;
    background: linear-gradient(90deg,#eab308,#f59e0b);
    color: #1a1030;
    font-weight: 800;
    font-size: 0.95rem;
    padding: 6px 14px;
    border-radius: 10px;
}
.bilhete-motivo {
    color: #cbd5e1;
    font-size: 0.9rem;
    margin-top: 12px;
    line-height: 1.5;
}
</style>
"""


def _extrair_odd_para_linha_gols(jogo, linha, tipo):
    """
    Tenta achar a odd real de mercado pra uma linha específica de
    gols (ex: Over 2.5 FT), usando o que já foi buscado no pipeline
    (odds_dict pode ter vindo do OddsPapi ou do The Odds API).
    Retorna None se não achar.
    """
    odds_dict = jogo.get("odds_dict")
    if not odds_dict:
        return None

    mercado_str = f"{tipo} {linha} FT"

    # Tenta como se fosse formato OddsPapi (dict com "mercados")
    try:
        if "mercados" in odds_dict:
            from oddspapi_engine import extrair_odd_para_mercado
            odd = extrair_odd_para_mercado(odds_dict, mercado_str, 1.01, 50.0)
            if odd:
                return odd
    except Exception:
        pass

    # Tenta como se fosse formato The Odds API (dict com "bookmakers")
    try:
        if "bookmakers" in odds_dict:
            from the_odds_api import extrair_melhor_odd_mercado
            odd, _ = extrair_melhor_odd_mercado(odds_dict, mercado_str, 1.01, 50.0)
            if odd:
                return odd
    except Exception:
        pass

    return None


def renderizar_analise_poisson(jogo):
    """
    Roda o modelo estatístico (Poisson) pra esse jogo e mostra, dentro
    de um expander, as melhores linhas de gols/escanteios/cartões.
    Para gols, também tenta comparar com a odd real do mercado pra
    confirmar se existe valor de verdade (não só probabilidade alta).
    Para escanteios/cartões, mostra a expectativa estatística mesmo
    sem odd de mercado pareada (deixamos isso bem claro no texto).
    """
    home_id = jogo.get("casa_id")
    away_id = jogo.get("fora_id")
    league_id = jogo.get("liga_id")
    season = jogo.get("season", 2025)

    if not home_id or not away_id or not league_id:
        return

    with st.spinner(f"Calculando modelo estatístico para {jogo.get('nome','')}..."):
        expectativas = calcular_expectativas_jogo(home_id, away_id, league_id, season)

    if not expectativas:
        return

    with st.expander(f"📐 Modelo estatístico (Poisson) — {jogo.get('nome','')}"):
        st.caption(
            "Isso é matemática de probabilidade baseada nas médias reais dos "
            "times — não é opinião da IA. Veja as limitações no rodapé."
        )

        # ── GOLS: compara com odd real quando disponível ──
        st.markdown("**⚽ Gols**")
        gols_scan = escanear_linhas(expectativas["gols_total_esperado"], LINHAS_GOLS, "FT")
        alguma_com_valor = False
        for item in gols_scan[:4]:
            partes = item["mercado"].split(" ")
            tipo, linha = partes[0], float(partes[1])
            odd_real = _extrair_odd_para_linha_gols(jogo, linha, tipo)
            if odd_real:
                prob_implicita = (1 / odd_real) * 100
                diferenca = item["probabilidade_pct"] - prob_implicita
                if diferenca >= 5:
                    alguma_com_valor = True
                    st.success(
                        f"💎 {item['mercado']} — modelo estima {item['probabilidade_pct']}% de chance, "
                        f"odd real @ {odd_real} (mercado implica {prob_implicita:.1f}%) → "
                        f"**{diferenca:.0f}pp de valor**"
                    )
                else:
                    st.caption(f"{item['mercado']} — modelo: {item['probabilidade_pct']}% | odd real @ {odd_real} (sem valor claro)")
            else:
                st.caption(f"{item['mercado']} — modelo estima {item['probabilidade_pct']}% (sem odd de mercado pra comparar)")

        if not alguma_com_valor:
            st.caption("Nenhuma linha de gols com valor confirmado contra o mercado agora.")

        # ── ESCANTEIOS: só expectativa estatística, sem odd pareada ──
        amostra = expectativas.get("amostra_escanteios_cartoes", 0)
        st.markdown(f"**🚩 Escanteios** (baseado em {amostra} jogo(s) recentes de cada time)")
        escanteios_scan = escanear_linhas(expectativas["escanteios_total_esperado"], LINHAS_ESCANTEIOS, "FT")
        melhor_escanteio = escanteios_scan[0]
        st.info(
            f"Expectativa estatística: **{melhor_escanteio['mercado']}** "
            f"({melhor_escanteio['probabilidade_pct']}% de chance pelo modelo). "
            f"Total esperado no jogo: {expectativas['escanteios_total_esperado']} escanteios."
        )

        # ── CARTÕES: idem ──
        st.markdown(f"**🟨 Cartões** (baseado em {amostra} jogo(s) recentes de cada time)")
        cartoes_scan = escanear_linhas(expectativas["cartoes_total_esperado"], LINHAS_CARTOES, "FT")
        melhor_cartao = cartoes_scan[0]
        st.info(
            f"Expectativa estatística: **{melhor_cartao['mercado']}** "
            f"({melhor_cartao['probabilidade_pct']}% de chance pelo modelo). "
            f"Total esperado no jogo: {expectativas['cartoes_total_esperado']} cartões."
        )

        if amostra < 5:
            st.warning(
                f"⚠️ Escanteios e cartões estão baseados em só {amostra} jogo(s) recentes "
                "por time — amostra pequena, trate com mais cautela."
            )

        st.caption(
            "Escanteios e cartões não têm odd de mercado comparada aqui (nossas "
            "APIs de odds não cobrem esses mercados de forma confiável) — são só "
            "a expectativa matemática, não uma confirmação de valor contra o mercado."
        )


def tela_bilhete_especial():
    """
    Tela principal do "Bilhete Especial do Dia". Busca as oportunidades
    do dia usando o pipeline de alavancagem, calcula o valor de cada
    uma contra a odd real do mercado e exibe os melhores achados em
    cartões estilizados.
    """
    st.subheader("💎 Bilhete Especial do Dia")
    st.caption(
        "Melhores oportunidades do dia, cruzando as estatísticas dos dois "
        "times com a odd real do mercado."
    )
    st.markdown(CSS_BILHETE, unsafe_allow_html=True)

    api_key = st.secrets["API_KEY"]
    odds_api_key = st.secrets.get("ODDS_API_KEY", "")

    if st.button("🔍 Buscar oportunidades de hoje", use_container_width=True):
        with st.spinner("Cruzando estatísticas e odds..."):
            jogos_prontos, _ = executar_pipeline_alavancagem(
                api_key, odds_api_key,
                odd_min=1.10, odd_max=3.00, confianca_min=65,
                modo_operacao="Completo (Varredura Total)"
            )

        if not jogos_prontos:
            st.warning("Nenhuma oportunidade encontrada agora. Tenta de novo mais tarde.")
            st.session_state["bilhete_especial_resultado"] = None
            return

        for j in jogos_prontos:
            odd = j.get("melhor_odd")
            conf = j.get("ia_confianca", 0)
            valor_pct, eh_valor = calcular_valor(odd, conf)
            j["_valor_pct"] = valor_pct
            j["_eh_valor"] = eh_valor

        jogos_prontos.sort(key=lambda j: j["_valor_pct"], reverse=True)
        st.session_state["bilhete_especial_resultado"] = jogos_prontos

    jogos_prontos = st.session_state.get("bilhete_especial_resultado")
    if not jogos_prontos:
        return

    melhores = [j for j in jogos_prontos if j["_eh_valor"]][:3]
    sem_valor_claro = False
    if not melhores:
        sem_valor_claro = True
        melhores = jogos_prontos[:1]

    if sem_valor_claro:
        st.info(
            "Nenhuma entrada com valor claro agora (a odd não está descontada "
            "o suficiente em relação à nossa confiança). Mostrando a melhor "
            "disponível mesmo assim — mas o ideal é esperar por algo melhor "
            "do que forçar uma entrada fraca."
        )

    for j in melhores:
        tag = "💎 OPORTUNIDADE DE VALOR" if j["_eh_valor"] else "📊 MELHOR DISPONÍVEL"
        odd = j.get("melhor_odd", "?")
        conf = j.get("ia_confianca", 0)
        valor_pct = j["_valor_pct"]

        valor_html = ""
        if j["_eh_valor"]:
            valor_html = (
                f'<span class="bilhete-valor">Mercado paga '
                f'{valor_pct:.0f}pp a mais do que nossa confiança sugere</span>'
            )

        st.markdown(
            f"""
<div class="bilhete-card">
  <span class="bilhete-tag">{tag}</span>
  <div class="bilhete-jogo">{j.get('nome','')}</div>
  <div class="bilhete-liga">{j.get('liga_nome','')}</div>
  <div class="bilhete-mercado">Mercado: <b>{j.get('ia_mercado','')}</b></div>
  <span class="bilhete-odd">@ {odd}</span>
  {valor_html}
  <div class="bilhete-motivo">{j.get('ia_motivo','')}</div>
  <div class="bilhete-motivo">Confiança da nossa IA: {conf}/100</div>
</div>
""",
            unsafe_allow_html=True
        )

        renderizar_analise_poisson(j)

    with st.expander("ℹ️ Como o 'valor' é calculado?"):
        st.markdown(
            "Pegamos a odd real do mercado e convertemos numa "
            "**probabilidade implícita** (1 dividido pela odd). Se a "
            "confiança que a nossa IA deu pra entrada for **maior** que "
            "essa probabilidade implícita, significa que o mercado está "
            "pagando mais do que a gente acredita ser justo — essa é a "
            "definição clássica de **valor** em apostas esportivas.\n\n"
            "Isso não é garantia de acerto — é uma estimativa baseada na "
            "nossa própria análise, não num modelo estatístico auditado "
            "externamente. Trate como um filtro a mais, não como certeza."
        )
