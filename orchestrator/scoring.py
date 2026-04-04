POIDS = {
    "technique":   0.25,
    "fondamental": 0.20,
    "sentiment":   0.10,
    "trends":      0.07,
    "insider":     0.08,
    "macro":       0.10,
    "risque":      0.20,
}

SEUIL_ACHAT = 0.10
SEUIL_VENTE = -0.10


def signal_en_score(signal: str) -> float:
    """Fallback : convertit un signal texte en score numérique."""
    mapping = {
        "ACHETER":  0.5,
        "NEUTRE":   0.0,
        "VENDRE":  -0.5,
    }
    return mapping.get(signal, 0.0)


def macro_en_multiplicateur(score_macro: float) -> float:
    """
    La macro agit comme multiplicateur global.
    Environnement favorable → bonus, défavorable → pénalité.
    """
    if score_macro >= 0.3:    return 1.10
    elif score_macro >= 0:    return 1.00
    elif score_macro >= -0.3: return 0.90
    else:                     return 0.75


def calculer_score(tech: dict, fund: dict, sent: dict, risk: dict,
                   trends: dict = None, insider: dict = None,
                   macro: dict = None) -> dict:
    """
    Calcule le score pondéré global.
    Utilise les scores continus des agents si disponibles.
    """
    s_tech     = tech.get("score_final",    signal_en_score(tech["signal"]))
    s_fund     = fund.get("score_final",    signal_en_score(fund["signal"]))
    s_sent     = signal_en_score(sent["signal"])
    s_trends   = trends.get("score_final",  0.0) if trends  else 0.0
    s_insider  = insider.get("score_final", 0.0) if insider else 0.0
    s_macro    = macro.get("score_final",   0.0) if macro   else 0.0
    mult_risk  = risk.get("multiplicateur", 1.0)
    mult_macro = macro_en_multiplicateur(s_macro) if macro else 1.0

    poids_actifs = (
        POIDS["technique"] +
        POIDS["fondamental"] +
        POIDS["sentiment"] +
        (POIDS["trends"]  if trends  else 0) +
        (POIDS["insider"] if insider else 0) +
        (POIDS["macro"]   if macro   else 0)
    )

    score_brut = (
        s_tech    * POIDS["technique"] +
        s_fund    * POIDS["fondamental"] +
        s_sent    * POIDS["sentiment"] +
        s_trends  * (POIDS["trends"]  if trends  else 0) +
        s_insider * (POIDS["insider"] if insider else 0) +
        s_macro   * (POIDS["macro"]   if macro   else 0)
    ) / poids_actifs

    score_final = round(score_brut * mult_risk * mult_macro, 4)
    score_final = max(-1.0, min(1.0, score_final))

    if score_final >= SEUIL_ACHAT:
        decision = "ACHETER"
    elif score_final <= SEUIL_VENTE:
        decision = "VENDRE"
    else:
        decision = "NEUTRE"

    return {
        "scores": {
            "technique":      round(s_tech, 4),
            "fondamental":    round(s_fund, 4),
            "sentiment":      round(s_sent, 4),
            "trends":         round(s_trends, 4),
            "insider":        round(s_insider, 4),
            "macro":          round(s_macro, 4),
            "multiplicateur": mult_risk,
            "mult_macro":     mult_macro,
        },
        "poids":       POIDS,
        "score_final": score_final,
        "decision":    decision,
    }


if __name__ == "__main__":
    tech    = {"score_final": 0.08,  "signal": "NEUTRE"}
    fund    = {"score_final": 0.125, "signal": "NEUTRE"}
    sent    = {"signal": "NEUTRE"}
    risk    = {"multiplicateur": 1.0, "risque": "MODERE"}
    trends  = {"score_final": 0.0}
    insider = {"score_final": -1.0}
    macro   = {"score_final": -0.1}

    resultat = calculer_score(tech, fund, sent, risk, trends, insider, macro)

    print("--- Scoring pondéré ---")
    print(f"Technique    : {resultat['scores']['technique']} × {POIDS['technique']}")
    print(f"Fondamental  : {resultat['scores']['fondamental']} × {POIDS['fondamental']}")
    print(f"Sentiment    : {resultat['scores']['sentiment']} × {POIDS['sentiment']}")
    print(f"Trends       : {resultat['scores']['trends']} × {POIDS['trends']}")
    print(f"Insider      : {resultat['scores']['insider']} × {POIDS['insider']}")
    print(f"Macro        : {resultat['scores']['macro']} × {POIDS['macro']}")
    print(f"Mult risque  : {resultat['scores']['multiplicateur']}")
    print(f"Mult macro   : {resultat['scores']['mult_macro']}")
    print(f"Score final  : {resultat['score_final']}")
    print(f"Décision     : {resultat['decision']}")