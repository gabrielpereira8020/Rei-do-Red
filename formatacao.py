import streamlit as st
import re


def pegar(texto, inicio, fim):
    try:
        inicio_escaped = re.escape(inicio)
        fim_escaped = re.escape(fim)
        padrao = rf"\*{{0,2}}{inicio_escaped}\*{{0,2}}(.*?)\*{{0,2}}{fim_escaped}"
        resultado = re.search(padrao, texto, re.DOTALL)
        if resultado:
            return resultado.group(1).strip()
        return "Não encontrado"
    except:
        return "Erro"


def limpar(texto):
    texto = re.sub(r'\*+', '', texto)
    texto = re.sub(r'^#+\s*', '', texto, flags=re.MULTILINE)
    texto = re.sub(r'^-{3,}', '', texto, flags=re.MULTILINE)
    return texto.strip()


def pegar_numero(texto):
    numeros = re.findall(r'\d+', texto)
    return numeros[0] if numeros else "0"


def extrair_projecao(texto, marcador):
    """Extrai os valores da projeção de cada time."""
    try:
        bloco = re.search(
            re.escape(marcador) + r"(.*?)(📊 PROJEÇÃO|FIM)",
            texto, re.DOTALL
        )
        if not bloco:
            return {}
        linhas = bloco.group(1).strip().split("\n")
        dados = {}
        for linha in linhas:
            linha = re.sub(r'\*+', '', linha).strip()
            if ":" in linha:
                chave, _, valor = linha.partition(":")
                num = re.findall(r'\d+', valor)
                dados[chave.strip()] = num[0] if num else "0"
        return dados
    except:
        return {}


def exibir_projecao(proj_casa, proj_fora, nome_casa, nome_fora, ao_vivo=False):
    """Exibe projeção dos dois times usando colunas nativas do Streamlit."""
    titulo = "📊 PROJEÇÃO RESTANTE DA PARTIDA" if ao_vivo else "📊 PROJEÇÃO DA PARTIDA"

    mercados = [("GOLS","⚽"), ("ESCANTEIOS","🚩"), ("CARTÕES","🟨")]
    if not ao_vivo:
        mercados += [("FALTAS","🦵"), ("FINALIZAÇÕES","🎯")]

    st.markdown(f"<h3 style='color:white;margin-top:24px'>{titulo}</h3>", unsafe_allow_html=True)

    # Cabeçalho
    st.markdown(f"""
    <div style='background:#1e293b;border-radius:12px 12px 0 0;padding:10px 16px;
    display:flex;justify-content:space-between;margin-top:8px'>
        <span style='color:#64748b;font-size:0.8rem;width:30%'>MERCADO</span>
        <span style='color:#38bdf8;font-size:0.85rem;font-weight:700;width:25%;text-align:center'>{nome_casa}</span>
        <span style='color:#64748b;font-size:0.8rem;width:10%;text-align:center'>x</span>
        <span style='color:#a78bfa;font-size:0.85rem;font-weight:700;width:25%;text-align:center'>{nome_fora}</span>
        <span style='color:#64748b;font-size:0.8rem;width:10%;text-align:right'>TOT</span>
    </div>
    """, unsafe_allow_html=True)

    for m, emoji in mercados:
        v_casa = proj_casa.get(m, "?")
        v_fora = proj_fora.get(m, "?")
        try:
            total = int(v_casa) + int(v_fora)
            total_str = str(total)
        except:
            total_str = "?"

        st.markdown(f"""
        <div style='background:#0f172a;border-left:1px solid #1e3a5f;border-right:1px solid #1e3a5f;
        border-bottom:1px solid #1e3a5f;padding:10px 16px;
        display:flex;justify-content:space-between;align-items:center'>
            <span style='color:#94a3b8;font-size:0.85rem;width:30%'>{emoji} {m}</span>
            <span style='color:#38bdf8;font-weight:800;font-size:1.2rem;width:25%;text-align:center'>{v_casa}</span>
            <span style='color:#475569;font-size:0.8rem;width:10%;text-align:center'>x</span>
            <span style='color:#a78bfa;font-weight:800;font-size:1.2rem;width:25%;text-align:center'>{v_fora}</span>
            <span style='color:#64748b;font-size:0.85rem;width:10%;text-align:right'>{total_str}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom:16px'></div>", unsafe_allow_html=True)


# =====================================================
# PRÉ-JOGO
# =====================================================
def exibir_analise(texto, nome_casa="Casa", nome_fora="Fora"):
    cravada      = limpar(pegar(texto, "🔥 APOSTA CRAVADA:",       "📊 CONFIANÇA:"))
    confianca    = limpar(pegar(texto, "📊 CONFIANÇA:",            "💎 OPORTUNIDADE DE OURO:"))
    oportunidade = limpar(pegar(texto, "💎 OPORTUNIDADE DE OURO:", "⚽ GOLS:"))
    gols         = limpar(pegar(texto, "⚽ GOLS:",                 "🚩 ESCANTEIOS:"))
    escanteios   = limpar(pegar(texto, "🚩 ESCANTEIOS:",           "🟨 CARTÕES:"))
    cartoes      = limpar(pegar(texto, "🟨 CARTÕES:",              "🎯 JOGADORES:"))
    jogadores    = limpar(pegar(texto, "🎯 JOGADORES:",            "📈 SCORE GOLS:"))
    score_gols       = pegar(texto, "📈 SCORE GOLS:",       "📈 SCORE ESCANTEIOS:")
    score_escanteios = pegar(texto, "📈 SCORE ESCANTEIOS:", "📈 SCORE CARTÕES:")
    score_cartoes    = pegar(texto, "📈 SCORE CARTÕES:",    "⚠️ RISCO:")
    risco        = limpar(pegar(texto, "⚠️ RISCO:",                "🔮 FEELING:"))
    feeling = limpar(pegar(texto, "🔮 FEELING:", "FIM"))
    proj_casa = extrair_projecao(texto, f"📊 PROJEÇÃO {nome_casa}:")
    proj_fora = extrair_projecao(texto, f"📊 PROJEÇÃO {nome_fora}:")

    confianca_num        = pegar_numero(confianca)
    score_gols_num       = pegar_numero(score_gols)
    score_escanteios_num = pegar_numero(score_escanteios)
    score_cartoes_num    = pegar_numero(score_cartoes)

    st.markdown("---")

    # APOSTA CRAVADA
    st.markdown(f"""<div style='background:linear-gradient(135deg,#1a0a2e,#2d1b69);
    border:2px solid #f59e0b;border-radius:16px;padding:20px;margin:10px 0'>
    <h3 style='color:#f59e0b;margin-bottom:8px'>🔥 APOSTA CRAVADA</h3>
    <p style='color:#e2e8f0;font-size:1rem;line-height:1.7'>{cravada}</p></div>
    """, unsafe_allow_html=True)

    # CONFIANÇA
    pct = min(int(confianca_num) * 10, 100)
    cor = "#22c55e" if pct >= 70 else "#f59e0b" if pct >= 50 else "#ef4444"
    st.markdown(f"""<div style='background:linear-gradient(135deg,#0a0a2e,#0a1a3a);
    border:2px solid #38bdf8;border-radius:16px;padding:20px;margin:10px 0'>
    <h3 style='color:#38bdf8;margin-bottom:8px'>📊 CONFIANÇA</h3>
    <div style='background:#1e293b;border-radius:999px;height:18px;overflow:hidden'>
    <div style='width:{pct}%;height:100%;background:linear-gradient(90deg,#38bdf8,#7a3cff);border-radius:999px'></div>
    </div>
    <p style='color:{cor};font-size:1.5rem;font-weight:800;margin:8px 0 4px'>{confianca_num}/10</p>
    </div>""", unsafe_allow_html=True)

    # OPORTUNIDADE
    st.markdown(f"""<div style='background:linear-gradient(135deg,#0a1a0a,#1a3a1a);
    border:2px solid #22c55e;border-radius:16px;padding:20px;margin:10px 0'>
    <h3 style='color:#22c55e;margin-bottom:8px'>💎 OPORTUNIDADE DE OURO</h3>
    <p style='color:#e2e8f0;font-size:1rem;line-height:1.7'>{oportunidade}</p></div>
    """, unsafe_allow_html=True)

    # GOLS / ESCANTEIOS / CARTÕES
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""<div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:16px'>
        <h4 style='color:#60a5fa;margin-bottom:8px'>⚽ GOLS</h4>
        <p style='color:#cbd5e1;font-size:0.9rem;line-height:1.6'>{gols}</p></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:16px'>
        <h4 style='color:#a78bfa;margin-bottom:8px'>🚩 ESCANTEIOS</h4>
        <p style='color:#cbd5e1;font-size:0.9rem;line-height:1.6'>{escanteios}</p></div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:16px'>
        <h4 style='color:#f59e0b;margin-bottom:8px'>🟨 CARTÕES</h4>
        <p style='color:#cbd5e1;font-size:0.9rem;line-height:1.6'>{cartoes}</p></div>""", unsafe_allow_html=True)

    # JOGADORES
    st.markdown(f"""<div style='background:#0f172a;border:1px solid #1e3a5f;
    border-radius:16px;padding:20px;margin:10px 0'>
    <h3 style='color:#60a5fa;margin-bottom:8px'>🎯 JOGADORES EM DESTAQUE</h3>
    <p style='color:#cbd5e1;font-size:0.95rem;line-height:1.7;white-space:pre-line'>{jogadores}</p></div>
    """, unsafe_allow_html=True)

    # SCORE DOS MERCADOS
    st.markdown("<h3 style='color:white;margin-top:20px'>📈 SCORE DOS MERCADOS</h3>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        v = min(int(score_gols_num), 100)
        st.markdown(f"""<div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:16px;text-align:center'>
        <p style='color:#94a3b8;margin:0;font-size:0.85rem'>⚽ Gols</p>
        <p style='color:#38bdf8;font-size:1.8rem;font-weight:800;margin:4px 0'>{score_gols_num}</p>
        <div style='background:#1e293b;border-radius:999px;height:8px'><div style='width:{v}%;height:100%;background:#38bdf8;border-radius:999px'></div></div>
        </div>""", unsafe_allow_html=True)
    with c2:
        v = min(int(score_escanteios_num), 100)
        st.markdown(f"""<div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:16px;text-align:center'>
        <p style='color:#94a3b8;margin:0;font-size:0.85rem'>🚩 Escanteios</p>
        <p style='color:#a78bfa;font-size:1.8rem;font-weight:800;margin:4px 0'>{score_escanteios_num}</p>
        <div style='background:#1e293b;border-radius:999px;height:8px'><div style='width:{v}%;height:100%;background:#a78bfa;border-radius:999px'></div></div>
        </div>""", unsafe_allow_html=True)
    with c3:
        v = min(int(score_cartoes_num), 100)
        st.markdown(f"""<div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:16px;text-align:center'>
        <p style='color:#94a3b8;margin:0;font-size:0.85rem'>🟨 Cartões</p>
        <p style='color:#f59e0b;font-size:1.8rem;font-weight:800;margin:4px 0'>{score_cartoes_num}</p>
        <div style='background:#1e293b;border-radius:999px;height:8px'><div style='width:{v}%;height:100%;background:#f59e0b;border-radius:999px'></div></div>
        </div>""", unsafe_allow_html=True)

    # RISCO
    st.markdown(f"""<div style='background:linear-gradient(135deg,#1a0a0a,#3a1a1a);
    border:2px solid #ef4444;border-radius:16px;padding:20px;margin:20px 0 10px'>
    <h3 style='color:#ef4444;margin-bottom:8px'>⚠️ RISCO</h3>
    <p style='color:#e2e8f0;font-size:1rem;line-height:1.7'>{risco}</p></div>
    """, unsafe_allow_html=True)

    # FEELING
    st.markdown(f"""<div style='background:linear-gradient(135deg,#1a1230,#2d1a50);
    border:2px solid #a78bfa;border-radius:16px;padding:20px;margin:10px 0'>
    <h3 style='color:#c4b5fd;margin-bottom:8px'>🔮 FEELING</h3>
    <p style='color:#e2e8f0;font-size:1rem;line-height:1.7'>{feeling}</p></div>
    """, unsafe_allow_html=True)

    # PROJEÇÃO
    if proj_casa or proj_fora:
        exibir_projecao(proj_casa, proj_fora, nome_casa, nome_fora, ao_vivo=False)


# =====================================================
# AO VIVO
# =====================================================
def exibir_analise_ao_vivo(texto, nome_casa="Casa", nome_fora="Fora"):
    entrada         = limpar(pegar(texto, "⚡ ENTRADA RECOMENDADA:", "🎯 CRAVO AO VIVO:"))
    cravo           = limpar(pegar(texto, "🎯 CRAVO AO VIVO:",       "⚽ GOLS AO VIVO:"))
    gols_vivo       = limpar(pegar(texto, "⚽ GOLS AO VIVO:",        "🚩 ESCANTEIOS AO VIVO:"))
    escanteios_vivo = limpar(pegar(texto, "🚩 ESCANTEIOS AO VIVO:",  "🟨 CARTÕES AO VIVO:"))
    cartoes_vivo    = limpar(pegar(texto, "🟨 CARTÕES AO VIVO:",     "📊 CONFIANÇA:"))
    confianca       = limpar(pegar(texto, "📊 CONFIANÇA:",            "⚠️ RISCOS:"))
    riscos          = limpar(pegar(texto, "⚠️ RISCOS:",              "🔮 FEELING:"))
    feeling         = limpar(pegar(texto, "🔮 FEELING:",             f"📊 PROJEÇÃO RESTANTE {nome_casa}:"))

    proj_casa = extrair_projecao(texto, f"📊 PROJEÇÃO RESTANTE {nome_casa}:")
    proj_fora = extrair_projecao(texto, f"📊 PROJEÇÃO RESTANTE {nome_fora}:")

    confianca_num = pegar_numero(confianca)

    st.markdown("---")

    # ENTRADA RECOMENDADA
    st.markdown(f"""<div style='background:linear-gradient(135deg,#1a0a0a,#3a1a1a);
    border:2px solid #ef4444;border-radius:16px;padding:20px;margin:10px 0'>
    <h3 style='color:#ef4444;margin-bottom:8px'>⚡ ENTRADA RECOMENDADA</h3>
    <p style='color:#e2e8f0;font-size:1rem;line-height:1.7'>{entrada}</p></div>
    """, unsafe_allow_html=True)

    # CRAVO AO VIVO
    st.markdown(f"""<div style='background:linear-gradient(135deg,#1a0a2e,#2d1b69);
    border:2px solid #f59e0b;border-radius:16px;padding:20px;margin:10px 0'>
    <h3 style='color:#f59e0b;margin-bottom:8px'>🎯 CRAVO AO VIVO</h3>
    <p style='color:#e2e8f0;font-size:1rem;line-height:1.7'>{cravo}</p></div>
    """, unsafe_allow_html=True)

    # GOLS / ESCANTEIOS / CARTÕES
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""<div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:16px'>
        <h4 style='color:#60a5fa;margin-bottom:8px'>⚽ GOLS</h4>
        <p style='color:#cbd5e1;font-size:0.9rem;line-height:1.6'>{gols_vivo}</p></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:16px'>
        <h4 style='color:#a78bfa;margin-bottom:8px'>🚩 ESCANTEIOS</h4>
        <p style='color:#cbd5e1;font-size:0.9rem;line-height:1.6'>{escanteios_vivo}</p></div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:16px'>
        <h4 style='color:#f59e0b;margin-bottom:8px'>🟨 CARTÕES</h4>
        <p style='color:#cbd5e1;font-size:0.9rem;line-height:1.6'>{cartoes_vivo}</p></div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)

    # CONFIANÇA
    pct = min(int(confianca_num) * 10, 100)
    cor = "#22c55e" if pct >= 70 else "#f59e0b" if pct >= 50 else "#ef4444"
    st.markdown(f"""<div style='background:linear-gradient(135deg,#0a0a2e,#0a1a3a);
    border:2px solid #38bdf8;border-radius:16px;padding:20px;margin:10px 0'>
    <h3 style='color:#38bdf8;margin-bottom:8px'>📊 CONFIANÇA</h3>
    <div style='background:#1e293b;border-radius:999px;height:18px;overflow:hidden'>
    <div style='width:{pct}%;height:100%;background:linear-gradient(90deg,#38bdf8,#7a3cff);border-radius:999px'></div>
    </div>
    <p style='color:{cor};font-size:1.5rem;font-weight:800;margin:8px 0 4px'>{confianca_num}/10</p>
    </div>""", unsafe_allow_html=True)

    # RISCOS
    st.markdown(f"""<div style='background:linear-gradient(135deg,#1a1000,#2a2000);
    border:2px solid #f87171;border-radius:16px;padding:20px;margin:10px 0'>
    <h3 style='color:#f87171;margin-bottom:8px'>⚠️ RISCOS</h3>
    <p style='color:#e2e8f0;font-size:1rem;line-height:1.7'>{riscos}</p></div>
    """, unsafe_allow_html=True)

    # FEELING
    st.markdown(f"""<div style='background:linear-gradient(135deg,#1a1230,#2d1a50);
    border:2px solid #a78bfa;border-radius:16px;padding:20px;margin:10px 0'>
    <h3 style='color:#c4b5fd;margin-bottom:8px'>🔮 FEELING</h3>
    <p style='color:#e2e8f0;font-size:1rem;line-height:1.7'>{feeling}</p></div>
    """, unsafe_allow_html=True)

    # PROJEÇÃO RESTANTE
    if proj_casa or proj_fora:
        exibir_projecao(proj_casa, proj_fora, nome_casa, nome_fora, ao_vivo=True)
