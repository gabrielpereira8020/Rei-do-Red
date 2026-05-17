# =========================================
# ARQUIVO: api.py
# =========================================

from google import genai
import streamlit as st

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"]
)

def perguntar_ia(prompt):

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:

        return f"""
🔥 APOSTA CRAVADA:
Erro ao gerar análise

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
Erro | Erro | 0

📈 SCORE GOLS:
0

📈 SCORE ESCANTEIOS:
0

📈 SCORE CARTÕES:
0

⚠️ RISCO:
{str(e)}
"""
