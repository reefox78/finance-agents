from data.insider_data import get_insider_trading


def analyze_insider(ticker: str) -> dict:
    """
    Analyse les transactions des dirigeants.
    Les insiders achètent pour une seule raison : ils pensent que ça va monter.
    Ils vendent pour plein de raisons (diversification, impôts...) mais en masse c'est un signal.
    """
    data = get_insider_trading(ticker)

    return {
        "ticker":       ticker,
        "nb_achats":    data["nb_achats"],
        "nb_ventes":    data["nb_ventes"],
        "total_achat":  data["total_achat"],
        "total_vente":  data["total_vente"],
        "ratio":        data["ratio"],
        "transactions": data["transactions"],
        "score_final":  data["score_final"],
        "signal":       data["signal"],
    }


if __name__ == "__main__":
    resultat = analyze_insider("AAPL")

    print(f"--- Agent Insider : {resultat['ticker']} ---")
    print(f"Achats  : {resultat['nb_achats']} ({resultat['total_achat']:,} $)")
    print(f"Ventes  : {resultat['nb_ventes']} ({resultat['total_vente']:,} $)")
    print(f"Ratio   : {resultat['ratio']}")
    print(f"Score   : {resultat['score_final']}")
    print(f"Signal  : {resultat['signal']}")