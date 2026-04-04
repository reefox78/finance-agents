from data.trends_data import get_trends
from data.market_data import get_stock_info


def analyze_trends(ticker: str) -> dict:
    """
    Analyse les tendances Google Search pour un ticker.
    Une hausse des recherches précède souvent un mouvement de prix.
    """
    info = get_stock_info(ticker)
    nom  = info.get("nom", None)

    trends = get_trends(ticker, nom=nom)

    score_final = trends["score_tendance"]

    if score_final >= 0.5:
        signal = "ACHETER"
    elif score_final <= -0.5:
        signal = "VENDRE"
    else:
        signal = "NEUTRE"

    return {
        "ticker":         ticker,
        "tendance":       trends["tendance"],
        "score_final":    score_final,
        "variation":      trends["variation"],
        "moyenne":        trends["moyenne"],
        "ratio_tendance": trends["ratio_tendance"],
        "signal":         signal,
    }


if __name__ == "__main__":
    resultat = analyze_trends("AAPL")

    print(f"--- Agent Trends : {resultat['ticker']} ---")
    print(f"Tendance        : {resultat['tendance']}")
    print(f"Variation       : {resultat['variation']} %")
    print(f"Ratio tendance  : {resultat['ratio_tendance']}")
    print(f"Score final     : {resultat['score_final']}")
    print(f"Signal          : {resultat['signal']}")