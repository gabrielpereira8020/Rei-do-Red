from google import genai
import streamlit as st

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"]
)

def gerar_analise_ia(jogo, dados):

    prompt = f"""
Você é uma IA especialista em apostas esportivas.

Analise PROFISSIONALMENTE a partida:

{jogo}

Dados reais da API Football:

{dados}

Analise:
- gols
- escanteios
- cartões
- intensidade
- faltas
- finalizações
- jogadores com maior chance de:
    - chute no gol
    - sofrer faltas
    - cometer faltas
    - tomar cartão
    - marcar gol

Depois gere:

1. APOSTA CRAVADA
2. CONFIANÇA
3. OPORTUNIDADE DE OURO
4. ANÁLISE DE GOLS
5. ESCANTEIOS
6. CARTÕES
7. JOGADORES EM DESTAQUE
8. SCORE DOS MERCADOS
9. RISCO DA PARTIDA

NÃO invente jogadores inexistentes.

Responda EXATAMENTE nesse formato:

🔥 APOSTA CRAVADA:
texto

📊 CONFIANÇA:
numero

💎 OPORTUNIDADE DE OURO:
texto

⚽ GOLS:
texto

🚩 ESCANTEIOS:
texto

🟨 CARTÕES:
texto

🎯 JOGADORES:
Nome | Mercado | Chance
Nome | Mercado | Chance
Nome | Mercado | Chance

📈 SCORE GOLS:
numero

📈 SCORE ESCANTEIOS:
numero

📈 SCORE CARTÕES:
numero

⚠️ RISCO:
texto

FIM
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": 0.3
            }
        )

        return response.text

    except Exception as e:

        return f"Erro IA: {str(e)}"
