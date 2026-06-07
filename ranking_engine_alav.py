 """
ranking_engine_alav.py
======================
ETAPA 1 da nova arquitetura:
  - Recebe jogos vindos APENAS da API Football (com stats reais)
  - Calcula score puramente com dados estatísticos, SEM depender de odds
  - Retorna top jogos ranqueados prontos para a IA avaliar

Fluxo correto:
  API Football → ranking_engine → IA → Odds API → IA valida odd → usuário
"""

import re


# ---------------------------------------------
# SCORE PURAMENTE ESTATÍSTICO (sem odds)
# ---------------------------------------------

def calcular_score_stats(jogo):
    """
    Pontua um jogo 0-100 usando SOMENTE dados da API Football.
    Odds não entram nessa etapa — a IA e a Odds API cuidam disso depois.
    """
    score = 0
    detalhes = []

    # -- 1. Liga (até 20 pts) ------------------
    prioridade = jogo.get("prioridade", 3)
    if prioridade == 1:
        score += 20
        detalhes.append("Liga elite +20")
    elif prioridade == 2:
        score += 12
        detalhes.append("Liga média +12")
    else:
        score += 4
        detalhes.append("Outra liga +4")

    # -- 2. Forma recente do mandante (até 20 pts) --
    forma_home = jogo.get("forma_home", "")
    if forma_home:
        vit_home = forma_home.count("W")
        if vit_home >= 4:
            score += 20
            detalhes.append(f"Mandante em chama {vit_home}V +20")
        elif vit_home >= 3:
            score += 14
            detalhes.append(f"Mandante em boa forma {vit_home}V +14")
        elif vit_home >= 2:
            score += 8
            detalhes.append(f"Mandante forma razoável {vit_home}V +8")
        elif vit_home == 1:
            score += 3
            detalhes.append(f"Mandante forma fraca {vit_home}V +3")

    # -- 3. Aproveitamento mandante em casa (até 15 pts) --
    aprov_home = jogo.get("aprov_home", 0)
    if isinstance(aprov_home, (int, float)):
        if aprov_home >= 70:
            score += 15
            detalhes.append(f"Aproveitamento casa {aprov_home}% +15")
        elif aprov_home >= 55:
            score += 10
            detalhes.append(f"Aproveitamento casa {aprov_home}% +10")
        elif aprov_home >= 40:
            score += 5
            detalhes.append(f"Aproveitamento casa {aprov_home}% +5")

    # -- 4. Gols marcados (média do mandante, até 15 pts) --
    try:
        gols_home = float(jogo.get("gols_marcados_home", 0) or 0)
        if gols_home >= 2.0:
            score += 15
            detalhes.append(f"Média gols mandante {gols_home} +15")
        elif gols_home >= 1.5:
            score += 10
            detalhes.append(f"Média gols mandante {gols_home} +10")
        elif gols_home >= 1.0:
            score += 5
            detalhes.append(f"Média gols mandante {gols_home} +5")
    except Exception:
        pass

    # -- 5. Gols sofridos visitante (até 10 pts) --
    try:
        gols_sof_away = float(jogo.get("gols_sofridos_away", 0) or 0)
        if gols_sof_away >= 1.8:
            score += 10
            detalhes.append(f"Visitante sofre muito {gols_sof_away} +10")
        elif gols_sof_away >= 1.3:
            score += 6
            detalhes.append(f"Visitante sofre bastante {gols_sof_away} +6")
    except Exception:
        pass

    # -- 6. H2H — histórico favorável (até 10 pts) --
    h2h_home_wins = jogo.get("h2h_home_wins", 0)
    h2h_total = jogo.get("h2h_total", 0)
    if h2h_total >= 3:
        taxa_h2h = h2h_home_wins / h2h_total
        if taxa_h2h >= 0.6:
            score += 10
            detalhes.append(f"H2H favorável {h2h_home_wins}/{h2h_total} +10")
        elif taxa_h2h >= 0.4:
            score += 5
            detalhes.append(f"H2H equilibrado {h2h_home_wins}/{h2h_total} +5")

    # -- 7. Sequência atual (até 10 pts) --
    sequencia_home = jogo.get("sequencia_home", "")
    if "vitoria" in str(sequencia_home).lower():
        try:
            num = int(re.search(r"(\d+)", sequencia_home).group(1))
            if num >= 3:
                score += 10
                detalhes.append(f"Sequência {num} vitórias +10")
            elif num >= 2:
                score += 6
                detalhes.append(f"Sequência {num} vitórias +6")
        except Exception:
            pass

    score = min(100, score)
    jogo["score"] = score
    jogo["detalhes_score"] = detalhes
    return score


def ranquear_jogos_por_stats(jogos):
    """
    Calcula score estatístico de todos os jogos e retorna ordenado do melhor ao pior.
    NÃO depende de odds — essa etapa é puramente da API Football.
    """
    for jogo in jogos:
        calcular_score_stats(jogo)
    jogos.sort(key=lambda x: x.get("score", 0), reverse=True)
    return jogos


def filtrar_top_para_ia(jogos_ranqueados, top_n=20, score_minimo=20):
    """
    Filtra os melhores jogos para enviar à IA.
    Score minimo 20 = qualquer jogo de liga monitorada passa.
    A IA faz o refinamento real depois.
    top_n limita para nao explodir o prompt.
    """
    aprovados = [j for j in jogos_ranqueados if j.get("score", 0) >= score_minimo]
    # Se ainda assim ficou vazio, pega os top_n independente de score
    if not aprovados and jogos_ranqueados:
        aprovados = jogos_ranqueados[:top_n]
    return aprovados[:top_n]


# ---------------------------------------------
# VALIDAÇÃO FINAL DA ODD (Etapa 4)
# ---------------------------------------------

def validar_odd_para_entrada(odd_real, odd_min, odd_max, confianca_ia):
    """
    Valida se a odd real faz sentido para entrar.
    Retorna (aprovado: bool, motivo: str)
    """
    try:
        odd_real = float(odd_real)
    except Exception:
        return False, "Odd inválida"

    if odd_real < odd_min:
        return False, f"Odd {odd_real} abaixo do mínimo {odd_min}"

    if odd_real > odd_max:
        return False, f"Odd {odd_real} acima do máximo {odd_max}"

    # Odd muito baixa mesmo dentro do range pode indicar mercado viciado
    if odd_real < 1.10:
        return False, f"Odd {odd_real} suspeita (muito baixa)"

    # Se confiança da IA for alta, aceita odd um pouco menor
    if confianca_ia >= 85 and odd_real >= 1.15:
        return True, f"IA confiante ({confianca_ia}/100) + odd {odd_real} aceitável"

    if odd_min <= odd_real <= odd_max:
        return True, f"Odd {odd_real} dentro da faixa ({odd_min}-{odd_max})"

    return False, f"Odd {odd_real} fora da faixa"
      
