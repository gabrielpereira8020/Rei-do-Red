# =========================================
# ARQUIVO: formatacao.py
# =========================================

import re

def pegar(texto, inicio, fim):

    try:
        padrao = f"{inicio}(.*?){fim}"
        resultado = re.search(padrao, texto, re.DOTALL)

        if resultado:
            return resultado.group(1).strip()

        return "Não encontrado"

    except:
        return "Erro"


def extrair_resposta(texto):

    cravada = pegar(
        texto,
        "🔥 APOSTA CRAVADA:",
        "📊 CONFIANÇA:"
    )

    confianca = pegar(
        texto,
        "📊 CONFIANÇA:",
        "💎 OPORTUNIDADE DE OURO:"
    )

    oportunidade = pegar(
        texto,
        "💎 OPORTUNIDADE DE OURO:",
        "⚽ GOLS:"
    )

    gols = pegar(
        texto,
        "⚽ GOLS:",
        "🚩 ESCANTEIOS:"
    )

    escanteios = pegar(
        texto,
        "🚩 ESCANTEIOS:",
        "🟨 CARTÕES:"
    )

    cartoes = pegar(
        texto,
        "🟨 CARTÕES:",
        "🎯 JOGADORES:"
    )

    jogadores_texto = pegar(
        texto,
        "🎯 JOGADORES:",
        "📈 SCORE GOLS:"
    )

    score_gols = pegar(
        texto,
        "📈 SCORE GOLS:",
        "📈 SCORE ESCANTEIOS:"
    )

    score_escanteios = pegar(
        texto,
        "📈 SCORE ESCANTEIOS:",
        "📈 SCORE CARTÕES:"
    )

    score_cartoes = pegar(
        texto,
        "📈 SCORE CARTÕES:",
        "⚠️ RISCO:"
    )

    risco = pegar(
        texto,
        "⚠️ RISCO:",
        "FIM"
    )

    jogadores = []

    linhas = jogadores_texto.split("\n")

    for linha in linhas:

        if "|" in linha:

            partes = linha.split("|")

            if len(partes) >= 3:

                jogadores.append({
                    "nome": partes[0].strip(),
                    "mercado": partes[1].strip(),
                    "chance": partes[2].strip()
                })

    return {
        "cravada": cravada,
        "confianca": confianca,
        "oportunidade": oportunidade,
        "gols": gols,
        "escanteios": escanteios,
        "cartoes": cartoes,
        "jogadores": jogadores,
        "score_gols": int(
            ''.join(filter(str.isdigit, score_gols))
        ) if any(char.isdigit() for char in score_gols) else 0,
        "score_escanteios": int(
            ''.join(filter(str.isdigit, score_escanteios))
        ) if any(char.isdigit() for char in score_escanteios) else 0,
        "score_cartoes": int(
            ''.join(filter(str.isdigit, score_cartoes))
        ) if any(char.isdigit() for char in score_cartoes) else 0,
        "risco": risco
    }
