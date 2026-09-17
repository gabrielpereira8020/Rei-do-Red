import pandas as pd
import streamlit as st

from football_intelligence.supabase_shadow_store import SHADOW_TABLE


def _pct(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "-"


def _fmt(value, digits=2):
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "-"


def _assessment_rows(snapshot_row):
    items = snapshot_row.get("assessments") or []
    rows = []
    for item in items:
        rows.append({
            "Mercado": item.get("market"),
            "Seleção": item.get("selection"),
            "Linha": item.get("line"),
            "Probabilidade": _pct(item.get("probability")),
            "Odd": _fmt(item.get("offered_odds")),
            "Prob. mercado": _pct(item.get("market_probability_devig")),
            "Edge": _pct(item.get("edge")),
            "EV": _pct(item.get("expected_value")),
            "Decisão": item.get("decision"),
            "Motivos": "; ".join(item.get("reasons") or []),
        })
    return rows


def tela_shadow_lab(supabase):
    st.subheader("🧪 SHADOW LAB")
    st.caption(
        "Painel de validação do Football Intelligence Engine. "
        "As análises exibidas aqui não substituem o sistema atual e não enviam entradas ao Telegram."
    )

    if supabase is None:
        st.error("Supabase indisponível.")
        return

    try:
        response = (
            supabase.table(SHADOW_TABLE)
            .select("*")
            .order("generated_at", desc=True)
            .limit(300)
            .execute()
        )
        snapshots = response.data or []
    except Exception as exc:
        st.warning(
            "Ainda não foi possível carregar snapshots Shadow. "
            "Confirme se a migration football_intelligence/sql/001_shadow_snapshots.sql foi aplicada no Supabase."
        )
        st.caption(f"Detalhe técnico: {exc}")
        return

    if not snapshots:
        st.info(
            "Nenhuma análise Shadow foi registrada ainda. Assim que o coletor começar a salvar snapshots reais, "
            "eles aparecerão aqui automaticamente."
        )
        return

    fixture_ids = sorted({int(row["fixture_id"]) for row in snapshots if row.get("fixture_id") is not None})
    selected_fixture = st.selectbox("Fixture", fixture_ids, index=0)
    fixture_rows = [row for row in snapshots if int(row.get("fixture_id", -1)) == int(selected_fixture)]
    latest = fixture_rows[0]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fixture", str(selected_fixture))
    col2.metric("xG casa", _fmt(latest.get("expected_home_goals")))
    col3.metric("xG fora", _fmt(latest.get("expected_away_goals")))
    col4.metric("Modelo", latest.get("model_name") or "-")

    q1, q2, q3 = st.columns(3)
    q1.metric("Qualidade dos dados", _pct(latest.get("data_quality")))
    q2.metric("Qualidade do modelo", _pct(latest.get("model_quality")))
    q3.metric("Snapshots", len(fixture_rows))

    rows = _assessment_rows(latest)
    if rows:
        df = pd.DataFrame(rows)
        st.markdown("### Última análise")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("O snapshot mais recente não possui avaliações de mercado.")

    history_rows = []
    for row in fixture_rows:
        assessments = row.get("assessments") or []
        eligible = sum(1 for item in assessments if item.get("decision") == "BET_ELIGIBLE")
        watch = sum(1 for item in assessments if item.get("decision") == "WATCH")
        no_bet = sum(1 for item in assessments if item.get("decision") == "NO_BET")
        insufficient = sum(1 for item in assessments if item.get("decision") == "INSUFFICIENT_DATA")
        history_rows.append({
            "Horário": row.get("generated_at"),
            "xG casa": row.get("expected_home_goals"),
            "xG fora": row.get("expected_away_goals"),
            "Dados": row.get("data_quality"),
            "Modelo": row.get("model_quality"),
            "BET_ELIGIBLE": eligible,
            "WATCH": watch,
            "NO_BET": no_bet,
            "INSUFFICIENT_DATA": insufficient,
        })

    if history_rows:
        st.markdown("### Evolução dos snapshots")
        history_df = pd.DataFrame(history_rows)
        st.dataframe(history_df, use_container_width=True, hide_index=True)

    st.markdown("### Interpretação")
    st.info(
        "BET_ELIGIBLE significa apenas que o mercado passou pelos filtros atuais do motor Shadow. "
        "Nesta fase isso é evidência para validação, não garantia de acerto nem recomendação automática."
    )
