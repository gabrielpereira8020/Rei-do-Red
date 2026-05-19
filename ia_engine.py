from google import genai
import streamlit as st
from api_football import buscar_contexto_completo, buscar_contexto_ao_vivo

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# =====================================================
# PRÉ-JOGO
# =====================================================
def gerar_analise_pre_jogo(jogo):
    contexto = buscar_contexto_completo(jogo)

    prompt = f"""
Você é uma IA especialista em apostas esportivas profissionais.
Responda SOMENTE em texto puro, SEM asteriscos, SEM markdown, SEM negrito.

Analise a partida PRÉ-JOGO com base nos dados reais abaixo:

{contexto}

Use os dados reais acima (classificação, H2H, forma recente e desempenho dos jogadores)
para embasar cada análise. Não invente informações que não estejam nos dados.

Responda EXATAMENTE neste formato:

🔥 APOSTA CRAVADA:
(aposta mais segura baseada nos dados reais)

📊 CONFIANÇA:
(apenas número de 0 a 10)

💎 OPORTUNIDADE DE OURO:
(aposta de valor com base nos dados)

⚽ GOLS:
(análise baseada no H2H, forma recente e atacantes em destaque)

🚩 ESCANTEIOS:
(análise baseada no estilo de jogo e dados)

🟨 CARTÕES:
(análise baseada no histórico e jogadores com cartões na temporada)

🎯 JOGADORES:
(liste 3 jogadores em destaque com mercado recomendado, ex: Nome | Chute no gol | Alta)

📈 SCORE GOLS:
(número de 0 a 100)

📈 SCORE ESCANTEIOS:
(número de 0 a 100)

📈 SCORE CARTÕES:
(número de 0 a 100)

⚠️ RISCO:
(risco da partida com base nos dados)

FIM
"""
    try:
        response = client.models.generate_content(
            model="models/gemini-3.1-flash-lite",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"🔥 APOSTA CRAVADA:\nErro\n📊 CONFIANÇA:\n0\n💎 OPORTUNIDADE DE OURO:\nErro\n⚽ GOLS:\nErro\n🚩 ESCANTEIOS:\nErro\n🟨 CARTÕES:\nErro\n🎯 JOGADORES:\nErro\n📈 SCORE GOLS:\n0\n📈 SCORE ESCANTEIOS:\n0\n📈 SCORE CARTÕES:\n0\n⚠️ RISCO:\n{str(e)}\nFIM"


# =====================================================
# AO VIVO
# =====================================================
def gerar_analise_ao_vivo(jogo):
    fixture_id = jogo.get("id")
    contexto   = buscar_contexto_ao_vivo(jogo, fixture_id)

    prompt = f"""
Você é uma IA especialista em trading esportivo AO VIVO.
Responda SOMENTE em texto puro, SEM asteriscos, SEM markdown, SEM negrito.

Analise o momento ATUAL da partida com os dados ao vivo abaixo:

{contexto}

Use os dados reais dos jogadores em campo (chutes, gols, cartões, nota)
para identificar tendências e recomendar entradas precisas.

Responda EXATAMENTE neste formato:

⚡ ENTRADA RECOMENDADA:
(ENTRA AGORA ou AGUARDA — em qual mercado e por quê, citando os dados)

🎯 CRAVO AO VIVO:
(melhor aposta para os próximos minutos baseada nos jogadores em destaque)

📊 CONFIANÇA:
(apenas número de 0 a 10)

⚠️ RISCOS:
(1 ou 2 riscos principais baseados nos dados)

🔮 FEELING:
(seu instinto sobre o momento do jogo)

FIM
"""
    try:
        response = client.models.generate_content(
            model="models/gemini-2.5-flash-lite",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"⚡ ENTRADA RECOMENDADA:\nErro\n🎯 CRAVO AO VIVO:\nErro\n📊 CONFIANÇA:\n0\n⚠️ RISCOS:\nErro\n🔮 FEELING:\n{str(e)}\nFIM"
