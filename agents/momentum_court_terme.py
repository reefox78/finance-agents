"""
Agent Momentum Court Terme.

Analyse les 5 dernières bougies daily pour détecter si le momentum
court terme confirme ou invalide le signal principal (swing).

Retourne un mult_momentum (0.85 → 1.12) appliqué comme multiplicateur
au score final — exactement comme mult_sectoriel.

Logique :
  - Variation totale sur 5j
  - Ratio bougies haussières / baissières
  - Tendance du volume (accumulation ou distribution ?)
  - Accélération du prix (momentum s'emballe ou ralentit ?)
  - Force de la dernière bougie (corps vs mèches)
"""

import numpy as np
from data.market_data import get_stock_data


# ── Scores partiels ────────────────────────────────────────────────────────────

def _score_variation_5j(closes: list) -> float:
    """Variation totale sur 5 jours normalisée."""
    if len(closes) < 2:
        return 0.0
    var = (closes[-1] - closes[0]) / closes[0] * 100
    if var >= 5.0:    return  1.0
    elif var >= 2.0:  return  0.6
    elif var >= 0.5:  return  0.3
    elif var >= -0.5: return  0.0
    elif var >= -2.0: return -0.3
    elif var >= -5.0: return -0.6
    else:             return -1.0


def _score_direction_bougies(opens: list, closes: list) -> float:
    """Ratio bougies haussières vs baissières (-1 à +1)."""
    if not opens:
        return 0.0
    haussières = sum(1 for o, c in zip(opens, closes) if c > o)
    ratio = haussières / len(opens)
    return round((ratio - 0.5) * 2, 4)


def _score_volume_trend(volumes: list) -> float:
    """
    Le volume augmente-t-il vers la fin ?
    Volume croissant sur hausse = accumulation (bullish).
    Volume croissant sur baisse = distribution (bearish) — géré via direction.
    """
    if len(volumes) < 3:
        return 0.0
    moy_debut = float(np.mean(volumes[:2]))
    moy_fin   = float(np.mean(volumes[-2:]))
    if moy_debut == 0:
        return 0.0
    ratio = moy_fin / moy_debut
    if ratio >= 1.5:    return  0.8
    elif ratio >= 1.2:  return  0.4
    elif ratio >= 0.9:  return  0.0
    elif ratio >= 0.7:  return -0.3
    else:               return -0.6


def _score_acceleration(closes: list) -> float:
    """
    Accélération du mouvement : dérivée seconde des clôtures.
    Momentum qui s'emballe = score positif.
    Momentum qui ralentit  = score négatif.
    """
    if len(closes) < 4:
        return 0.0
    variations = [(closes[i] - closes[i-1]) / closes[i-1] * 100
                  for i in range(1, len(closes))]
    mi = len(variations) // 2
    moy_debut = float(np.mean(variations[:mi]))
    moy_fin   = float(np.mean(variations[mi:]))
    accel = moy_fin - moy_debut
    if accel >= 1.0:    return  0.8
    elif accel >= 0.3:  return  0.4
    elif accel >= -0.3: return  0.0
    elif accel >= -1.0: return -0.4
    else:               return -0.8


def _score_force_bougie(open_: float, close: float, high: float, low: float) -> float:
    """
    Force de la dernière bougie.
    Corps large / mèches faibles = signal fort dans la direction de la bougie.
    Doji / mèches larges = hésitation → score ~0.
    """
    corps  = abs(close - open_)
    range_ = high - low
    if range_ == 0:
        return 0.0
    ratio_corps = corps / range_
    direction   = 1.0 if close >= open_ else -1.0
    if ratio_corps >= 0.7:   score = 0.7 * direction
    elif ratio_corps >= 0.4: score = 0.3 * direction
    else:                    score = 0.0   # doji / indécision
    return round(score, 4)


# ── Poids ──────────────────────────────────────────────────────────────────────

POIDS = {
    "variation_5j":  0.30,
    "direction":     0.25,
    "volume_trend":  0.20,
    "acceleration":  0.15,
    "force_bougie":  0.10,
}


def _mult_from_score(score: float) -> float:
    """Convertit le score momentum en multiplicateur."""
    if score >= 0.35:    return 1.12
    elif score >= 0.15:  return 1.05
    elif score >= -0.15: return 1.00
    elif score >= -0.35: return 0.93
    else:                return 0.85


# ── Agent principal ────────────────────────────────────────────────────────────

def analyze_momentum_court_terme(ticker: str, n_candles: int = 5) -> dict:
    """
    Analyse le momentum sur les n dernières bougies daily.

    Retourne :
        score_final   : -1 à +1
        mult_momentum : multiplicateur (0.85 → 1.12)
        signal        : CONFIRME | NEUTRE | INVALIDE
    """
    try:
        df = get_stock_data(ticker, period="1mo")
        if df is None or len(df) < n_candles + 1:
            return {
                "erreur":        "Données insuffisantes",
                "score_final":   0.0,
                "mult_momentum": 1.0,
                "signal":        "NEUTRE",
            }

        df = df.tail(n_candles)
        closes  = df["Close"].tolist()
        opens   = df["Open"].tolist()
        highs   = df["High"].tolist()
        lows    = df["Low"].tolist()
        volumes = df["Volume"].tolist()

        # ── Scores partiels ──────────────────────────────────────────────────
        s_var    = _score_variation_5j(closes)
        s_dir    = _score_direction_bougies(opens, closes)
        s_vol    = _score_volume_trend(volumes)
        s_accel  = _score_acceleration(closes)
        s_bougie = _score_force_bougie(opens[-1], closes[-1], highs[-1], lows[-1])

        score_brut = (
            s_var    * POIDS["variation_5j"] +
            s_dir    * POIDS["direction"]    +
            s_vol    * POIDS["volume_trend"] +
            s_accel  * POIDS["acceleration"] +
            s_bougie * POIDS["force_bougie"]
        )
        score_final = round(max(-1.0, min(1.0, score_brut)), 4)
        mult        = _mult_from_score(score_final)

        if score_final >= 0.15:
            signal = "CONFIRME"
        elif score_final <= -0.15:
            signal = "INVALIDE"
        else:
            signal = "NEUTRE"

        # ── Métriques lisibles ───────────────────────────────────────────────
        variation_5j  = round((closes[-1] - closes[0]) / closes[0] * 100, 2)
        variations_j  = [
            round((closes[i] - closes[i-1]) / closes[i-1] * 100, 2)
            for i in range(1, len(closes))
        ]
        nb_haussières = sum(1 for o, c in zip(opens, closes) if c > o)
        moy_debut_vol = float(np.mean(volumes[:2]))
        vol_ratio     = round(float(np.mean(volumes[-2:])) / moy_debut_vol, 2) \
                        if moy_debut_vol > 0 else 1.0
        r_            = highs[-1] - lows[-1]
        force_pct     = round(abs(closes[-1] - opens[-1]) / r_ * 100, 1) if r_ > 0 else 0.0

        return {
            "ticker":         ticker,
            "n_candles":      n_candles,
            "variation_5j":   variation_5j,
            "variations_j":   variations_j,
            "nb_haussières":  nb_haussières,
            "vol_ratio":      vol_ratio,
            "force_bougie":   force_pct,
            "scores": {
                "variation_5j": round(s_var,    4),
                "direction":    round(s_dir,    4),
                "volume_trend": round(s_vol,    4),
                "acceleration": round(s_accel,  4),
                "force_bougie": round(s_bougie, 4),
            },
            "score_final":    score_final,
            "mult_momentum":  mult,
            "signal":         signal,
        }

    except Exception as e:
        return {
            "erreur":        str(e),
            "score_final":   0.0,
            "mult_momentum": 1.0,
            "signal":        "NEUTRE",
        }


if __name__ == "__main__":
    for t in ["AAPL", "MC.PA", "BTC-USD", "TTE.PA"]:
        r = analyze_momentum_court_terme(t)
        print(f"\n── {t} ──")
        print(f"Variation 5j   : {r.get('variation_5j')} %")
        print(f"Variations/j   : {r.get('variations_j')}")
        print(f"Bougies haussières : {r.get('nb_haussières')}/{r.get('n_candles')}")
        print(f"Volume ratio   : {r.get('vol_ratio')}x")
        print(f"Force bougie   : {r.get('force_bougie')} %")
        print(f"Score final    : {r.get('score_final')}")
        print(f"Mult momentum  : {r.get('mult_momentum')}")
        print(f"Signal         : {r.get('signal')}")
