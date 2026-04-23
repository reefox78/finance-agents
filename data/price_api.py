"""
price_api.py — Prix temps réel et historique OHLCV via Twelve Data + Finnhub.

Cascade :
  get_current_price()  → Twelve Data → Finnhub → yfinance (cache)
  get_ohlcv_td()       → Twelve Data → None (l'appelant tombera sur yfinance)

Limites gratuites :
  Twelve Data : 800 req/jour, 8 req/min
  Finnhub     : 60 req/min (pas de limite quotidienne documentée)
"""

import os
import time
import logging
import requests
import pandas as pd
from datetime import date

logger = logging.getLogger(__name__)

# ── Clés ──────────────────────────────────────────────────────────────────────
_TD_KEY      = os.getenv("TWELVEDATA_API_KEY", "")
_FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

_TD_BASE      = "https://api.twelvedata.com"
_FINNHUB_BASE = "https://finnhub.io/api/v1"

_TIMEOUT = 6  # secondes — ne pas bloquer l'app si l'API est lente

# ── Compteur Twelve Data (800 req/jour) ───────────────────────────────────────
_td_calls_today = 0
_td_reset_date  = ""
_TD_DAILY_LIMIT = 790  # marge de sécurité de 10 appels

# Map period yfinance → outputsize Twelve Data
_PERIOD_TO_SIZE = {
    "1d":  2,
    "5d":  5,
    "1mo": 23,
    "3mo": 65,
    "6mo": 130,
    "1y":  252,
    "2y":  504,
    "5y":  1260,
}


def _td_budget_ok() -> bool:
    """Retourne True si on n'a pas encore atteint la limite quotidienne TD."""
    global _td_calls_today, _td_reset_date
    today = date.today().isoformat()
    if _td_reset_date != today:
        _td_calls_today = 0
        _td_reset_date  = today
    return _td_calls_today < _TD_DAILY_LIMIT


def _td_increment():
    global _td_calls_today
    _td_calls_today += 1


# ── Twelve Data — prix actuel ─────────────────────────────────────────────────

def _price_from_td(ticker: str) -> float | None:
    """Prix actuel via Twelve Data /price."""
    if not _TD_KEY or not _td_budget_ok():
        return None
    try:
        r = requests.get(
            f"{_TD_BASE}/price",
            params={"symbol": ticker, "apikey": _TD_KEY},
            timeout=_TIMEOUT,
        )
        _td_increment()
        if r.status_code == 200:
            data = r.json()
            if "price" in data:
                return float(data["price"])
        logger.debug("TD /price %s → %s %s", ticker, r.status_code, r.text[:120])
    except Exception as e:
        logger.debug("TD /price %s exception: %s", ticker, e)
    return None


# ── Finnhub — prix actuel ─────────────────────────────────────────────────────

def _price_from_finnhub(ticker: str) -> float | None:
    """Prix actuel via Finnhub /quote (champ 'c' = current price)."""
    if not _FINNHUB_KEY:
        return None
    try:
        r = requests.get(
            f"{_FINNHUB_BASE}/quote",
            params={"symbol": ticker, "token": _FINNHUB_KEY},
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            price = data.get("c")
            if price and price > 0:
                return float(price)
        logger.debug("Finnhub /quote %s → %s %s", ticker, r.status_code, r.text[:120])
    except Exception as e:
        logger.debug("Finnhub /quote %s exception: %s", ticker, e)
    return None


# ── yfinance — prix actuel (dernier recours) ──────────────────────────────────

def _price_from_yf(ticker: str) -> float | None:
    """Prix actuel via yfinance (cache mémoire/disque existant)."""
    try:
        # Import ici pour éviter la dépendance circulaire
        from data.market_data import get_ticker_raw_info, get_stock_data
        info = get_ticker_raw_info(ticker)
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price:
            return float(price)
        # Dernier recours : dernière clôture
        df = get_stock_data(ticker, "1d")
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except Exception as e:
        logger.debug("yfinance price %s exception: %s", ticker, e)
    return None


# ── API publique — prix actuel ─────────────────────────────────────────────────

def get_current_price(ticker: str) -> float | None:
    """
    Prix actuel en cascade : Twelve Data → Finnhub → yfinance.
    Retourne None si aucune source ne répond.
    """
    price = _price_from_td(ticker)
    if price is not None:
        logger.debug("Prix %s depuis Twelve Data : %.4f", ticker, price)
        return price

    price = _price_from_finnhub(ticker)
    if price is not None:
        logger.debug("Prix %s depuis Finnhub : %.4f", ticker, price)
        return price

    price = _price_from_yf(ticker)
    if price is not None:
        logger.debug("Prix %s depuis yfinance (fallback) : %.4f", ticker, price)
        return price

    logger.warning("Impossible d'obtenir le prix de %s (toutes sources épuisées)", ticker)
    return None


# ── Twelve Data — historique OHLCV ───────────────────────────────────────────

def get_ohlcv_td(ticker: str, period: str = "3mo") -> pd.DataFrame | None:
    """
    Historique OHLCV journalier via Twelve Data /time_series.
    Retourne un DataFrame avec colonnes Open/High/Low/Close/Volume,
    index DatetimeIndex trié ASC — ou None si indisponible.
    """
    if not _TD_KEY or not _td_budget_ok():
        return None

    outputsize = _PERIOD_TO_SIZE.get(period, 65)

    try:
        r = requests.get(
            f"{_TD_BASE}/time_series",
            params={
                "symbol":     ticker,
                "interval":   "1day",
                "outputsize": outputsize,
                "apikey":     _TD_KEY,
            },
            timeout=_TIMEOUT,
        )
        _td_increment()

        if r.status_code != 200:
            logger.debug("TD /time_series %s → HTTP %s", ticker, r.status_code)
            return None

        data = r.json()

        # Erreur API (ticker inconnu, quota dépassé, etc.)
        if data.get("status") == "error" or "values" not in data:
            logger.debug("TD /time_series %s → %s", ticker, data.get("message", data))
            return None

        values = data["values"]
        if not values:
            return None

        rows = []
        for v in values:
            rows.append({
                "Date":   pd.to_datetime(v["datetime"]),
                "Open":   float(v["open"]),
                "High":   float(v["high"]),
                "Low":    float(v["low"]),
                "Close":  float(v["close"]),
                "Volume": int(float(v.get("volume", 0))),
            })

        df = pd.DataFrame(rows).set_index("Date").sort_index()
        logger.debug("TD /time_series %s → %d lignes OK", ticker, len(df))
        return df

    except Exception as e:
        logger.debug("TD /time_series %s exception: %s", ticker, e)
        return None


# ── Finnhub — quote complet (OHLC du jour) ───────────────────────────────────

def get_quote_finnhub(ticker: str) -> dict | None:
    """
    Quote complet Finnhub : current, high, low, open, prev_close, change_pct.
    Utile pour afficher la variation du jour sans consommer le budget TD.
    """
    if not _FINNHUB_KEY:
        return None
    try:
        r = requests.get(
            f"{_FINNHUB_BASE}/quote",
            params={"symbol": ticker, "token": _FINNHUB_KEY},
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            d = r.json()
            if d.get("c", 0) > 0:
                return {
                    "current":    d["c"],
                    "high":       d["h"],
                    "low":        d["l"],
                    "open":       d["o"],
                    "prev_close": d["pc"],
                    "change_pct": round((d["c"] - d["pc"]) / d["pc"] * 100, 2) if d["pc"] else None,
                }
    except Exception as e:
        logger.debug("Finnhub quote_full %s exception: %s", ticker, e)
    return None


# ── Diagnostique ──────────────────────────────────────────────────────────────

def api_status() -> dict:
    """Retourne l'état des APIs (budget TD restant, clés configurées)."""
    return {
        "twelvedata": {
            "key_configured": bool(_TD_KEY),
            "calls_today":    _td_calls_today,
            "remaining":      max(0, _TD_DAILY_LIMIT - _td_calls_today),
            "reset_date":     _td_reset_date,
        },
        "finnhub": {
            "key_configured": bool(_FINNHUB_KEY),
        },
    }
