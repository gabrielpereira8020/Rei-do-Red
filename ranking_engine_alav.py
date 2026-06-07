"""
ranking_engine_alav.py
======================
Pontua jogos 0-100 usando SOMENTE stats da API Football.
Sem odds nessa etapa — a IA refina depois.
"""

import re


def calcular_score_stats(jogo):
    score = 0
    detalhes = []

    # 1. Prioridade da liga (ate 20 pts)
    prioridade = jogo.get("prioridade", 3)
    if prioridade == 1:
        score += 20
        detalhes.append("Liga top +20")
    elif prioridade == 2:
        score += 12
        detalhes.append("Liga media +12")
    else:
        score += 4
        detalhes.append("Liga menor +4")

    # 2. Forma mandante (ate 20 pts)
    forma_home = jogo.get("forma_home", "")
    if forma_home:
        vit = forma_home.count("W")
        if vit >= 4:
            score += 20; detalhes.append(f"Forma {vit}V +20")
        elif vit >= 3:
            score += 14; detalhes.append(f"Forma {vit}V +14")
        elif vit >= 2:
            score += 8;  detalhes.append(f"Forma {vit}V +8")
        elif vit >= 1:
            score += 3;  detalhes.append(f"Forma {vit}V +3")

    # 3. Aproveitamento em casa (ate 15 pts)
    aprov = jogo.get("aprov_home", 0)
    if aprov >= 70:
        score += 15; detalhes.append(f"Aprov casa {aprov}% +15")
    elif aprov >= 55:
        score += 10; detalhes.append(f"Aprov casa {aprov}% +10")
    elif aprov >= 40:
        score += 5;  detalhes.append(f"Aprov casa {aprov}% +5")

    # 4. Gols marcados mandante (ate 15 pts)
    try:
        gols = float(jogo.get("gols_marcados_home", 0) or 0)
        if gols >= 2.0:
            score += 15; detalhes.append(f"Gols {gols} +15")
        elif gols >= 1.5:
            score += 10; detalhes.append(f"Gols {gols} +10")
        elif gols >= 1.0:
            score += 5;  detalhes.append(f"Gols {gols} +5")
    except Exception:
        pass

    # 5. Gols sofridos visitante (ate 10 pts)
    try:
        sof = float(jogo.get("gols_sofridos_away", 0) or 0)
        if sof >= 1.8:
            score += 10; detalhes.append(f"Visit sofre {sof} +10")
        elif sof >= 1.3:
            score += 6;  detalhes.append(f"Visit sofre {sof} +6")
    except Exception:
        pass

    # 6. H2H (ate 10 pts)
    h2h_wins = jogo.get("h2h_home_wins", 0)
    h2h_total = jogo.get("h2h_total", 0)
    if h2h_total >= 3:
        taxa = h2h_wins / h2h_total
        if taxa >= 0.6:
            score += 10; detalhes.append(f"H2H {h2h_wins}/{h2h_total} +10")
        elif taxa >= 0.4:
            score += 5;  detalhes.append(f"H2H {h2h_wins}/{h2h_total} +5")

    # 7. Sequencia vitorias (ate 10 pts)
    seq = jogo.get("sequencia_home", "")
    if "vitoria" in str(seq).lower():
        try:
            n = int(re.search(r"(\d+)", seq).group(1))
            if n >= 3:
                score += 10; detalhes.append(f"Seq {n}V +10")
            elif n >= 2:
                score += 6;  detalhes.append(f"Seq {n}V +6")
        except Exception:
            pass

    score = min(100, score)
    jogo["score"] = score
    jogo["detalhes_score"] = detalhes
    return score


def ranquear_jogos_por_stats(jogos):
    for jogo in jogos:
        calcular_score_stats(jogo)
    jogos.sort(key=lambda x: x.get("score", 0), reverse=True)
    return jogos


def filtrar_top_para_ia(jogos_ranqueados, top_n=20, score_minimo=20):
    """
    Filtra top jogos para a IA analisar.
    Score minimo 20 = qualquer jogo de liga monitorada passa.
    Se ainda assim vazio, passa os top_n direto.
    """
    aprovados = [j for j in jogos_ranqueados if j.get("score", 0) >= score_minimo]
    if not aprovados and jogos_ranqueados:
        aprovados = jogos_ranqueados
    return aprovados[:top_n]


def validar_odd_para_entrada(odd_real, odd_min, odd_max, confianca_ia):
    try:
        odd_real = float(odd_real)
    except Exception:
        return False, "Odd invalida"

    if odd_real < 1.05:
        return False, f"Odd {odd_real} muito baixa"
    if odd_real < odd_min:
        return False, f"Odd {odd_real} abaixo do minimo {odd_min}"
    if odd_real > odd_max:
        return False, f"Odd {odd_real} acima do maximo {odd_max}"

    if confianca_ia >= 85 and odd_real >= 1.10:
        return True, f"IA confiante ({confianca_ia}/100) odd {odd_real} OK"

    return True, f"Odd {odd_real} dentro da faixa ({odd_min}-{odd_max})"
  
