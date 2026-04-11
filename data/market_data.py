import yfinance as yf
import pandas as pd
from datetime import datetime
import time

# ---------------------------------------------------------------------------
# Cache TTL simple — évite les appels yfinance redondants dans un même run
# (ex: technical + risk + fundamental + trends appellent tous yfinance pour
#  le même ticker → Yahoo Finance rate-limit 429)
# ---------------------------------------------------------------------------
_TTL = 300  # secondes
_cache_data: dict = {}   # key: (ticker, period) → (timestamp, DataFrame)
_cache_info: dict = {}   # key: ticker           → (timestamp, dict)
_cache_news: dict = {}   # key: (ticker, n)      → (timestamp, list)


def _cache_get(store: dict, key):
    entry = store.get(key)
    if entry and (time.time() - entry[0]) < _TTL:
        return entry[1]
    return None


def _cache_set(store: dict, key, value):
    store[key] = (time.time(), value)


def _yf_ticker_with_retry(ticker: str, max_retries: int = 3) -> yf.Ticker:
    """Crée un objet Ticker yfinance avec retry si rate-limitée."""
    for attempt in range(max_retries):
        try:
            t = yf.Ticker(ticker)
            return t
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


def get_stock_data(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """
    Récupère les données historiques d'une action.

    ticker : symbole boursier (ex: "AAPL", "MSFT", "MC.PA")
    period : 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y
    """
    key = (ticker, period)
    cached = _cache_get(_cache_data, key)
    if cached is not None:
        return cached

    for attempt in range(3):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            if df.empty:
                raise ValueError(f"Aucune donnée trouvée pour {ticker}")
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df.index = pd.to_datetime(df.index)
            _cache_set(_cache_data, key, df)
            return df
        except ValueError:
            raise
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e) or "too many" in str(e).lower():
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
            raise

    raise RuntimeError(f"Impossible de récupérer les données pour {ticker} après 3 tentatives")


def get_stock_info(ticker: str) -> dict:
    """
    Récupère les infos fondamentales d'une action.
    ex: secteur, PER, capitalisation, dividendes...
    """
    cached = _cache_get(_cache_info, ticker)
    if cached is not None:
        return cached

    for attempt in range(3):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            result = {
                "nom": info.get("longName", "N/A"),
                "secteur": info.get("sector", "N/A"),
                "industrie": info.get("industry", "N/A"),
                "capitalisation": info.get("marketCap", "N/A"),
                "per": info.get("trailingPE", "N/A"),
                "dividende": info.get("dividendYield", "N/A"),
                "pays": info.get("country", "N/A"),
            }
            _cache_set(_cache_info, ticker, result)
            return result
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e) or "too many" in str(e).lower():
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
            raise

    raise RuntimeError(f"Impossible de récupérer les infos pour {ticker} après 3 tentatives")


def get_news(ticker: str, max_articles: int = 10) -> list[dict]:
    """
    Récupère les dernières news liées à une action.

    ticker       : symbole boursier (ex: "AAPL")
    max_articles : nombre max d'articles à récupérer
    """
    key = (ticker, max_articles)
    cached = _cache_get(_cache_news, key)
    if cached is not None:
        return cached

    news = []
    for attempt in range(3):
        try:
            stock = yf.Ticker(ticker)
            news = stock.news or []
            break
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e) or "too many" in str(e).lower():
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
            break  # autres erreurs : on retourne []

    if not news:
        _cache_set(_cache_news, key, [])
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

    _cache_set(_cache_news, key, articles)
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

