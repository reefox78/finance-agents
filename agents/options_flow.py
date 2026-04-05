"""
Agent Options Flow.

Analyse le flux d'options pour détecter un sentiment directionnel institutionnel :
- Put/call ratio (volume + open interest)
- Activité anormale (volume >> OI = conviction)
- IV skew (prime de risque baissier = peur institutionnelle)

Disponible pour les actions US. Retourne None pour les autres types d'actifs.
"""

from data.options_data import get_options_flow


def _score_pc_ratio(pc: float) -> float:
    """
    Score basé sur le ratio put/call volumique.
    Ratio moyen marché ≈ 0.70 à 0.80 sur les actions.
    < 0.50 → forte demande calls = bullish
    > 1.20 → forte demande puts  = bearish
    """
    if pc is None:
        return 0.0
    if pc < 0.50:   return  1.0
    elif pc < 0.70: return  0.5
    elif pc < 1.00: return  0.0
    elif pc < 1.30: return -0.5
    else:           return -1.0


def _score_skew(skew: float) -> float:
    """
    Score basé sur le skew IV (OTM puts − OTM calls).
    Skew normal ≈ 0.05-0.10 (les puts ont toujours une prime)
    Skew élevé → peur institutionnelle → bearish
    Skew négatif → calls premium → bullish
    """
    if skew is None:
        return 0.0
    if skew < 0.0:    return  0.5   # calls plus chers = momentum haussier
    elif skew < 0.10: return  0.0   # normal
    elif skew < 0.25: return -0.5   # prime de risque élevée
    else:             return -1.0   # protection institutionnelle extrême


def _score_unusual(unusual_calls: int, unusual_puts: int) -> float:
    """
    Score basé sur l'activité anormale (volume > 5× OI).
    Appels inhabituels >> puts : conviction d'achat institutionnel.
    """
    total = unusual_calls + unusual_puts
    if total == 0:
        return 0.0
    ratio_calls = unusual_calls / total
    if ratio_calls >= 0.70:   return  0.5
    elif ratio_calls >= 0.55: return  0.2
    elif ratio_calls <= 0.30: return -0.5
    elif ratio_calls <= 0.45: return -0.2
    return 0.0


def analyze_options_flow(ticker: str) -> dict:
    """
    Analyse le flux d'options du ticker.

    Retourne un dict avec score_final [-1, +1] et signal (ACHETER/NEUTRE/VENDRE).
    Retourne None si les données ne sont pas disponibles.
    """
    data = get_options_flow(ticker)

    if not data.get("disponible"):
        return None

    pc   = data.get("pc_ratio_vol")
    skew = data.get("skew_iv")
    uc   = data.get("unusual_calls", 0)
    up   = data.get("unusual_puts",  0)

    s_pc      = _score_pc_ratio(pc)
    s_skew    = _score_skew(skew)
    s_unusual = _score_unusual(uc, up)

    # Pondération : P/C ratio = signal le plus fiable, skew = contexte, unusual = conviction
    score_final = round(
        s_pc      * 0.50 +
        s_skew    * 0.30 +
        s_unusual * 0.20,
        4
    )

    if score_final >= 0.20:
        signal = "ACHETER"
    elif score_final <= -0.20:
        signal = "VENDRE"
    else:
        signal = "NEUTRE"

    return {
        "ticker":         ticker,
        "pc_ratio_vol":   data.get("pc_ratio_vol"),
        "pc_ratio_oi":    data.get("pc_ratio_oi"),
        "call_volume":    data.get("call_volume"),
        "put_volume":     data.get("put_volume"),
        "unusual_calls":  uc,
        "unusual_puts":   up,
        "skew_iv":        skew,
        "scores": {
            "pc_ratio":  s_pc,
            "skew":      s_skew,
            "unusual":   s_unusual,
        },
        "score_final":    score_final,
        "signal":         signal,
    }


if __name__ == "__main__":
    r = analyze_options_flow("AAPL")
    if r:
        print(f"--- Options Flow : {r['ticker']} ---")
        print(f"P/C ratio (vol) : {r['pc_ratio_vol']}")
        print(f"P/C ratio (OI)  : {r['pc_ratio_oi']}")
        print(f"Volume calls    : {r['call_volume']:,}")
        print(f"Volume puts     : {r['put_volume']:,}")
        print(f"Activite anorm. : {r['unusual_calls']} calls / {r['unusual_puts']} puts")
        print(f"IV Skew         : {r['skew_iv']}")
        print(f"Score final     : {r['score_final']}")
        print(f"Signal          : {r['signal']}")
    else:
        print("Pas de donnees options disponibles.")
