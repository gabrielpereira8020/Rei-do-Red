from google import genai
import streamlit as st
import time
from api_football import buscar_contexto_completo, buscar_contexto_ao_vivo

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


# =====================================================
# RETRY AUTOMÁTICO PARA ERROS TEMPORÁRIOS DO GEMINI (503)
# =====================================================
def _chamar_gemini_com_retry(prompt, max_tentativas=3, espera_base=5):
    """
    Chama o Gemini e tenta novamente automaticamente se o erro for
    temporário (503 - modelo sobrecarregado/indisponível no momento).
    Usa backoff crescente: espera 5s, depois 10s, depois 15s...
    Se o erro não for 503 (ex: erro de autenticação, prompt inválido),
    não faz sentido tentar de novo, então relança na hora.
    """
    ultima_excecao = None

    for tentativa in range(1, max_tentativas + 1):
        try:
            response = client.models.generate_content(
                model="models/gemini-3.1-flash-lite",
                contents=prompt
            )
            return response.text

        except Exception as e:
            ultima_excecao = e
            erro_str = str(e)

            # Só vale a pena tentar de novo se for erro de indisponibilidade
            # temporária do modelo (503 / UNAVAILABLE / overloaded)
            eh_erro_temporario = (
                "503" in erro_str
                or "UNAVAILABLE" in erro_str
                or "overloaded" in erro_str.lower()
                or "currently exp" in erro_str.lower()
            )

            if eh_erro_temporario and tentativa < max_tentativas:
                espera = espera_base * tentativa  # 5s, 10s, 15s...
                time.sleep(espera)
                continue
            else:
                # Não é erro temporário, ou já esgotou as tentativas
                raise ultima_excecao

    # Não deveria chegar aqui, mas por garantia:
    raise ultima_excecao


# =====================================================
# PRÉ-JOGO
# =====================================================
def gerar_analise_pre_jogo(jogo):
    contexto = buscar_contexto_completo(jogo)
    casa = jogo["casa"]
    fora = jogo["fora"]

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
(sua opinião pessoal como especialista sobre esse jogo)

📊 PROJEÇÃO {casa}:
GOLS: (número inteiro)
ESCANTEIOS: (número inteiro)
CARTÕES: (número inteiro)
FALTAS: (número inteiro)
FINALIZAÇÕES: (número inteiro)

📊 PROJEÇÃO {fora}:
GOLS: (número inteiro)
ESCANTEIOS: (número inteiro)
CARTÕES: (número inteiro)
FALTAS: (número inteiro)
FINALIZAÇÕES: (número inteiro)

FIM
"""
    try:
        return _chamar_gemini_com_retry(prompt)
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
            f"📊 PROJEÇÃO {jogo['casa']}:\nGOLS: 0\nESCANTEIOS: 0\nCARTÕES: 0\nFALTAS: 0\nFINALIZAÇÕES: 0\n"
            f"📊 PROJEÇÃO {jogo['fora']}:\nGOLS: 0\nESCANTEIOS: 0\nCARTÕES: 0\nFALTAS: 0\nFINALIZAÇÕES: 0\n"
            "FIM"
        )


# =====================================================
# AO VIVO
# =====================================================
def gerar_analise_ao_vivo(jogo):
    fixture_id = jogo.get("id")
    contexto   = buscar_contexto_ao_vivo(jogo, fixture_id)
    casa = jogo["casa"]
    fora = jogo["fora"]

    prompt = f"""
Você é uma IA especialista em trading esportivo AO VIVO.
Responda SOMENTE em texto puro, SEM asteriscos, SEM markdown, SEM negrito.

Analise o momento ATUAL da partida com TODOS os dados ao vivo abaixo:

{contexto}

INSTRUÇÕES:
- Use os eventos reais (gols, cartões, subs) para entender o momento do jogo
- Use as faltas por jogador para identificar riscos de cartão
- Use passes e posse para avaliar domínio do jogo
- Use chutes bloqueados e defesas do goleiro para avaliar pressão real
- Use as odds ao vivo se disponíveis para calibrar a análise
- Analise os 3 mercados: GOLS, ESCANTEIOS e CARTÕES

Responda EXATAMENTE neste formato:

⚡ ENTRADA RECOMENDADA:
(Qual mercado entrar AGORA e por quê — baseado nos dados reais)

🎯 CRAVO AO VIVO:
(Melhor aposta agora — gol de jogador específico, próximo escanteio ou cartão iminente)

⚽ GOLS AO VIVO:
(Tendência de gols baseada em chutes, pressão e odds ao vivo)

🚩 ESCANTEIOS AO VIVO:
(Tendência baseada em volume de ataque, chutes bloqueados e escanteios acumulados)

🟨 CARTÕES AO VIVO:
(Nome do jogador em maior risco com quantidade de faltas — use os dados reais)

📊 CONFIANÇA:
(apenas número de 0 a 10)

⚠️ RISCOS:
(1 ou 2 riscos principais baseados nos dados)

🔮 FEELING:
(sua leitura do momento atual do jogo)

📊 PROJEÇÃO RESTANTE {casa}:
GOLS: (quantos gols ainda espera desse time até o fim)
ESCANTEIOS: (quantos escanteios restantes espera)
CARTÕES: (quantos cartões restantes espera)

📊 PROJEÇÃO RESTANTE {fora}:
GOLS: (quantos gols ainda espera desse time até o fim)
ESCANTEIOS: (quantos escanteios restantes espera)
CARTÕES: (quantos cartões restantes espera)

FIM
"""
    try:
        return _chamar_gemini_com_retry(prompt)
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
            f"📊 PROJEÇÃO RESTANTE {jogo['casa']}:\nGOLS: 0\nESCANTEIOS: 0\nCARTÕES: 0\n"
            f"📊 PROJEÇÃO RESTANTE {jogo['fora']}:\nGOLS: 0\nESCANTEIOS: 0\nCARTÕES: 0\n"
            "FIM"
        )
