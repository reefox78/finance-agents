import pandas as pd
from data.market_data import get_stock_data, get_stock_info
from data.sector_data import get_sector_averages


def _score_volatilite(vol: float, vol_secteur: float) -> float:
    """Score continu basé sur la volatilité vs secteur."""
    if not vol_secteur:
        if vol < 15:
            return 1.0
        elif vol < 25:
            return 0.5
        elif vol < 40:
            return 0.0
        else:
            return -1.0

    ratio = vol / vol_secteur
    if ratio < 0.60:
        return 1.0
    elif ratio < 0.80:
        return 0.5
    elif ratio < 1.10:
        return 0.0
    elif ratio < 1.30:
        return -0.5
    else:
        return -1.0


def _score_drawdown(drawdown: float) -> float:
    """Score continu basé sur le drawdown maximum."""
    if drawdown > -5:
        return 1.0
    elif drawdown > -10:
        return 0.5
    elif drawdown > -20:
        return 0.0
    elif drawdown > -30:
        return -0.5
    else:
        return -1.0


def _score_sharpe(rendements: pd.Series) -> float:
    """
    Score basé sur le ratio de Sharpe simplifié.
    Rendement moyen / volatilité → mesure rendement ajusté au risque.
    """
    if rendements.std() == 0:
        return 0.0
    sharpe = (rendements.mean() / rendements.std()) * (252 ** 0.5)
    if sharpe > 1.5:
        return 1.0
    elif sharpe > 0.5:
        return 0.5
    elif sharpe > 0:
        return 0.0
    elif sharpe > -0.5:
        return -0.5
    else:
        return -1.0


POIDS = {
    "volatilite": 0.40,
    "drawdown":   0.35,
    "sharpe":     0.25,
}


def analyze_risk(ticker: str, period: str = "3mo") -> dict:
    """
    Analyse du risque avec scores continus.
    Intègre volatilité vs secteur, drawdown et ratio de Sharpe.
    """
    df    = get_stock_data(ticker, period=period)
    close = df["Close"]
    info  = get_stock_info(ticker)

    secteur     = info.get("secteur", "N/A")
    moyennes    = get_sector_averages(secteur) if secteur != "N/A" else {}
    vol_secteur = moyennes.get("volatilite_moyenne")

    rendements   = close.pct_change().dropna()
    volatilite   = round(rendements.std() * (252 ** 0.5) * 100, 2)
    sommet       = close.cummax()
    drawdown     = ((close - sommet) / sommet * 100)
    drawdown_max = round(drawdown.min(), 2)

    s_vol     = _score_volatilite(volatilite, vol_secteur)
    s_dd      = _score_drawdown(drawdown_max)
    s_sharpe  = _score_sharpe(rendements)

    score_final = round(
        s_vol    * POIDS["volatilite"] +
        s_dd     * POIDS["drawdown"] +
        s_sharpe * POIDS["sharpe"],
        4
    )

    if score_final >= 0.25:
        risque = "FAIBLE"
    elif score_final >= -0.25:
        risque = "MODERE"
    else:
        risque = "ELEVE"

    # Multiplicateur pour le scoring global
    if risque == "FAIBLE":
        multiplicateur = 1.10
    elif risque == "MODERE":
        multiplicateur = 1.00
    else:
        multiplicateur = 0.75

    return {
        "ticker":              ticker,
        "volatilite":          volatilite,
        "volatilite_secteur":  vol_secteur,
        "drawdown_max":        drawdown_max,
        "scores": {
            "volatilite": s_vol,
            "drawdown":   s_dd,
            "sharpe":     s_sharpe,
        },
        "score_final":    score_final,
        "risque":         risque,
        "multiplicateur": multiplicateur,
    }


if __name__ == "__main__":
    resultat = analyze_risk("AAPL")

    print(f"--- Analyse risque : {resultat['ticker']} ---")
    print(f"Volatilité             : {resultat['volatilite']} %")
    print(f"Volatilité moy secteur : {resultat['volatilite_secteur']} %")
    print(f"Drawdown maximum       : {resultat['drawdown_max']} %")
    print(f"\n--- Scores continus ---")
    print(f"Volatilité (×{POIDS['volatilite']}) : {resultat['scores']['volatilite']}")
    print(f"Drawdown   (×{POIDS['drawdown']})  : {resultat['scores']['drawdown']}")
    print(f"Sharpe     (×{POIDS['sharpe']})  : {resultat['scores']['sharpe']}")
    print(f"\nScore final      : {resultat['score_final']}")
    print(f"Niveau de risque : {resultat['risque']}")
    print(f"Multiplicateur   : {resultat['multiplicateur']}")