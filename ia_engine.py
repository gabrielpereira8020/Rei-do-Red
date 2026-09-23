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
            modelos = [
                "models/gemini-3.1-flash-lite",
                "models/gemini-2.5-flash-lite",
            ]
            ultimo_erro_modelo = None
            for modelo in modelos:
                try:
                    response = client.models.generate_content(
                        model=modelo,
                        contents=prompt
                    )
                    return response.text
                except Exception as model_error:
                    ultimo_erro_modelo = model_error
                    erro_modelo = str(model_error)
                    eh_503_modelo = (
                        "503" in erro_modelo
                        or "UNAVAILABLE" in erro_modelo
                        or "overloaded" in erro_modelo.lower()
                        or "high demand" in erro_modelo.lower()
                    )
                    if not eh_503_modelo:
                        raise
            raise ultimo_erro_modelo

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
def gerar_analise_pre_jogo(jogo, fi_context=None):
    contexto = buscar_contexto_completo(jogo)
    casa = jogo["casa"]
    fora = jogo["fora"]

    bloco_fi = ""
    if fi_context:
        bloco_fi = f"""
FOOTBALL INTELLIGENCE — FONTE PRINCIPAL DA DECISÃO:
{fi_context}

REGRAS DE HIERARQUIA:
- O Football Intelligence é a fonte principal para escolher o mercado.
- Se houver BET_ELIGIBLE, sua APOSTA CRAVADA deve repetir o melhor BET_ELIGIBLE.
- Você NÃO pode trocar por outro mercado só porque parece mais intuitivo.
- Se não houver BET_ELIGIBLE, você pode apontar UMA SUGESTÃO ESTATÍSTICA somente se o bloco indicar MODO SUGESTÃO.
- Nesse caso, chame explicitamente de SUGESTÃO / FEELING e diga que NÃO foi validada por odd/edge/EV.
- Nunca chame uma sugestão sem preço de "aposta cravada".
- Use probabilidade, odd justa, odd de mercado, edge, EV, qualidade e riscos do Football Intelligence.
- Sua função é explicar o racional e contextualizar os dados, não substituir o motor matemático.
- Não altere a probabilidade calculada pelo Football Intelligence.
"""

    prompt = f"""
Você é uma IA especialista em apostas esportivas profissionais.
Responda SOMENTE em texto puro, SEM asteriscos, SEM markdown, SEM negrito.

Analise a partida PRÉ-JOGO com base nos dados reais abaixo:

{contexto}
{bloco_fi}

Use os dados reais acima para embasar cada análise.
Não invente informações que não estejam nos dados.

Responda EXATAMENTE neste formato:

🔥 APOSTA CRAVADA:
(se houver BET_ELIGIBLE no Football Intelligence, repita o melhor mercado exatamente; se não houver, escreva SEM ENTRADA VALIDADA)

💡 SUGESTÃO / FEELING:
(se houver MODO SUGESTÃO, mostre somente a melhor linha estatística exata, por exemplo OVER 2.5 GOLS, e avise que não foi validada por odd/edge/EV; caso contrário escreva NENHUMA)

📊 CONFIANÇA:
(use a probabilidade do mercado principal como referência e converta para uma nota de 0 a 10 sem inflar)

💎 OPORTUNIDADE DE OURO:
(se houver outro BET_ELIGIBLE, mostre; caso contrário escreva NENHUMA ADICIONAL)

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
(explique o que pode fazer o mercado principal falhar, incluindo limitações de dados/modelo quando houver)

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
        erro = str(e)
        return (
            "⚠️ GEMINI INDISPONÍVEL NO MOMENTO\n"
            "O Football Intelligence foi calculado normalmente, mas a camada explicativa do Gemini não respondeu.\n\n"
            f"Detalhe técnico: {erro}\n\n"
            "A decisão matemática do Football Intelligence continua válida e deve ser exibida separadamente pela interface.\n"
            "Não gere aposta alternativa por conta própria enquanto o Gemini estiver indisponível."
        )


# =====================================================
# AO VIVO
# =====================================================
def gerar_analise_ao_vivo(jogo, previsao_anterior=None, fi_signals=None):
    """
    previsao_anterior: dict opcional {"mercado": str, "confianca": int, "minuto": str}
    com a última previsão que a IA deu para ESTE MESMO jogo. Isso dá
    "memória" pra IA, pra ela não ficar mudando de ideia a cada
    checagem — só deve trocar de posição se algo decisivo aconteceu
    (gol, expulsão, mudança clara de padrão), não por uma pequena
    oscilação estatística.
    """
    fixture_id = jogo.get("id")
    contexto   = buscar_contexto_ao_vivo(jogo, fixture_id)
    casa = jogo["casa"]
    fora = jogo["fora"]

    bloco_previsao_anterior = ""
    bloco_fi = ""
    if fi_signals:
        linhas = []
        for s in fi_signals:
            try:
                fair = f"{s.fair_odds:.2f}" if s.fair_odds is not None else "—"
                linhas.append(
                    f"- {s.label}: {s.probability*100:.1f}% | status {s.status} | odd justa {fair} | motivo: {s.reason}"
                )
            except Exception:
                pass
        if linhas:
            bloco_fi = """
FOOTBALL INTELLIGENCE — SINAIS JÁ CALCULADOS PELO MOTOR MATEMÁTICO:
""" + "\n".join(linhas) + """

REGRA DE HIERARQUIA — OBRIGATÓRIA:
- O Football Intelligence é a fonte principal para escolher o mercado.
- Você NÃO pode recomendar um mercado que contradiga o melhor SIGNAL do Football Intelligence.
- Se houver SIGNAL, explique e contextualize ESSE SIGNAL.
- Se houver vários SIGNALS, priorize o de maior probabilidade.
- Se não houver SIGNAL, você pode explicar os WATCH, mas NÃO deve criar uma entrada nova por conta própria.
- Não altere a probabilidade calculada pelo Football Intelligence.
- Sua função aqui é interpretar contexto, riscos e tornar o sinal fácil de entender.
"""
    if previsao_anterior:
        bloco_previsao_anterior = f"""
SUA PREVISÃO ANTERIOR PARA ESSE MESMO JOGO (feita aos {previsao_anterior.get('minuto','?')}'):
  Mercado: {previsao_anterior.get('mercado','')}
  Confiança: {previsao_anterior.get('confianca',0)}%

REGRA DE CONTINUIDADE — MUITO IMPORTANTE:
Mantenha essa mesma linha de raciocínio, a menos que algo DECISIVO tenha
mudado desde então (gol, expulsão, lesão de titular, mudança tática clara).
NÃO troque de mercado só por uma pequena variação estatística (tipo mais um
escanteio ou um pouco mais de posse). Se a situação não mudou de forma
relevante, repita o MESMO mercado e ajuste a confiança pra cima (se o jogo
está confirmando sua visão) ou mantenha estável. Só mude de mercado se
puder justificar com um evento concreto que aconteceu.
"""

    prompt = f"""
Você é uma IA especialista em trading esportivo AO VIVO. Sua reputação
depende de dar previsões CONSISTENTES e DECISIVAS, não sinais fracos e
que mudam a cada minuto.
Responda SOMENTE em texto puro, SEM asteriscos, SEM markdown, SEM negrito.

Analise o momento ATUAL da partida com TODOS os dados ao vivo abaixo:

{contexto}
{bloco_fi}
{bloco_previsao_anterior}
INSTRUÇÕES:
- Use os eventos reais (gols, cartões, subs) para entender o momento do jogo
- Use as faltas por jogador para identificar riscos de cartão
- Use passes e posse para avaliar domínio do jogo
- Use chutes bloqueados e defesas do goleiro para avaliar pressão real
- Use as odds ao vivo se disponíveis para calibrar a análise
- Se o bloco FOOTBALL INTELLIGENCE estiver presente, a previsão principal DEVE ser o melhor SIGNAL dele.
- Não invente outro mercado concorrente quando já existir SIGNAL.
- Se não existir SIGNAL, diga claramente que não há entrada forte e explique o melhor WATCH.
- A confiança deve refletir uma convicção real: só use 75%+ se você
  realmente acredita que vai acontecer, baseado em padrão consistente
  dos dados — não infle o número artificialmente.

Responda EXATAMENTE neste formato:

🎯 PREVISÃO PRINCIPAL:
(o mesmo mercado aprovado pelo Football Intelligence; se não houver SIGNAL, escreva "SEM ENTRADA FORTE")

📊 CONFIANÇA:
(use a probabilidade do SIGNAL principal do Football Intelligence quando houver SIGNAL; se não houver, use a do melhor WATCH)

🧠 POR QUE ISSO VAI ACONTECER:
(explique o raciocínio de forma afirmativa e decisiva — não "pode acontecer", mas "vai acontecer porque X, Y, Z" com base nos dados reais)

⚡ ENTRADA RECOMENDADA:
(repita o mercado aprovado pelo Football Intelligence e explique por que o contexto ao vivo confirma ou enfraquece esse sinal; se não houver SIGNAL, escreva "AGUARDAR")

⚽ GOLS AO VIVO:
(tendência de gols baseada em chutes, pressão e odds ao vivo)

🚩 ESCANTEIOS AO VIVO:
(tendência baseada em volume de ataque, chutes bloqueados e escanteios acumulados)

🟨 CARTÕES AO VIVO:
(nome do jogador em maior risco com quantidade de faltas — use os dados reais)

⚠️ RISCOS:
(o que pode fazer essa previsão dar errado)

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
            "🎯 PREVISÃO PRINCIPAL:\nErro\n"
            "📊 CONFIANÇA:\n0\n"
            "🧠 POR QUE ISSO VAI ACONTECER:\nErro\n"
            "⚡ ENTRADA RECOMENDADA:\nErro\n"
            "⚽ GOLS AO VIVO:\nErro\n"
            "🚩 ESCANTEIOS AO VIVO:\nErro\n"
            "🟨 CARTÕES AO VIVO:\nErro\n"
            f"⚠️ RISCOS:\n{str(e)}\n"
            f"📊 PROJEÇÃO RESTANTE {jogo['casa']}:\nGOLS: 0\nESCANTEIOS: 0\nCARTÕES: 0\n"
            f"📊 PROJEÇÃO RESTANTE {jogo['fora']}:\nGOLS: 0\nESCANTEIOS: 0\nCARTÕES: 0\n"
            "FIM"
        )
