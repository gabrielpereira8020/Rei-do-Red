import streamlit as st
import google.generativeai as genai

genai.configure(
    api_key=st.secrets["GEMINI_API_KEY"]
)

model = genai.GenerativeModel(
    "gemini-1.5-flash"
)

def gerar_analise_ia(jogo, dados):

    prompt = f"""
Você é uma IA especialista em apostas esportivas profissionais.

Analise PROFISSIONALMENTE:

{jogo}

Dados reais:

{dados}

Faça análise de:
- gols
- escanteios
- cartões
- faltas
- intensidade
- jogadores com chance de:
    - chute no gol
    - sofrer faltas
    - cometer faltas
    - tomar cartão
    - marcar gol

Depois gere:

🔥 APOSTA CRAVADA
📊 CONFIANÇA
💎 OPORTUNIDADE DE OURO
⚽ GOLS
🚩 ESCANTEIOS
🟨 CARTÕES
🎯 JOGADORES
📈 SCORE GOLS
📈 SCORE ESCANTEIOS
📈 SCORE CARTÕES
⚠️ RISCO

Responda em formato organizado.
"""

    try:

        response = model.generate_content(prompt)

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
"""
