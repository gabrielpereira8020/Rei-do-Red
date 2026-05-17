# =========================================
# ARQUIVO: analise_pre_jogo.py
# =========================================

from api import perguntar_ia
from formatacao import extrair_resposta

def analisar_pre_jogo(jogo):

    prompt = f"""
Você é uma IA especialista em apostas esportivas profissionais.

Faça uma análise COMPLETA da partida:

{jogo}

Analise:
- tendência de gols
- escanteios
- cartões
- intensidade do jogo
- jogadores com chance de:
    - chutar no gol
    - sofrer faltas
    - cometer faltas
    - tomar cartão
    - marcar gol

Depois gere:

1. APOSTA CRAVADA
2. % DE CONFIANÇA
3. OPORTUNIDADE DE OURO
4. ANÁLISE DE GOLS
5. ANÁLISE DE ESCANTEIOS
6. ANÁLISE DE CARTÕES
7. 3 jogadores em destaque
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
"""

    resposta = perguntar_ia(prompt)

    return extrair_resposta(resposta)
