import threading
import logging
import json
import pickle
import os
import yfinance as yf
import pandas as pd
from pathlib import Path
from io import StringIO
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache à deux niveaux :
#
#   Niveau 1 — mémoire (rapide, TTL 30 min, perdu au redémarrage)
#   Niveau 2 — disque  (lent, TTL 7 jours, SURVIT aux redémarrages)
#
# Logique sur 429 :
#   1. Cherche dans stale mémoire (< 24h)
#   2. Cherche dans cache disque   (< 7 jours)
#   3. Si rien → raise → l'agent retourne N/A
# ---------------------------------------------------------------------------
_TTL            = 1800        # 30 min  — TTL mémoire normale
_STALE_TTL      = 86400       # 24 h    — stale mémoire après expiration
_DISK_STALE_TTL = 7 * 86400   # 7 jours — stale disque (survit aux redémarrages)

# ── Cache disque ──────────────────────────────────────────────────────────────
_CACHE_DIR = Path(__file__).parent.parent / "cache" / "yf"


def _safe_key(key) -> str:
    """Transforme une clé (str ou tuple) en nom de fichier sûr."""
    s = str(key)
    for c in r'\/:*?"<>|(),' :
        s = s.replace(c, '_')
    return s[:180]  # limite longueur


def _disk_get(key) -> object | None:
    """Lit un objet sérialisé en JSON depuis le cache disque."""
    try:
        path = _CACHE_DIR / f"{_safe_key(key)}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
        if time.time() - entry["ts"] > _DISK_STALE_TTL:
            return None
        return entry["data"]
    except Exception:
        return None


def _disk_set(key, data: object) -> None:
    """Écrit un objet JSON-sérialisable dans le cache disque."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _CACHE_DIR / f"{_safe_key(key)}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "data": data}, f, default=str)
    except Exception:
        pass


def _disk_get_df(key) -> pd.DataFrame | None:
    """Lit un DataFrame sérialisé depuis le cache disque."""
    try:
        path = _CACHE_DIR / f"{_safe_key(key)}_df.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
        if time.time() - entry["ts"] > _DISK_STALE_TTL:
            return None
        df = pd.read_json(StringIO(entry["data"]), orient="split")
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return None


def _disk_set_df(key, df: pd.DataFrame) -> None:
    """Écrit un DataFrame JSON dans le cache disque."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _CACHE_DIR / f"{_safe_key(key)}_df.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "data": df.to_json(orient="split", date_format="iso")}, f)
    except Exception:
        pass


# ── Cache mémoire ─────────────────────────────────────────────────────────────
_cache_data:     dict = {}
_cache_info:     dict = {}
_cache_news:     dict = {}
_cache_raw_info: dict = {}
_cache_earnings: dict = {}
_cache_download: dict = {}

_stale_data:     dict = {}
_stale_info:     dict = {}
_stale_raw_info: dict = {}
_stale_earnings: dict = {}
_stale_download: dict = {}

# Per-ticker locks — évite le thundering herd
_ticker_locks:     dict = {}
_ticker_locks_lock = threading.Lock()


def _get_ticker_lock(key: str) -> threading.Lock:
    with _ticker_locks_lock:
        if key not in _ticker_locks:
            _ticker_locks[key] = threading.Lock()
        return _ticker_locks[key]


# ── Helpers cache mémoire ─────────────────────────────────────────────────────

def _cache_get(store: dict, key):
    entry = store.get(key)
    if entry and (time.time() - entry[0]) < _TTL:
        return entry[1]
    return None


def _stale_get(store: dict, key):
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


def _fallback(stale_store, disk_key, label: str, is_df=False):
    """Cherche un fallback stale mémoire puis disque. Log un warning si trouvé."""
    # 1. Stale mémoire
    stale = _stale_get(stale_store, disk_key)
    if stale is not None:
        logger.warning("429 yfinance %s — stale mémoire utilisé", label)
        return stale
    # 2. Cache disque
    cached = _disk_get_df(disk_key) if is_df else _disk_get(disk_key)
    if cached is not None:
        logger.warning("429 yfinance %s — cache DISQUE utilisé (survie redémarrage)", label)
        return cached
    return None


# ── get_stock_data ────────────────────────────────────────────────────────────

def get_stock_data(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """Données historiques OHLCV — cache mémoire 30 min + disque 7 jours."""
    key = (ticker, period)

    cached = _cache_get(_cache_data, key)
    if cached is not None:
        return cached

    lock = _get_ticker_lock(f"data:{key}")
    with lock:
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
                _disk_set_df(key, df)
                return df
            except ValueError:
                raise
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    fb = _fallback(_stale_data, key, f"{ticker} history({period})", is_df=True)
                    if fb is not None:
                        return fb
                raise

        raise RuntimeError(f"Impossible de récupérer les données pour {ticker} après 3 tentatives")


# ── get_stock_info ────────────────────────────────────────────────────────────

def get_stock_info(ticker: str) -> dict:
    """Infos fondamentales formatées — cache mémoire 30 min + disque 7 jours."""
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
                    "nom":            info.get("longName", "N/A"),
                    "secteur":        info.get("sector", "N/A"),
                    "industrie":      info.get("industry", "N/A"),
                    "capitalisation": info.get("marketCap", "N/A"),
                    "per":            info.get("trailingPE", "N/A"),
                    "dividende":      info.get("dividendYield", "N/A"),
                    "pays":           info.get("country", "N/A"),
                }
                _cache_set(_cache_info, _stale_info, ticker, result)
                _disk_set(f"info_{ticker}", result)
                return result
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    fb = _fallback(_stale_info, f"info_{ticker}", f"{ticker} info")
                    if fb is not None:
                        return fb
                raise

        raise RuntimeError(f"Impossible de récupérer les infos pour {ticker} après 3 tentatives")


# ── get_ticker_raw_info ───────────────────────────────────────────────────────

def get_ticker_raw_info(ticker: str) -> dict:
    """Dict brut complet yf.Ticker.info — cache mémoire 30 min + disque 7 jours."""
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
                _disk_set(f"raw_{ticker}", info)
                return info
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    fb = _fallback(_stale_raw_info, f"raw_{ticker}", f"{ticker} raw_info")
                    if fb is not None:
                        return fb
                raise

        raise RuntimeError(f"Impossible de récupérer raw_info pour {ticker} après 3 tentatives")


# ── get_earnings_dates ────────────────────────────────────────────────────────

def get_earnings_dates(ticker: str) -> pd.DataFrame | None:
    """earnings_dates — cache mémoire 30 min + disque 7 jours."""
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
                if df is not None and not df.empty:
                    _disk_set_df(f"earn_{ticker}", df)
                return df
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    fb = _fallback(_stale_earnings, f"earn_{ticker}", f"{ticker} earnings_dates", is_df=True)
                    if fb is not None:
                        return fb
                raise

        raise RuntimeError(f"Impossible de récupérer earnings_dates pour {ticker} après 3 tentatives")


# ── get_yf_download_cached ────────────────────────────────────────────────────

def get_yf_download_cached(ticker: str, start: str, end: str) -> pd.DataFrame:
    """yf.download() — cache mémoire 30 min + disque 7 jours."""
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
                _disk_set_df(f"dl_{_safe_key(key)}", df)
                return df
            except Exception as e:
                if _is_rate_limit(e):
                    if attempt < 2:
                        time.sleep(5 * (attempt + 1))
                        continue
                    fb = _fallback(_stale_download, f"dl_{_safe_key(key)}",
                                   f"download {ticker}", is_df=True)
                    if fb is not None:
                        return fb
                raise

        raise RuntimeError(f"Impossible de télécharger {ticker} après 3 tentatives")


# ── get_news ──────────────────────────────────────────────────────────────────

def get_news(ticker: str, max_articles: int = 10) -> list[dict]:
    """Dernières news — cache mémoire 30 min."""
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
            break

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
