"""
Agent Short Interest.

Analyse la position vendeuse à découvert sur un titre :
- % du float shortée (pression baissière structurelle)
- Jours pour couvrir = squeeze potential si momentum haussier
- Variation mensuelle : covering = bullish, accumulation = bearish

Logique :
  - Short % élevé + en hausse → bear thesis institutionnel → VENDRE
  - Short % élevé + en baisse → covering = flux acheteurs forcés → ACHETER
  - Short % faible             → pas de pression → NEUTRE

Disponible pour US et EU stocks via yfinance. Pas applicable crypto/forex.
"""

from data.short_interest_data import get_short_interest


def _score_short_pct(pct: float) -> float:
    """
    Score basé sur le % du float shortée.
    Seuils de référence marché US :
      < 5%  : bas = neutre
      5-10% : modéré = légèrement baissier
      10-20%: élevé  = baissier
      > 20% : très élevé = baissier (mais aussi potentiel de squeeze)
    """
    if pct is None:
        return 0.0
    if pct < 5.0:    return  0.0
    elif pct < 10.0: return -0.30
    elif pct < 20.0: return -0.60
    else:            return -1.00


def _score_mom(mom_change: float) -> float:
    """
    Score basé sur la variation mensuelle du short interest.
    Négatif = couverture (shorts qui rachètent = pression haussière)
    Positif = accumulation de nouvelles positions shortées
    """
    if mom_change is None:
        return 0.0
    if mom_change < -20.0:   return  1.0    # couverture massive → bullish
    elif mom_change < -10.0: return  0.5
    elif mom_change < -3.0:  return  0.2
    elif mom_change < 3.0:   return  0.0    # stable
    elif mom_change < 10.0:  return -0.3
    elif mom_change < 20.0:  return -0.6
    else:                    return -1.0    # accumulation agressive


def _score_days_cover(days: float) -> float:
    """
    Jours pour couvrir = potentiel de squeeze.
    Seul, un ratio élevé n'est ni bullish ni bearish — il amplifie la direction.
    On l'utilise ici comme signal d'intensité modérée.
    """
    if days is None:
        return 0.0
    if days < 1.5:  return  0.0    # couverture facile = pas de tension
    elif days < 3:  return -0.1
    elif days < 5:  return -0.2
    elif days < 10: return -0.3    # difficile à couvrir
    else:           return -0.5    # très difficile = risque si rebond


def analyze_short_interest(ticker: str) -> dict:
    """
    Analyse le short interest du ticker.

    Retourne un dict avec score_final [-1, +1] et signal.
    Retourne None si données non disponibles.
    """
    data = get_short_interest(ticker)

    if not data.get("disponible"):
        return None

    short_pct  = data.get("short_pct")
    days_cover = data.get("days_to_cover")
    mom        = data.get("mom_change_pct")

    if short_pct is None:
        return None

    s_pct  = _score_short_pct(short_pct)
    s_mom  = _score_mom(mom)
    s_days = _score_days_cover(days_cover)

    # Interaction clé : si short élevé MAIS couverture en cours → signal squeeze positif
    # On inverse le signal pct quand la couverture est forte
    if short_pct > 15.0 and mom is not None and mom < -10.0:
        # Squeeze setup : fort short + covering rapide → acheter
        score_final = round(s_mom * 0.70 + s_pct * 0.30, 4)
    else:
        score_final = round(s_pct * 0.45 + s_mom * 0.40 + s_days * 0.15, 4)

    score_final = max(-1.0, min(1.0, score_final))

    if score_final >= 0.15:
        signal = "ACHETER"
    elif score_final <= -0.15:
        signal = "VENDRE"
    else:
        signal = "NEUTRE"

    return {
        "ticker":         ticker,
        "short_pct":      short_pct,
        "days_to_cover":  days_cover,
        "mom_change_pct": mom,
        "scores": {
            "short_pct":  s_pct,
            "mom":        s_mom,
            "days_cover": s_days,
        },
        "score_final":    score_final,
        "signal":         signal,
    }


if __name__ == "__main__":
    for t in ["AAPL", "NVDA", "GME"]:
        r = analyze_short_interest(t)
        if r:
            print(f"\n--- Short Interest : {r['ticker']} ---")
            print(f"Short % float     : {r['short_pct']} %")
            print(f"Jours couverture  : {r['days_to_cover']}")
            print(f"Var. mensuelle    : {r['mom_change_pct']} %")
            print(f"Score final       : {r['score_final']}")
            print(f"Signal            : {r['signal']}")
        else:
            print(f"\n{t}: Non disponible")
