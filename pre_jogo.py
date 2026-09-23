import streamlit as st

from ligas import LIGAS, COMPETICOES_INTERNACIONAIS
from api_football import buscar_jogos_da_liga
from ia_engine import gerar_analise_pre_jogo
from formatacao import exibir_analise
from pregame_intelligence_panel import render_pregame_intelligence, build_pregame_fi_context, render_integrated_pregame_summary


def tela_pre_jogo(enviar_telegram, salvar_resultado, supabase=None):

    st.subheader("⚽ Análise Pré-Jogo")

    LIGAS_COMPLETO = dict(LIGAS)
    LIGAS_COMPLETO["🌍 Internacional / Copas"] = COMPETICOES_INTERNACIONAIS

    pais = st.selectbox(
        "🌍 Escolha o país ou competição internacional",
        list(LIGAS_COMPLETO.keys())
    )

    competicoes = LIGAS_COMPLETO[pais]

    campeonato = st.selectbox(
        "🏆 Escolha a competição",
        list(competicoes.keys())
    )

    league_id = competicoes[campeonato]
    jogos = buscar_jogos_da_liga(league_id)

    if not jogos:
        st.error("Nenhum jogo encontrado para essa competição.")
        return

    nomes_jogos = [jogo["nome"] for jogo in jogos]

    jogo_escolhido = st.selectbox(
        "⚽ Escolha o jogo",
        nomes_jogos
    )

    jogo_info = next(
        (jogo for jogo in jogos if jogo["nome"] == jogo_escolhido),
        None
    )

    if not jogo_info:
        st.error("Erro ao carregar informações do jogo.")
        return

    st.markdown("### 🧠 Rei-do-Red Intelligence Integrado")
    st.caption(
        "O Football Intelligence calcula primeiro. O Gemini recebe os mercados aprovados e explica o raciocínio, sem trocar a decisão matemática."
    )

    integrated_key = f"integrated_pre_{jogo_info.get('id', jogo_escolhido)}"

    if st.button("🔥 GERAR ANÁLISE INTEGRADA", key="gerar_pre_integrado", use_container_width=True):
        with st.spinner("Calculando Football Intelligence e depois chamando o Gemini..."):
            try:
                fi_context, fi_result, fi_shadow = build_pregame_fi_context(jogo_info)
                resposta = gerar_analise_pre_jogo(jogo_info, fi_context=fi_context)
                st.session_state[integrated_key] = {
                    "text": resposta,
                    "fi_context": fi_context,
                    "result": fi_result,
                    "shadow": fi_shadow,
                }

                fi_header = (
                    "<b>🔮 PRÉ-JOGO INTEGRADO - REI-DO-RED</b>\n\n"
                    + jogo_info["nome"]
                    + "\n\n"
                    + fi_context[:1200]
                )
                if "GEMINI INDISPONÍVEL" in resposta:
                    enviar_telegram(
                        fi_header
                        + "\n\n⚠️ Gemini indisponível no momento. "
                        + "A decisão acima veio do Football Intelligence."
                    )
                else:
                    enviar_telegram(
                        fi_header
                        + "\n\n🧠 Gemini:\n"
                        + resposta[:1200]
                    )
            except Exception as erro:
                st.error(f"Erro ao gerar análise integrada: {erro}")

    integrated = st.session_state.get(integrated_key)
    if integrated:
        render_integrated_pregame_summary(
            jogo_info,
            integrated["text"],
            integrated["result"],
            integrated["shadow"],
        )

        with st.expander("📐 Ver detalhes matemáticos do Football Intelligence"):
            render_pregame_intelligence(
                jogo_info,
                supabase=supabase,
                legacy_text=integrated["text"],
            )

        st.markdown("#### Registrar resultado:")
        c1, c2 = st.columns(2)
        jogo_id = str(jogo_info.get("id", jogo_escolhido))
        if c1.button("✅ GREEN", key=f"green_pre_{jogo_id}"):
            salvar_resultado(jogo_info["nome"], "GREEN", 0)
        if c2.button("❌ RED", key=f"red_pre_{jogo_id}"):
            salvar_resultado(jogo_info["nome"], "RED", 0)
