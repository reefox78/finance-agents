import pandas as pd
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from data.market_data import get_stock_data


def _score_rsi(rsi: float) -> float:
    """
    Score continu basé sur le RSI.
    RSI 20 → +1.0 (fortement survendu = achat)
    RSI 50 → 0.0 (neutre)
    RSI 80 → -1.0 (fortement suracheté = vente)
    """
    if rsi <= 30:
        return 1.0
    elif rsi <= 50:
        return (50 - rsi) / 20 * 0.5
    elif rsi <= 70:
        return -(rsi - 50) / 20 * 0.5
    else:
        return -1.0


def _score_macd(macd: float, signal: float) -> float:
    """
    Score continu basé sur l'écart MACD / Signal.
    Plus l'écart est grand, plus le signal est fort.
    Plafonné à +1 / -1.
    """
    ecart = macd - signal
    score = ecart / 2.0
    return max(-1.0, min(1.0, score))


def _score_bb(position: float) -> float:
    """
    Score continu basé sur la position dans les Bollinger Bands.
    0% (bande basse) → +1.0
    50% (milieu)     →  0.0
    100% (bande haute) → -1.0
    """
    return round((50 - position) / 50, 4)


def _score_sma(prix: float, sma20: float, sma50: float) -> float:
    """
    Score basé sur la position du prix par rapport aux SMA.
    Prix > SMA20 > SMA50 → +1.0 (tendance haussière forte)
    Prix < SMA20 < SMA50 → -1.0 (tendance baissière forte)
    """
    if prix > sma20 and sma20 > sma50:
        return 1.0
    elif prix > sma20 and sma20 <= sma50:
        return 0.3
    elif prix <= sma20 and prix > sma50:
        return -0.3
    else:
        return -1.0


def _score_atr(atr_relatif: float) -> float:
    """
    Score basé sur l'ATR relatif.
    ATR faible = marché calme = signal plus fiable → bonus
    ATR élevé  = marché agité = signal moins fiable → pénalité
    """
    if atr_relatif < 1.0:
        return 0.5
    elif atr_relatif < 2.0:
        return 0.2
    elif atr_relatif < 3.0:
        return 0.0
    else:
        return -0.3


# --- Poids de chaque indicateur dans le score final ---
POIDS = {
    "macd": 0.30,
    "rsi":  0.25,
    "bb":   0.25,
    "sma":  0.15,
    "atr":  0.05,
}


def analyze_technical(ticker: str, period: str = "3mo") -> dict:
    """
    Analyse technique d'une action.
    Utilise des scores continus pondérés au lieu de seuils binaires.
    """
    df    = get_stock_data(ticker, period=period)
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]

    # --- Calcul des indicateurs ---
    sma20 = SMAIndicator(close, window=20).sma_indicator()
    sma50 = SMAIndicator(close, window=50).sma_indicator()
    rsi   = RSIIndicator(close, window=14).rsi()

    macd_ind    = MACD(close)
    macd_line   = macd_ind.macd()
    macd_signal = macd_ind.macd_signal()

    bb             = BollingerBands(close, window=20, window_dev=2)
    bb_haute       = bb.bollinger_hband()
    bb_basse       = bb.bollinger_lband()
    bb_moyenne     = bb.bollinger_mavg()
    atr            = AverageTrueRange(high, low, close, window=14).average_true_range()

    # --- Valeurs actuelles ---
    prix_actuel     = round(close.iloc[-1], 2)
    sma20_actuel    = round(sma20.iloc[-1], 2)
    sma50_actuel    = round(sma50.iloc[-1], 2)
    rsi_actuel      = round(rsi.iloc[-1], 2)
    macd_actuel     = round(macd_line.iloc[-1], 4)
    signal_actuel   = round(macd_signal.iloc[-1], 4)
    bb_haute_actuel = round(bb_haute.iloc[-1], 2)
    bb_basse_actuel = round(bb_basse.iloc[-1], 2)
    bb_moy_actuel   = round(bb_moyenne.iloc[-1], 2)
    atr_actuel      = round(atr.iloc[-1], 2)
    atr_relatif     = round(atr_actuel / prix_actuel * 100, 2)

    bb_largeur  = bb_haute_actuel - bb_basse_actuel
    bb_position = round(
        (prix_actuel - bb_basse_actuel) / bb_largeur * 100, 1
    ) if bb_largeur > 0 else 50.0

    # --- Scores continus ---
    s_rsi  = _score_rsi(rsi_actuel)
    s_macd = _score_macd(macd_actuel, signal_actuel)
    s_bb   = _score_bb(bb_position)
    s_sma  = _score_sma(prix_actuel, sma20_actuel, sma50_actuel)
    s_atr  = _score_atr(atr_relatif)

    # --- Score pondéré final (entre -1 et +1) ---
    score_brut = (
        s_macd * POIDS["macd"] +
        s_rsi  * POIDS["rsi"] +
        s_bb   * POIDS["bb"] +
        s_sma  * POIDS["sma"] +
        s_atr  * POIDS["atr"]
    )
    score_final = round(score_brut, 4)

    # --- Signal ---
    if score_final >= 0.15:
        signal = "ACHETER"
    elif score_final <= -0.15:
        signal = "VENDRE"
    else:
        signal = "NEUTRE"

    return {
        "ticker":        ticker,
        "prix_actuel":   prix_actuel,
        "sma20":         sma20_actuel,
        "sma50":         sma50_actuel,
        "rsi":           rsi_actuel,
        "macd":          macd_actuel,
        "macd_signal":   signal_actuel,
        "bb_haute":      bb_haute_actuel,
        "bb_basse":      bb_basse_actuel,
        "bb_moyenne":    bb_moy_actuel,
        "bb_position":   bb_position,
        "atr":           atr_actuel,
        "atr_relatif":   atr_relatif,
        "scores": {
            "macd": s_macd,
            "rsi":  s_rsi,
            "bb":   s_bb,
            "sma":  s_sma,
            "atr":  s_atr,
        },
        "score_final":   score_final,
        "signal":        signal,
    }


if __name__ == "__main__":
    resultat = analyze_technical("AAPL")

    print(f"--- Analyse technique : {resultat['ticker']} ---")
    print(f"Prix actuel   : {resultat['prix_actuel']} $")
    print(f"SMA 20        : {resultat['sma20']}")
    print(f"SMA 50        : {resultat['sma50']}")
    print(f"RSI           : {resultat['rsi']}")
    print(f"MACD          : {resultat['macd']}")
    print(f"BB Position   : {resultat['bb_position']} %")
    print(f"ATR relatif   : {resultat['atr_relatif']} %")
    print(f"\n--- Scores continus ---")
    print(f"MACD (×{POIDS['macd']}) : {resultat['scores']['macd']}")
    print(f"RSI  (×{POIDS['rsi']}) : {resultat['scores']['rsi']}")
    print(f"BB   (×{POIDS['bb']}) : {resultat['scores']['bb']}")
    print(f"SMA  (×{POIDS['sma']}) : {resultat['scores']['sma']}")
    print(f"ATR  (×{POIDS['atr']}) : {resultat['scores']['atr']}")
    print(f"\nScore final   : {resultat['score_final']}")
    print(f"Signal        : {resultat['signal']}")