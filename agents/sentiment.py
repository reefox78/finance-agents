from transformers import pipeline
from data.market_data import get_news

finbert=pipeline("text-classification", 
                 model="ProsusAI/finbert", tokenizer="ProsusAI/finbert")

def analyze_sentiment(ticker: str, max_articles: int = 10) -> dict:
    """
    Analyse le sentiment des news d'une action avec FinBERT.
    Produit un score global et un signal.
    """
    news = get_news(ticker, max_articles=max_articles)

    if not news:
        return {
            "ticker":   ticker,
            "articles": 0,
            "positif":  0,
            "negatif":  0,
            "neutre":   0,
            "points":   0,
            "signal":   "NEUTRE",
        }

    titres = [article["titre"] for article in news if article["titre"] != "N/A"]

    resultats = finbert(titres, truncation=True, max_length=512)

    positif = 0
    negatif = 0
    neutre  = 0

    for r in resultats:
        label = r["label"].lower()
        if label == "positive":
            positif += 1
        elif label == "negative":
            negatif += 1
        else:
            neutre += 1

    total  = len(resultats)
    points = positif - negatif

    if points >= 2:
        signal = "ACHETER"
    elif points <= -2:
        signal = "VENDRE"
    else:
        signal = "NEUTRE"

    return {
        "ticker":   ticker,
        "articles": total,
        "positif":  positif,
        "negatif":  negatif,
        "neutre":   neutre,
        "points":   points,
        "signal":   signal,
    }


if __name__ == "__main__":
    print("Chargement de FinBERT (peut prendre quelques secondes)...")
    resultat = analyze_sentiment("AAPL")

    print(f"\n--- Analyse sentiment : {resultat['ticker']} ---")
    print(f"Articles analysés : {resultat['articles']}")
    print(f"Positif           : {resultat['positif']}")
    print(f"Négatif           : {resultat['negatif']}")
    print(f"Neutre            : {resultat['neutre']}")
    print(f"Points            : {resultat['points']}")
    print(f"Signal            : {resultat['signal']}")