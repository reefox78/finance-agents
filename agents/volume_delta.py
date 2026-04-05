"""
Agent Volume Delta — Cryptomonnaies uniquement.

Utilise l'API publique Binance (sans clé API) pour obtenir le volume réel
d'achat vs vente (taker buy volume vs taker sell volume) sur chaque bougie.

Concepts :
  Delta journalier  = buy_volume - sell_volume
  Delta %           = buy_volume / total_volume × 100
                      (50% = équilibré, >55% = acheteurs dominants)
  CVD (14j)         = somme des deltas sur 14 jours
                      CVD croissant = accumulation = haussier
                      CVD décroissant = distribution = baissier
"""

import urllib.request
import json


# Quelques synonymes courants yfinance → Binance
_OVERRIDES = {
    "BTC-USD":  "BTCUSDT",
    "ETH-USD":  "ETHUSDT",
    "BNB-USD":  "BNBUSDT",
    "SOL-USD":  "SOLUSDT",
    "XRP-USD":  "XRPUSDT",
    "ADA-USD":  "ADAUSDT",
    "DOGE-USD": "DOGEUSDT",
    "DOT-USD":  "DOTUSDT",
    "AVAX-USD": "AVAXUSDT",
    "MATIC-USD":"MATICUSDT",
    "LINK-USD": "LINKUSDT",
    "UNI-USD":  "UNIUSDT",
    "LTC-USD":  "LTCUSDT",
    "BCH-USD":  "BCHUSDT",
    "ATOM-USD": "ATOMUSDT",
}


def _ticker_to_binance(ticker: str) -> list[str]:
    """
    Retourne une liste de symboles Binance à essayer dans l'ordre.
    Ex : BTC-USD → ["BTCUSDT", "BTCUSD"]
    """
    t = ticker.upper().strip()
    if t in _OVERRIDES:
        base = _OVERRIDES[t]
        return [base]
    # Générique : retire le tiret, essaie USDT puis USD
    symbol = t.replace("-", "")
    candidates = [symbol]
    if symbol.endswith("USD") and not symbol.endswith("USDT"):
        candidates.insert(0, symbol + "T")   # BTCUSD → essaie BTCUSDT d'abord
    return candidates


def _fetch_klines(symbol: str, interval: str = "1d", limit: int = 35) -> list | None:
    """Récupère les klines Binance. Retourne None si indisponible."""
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol={symbol}&interval={interval}&limit={limit}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            # Binance renvoie une erreur JSON si le symbole est inconnu
            if isinstance(data, dict) and "code" in data:
                return None
            return data
    except Exception:
        return None


def analyze_volume_delta(ticker: str, days: int = 14) -> dict:
    """
    Analyse le Volume Delta via l'API publique Binance.

    Paramètres
    ----------
    ticker : str  — symbole yfinance crypto (ex: "BTC-USD", "ETH-USD")
    days   : int  — fenêtre d'analyse en jours (défaut 14)

    Retourne
    --------
    dict avec :
      delta_pct_moyen  — % moyen d'achat (50 = équilibré)
      cvd_tendance     — "HAUSSE" | "BAISSE" | "NEUTRE"
      cvd_14j          — CVD brut sur la fenêtre
      signal           — "ACHETER" | "VENDRE" | "NEUTRE"
      score_final      — float dans [-1, +1]
    """
    candidates = _ticker_to_binance(ticker)
    klines = None
    for sym in candidates:
        klines = _fetch_klines(sym, limit=max(35, days + 10))
        if klines:
            break

    if not klines or len(klines) < days:
        return {
            "ticker":     ticker,
            "signal":     "NEUTRE",
            "score_final": 0.0,
            "erreur":     "Données Binance indisponibles",
        }

    # --- Calcul delta par bougie ---
    deltas     = []
    delta_pcts = []
    for k in klines[-days:]:
        total_vol = float(k[5])
        buy_vol   = float(k[9])   # taker buy base asset volume
        if total_vol <= 0:
            continue
        sell_vol  = total_vol - buy_vol
        delta     = buy_vol - sell_vol
        delta_pct = buy_vol / total_vol * 100
        deltas.append(delta)
        delta_pcts.append(delta_pct)

    if not deltas:
        return {"ticker": ticker, "signal": "NEUTRE", "score_final": 0.0}

    cvd             = round(sum(deltas), 4)
    delta_pct_moyen = round(sum(delta_pcts) / len(delta_pcts), 2)

    # --- Tendance CVD : première moitié vs deuxième moitié ---
    mi        = len(deltas) // 2
    cvd_debut = sum(deltas[:mi])
    cvd_fin   = sum(deltas[mi:])
    if cvd_debut == 0:
        cvd_tendance = "NEUTRE"
    elif cvd_fin > cvd_debut * 1.1:
        cvd_tendance = "HAUSSE"
    elif cvd_fin < cvd_debut * 0.9:
        cvd_tendance = "BAISSE"
    else:
        cvd_tendance = "NEUTRE"

    # --- Score final ---
    # delta_pct_moyen centré sur 50 : 60% → +0.2, 40% → -0.2, 70% → +0.4…
    score_delta = (delta_pct_moyen - 50) / 50   # [-1, +1]
    score_cvd   = {"HAUSSE": 0.3, "NEUTRE": 0.0, "BAISSE": -0.3}[cvd_tendance]
    score_final = round(max(-1.0, min(1.0, score_delta * 0.7 + score_cvd)), 4)

    if score_final >= 0.15:
        signal = "ACHETER"
    elif score_final <= -0.15:
        signal = "VENDRE"
    else:
        signal = "NEUTRE"

    return {
        "ticker":          ticker,
        "delta_pct_moyen": delta_pct_moyen,
        "cvd_14j":         cvd,
        "cvd_tendance":    cvd_tendance,
        "days":            days,
        "signal":          signal,
        "score_final":     score_final,
    }


if __name__ == "__main__":
    for t in ["BTC-USD", "ETH-USD", "SOL-USD"]:
        r = analyze_volume_delta(t)
        print(f"\n--- Volume Delta : {t} ---")
        if "erreur" in r:
            print(f"  Erreur : {r['erreur']}")
        else:
            print(f"  Delta % moyen  : {r['delta_pct_moyen']}%  (50% = équilibré)")
            print(f"  CVD {r['days']}j        : {r['cvd_14j']}")
            print(f"  Tendance CVD   : {r['cvd_tendance']}")
            print(f"  Score          : {r['score_final']}")
            print(f"  Signal         : {r['signal']}")
