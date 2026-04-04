import yfinance as yf
import pandas as pd
from datetime import datetime



def get_stock_data(ticker:str,period:str ="3mo") -> pd.DataFrame:
    """
    Récupère les données historiques d'une action.
    
    ticker : symbole boursier (ex: "AAPL", "MSFT", "MC.PA")
    period : 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y
    """
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)

    if df.empty:
          raise ValueError(f"Aucune donnée trouvée par {ticker}")
         
    # On garde uniquement les colonnes utiles
    df = df[["Open","High","Low","Close","Volume"]]
    df.index = pd.to_datetime(df.index)
    return df

def get_stock_info(ticker:str)->dict:
    """
    Récupère les infos fondamentales d'une action.
    ex: secteur, PER, capitalisation, dividendes...
    """
    stock = yf.Ticker(ticker)
    info = stock.info

    return {
        "nom": info.get("longName", "N/A"),
        "secteur": info.get("sector", "N/A"),
        "industrie": info.get("industry", "N/A"),
        "capitalisation": info.get("marketCap", "N/A"),
        "per": info.get("trailingPE", "N/A"),
        "dividende": info.get("dividendYield", "N/A"),
        "pays": info.get("country", "N/A"),
    }

def get_news(ticker: str, max_articles: int = 10) -> list[dict]:
    """
    Récupère les dernières news liées à une action.
    
    ticker       : symbole boursier (ex: "AAPL")
    max_articles : nombre max d'articles à récupérer
    """
    stock = yf.Ticker(ticker)
    news = stock.news

    if not news:
        return []

    articles = []
    for article in news[:max_articles]:
        content = article.get("content", {})
        articles.append({
            "titre":  content.get("title", "N/A"),
            "date":   content.get("pubDate", "N/A"),
            "source": content.get("provider", {}).get("displayName", "N/A"),
            "url":    content.get("canonicalUrl", {}).get("url", "N/A"),
        })

    return articles


if __name__ == "__main__":
    ticker = "AAPL"

    print(f"--- Données historiques : {ticker} ---")
    df = get_stock_data(ticker, period="1mo")
    print(df.tail(5))

    print(f"\n--- Infos fondamentales : {ticker} ---")
    info = get_stock_info(ticker)
    for cle, valeur in info.items():
        print(f"{cle:20} : {valeur}")

    print(f"\n--- Dernières news : {ticker} ---")
    news = get_news(ticker)
    for article in news:
        print(f"[{article['date']}] {article['titre']} ({article['source']})")

