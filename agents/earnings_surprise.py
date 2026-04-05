"""
Agent Earnings Surprise.

Exploite le post-earnings drift, une des anomalies les plus robustes en finance :
les actions qui battent le consensus Wall Street continuent de monter 1 à 3 mois.
Les actions qui déçoivent continuent de baisser.

Signal basé sur :
  1. Surprise du dernier trimestre (la plus récente = la plus informative)
  2. Surprise moyenne sur les 4 derniers trimestres (trend de gestion)
  3. Taux de réussite (nb beats / nb trimestres) = qualité de guidance

Disponible pour les actions US et EU (yfinance en a pour les deux).
Non applicable pour crypto et forex (pas d'EPS).
"""

from data.earnings_data import get_earnings_surprise


def _score_surprise(surprise_pct: float) -> float:
    """
    Score basé sur l'écart EPS actual vs estimate.
    Une surprise > 5% est considérée significative.
    """
    if surprise_pct is None:
        return 0.0
    if surprise_pct > 15.0:    return  1.0
    elif surprise_pct > 5.0:   return  0.5
    elif surprise_pct > 0.0:   return  0.2
    elif surprise_pct > -5.0:  return -0.2
    elif surprise_pct > -15.0: return -0.5
    else:                      return -1.0


def _score_consistency(nb_beats: int, nb_quarters: int) -> float:
    """
    Score basé sur la régularité des beats.
    Un management qui bat régulièrement = meilleure visibilité → prime de fiabilité.
    """
    if nb_quarters == 0:
        return 0.0
    ratio = nb_beats / nb_quarters
    if ratio >= 0.75:   return  0.5
    elif ratio >= 0.50: return  0.0
    elif ratio >= 0.25: return -0.3
    else:               return -0.6


def analyze_earnings_surprise(ticker: str) -> dict:
    """
    Analyse la qualité des surprises sur bénéfices du ticker.

    Retourne un dict avec score_final [-1, +1] et signal.
    Retourne None si données non disponibles.
    """
    data = get_earnings_surprise(ticker, quarters=4)

    if not data.get("disponible"):
        return None

    latest  = data["latest_surprise"]
    avg     = data["avg_surprise"]
    beats   = data["nb_beats"]
    total_q = data["nb_quarters"]

    s_latest      = _score_surprise(latest)
    s_avg         = _score_surprise(avg)
    s_consistency = _score_consistency(beats, total_q)

    # Pondération : dernière surprise = signal le plus fort (post-earnings drift récent)
    score_final = round(
        s_latest      * 0.50 +
        s_avg         * 0.30 +
        s_consistency * 0.20,
        4
    )
    score_final = max(-1.0, min(1.0, score_final))

    if score_final >= 0.15:
        signal = "ACHETER"
    elif score_final <= -0.15:
        signal = "VENDRE"
    else:
        signal = "NEUTRE"

    return {
        "ticker":          ticker,
        "latest_surprise": latest,
        "avg_surprise":    avg,
        "nb_beats":        beats,
        "nb_quarters":     total_q,
        "surprises":       data["surprises"],
        "next_earnings":   data.get("next_earnings"),
        "scores": {
            "latest":      s_latest,
            "average":     s_avg,
            "consistency": s_consistency,
        },
        "score_final":     score_final,
        "signal":          signal,
    }


if __name__ == "__main__":
    for t in ["AAPL", "NVDA", "MSFT", "MC.PA"]:
        r = analyze_earnings_surprise(t)
        if r:
            print(f"\n--- Earnings Surprise : {r['ticker']} ---")
            print(f"Derniere surprise : {r['latest_surprise']} %")
            print(f"Moyenne 4T        : {r['avg_surprise']} %")
            print(f"Beats             : {r['nb_beats']}/{r['nb_quarters']}")
            print(f"Prochain earnings : {r['next_earnings']}")
            print(f"Score final       : {r['score_final']}")
            print(f"Signal            : {r['signal']}")
        else:
            print(f"\n{t}: Non disponible")
