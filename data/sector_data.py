import yfinance as yf
import pandas as pd

SECTEURS = {
    "Technology":           ["MSFT", "GOOGL", "META", "NVDA", "AMZN"],
    "Financial Services":   ["JPM", "BAC", "GS", "MS", "WFC"],
    "Healthcare":           ["JNJ", "PFE", "UNH", "MRK", "ABT"],
    "Energy":               ["XOM", "CVX", "COP", "SLB", "EOG"],
    "Consumer Defensive":   ["MCD", "KO", "PG", "WMT", "COST"],
    "Industrials":          ["BA", "CAT", "HON", "UPS", "GE"],
    "Communication Services": ["DIS", "NFLX", "T", "VZ", "CMCSA"],
}


def get_sector_peers(secteur: str) -> list[str]:
    """Retourne la liste des tickers de référence pour un secteur."""
    return SECTEURS.get(secteur, [])


def get_sector_averages(secteur: str) -> dict:
    """
    Calcule les moyennes fondamentales et de risque
    des entreprises de référence du secteur.
    """
    peers = get_sector_peers(secteur)

    if not peers:
        return {}

    pers        = []
    dividendes  = []
    volatilites = []
    caps        = []

    for ticker in peers:
        try:
            stock = yf.Ticker(ticker)
            info  = stock.info

            per = info.get("trailingPE")
            div = info.get("dividendYield")
            cap = info.get("marketCap")

            if per and per > 0:
                pers.append(per)
            if div and div > 0:
                dividendes.append(div)
            if cap and cap > 0:
                caps.append(cap)

            # Volatilité sur 3 mois
            hist = stock.history(period="3mo")
            if not hist.empty:
                rendements  = hist["Close"].pct_change().dropna()
                volatilite  = rendements.std() * (252 ** 0.5) * 100
                volatilites.append(volatilite)

        except Exception:
            continue

    return {
        "secteur":            secteur,
        "peers":              peers,
        "per_moyen":          round(sum(pers) / len(pers), 2)               if pers        else None,
        "dividende_moyen":    round(sum(dividendes) / len(dividendes), 4)   if dividendes  else None,
        "volatilite_moyenne": round(sum(volatilites) / len(volatilites), 2) if volatilites else None,
        "cap_moyenne":        round(sum(caps) / len(caps), 0)               if caps        else None,
    }


if __name__ == "__main__":
    print("Récupération des moyennes secteur Technology...")
    moyennes = get_sector_averages("Technology")

    print(f"\n--- Moyennes secteur : {moyennes['secteur']} ---")
    print(f"Peers             : {moyennes['peers']}")
    print(f"PER moyen         : {moyennes['per_moyen']}")
    print(f"Dividende moyen   : {moyennes['dividende_moyen']}")
    print(f"Volatilité moyenne: {moyennes['volatilite_moyenne']} %")
    print(f"Cap moyenne       : {moyennes['cap_moyenne']:,.0f} $")