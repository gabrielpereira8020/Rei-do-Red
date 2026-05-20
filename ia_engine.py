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

Use os dados reais acima para embasar cada análise.
Não invente informações que não estejam nos dados.

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
Nome | Mercado | Probabilidade

📈 SCORE GOLS:
(número de 0 a 100)

📈 SCORE ESCANTEIOS:
(número de 0 a 100)

📈 SCORE CARTÕES:
(número de 0 a 100)

⚠️ RISCO:
(risco da partida com base nos dados)

🔮 FEELING:
(sua opinião pessoal como especialista — o que seus instintos dizem sobre esse jogo além dos números? Seja direto e confiante)

FIM
"""
    try:
        response = client.models.generate_content(
            model="models/gemini-3.1-flash-lite",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return (
            "🔥 APOSTA CRAVADA:\nErro\n"
            "📊 CONFIANÇA:\n0\n"
            "💎 OPORTUNIDADE DE OURO:\nErro\n"
            "⚽ GOLS:\nErro\n"
            "🚩 ESCANTEIOS:\nErro\n"
            "🟨 CARTÕES:\nErro\n"
            "🎯 JOGADORES:\nErro\n"
            "📈 SCORE GOLS:\n0\n"
            "📈 SCORE ESCANTEIOS:\n0\n"
            "📈 SCORE CARTÕES:\n0\n"
            f"⚠️ RISCO:\n{str(e)}\n"
            "🔮 FEELING:\nErro\n"
            "FIM"
        )


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

Analise os 3 mercados principais: GOLS, ESCANTEIOS e CARTÕES.
Use os dados reais dos jogadores em campo para identificar tendências em cada mercado.

Responda EXATAMENTE neste formato:

⚡ ENTRADA RECOMENDADA:
(Qual mercado entrar AGORA entre gols, escanteios ou cartões — e por quê, citando os dados)

🎯 CRAVO AO VIVO:
(Melhor aposta agora — pode ser gol de jogador específico, próximo escanteio, ou cartão para jogador com faltas)

⚽ GOLS AO VIVO:
(Tendência de gols nos próximos minutos baseada nos chutes e pressão)

🚩 ESCANTEIOS AO VIVO:
(Tendência de escanteios baseada no volume de ataque e laterais)

🟨 CARTÕES AO VIVO:
(Jogador em risco de cartão baseado em faltas cometidas e amarelos)

📊 CONFIANÇA:
(apenas número de 0 a 10)

⚠️ RISCOS:
(1 ou 2 riscos principais)

🔮 FEELING:
(sua opinião pessoal sobre esse momento do jogo)

FIM
"""
    try:
        response = client.models.generate_content(
            model="models/gemini-3.1-flash-lite",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return (
            "⚡ ENTRADA RECOMENDADA:\nErro\n"
            "🎯 CRAVO AO VIVO:\nErro\n"
            "⚽ GOLS AO VIVO:\nErro\n"
            "🚩 ESCANTEIOS AO VIVO:\nErro\n"
            "🟨 CARTÕES AO VIVO:\nErro\n"
            "📊 CONFIANÇA:\n0\n"
            "⚠️ RISCOS:\nErro\n"
            f"🔮 FEELING:\n{str(e)}\n"
            "FIM"
        )
