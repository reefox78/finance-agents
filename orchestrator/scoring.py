import json
from pathlib import Path

_FICHIER_CUSTOM = Path(__file__).parent.parent / "config" / "weights_custom.json"

POIDS = {
    "technique":         0.25,
    "fondamental":       0.18,
    "sentiment":         0.09,
    "trends":            0.06,
    "insider":           0.07,
    "macro":             0.09,
    "risque":            0.20,   # multiplicateur, pas poids additif
    "options_flow":      0.09,   # flux institutionnel options
    "sec_filings":       0.06,   # événements réglementaires
    "short_interest":    0.06,   # pression vendeuse
    "earnings_surprise": 0.10,   # anomalie post-earnings drift
    "volume_delta":      0.12,   # buy/sell pressure via Binance (crypto)
}

SEUIL_ACHAT = 0.10
SEUIL_VENTE = -0.10


def _charger_poids() -> dict:
    """Retourne les poids custom si disponibles, sinon les poids par défaut."""
    if _FICHIER_CUSTOM.exists():
        try:
            with open(_FICHIER_CUSTOM, encoding="utf-8") as f:
                custom = json.load(f)
            # Complète les clés manquantes avec les défauts
            return {**POIDS, **custom}
        except Exception:
            pass
    return POIDS


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


def calculer_score(tech: dict, fund: dict = None, sent: dict = None,
                   risk: dict = None, trends: dict = None,
                   insider: dict = None, macro: dict = None,
                   options_flow: dict = None, sec_filings: dict = None,
                   short_interest: dict = None, earnings_surprise: dict = None,
                   volume_delta: dict = None,
                   sector_risk: dict = None,
                   momentum_ct: dict = None) -> dict:
    """
    Calcule le score pondéré global.
    Tous les agents sauf 'tech' et 'risk' sont optionnels (None = ignoré).
    Les poids sont renormalisés automatiquement selon les agents actifs.
    """
    s_tech     = tech.get("score_final",    signal_en_score(tech["signal"]))
    s_fund     = fund.get("score_final",    signal_en_score(fund["signal"])) if fund     else 0.0
    s_sent     = signal_en_score(sent["signal"])                              if sent     else 0.0
    s_trends   = trends.get("score_final",  0.0)                             if trends   else 0.0
    s_insider  = insider.get("score_final", 0.0)                             if insider  else 0.0
    s_macro    = macro.get("score_final",   0.0)                             if macro    else 0.0
    s_options  = options_flow.get("score_final",      0.0)                  if options_flow      else 0.0
    s_sec      = sec_filings.get("score_final",       0.0)                  if sec_filings       else 0.0
    s_short    = short_interest.get("score_final",    0.0)                  if short_interest    else 0.0
    s_earnings = earnings_surprise.get("score_final", 0.0)                  if earnings_surprise else 0.0
    s_voldelta = volume_delta.get("score_final",      0.0)                  if volume_delta      else 0.0

    mult_risk     = risk.get("multiplicateur", 1.0)           if risk        else 1.0
    mult_macro    = macro_en_multiplicateur(s_macro)          if macro       else 1.0
    mult_secteur  = sector_risk.get("mult_sectoriel", 1.0)   if sector_risk else 1.0
    mult_momentum = momentum_ct.get("mult_momentum",  1.0)   if momentum_ct else 1.0

    P = _charger_poids()   # poids actifs (custom ou défauts)

    poids_actifs = (
        P["technique"] +
        (P["fondamental"]       if fund              else 0) +
        (P["sentiment"]         if sent              else 0) +
        (P["trends"]            if trends            else 0) +
        (P["insider"]           if insider           else 0) +
        (P["macro"]             if macro             else 0) +
        (P["options_flow"]      if options_flow      else 0) +
        (P["sec_filings"]       if sec_filings       else 0) +
        (P["short_interest"]    if short_interest    else 0) +
        (P["earnings_surprise"] if earnings_surprise else 0) +
        (P["volume_delta"]      if volume_delta      else 0)
    )

    score_brut = (
        s_tech     * P["technique"] +
        s_fund     * (P["fondamental"]       if fund              else 0) +
        s_sent     * (P["sentiment"]         if sent              else 0) +
        s_trends   * (P["trends"]            if trends            else 0) +
        s_insider  * (P["insider"]           if insider           else 0) +
        s_macro    * (P["macro"]             if macro             else 0) +
        s_options  * (P["options_flow"]      if options_flow      else 0) +
        s_sec      * (P["sec_filings"]       if sec_filings       else 0) +
        s_short    * (P["short_interest"]    if short_interest    else 0) +
        s_earnings * (P["earnings_surprise"] if earnings_surprise else 0) +
        s_voldelta * (P["volume_delta"]      if volume_delta      else 0)
    ) / poids_actifs

    score_final = round(score_brut * mult_risk * mult_macro * mult_secteur * mult_momentum, 4)
    score_final = max(-1.0, min(1.0, score_final))

    if score_final >= SEUIL_ACHAT:
        decision = "ACHETER"
    elif score_final <= SEUIL_VENTE:
        decision = "VENDRE"
    else:
        decision = "NEUTRE"

    return {
        "scores": {
            "technique":         round(s_tech,     4),
            "fondamental":       round(s_fund,     4),
            "sentiment":         round(s_sent,     4),
            "trends":            round(s_trends,   4),
            "insider":           round(s_insider,  4),
            "macro":             round(s_macro,    4),
            "options_flow":      round(s_options,  4),
            "sec_filings":       round(s_sec,      4),
            "short_interest":    round(s_short,    4),
            "earnings_surprise": round(s_earnings, 4),
            "volume_delta":      round(s_voldelta, 4),
            "multiplicateur":    mult_risk,
            "mult_macro":        mult_macro,
            "mult_secteur":      mult_secteur,
            "mult_momentum":     mult_momentum,
        },
        "poids":       P,
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