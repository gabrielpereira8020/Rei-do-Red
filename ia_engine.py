from google import genai
import streamlit as st

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def gerar_analise_pre_jogo(jogo):
    prompt = f"""
Você é uma IA especialista em apostas esportivas profissionais.
Responda SOMENTE em texto puro, SEM asteriscos, SEM markdown, SEM negrito.

Analise a partida PRÉ-JOGO:
{jogo["time_casa"]} x {jogo["time_fora"]}

Considere: tendência de gols, escanteios, cartões, intensidade,
faltas, finalizações, jogadores perigosos e chances da partida.

Responda EXATAMENTE neste formato:

🔥 APOSTA CRAVADA:
(aposta mais segura)

📊 CONFIANÇA:
(apenas número de 0 a 10)

💎 OPORTUNIDADE DE OURO:
(aposta de valor)

⚽ GOLS:
(análise)

🚩 ESCANTEIOS:
(análise)

🟨 CARTÕES:
(análise)

🎯 JOGADORES:
Nome | Mercado | Chance
Nome | Mercado | Chance
Nome | Mercado | Chance

📈 SCORE GOLS:
(número de 0 a 100)

📈 SCORE ESCANTEIOS:
(número de 0 a 100)

📈 SCORE CARTÕES:
(número de 0 a 100)

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
        return f"🔥 APOSTA CRAVADA:\nErro\n📊 CONFIANÇA:\n0\n💎 OPORTUNIDADE DE OURO:\nErro\n⚽ GOLS:\nErro\n🚩 ESCANTEIOS:\nErro\n🟨 CARTÕES:\nErro\n🎯 JOGADORES:\nErro\n📈 SCORE GOLS:\n0\n📈 SCORE ESCANTEIOS:\n0\n📈 SCORE CARTÕES:\n0\n⚠️ RISCO:\n{str(e)}\nFIM"


def gerar_analise_ao_vivo(jogo):
    prompt = f"""
Você é uma IA especialista em trading esportivo AO VIVO.
Responda SOMENTE em texto puro, SEM asteriscos, SEM markdown, SEM negrito.

Analise o momento ATUAL da partida:
{jogo["casa"]} x {jogo["fora"]}
Minuto: {jogo.get("minuto", "?")}
Placar: {jogo.get("placar", "0 x 0")}
Estatísticas ao vivo: {jogo.get("stats", "indisponível")}
Índice de Pressão: {jogo.get("pressao", 0)}

Com base nesses dados ao vivo, responda EXATAMENTE neste formato:

⚡ ENTRADA RECOMENDADA:
(ENTRA AGORA ou AGUARDA — em qual mercado e por quê)

🎯 CRAVO AO VIVO:
(melhor aposta para os próximos minutos)

📊 CONFIANÇA:
(apenas número de 0 a 10)

⚠️ RISCOS:
(1 ou 2 riscos principais)

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
