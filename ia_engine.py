import streamlit as st
from google import genai

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"]
)

def gerar_analise_ia(jogo):

    prompt = f"""
Você é uma IA especialista em apostas esportivas profissionais.

Analise a partida:

{jogo["casa"]} x {jogo["fora"]}

Faça análise COMPLETA considerando:

- tendência de gols
- escanteios
- cartões
- intensidade
- faltas
- finalizações
- jogadores perigosos
- chances da partida

Depois gere:

🔥 APOSTA CRAVADA:
(aposta mais segura)

📊 CONFIANÇA:
(apenas número)

💎 OPORTUNIDADE DE OURO:
(aposta de valor)

⚽ GOLS:
(análise)

🚩 ESCANTEIOS:
(análise)

🟨 CARTÕES:
(análise)

🎯 JOGADORES:
- provável chute no gol
- provável sofrer faltas
- provável cartão

📈 SCORE GOLS:
(número)

📈 SCORE ESCANTEIOS:
(número)

📈 SCORE CARTÕES:
(número)

⚠️ RISCO:
(risco da partida)

FIM
"""

    try:

        response = client.models.generate_content(
            model="models/gemini-2.5-flash-lite",
            contents=prompt
        )

        return response.text

    except Exception as e:

        return f"""
🔥 APOSTA CRAVADA:
Erro

📊 CONFIANÇA:
0

💎 OPORTUNIDADE DE OURO:
Erro

⚽ GOLS:
Erro

🚩 ESCANTEIOS:
Erro

🟨 CARTÕES:
Erro

🎯 JOGADORES:
Erro

📈 SCORE GOLS:
0

📈 SCORE ESCANTEIOS:
0

📈 SCORE CARTÕES:
0

⚠️ RISCO:
{str(e)}

FIM
"""
