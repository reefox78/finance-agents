"""
Analyse sentiment via Groq/LLaMA — remplace FinBERT (trop lourd pour Streamlit Cloud).
Groq est déjà utilisé par l'orchestrateur, 0 MB de modèle local.
"""
import os
from groq import Groq
from dotenv import load_dotenv
from data.market_data import get_news

load_dotenv("config/.env")

_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def analyze_sentiment(ticker: str, max_articles: int = 10) -> dict:
    """
    Analyse le sentiment des news d'une action via Groq (LLaMA 3).
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

    titres = [a["titre"] for a in news if a["titre"] not in ("N/A", "")]
    if not titres:
        return {
            "ticker":   ticker,
            "articles": 0,
            "positif":  0,
            "negatif":  0,
            "neutre":   0,
            "points":   0,
            "signal":   "NEUTRE",
        }

    # Prompt compact : classification en masse
    prompt = (
        f"Classify each news headline about {ticker} as POSITIVE, NEGATIVE, or NEUTRAL.\n"
        f"Reply ONLY with one label per line, in the same order.\n\n"
        + "\n".join(f"{i+1}. {t}" for i, t in enumerate(titres))
    )

    try:
        response = _get_client().chat.completions.create(
            model="llama-3.1-8b-instant",   # modèle rapide et économique
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=len(titres) * 5 + 20,
        )
        raw = response.choices[0].message.content or ""
        lines = [l.strip().upper() for l in raw.strip().splitlines() if l.strip()]
    except Exception:
        lines = []

    positif = sum(1 for l in lines if "POSITIVE" in l or l == "POSITIVE")
    negatif = sum(1 for l in lines if "NEGATIVE" in l or l == "NEGATIVE")
    neutre  = sum(1 for l in lines if "NEUTRAL"  in l or l == "NEUTRAL")

    # Si pas de réponse valide → neutre
    if positif + negatif + neutre == 0:
        neutre = len(titres)

    points = positif - negatif

    if points >= 2:
        signal = "ACHETER"
    elif points <= -2:
        signal = "VENDRE"
    else:
        signal = "NEUTRE"

    return {
        "ticker":   ticker,
        "articles": len(titres),
        "positif":  positif,
        "negatif":  negatif,
        "neutre":   neutre,
        "points":   points,
        "signal":   signal,
    }


if __name__ == "__main__":
    print("Test sentiment AAPL via Groq...")
    r = analyze_sentiment("AAPL")
    print(f"Articles : {r['articles']}")
    print(f"Positif / Négatif / Neutre : {r['positif']} / {r['negatif']} / {r['neutre']}")
    print(f"Signal : {r['signal']}")
