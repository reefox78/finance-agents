import threading
import logging
import yfinance as yf
import pandas as pd
from datetime import datetime, date, timedelta
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache TTL + stale fallback
#   _TTL       : durée de vie normale du cache (30 min)
#   _STALE_TTL : durée de vie du stale (fallback 429 — 24 h)
#
# Sur une 429 :
#   → si données stale disponibles (< 24 h) : retour silencieux avec warning
#   → sinon : raise pour que l'agent retourne N/A
# ---------------------------------------------------------------------------
_TTL       = 1800   # 30 minutes
_STALE_TTL = 86400  # 24 heures

_cache_data:        dict = {}   # (ticker, period) → (ts, DataFrame)
_cache_info:        dict = {}   # ticker            → (ts, dict)
_cache_news:        dict = {}   # (ticker, n)        → (ts, list)
_cache_raw_info:    dict = {}   # ticker            → (ts, dict)   raw yf.info
_cache_earnings:    dict = {}   # ticker            → (ts, DataFrame)
_cache_download:    dict = {}   # (ticker, start, end) → (ts, DataFrame)

# Stale stores — gardent la dernière valeur connue (même expirée)
_stale_data:        dict = {}
_stale_info:        dict = {}
_stale_raw_info:    dict = {}
_stale_earnings:    dict = {}
_stale_download:    dict = {}

# Per-ticker locks — évite le thundering herd quand N threads demandent
# le même ticker simultanément
_ticker_locks:      dict = {}
_ticker_locks_lock  = threading.Lock()


def _get_ticker_lock(key: str) -> threading.Lock:
    with _ticker_locks_lock:
        if key not in _ticker_locks:
            _ticker_locks[key] = threading.Lock()
        return _ticker_locks[key]


# ── Helpers cache ─────────────────────────────────────────────────────────────

def _cache_get(store: dict, key):
    entry = store.get(key)
    if entry and (time.time() - entry[0]) < _TTL:
        return entry[1]
    return None


def _stale_get(store: dict, key):
    """Retourne la valeur stale si < 24 h, sinon None."""
    entry = store.get(key)
    if entry and (time.time() - entry[0]) < _STALE_TTL:
        return entry[1]
    return None


def _cache_set(store: dict, stale_store: dict | None, key, value):
    ts = time.time()
    store[key] = (ts, value)
    if stale_store is not None:
        stale_store[key] = (ts, value)


def _is_rate_limit(exc: Exception) -> bool:
    s = str(exc).lower()
    return "rate" in s or "429" in s or "too many" in s or "ratelimit" in s


# ── get_stock_data ────────────────────────────────────────────────────────────

def get_stock_data(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """Données historiques OHLCV avec cache 30 min + stale fallback 24 h."""
    key = (ticker, period)

    cached = _cache_get(_cache_data, key)
    if cached is not None:
        return cached

    lock = _get_ticker_lock(f"data:{key}")
    with lock:
        # Double-checked locking
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
                _cache_set(_cache_data, _stale_data, key, df)
                return df
            except ValueError:
                raise
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    # 429 après retries → stale fallback
                    stale = _stale_get(_stale_data, key)
                    if stale is not None:
                        logger.warning("429 yfinance %s history(%s) — données stale utilisées", ticker, period)
                        return stale
                raise

        raise RuntimeError(f"Impossible de récupérer les données pour {ticker} après 3 tentatives")


# ── get_stock_info ────────────────────────────────────────────────────────────

def get_stock_info(ticker: str) -> dict:
    """Infos fondamentales formatées (secteur, PER…) avec cache 30 min."""
    cached = _cache_get(_cache_info, ticker)
    if cached is not None:
        return cached

    lock = _get_ticker_lock(f"info:{ticker}")
    with lock:
        cached = _cache_get(_cache_info, ticker)
        if cached is not None:
            return cached

        for attempt in range(3):
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                result = {
                    "nom":           info.get("longName", "N/A"),
                    "secteur":       info.get("sector", "N/A"),
                    "industrie":     info.get("industry", "N/A"),
                    "capitalisation":info.get("marketCap", "N/A"),
                    "per":           info.get("trailingPE", "N/A"),
                    "dividende":     info.get("dividendYield", "N/A"),
                    "pays":          info.get("country", "N/A"),
                }
                _cache_set(_cache_info, _stale_info, ticker, result)
                return result
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    stale = _stale_get(_stale_info, ticker)
                    if stale is not None:
                        logger.warning("429 yfinance %s info — données stale utilisées", ticker)
                        return stale
                raise

        raise RuntimeError(f"Impossible de récupérer les infos pour {ticker} après 3 tentatives")


# ── get_ticker_raw_info ───────────────────────────────────────────────────────

def get_ticker_raw_info(ticker: str) -> dict:
    """
    Retourne le dict brut complet de yf.Ticker.info avec cache 30 min.

    Utilisé par :
      - short_interest_data.py  (shortPercentOfFloat, shortRatio, …)
      - sector_risk.py          (sector, quoteType)
    """
    cached = _cache_get(_cache_raw_info, ticker)
    if cached is not None:
        return cached

    lock = _get_ticker_lock(f"raw:{ticker}")
    with lock:
        cached = _cache_get(_cache_raw_info, ticker)
        if cached is not None:
            return cached

        for attempt in range(3):
            try:
                info = yf.Ticker(ticker).info
                _cache_set(_cache_raw_info, _stale_raw_info, ticker, info)
                return info
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    stale = _stale_get(_stale_raw_info, ticker)
                    if stale is not None:
                        logger.warning("429 yfinance %s raw_info — données stale utilisées", ticker)
                        return stale
                raise

        raise RuntimeError(f"Impossible de récupérer raw_info pour {ticker} après 3 tentatives")


# ── get_earnings_dates ────────────────────────────────────────────────────────

def get_earnings_dates(ticker: str) -> pd.DataFrame | None:
    """
    Retourne yf.Ticker.earnings_dates avec cache 30 min.

    Utilisé par earnings_data.py.
    """
    cached = _cache_get(_cache_earnings, ticker)
    if cached is not None:
        return cached

    lock = _get_ticker_lock(f"earn:{ticker}")
    with lock:
        cached = _cache_get(_cache_earnings, ticker)
        if cached is not None:
            return cached

        for attempt in range(3):
            try:
                df = yf.Ticker(ticker).earnings_dates
                _cache_set(_cache_earnings, _stale_earnings, ticker, df)
                return df
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    stale = _stale_get(_stale_earnings, ticker)
                    if stale is not None:
                        logger.warning("429 yfinance %s earnings_dates — données stale utilisées", ticker)
                        return stale
                raise

        raise RuntimeError(f"Impossible de récupérer earnings_dates pour {ticker} après 3 tentatives")


# ── get_yf_download_cached ────────────────────────────────────────────────────

def get_yf_download_cached(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    yf.download() avec cache 30 min.

    Clé = (ticker, start, end).
    Utilisé par sector_risk.py pour télécharger les drivers ETF/futures.
    """
    key = (ticker, start, end)
    cached = _cache_get(_cache_download, key)
    if cached is not None:
        return cached

    lock = _get_ticker_lock(f"dl:{key}")
    with lock:
        cached = _cache_get(_cache_download, key)
        if cached is not None:
            return cached

        for attempt in range(3):
            try:
                df = yf.download(ticker, start=start, end=end,
                                 progress=False, auto_adjust=True)
                _cache_set(_cache_download, _stale_download, key, df)
                return df
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    stale = _stale_get(_stale_download, key)
                    if stale is not None:
                        logger.warning("429 yfinance download %s — données stale utilisées", ticker)
                        return stale
                raise

        raise RuntimeError(f"Impossible de télécharger {ticker} après 3 tentatives")


# ── get_news ──────────────────────────────────────────────────────────────────

def get_news(ticker: str, max_articles: int = 10) -> list[dict]:
    """Dernières news avec cache 30 min."""
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
            if _is_rate_limit(e):
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
            break  # autres erreurs : on retourne []

    if not news:
        _cache_set(_cache_news, None, key, [])
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

    _cache_set(_cache_news, None, key, articles)
    return articles


# ── Test standalone ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    ticker = "AAPL"

    print(f"--- Données historiques : {ticker} ---")
    df = get_stock_data(ticker, period="1mo")
    print(df.tail(5))

    print(f"\n--- Infos fondamentales : {ticker} ---")
    info = get_stock_info(ticker)
    for cle, valeur in info.items():
        print(f"{cle:20} : {valeur}")

    print(f"\n--- Raw info (short interest fields) ---")
    raw = get_ticker_raw_info(ticker)
    for field in ["shortPercentOfFloat", "shortRatio", "sharesShort", "sector"]:
        print(f"{field:30} : {raw.get(field)}")

    print(f"\n--- Dernières news : {ticker} ---")
    news = get_news(ticker)
    for article in news:
        print(f"[{article['date']}] {article['titre']} ({article['source']})")
