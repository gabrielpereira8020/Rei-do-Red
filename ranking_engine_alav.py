import re

# Pesos para o ranking de confiança
PESOS = {
    "odd_segura": 25,       # Odd na faixa segura
    "liga_elite": 20,       # Liga de alta prioridade
    "forma_boa": 15,        # Time em boa forma
    "gols_favor": 15,       # Boa média de gols marcados
    "aprov_mandante": 10,   # Bom aproveitamento em casa
    "h2h_favor": 10,        # H2H favorável
    "sequencia_boa": 5,     # Sequência positiva
}

def calcular_score_odd(odds_txt, odd_min, odd_max):
    """Extrai odds do texto e verifica se estão na faixa alvo."""
    odds_encontradas = []
    try:
        # Extrai todos os valores de odd do texto
        matches = re.findall(r'@([\d.]+)', odds_txt)
        for m in matches:
            try:
                odds_encontradas.append(float(m))
            except Exception:
                pass
    except Exception:
        pass

    # Verifica se alguma odd está na faixa alvo
    odds_na_faixa = [o for o in odds_encontradas if odd_min <= o <= odd_max]
    if odds_na_faixa:
        # Quanto mais próxima do meio da faixa, melhor
        meio = (odd_min + odd_max) / 2
        melhor = min(odds_na_faixa, key=lambda x: abs(x - meio))
        # Pontuação baseada na faixa
        if melhor <= 1.35:
            return PESOS["odd_segura"], melhor, "muito_segura"
        elif melhor <= 1.55:
            return int(PESOS["odd_segura"] * 0.8), melhor, "segura"
        elif melhor <= 1.80:
            return int(PESOS["odd_segura"] * 0.6), melhor, "moderada"
        else:
            return int(PESOS["odd_segura"] * 0.3), melhor, "arriscada"
    return 0, 0, "fora_da_faixa"


def calcular_score_forma(stats_home, stats_away):
    """Pontuação baseada na forma recente dos times."""
    score = 0
    detalhes = []

    if stats_home:
        vit_home = stats_home.get("vit", 0)
        if vit_home >= 3:
            score += PESOS["forma_boa"]
            detalhes.append("Mandante em boa forma")
        elif vit_home >= 2:
            score += int(PESOS["forma_boa"] * 0.6)

        aprov = stats_home.get("aprov_home", 0)
        if aprov >= 70:
            score += PESOS["aprov_mandante"]
            detalhes.append(f"Aproveitamento em casa: {aprov}%")
        elif aprov >= 50:
            score += int(PESOS["aprov_mandante"] * 0.5)

        seq = stats_home.get("sequencia", "")
        if "vitoria" in str(seq).lower():
            score += PESOS["sequencia_boa"]
            detalhes.append("Em sequencia de vitorias")

    if stats_home:
        try:
            gols_marc = float(str(stats_home.get("gols_marcados", "0")).replace(",", "."))
            gols_sofr = float(str(stats_home.get("gols_sofridos", "0")).replace(",", "."))
            if gols_marc >= 1.5:
                score += PESOS["gols_favor"]
                detalhes.append(f"Media gols marcados: {gols_marc}")
            if gols_sofr <= 1.0:
                score += int(PESOS["gols_favor"] * 0.5)
                detalhes.append(f"Defesa solida: {gols_sofr} sofridos")
        except Exception:
            pass

    return score, detalhes


def calcular_score_h2h(h2h_list, nome_mandante):
    """Pontuação baseada no histórico H2H."""
    if not h2h_list:
        return 0, []

    vitorias_mandante = 0
    for confronto in h2h_list:
        if nome_mandante.lower() in confronto.lower():
            partes = confronto.split(":")
            if len(partes) > 1:
                placar_parte = partes[1].strip()
                numeros = re.findall(r'\d+', placar_parte)
                if len(numeros) >= 2:
                    try:
                        if int(numeros[0]) > int(numeros[1]):
                            vitorias_mandante += 1
                    except Exception:
                        pass

    if vitorias_mandante >= 3:
        return PESOS["h2h_favor"], [f"H2H favoravel: {vitorias_mandante}/5 vitorias"]
    elif vitorias_mandante >= 2:
        return int(PESOS["h2h_favor"] * 0.5), [f"H2H equilibrado: {vitorias_mandante}/5"]
    return 0, []


def ranquear_jogos(jogos_com_stats, odd_min, odd_max):
    """
    Recebe lista de jogos com stats e odds.
    Retorna lista ordenada por score de confiança.
    """
    jogos_ranqueados = []

    for jogo in jogos_com_stats:
        score_total = 0
        detalhes = []

        # Score por liga
        prioridade = jogo.get("prioridade", 3)
        if prioridade == 1:
            score_total += PESOS["liga_elite"]
            detalhes.append("Liga elite")
        elif prioridade == 2:
            score_total += int(PESOS["liga_elite"] * 0.5)

        # Score por odd
        score_odd, melhor_odd, faixa = calcular_score_odd(
            jogo.get("odds_txt", ""), odd_min, odd_max
        )
        score_total += score_odd
        if melhor_odd:
            detalhes.append(f"Melhor odd: {melhor_odd} ({faixa})")

        # Score por forma e estatísticas
        stats_home = jogo.get("stats_home", {})
        stats_away = jogo.get("stats_away", {})
        score_forma, det_forma = calcular_score_forma(stats_home, stats_away)
        score_total += score_forma
        detalhes.extend(det_forma)

        # Score por H2H
        h2h = jogo.get("h2h", [])
        score_h2h, det_h2h = calcular_score_h2h(h2h, jogo.get("casa", ""))
        score_total += score_h2h
        detalhes.extend(det_h2h)

        # Normaliza para 0-100
        score_final = min(100, score_total)

        jogos_ranqueados.append({
            **jogo,
            "score": score_final,
            "melhor_odd": melhor_odd,
            "faixa_odd": faixa,
            "detalhes_score": detalhes
        })

    # Ordena do maior para o menor score
    jogos_ranqueados.sort(key=lambda x: x["score"], reverse=True)
    return jogos_ranqueados


def filtrar_por_confianca(jogos_ranqueados, confianca_minima=70):
    """Filtra apenas jogos acima do threshold de confiança."""
    return [j for j in jogos_ranqueados if j["score"] >= confianca_minima]
