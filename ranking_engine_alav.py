import re

def calcular_score(jogo, odd_min, odd_max):
    score = 0
    detalhes = []

    # +20 Liga elite
    prioridade = jogo.get("prioridade", 3)
    if prioridade == 1:
        score += 20
        detalhes.append("Liga elite +20")
    elif prioridade == 2:
        score += 10
        detalhes.append("Liga media +10")
    else:
        score += 5
        detalhes.append("Outra liga +5")

    # +20 Odds na faixa alvo
    odds_encontradas = []
    try:
        matches = re.findall(r'@([\d.]+)', jogo.get("odds_txt", ""))
        for m in matches:
            try:
                v = float(m)
                if odd_min <= v <= odd_max:
                    odds_encontradas.append(v)
            except Exception:
                pass
    except Exception:
        pass

    if odds_encontradas:
        melhor = min(odds_encontradas, key=lambda x: abs(x - ((odd_min + odd_max) / 2)))
        jogo["melhor_odd"] = melhor
        if melhor <= 1.35:
            score += 20
            jogo["faixa_odd"] = "muito_segura"
            detalhes.append(f"Odd muito segura {melhor} +20")
        elif melhor <= 1.55:
            score += 16
            jogo["faixa_odd"] = "segura"
            detalhes.append(f"Odd segura {melhor} +16")
        elif melhor <= 1.80:
            score += 10
            jogo["faixa_odd"] = "moderada"
            detalhes.append(f"Odd moderada {melhor} +10")
        else:
            score += 4
            jogo["faixa_odd"] = "arriscada"
            detalhes.append(f"Odd arriscada {melhor} +4")
    else:
        jogo["melhor_odd"] = 0
        jogo["faixa_odd"] = "sem_odd"

    # +15 Double Chance disponível
    odds_txt = jogo.get("odds_txt", "").lower()
    if "double chance" in odds_txt or "1x" in odds_txt or "dc" in odds_txt:
        score += 15
        detalhes.append("Double Chance disponivel +15")

    # +15 Over/Under disponível
    if "over" in odds_txt or "under" in odds_txt or "o/u" in odds_txt:
        score += 10
        detalhes.append("Over/Under disponivel +10")

    # +10 Ambos Marcam disponível
    if "ambos" in odds_txt or "btts" in odds_txt or "both teams" in odds_txt:
        score += 8
        detalhes.append("BTTS disponivel +8")

    # +20 Estatísticas (forma, gols, aproveitamento)
    stats_txt = jogo.get("stats_txt", "")
    if stats_txt:
        # Forma boa (W W W)
        vitorias = stats_txt.count(" W")
        if vitorias >= 4:
            score += 15
            detalhes.append(f"Forma excelente {vitorias}V +15")
        elif vitorias >= 3:
            score += 10
            detalhes.append(f"Boa forma {vitorias}V +10")
        elif vitorias >= 2:
            score += 5
            detalhes.append(f"Forma razoavel {vitorias}V +5")

        # Aproveitamento em casa
        import re as re2
        match_aprov = re2.search(r'casa.*?(\d+)%', stats_txt, re.IGNORECASE)
        if match_aprov:
            aprov = int(match_aprov.group(1))
            if aprov >= 70:
                score += 15
                detalhes.append(f"Aproveitamento casa {aprov}% +15")
            elif aprov >= 55:
                score += 8
                detalhes.append(f"Aproveitamento casa {aprov}% +8")
            elif aprov >= 40:
                score += 3
                detalhes.append(f"Aproveitamento casa {aprov}% +3")

        # Média de gols
        match_gols = re2.search(r'marcados.*?([\d.]+)', stats_txt, re.IGNORECASE)
        if match_gols:
            try:
                media = float(match_gols.group(1))
                if media >= 2.0:
                    score += 10
                    detalhes.append(f"Media gols {media} +10")
                elif media >= 1.5:
                    score += 6
                    detalhes.append(f"Media gols {media} +6")
            except Exception:
                pass

    # Normaliza 0-100
    score = min(100, score)
    jogo["score"] = score
    jogo["detalhes_score"] = detalhes
    return score


def ranquear_jogos(jogos, odd_min, odd_max):
    for jogo in jogos:
        calcular_score(jogo, odd_min, odd_max)
    jogos.sort(key=lambda x: x.get("score", 0), reverse=True)
    return jogos


def filtrar_por_confianca(jogos_ranqueados, confianca_minima=40):
    return [j for j in jogos_ranqueados if j.get("score", 0) >= confianca_minima]
