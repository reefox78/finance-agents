import pandas as pd
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator, ChaikinMoneyFlowIndicator
from data.market_data import get_stock_data


def _score_rsi(rsi: float) -> float:
    if rsi <= 30:
        return 1.0
    elif rsi <= 50:
        return (50 - rsi) / 20 * 0.5
    elif rsi <= 70:
        return -(rsi - 50) / 20 * 0.5
    else:
        return -1.0


def _score_macd(macd: float, signal: float) -> float:
    ecart = macd - signal
    score = ecart / 2.0
    return max(-1.0, min(1.0, score))


def _score_bb(position: float) -> float:
    return round((50 - position) / 50, 4)


def _score_sma(prix: float, sma20: float, sma50: float) -> float:
    if prix > sma20 and sma20 > sma50:
        return 1.0
    elif prix > sma20 and sma20 <= sma50:
        return 0.3
    elif prix <= sma20 and prix > sma50:
        return -0.3
    else:
        return -1.0


def _score_atr(atr_relatif: float) -> float:
    if atr_relatif < 1.0:
        return 0.5
    elif atr_relatif < 2.0:
        return 0.2
    elif atr_relatif < 3.0:
        return 0.0
    else:
        return -0.3


def _score_obv(obv: pd.Series) -> float:
    """
    Score basé sur la tendance de l'OBV (On-Balance Volume).
    OBV croissant = accumulation = haussier
    OBV décroissant = distribution = baissier
    """
    if len(obv) < 20:
        return 0.0
    obv_last  = obv.iloc[-1]
    obv_10    = obv.iloc[-10]
    obv_20    = obv.iloc[-20]
    trend_court  = obv_last > obv_10
    trend_long   = obv_last > obv_20
    if trend_court and trend_long:
        return 0.8
    elif trend_court:
        return 0.3
    elif not trend_court and not trend_long:
        return -0.8
    else:
        return -0.3


def _score_cmf(cmf: float) -> float:
    """
    Chaikin Money Flow : entre -1 et +1, déjà normalisé.
    >+0.1 = pression acheteuse, <-0.1 = pression vendeuse.
    """
    return max(-1.0, min(1.0, cmf))


def _score_vwap(prix: float, vwap: float) -> float:
    """
    Score basé sur la position du prix vs VWAP (20j).
    Prix nettement au-dessus du VWAP = acheteurs dominants.
    """
    if vwap <= 0:
        return 0.0
    pct = (prix - vwap) / vwap * 100
    if pct >= 3.0:
        return 0.6
    elif pct >= 1.0:
        return 0.3
    elif pct <= -3.0:
        return -0.6
    elif pct <= -1.0:
        return -0.3
    return 0.0


def _score_vol_ratio(vol_ratio: float, direction: float) -> float:
    """
    Score basé sur le volume relatif combiné à la direction de la bougie.
    Volume fort sur bougie haussière = confirmation achat.
    Volume fort sur bougie baissière = confirmation vente.
    direction : +1 (close > open) ou -1 (close < open)
    """
    if vol_ratio >= 1.5:
        return 0.5 * direction
    elif vol_ratio >= 1.2:
        return 0.2 * direction
    else:
        return 0.1 * direction


# --- Poids de chaque indicateur dans le score final ---
POIDS = {
    "macd":      0.22,
    "rsi":       0.18,
    "bb":        0.18,
    "sma":       0.12,
    "atr":       0.04,
    "obv":       0.12,
    "cmf":       0.08,
    "vwap":      0.04,
    "vol_ratio": 0.02,
}


def analyze_technical(ticker: str, period: str = "3mo") -> dict:
    """
    Analyse technique d'une action.
    Utilise des scores continus pondérés — inclut les indicateurs de volume
    (OBV, CMF, VWAP, ratio de volume) en plus des indicateurs classiques.
    """
    df     = get_stock_data(ticker, period=period)
    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"]
    open_  = df["Open"]

    # --- Indicateurs classiques ---
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

    # --- Indicateurs de volume ---
    obv = OnBalanceVolumeIndicator(close, volume).on_balance_volume()
    cmf = ChaikinMoneyFlowIndicator(high, low, close, volume, window=20).chaikin_money_flow()

    # VWAP 20 jours (moyenne mobile pondérée par le volume)
    typical_price = (high + low + close) / 3
    vwap_series   = (typical_price * volume).rolling(20).sum() / volume.rolling(20).sum()

    # Ratio volume actuel / moyenne 20 jours
    vol_moy_20 = volume.rolling(20).mean()

    # --- Valeurs actuelles ---
    prix_actuel     = round(close.iloc[-1], 2)
    open_actuel     = round(open_.iloc[-1], 2)
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
    cmf_actuel      = round(cmf.iloc[-1], 4)
    vwap_actuel     = round(vwap_series.iloc[-1], 2)
    vol_actuel      = int(volume.iloc[-1])
    vol_moy_actuel  = vol_moy_20.iloc[-1]
    vol_ratio       = round(vol_actuel / vol_moy_actuel, 2) if vol_moy_actuel > 0 else 1.0

    bb_largeur  = bb_haute_actuel - bb_basse_actuel
    bb_position = round(
        (prix_actuel - bb_basse_actuel) / bb_largeur * 100, 1
    ) if bb_largeur > 0 else 50.0

    direction_bougie = 1.0 if prix_actuel >= open_actuel else -1.0

    # --- Scores continus ---
    s_rsi      = _score_rsi(rsi_actuel)
    s_macd     = _score_macd(macd_actuel, signal_actuel)
    s_bb       = _score_bb(bb_position)
    s_sma      = _score_sma(prix_actuel, sma20_actuel, sma50_actuel)
    s_atr      = _score_atr(atr_relatif)
    s_obv      = _score_obv(obv)
    s_cmf      = _score_cmf(cmf_actuel)
    s_vwap     = _score_vwap(prix_actuel, vwap_actuel)
    s_vol_ratio= _score_vol_ratio(vol_ratio, direction_bougie)

    # --- Score pondéré final (entre -1 et +1) ---
    score_brut = (
        s_macd      * POIDS["macd"]      +
        s_rsi       * POIDS["rsi"]       +
        s_bb        * POIDS["bb"]        +
        s_sma       * POIDS["sma"]       +
        s_atr       * POIDS["atr"]       +
        s_obv       * POIDS["obv"]       +
        s_cmf       * POIDS["cmf"]       +
        s_vwap      * POIDS["vwap"]      +
        s_vol_ratio * POIDS["vol_ratio"]
    )
    score_final = round(score_brut, 4)

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
        # Volume
        "obv":           round(obv.iloc[-1], 0),
        "cmf":           cmf_actuel,
        "vwap":          vwap_actuel,
        "vol_actuel":    vol_actuel,
        "vol_ratio":     vol_ratio,
        "scores": {
            "macd":      s_macd,
            "rsi":       s_rsi,
            "bb":        s_bb,
            "sma":       s_sma,
            "atr":       s_atr,
            "obv":       s_obv,
            "cmf":       s_cmf,
            "vwap":      s_vwap,
            "vol_ratio": s_vol_ratio,
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
    print(f"OBV           : {resultat['obv']}")
    print(f"CMF           : {resultat['cmf']}")
    print(f"VWAP (20j)    : {resultat['vwap']}")
    print(f"Vol ratio     : {resultat['vol_ratio']}x la moyenne")
    print(f"\n--- Scores continus ---")
    for k, v in resultat['scores'].items():
        print(f"{k:12} (×{POIDS[k]}) : {v}")
    print(f"\nScore final   : {resultat['score_final']}")
    print(f"Signal        : {resultat['signal']}")
