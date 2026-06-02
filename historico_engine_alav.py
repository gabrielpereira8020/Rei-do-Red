import streamlit as st
import pandas as pd
from datetime import datetime

def salvar_entrada(supabase, entrada_data):
    """Salva resultado de uma entrada no Supabase."""
    try:
        supabase.table("alavancagem_historico").insert({
            "data": datetime.now().isoformat(),
            "entrada_num": entrada_data.get("entrada", 0),
            "jogo": entrada_data.get("jogo", ""),
            "mercado": entrada_data.get("mercado", ""),
            "odd": entrada_data.get("odd", 0),
            "liga": entrada_data.get("liga", ""),
            "resultado": entrada_data.get("resultado", ""),
            "valor": entrada_data.get("valor", 0),
            "retorno": entrada_data.get("retorno", 0),
            "confianca": entrada_data.get("confianca", 0),
        }).execute()
        return True
    except Exception:
        return False


def buscar_historico(supabase, limite=200):
    """Busca histórico completo de apostas."""
    try:
        data = supabase.table("alavancagem_historico").select("*").execute()
        return data.data if data.data else []
    except Exception:
        return []


def calcular_stats_mercados(historico):
    """
    Calcula taxa de acerto por mercado.
    Retorna dict: {mercado: {total, greens, taxa}}
    """
    stats = {}
    for entrada in historico:
        mercado = entrada.get("mercado", "Outro")
        resultado = entrada.get("resultado", "")

        # Normaliza nome do mercado
        if "over 0.5" in mercado.lower() or "over 0,5" in mercado.lower():
            mercado = "Over 0.5 Gols"
        elif "over 1.5" in mercado.lower() or "over 1,5" in mercado.lower():
            mercado = "Over 1.5 Gols"
        elif "over 2.5" in mercado.lower() or "over 2,5" in mercado.lower():
            mercado = "Over 2.5 Gols"
        elif "double chance" in mercado.lower() or "dupla" in mercado.lower():
            mercado = "Double Chance"
        elif "ambos marcam" in mercado.lower() or "btts" in mercado.lower():
            mercado = "Ambos Marcam"
        elif "vitoria" in mercado.lower() or "vencedor" in mercado.lower():
            mercado = "Vencedor da Partida"

        if mercado not in stats:
            stats[mercado] = {"total": 0, "greens": 0, "reds": 0, "taxa": 0}

        stats[mercado]["total"] += 1
        if resultado == "GREEN":
            stats[mercado]["greens"] += 1
        elif resultado == "RED":
            stats[mercado]["reds"] += 1

    # Calcula taxa
    for m in stats:
        total = stats[m]["total"]
        if total > 0:
            stats[m]["taxa"] = round((stats[m]["greens"] / total) * 100, 1)

    # Ordena por taxa
    return dict(sorted(stats.items(), key=lambda x: x[1]["taxa"], reverse=True))


def exibir_painel_aprendizado(supabase):
    """Exibe painel de aprendizado com stats por mercado."""
    historico = buscar_historico(supabase)

    if not historico:
        st.info("Nenhum historico registrado ainda. As estatisticas aparecerao apos suas primeiras apostas.")
        return

    st.markdown("### 📊 Painel de Aprendizado")

    total = len(historico)
    greens = sum(1 for h in historico if h.get("resultado") == "GREEN")
    reds = sum(1 for h in historico if h.get("resultado") == "RED")
    winrate = round((greens / total * 100), 1) if total > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de apostas", total)
    col2.metric("✅ Greens", greens)
    col3.metric("❌ Reds", reds)
    col4.metric("📈 Winrate geral", str(winrate) + "%")

    if total < 10:
        st.caption("Apos 10 apostas o sistema comeca a aprender seus melhores mercados.")

    st.markdown("---")
    st.markdown("#### Taxa de acerto por mercado")

    stats = calcular_stats_mercados(historico)

    for mercado, dados in stats.items():
        taxa = dados["taxa"]
        total_m = dados["total"]
        greens_m = dados["greens"]

        cor = "#22c55e" if taxa >= 80 else "#f59e0b" if taxa >= 60 else "#ef4444"

        st.markdown(
            f"<div style='background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:12px 16px;margin:6px 0'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center'>"
            f"<span style='color:#e2e8f0;font-weight:600'>{mercado}</span>"
            f"<span style='color:{cor};font-weight:800;font-size:1.1rem'>{taxa}%</span>"
            f"</div>"
            f"<div style='background:#1e293b;border-radius:999px;height:6px;margin-top:8px'>"
            f"<div style='width:{taxa}%;height:100%;background:{cor};border-radius:999px'></div>"
            f"</div>"
            f"<small style='color:#64748b'>{greens_m} greens de {total_m} apostas</small>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")
    st.markdown("#### Historico recente")
    df = pd.DataFrame(historico)
    if not df.empty:
        colunas = ["data", "jogo", "mercado", "odd", "resultado", "valor", "retorno"]
        colunas_existentes = [c for c in colunas if c in df.columns]
        df = df[colunas_existentes].sort_values("data", ascending=False).head(20)
        st.dataframe(df, use_container_width=True)
