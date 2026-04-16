"""
Calendrier économique — événements macro de la semaine.

Sources (par ordre de priorité) :
  1. FRED release calendar (clé API déjà configurée — fiable depuis serveur)
  2. Forex Factory JSON (optionnel — souvent rate-limité depuis serveur cloud)

Endpoints :
  GET /api/calendar/week    → 14 prochains jours
  GET /api/calendar/today   → HIGH/MEDIUM du jour (bannière Analyse)
  GET /api/calendar/status  → diagnostic (public, sans auth)
  GET /api/calendar/earnings?ticker= → prochaine date résultats
"""
import logging
import os
import time
from datetime import datetime, date, timedelta

import pytz
import requests as _req
from fastapi import APIRouter, Query

from api.deps import CurrentUser

logger = logging.getLogger(__name__)
router  = APIRouter()

_FF_THIS_WEEK = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_FF_NEXT_WEEK = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"
_TIMEOUT      = 10.0
_PARIS        = pytz.timezone("Europe/Paris")

# Cache en mémoire 15 min (pour rafraîchir les valeurs réelles publiées dans la journée)
_CACHE: dict = {"data": [], "ts": 0.0, "source": "none"}
_CACHE_TTL   = 900

_FLAGS: dict[str, str] = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "CAD": "🇨🇦", "AUD": "🇦🇺", "NZD": "🇳🇿", "CHF": "🇨🇭",
    "CNY": "🇨🇳", "ALL": "🌐",
}

# Releases FRED importantes (impact estimé)
_FRED_HIGH = {
    "Employment Situation", "Consumer Price Index", "Gross Domestic Product",
    "FOMC", "Federal Open Market Committee", "Personal Income and Outlays",
    "Producer Price Index", "Retail Sales", "Industrial Production",
    "Consumer Confidence Index", "ISM Manufacturing", "Trade Balance",
    "Housing Starts", "Durable Goods Orders", "Unemployment Insurance",
}
_FRED_MEDIUM = {
    "Business Inventories", "Factory Orders", "Wholesale Trade",
    "New Residential Sales", "Existing Home Sales", "Construction Spending",
    "Personal Consumption Expenditures", "Import and Export Price Indexes",
    "Job Openings and Labor Turnover", "ADP Employment Report",
}


# ---------------------------------------------------------------------------
# Source 1 : FRED release calendar (source principale)
# ---------------------------------------------------------------------------

def _get_fred_events(days: int = 14) -> list[dict]:
    """Charge les releases FRED des prochains jours."""
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        logger.warning("FRED_API_KEY non définie — source principale indisponible")
        return []
    try:
        today  = date.today()
        cutoff = today + timedelta(days=days)
        url = (
            "https://api.stlouisfed.org/fred/releases/dates"
            f"?api_key={api_key}"
            f"&realtime_start={today}&realtime_end={cutoff}"
            "&sort_order=asc&file_type=json&limit=500"
        )
        resp = _req.get(url, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("release_dates", [])
        logger.info("FRED OK: %d releases", len(items))

        evts = []
        for item in items:
            name = item.get("release_name", "")
            d    = item.get("date", "")
            if not d or not name:
                continue
            if any(k in name for k in _FRED_HIGH):
                impact = "High"
            elif any(k in name for k in _FRED_MEDIUM):
                impact = "Medium"
            else:
                impact = "Low"
            evts.append({
                "title":    name,
                "country":  "USD",
                "flag":     "🇺🇸",
                "date":     d,
                "time":     "",
                "impact":   impact,
                "forecast": "",
                "previous": "",
                "actual":   "",
                "source":   "fred",
            })
        return evts
    except Exception as e:
        logger.warning("FRED failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Source 2 : Forex Factory (optionnel — peut être rate-limité depuis cloud)
# ---------------------------------------------------------------------------

_FF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.forexfactory.com/",
    "Origin":          "https://www.forexfactory.com",
}


def _fetch_ff(url: str) -> list[dict]:
    """Tente de récupérer FF. Retourne [] si bloqué/rate-limité."""
    try:
        resp = _req.get(url, headers=_FF_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 429:
            logger.warning("FF rate-limited (429) pour %s — IP serveur bloquée", url.split("/")[-1])
            return []
        resp.raise_for_status()
        data = resp.json()
        logger.info("FF OK (%s): %d events", url.split("/")[-1], len(data))
        return data
    except Exception as e:
        logger.warning("FF failed (%s): %s", url.split("/")[-1], e)
        return []


def _parse_ff_event(item: dict) -> dict | None:
    impact = item.get("impact", "")
    if impact == "Non-Economic":
        return None
    date_str = item.get("date", "")
    try:
        dt_paris   = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(_PARIS)
        date_local = dt_paris.strftime("%Y-%m-%d")
        time_local = dt_paris.strftime("%H:%M")
    except Exception:
        date_local = date_str[:10] if len(date_str) >= 10 else date_str
        time_local  = ""
    country = item.get("country", "").upper()
    return {
        "title":    item.get("title", ""),
        "country":  country,
        "flag":     _FLAGS.get(country, "🌐"),
        "date":     date_local,
        "time":     time_local,
        "impact":   impact,
        "forecast": item.get("forecast", "") or "",
        "previous": item.get("previous", "") or "",
        "actual":   item.get("actual",   "") or "",
        "source":   "forexfactory",
    }


def _get_ff_events() -> list[dict]:
    raw  = _fetch_ff(_FF_THIS_WEEK) + _fetch_ff(_FF_NEXT_WEEK)
    evts = [e for item in raw if (e := _parse_ff_event(item)) is not None]
    evts.sort(key=lambda e: (e["date"], e["time"]))
    return evts


# ---------------------------------------------------------------------------
# Orchestration + cache
# ---------------------------------------------------------------------------

def _refresh_cache() -> str:
    """Rafraîchit le cache. Retourne la source utilisée."""
    global _CACHE

    # Essai 1 : Forex Factory (optionnel, souvent bloqué depuis cloud)
    ff_evts = _get_ff_events()
    if ff_evts:
        _CACHE = {"data": ff_evts, "ts": time.monotonic(), "source": "forexfactory"}
        logger.info("Cache mis à jour depuis ForexFactory (%d events)", len(ff_evts))
        return "forexfactory"

    # Essai 2 : FRED (source principale fiable)
    logger.info("ForexFactory indisponible → FRED")
    fred_evts = _get_fred_events()
    if fred_evts:
        _CACHE = {"data": fred_evts, "ts": time.monotonic(), "source": "fred"}
        logger.info("Cache mis à jour depuis FRED (%d events)", len(fred_evts))
        return "fred"

    logger.error("Toutes les sources ont échoué — cache inchangé")
    return "none"


def _get_all_events() -> list[dict]:
    now = time.monotonic()
    if _CACHE["data"] and (now - _CACHE["ts"]) < _CACHE_TTL:
        return _CACHE["data"]
    _refresh_cache()
    return _CACHE["data"]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/week")
def get_week(current_user: CurrentUser):
    today  = date.today().strftime("%Y-%m-%d")
    cutoff = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
    return [e for e in _get_all_events() if today <= e["date"] <= cutoff]


@router.get("/today")
def get_today(current_user: CurrentUser):
    today = date.today().strftime("%Y-%m-%d")
    return [e for e in _get_all_events()
            if e["date"] == today and e["impact"] in ("High", "Medium")]


@router.get("/status")
def get_status():
    """Diagnostic public — état du cache + test live des sources."""
    now = time.monotonic()
    age = int(now - _CACHE["ts"]) if _CACHE["ts"] else None

    # Test live FRED
    fred_ok    = False
    fred_count = 0
    fred_error = ""
    fred_key   = bool(os.getenv("FRED_API_KEY"))
    if fred_key:
        try:
            today  = date.today()
            cutoff = today + timedelta(days=14)
            r = _req.get(
                "https://api.stlouisfed.org/fred/releases/dates"
                f"?api_key={os.getenv('FRED_API_KEY')}"
                f"&realtime_start={today}&realtime_end={cutoff}"
                "&file_type=json&limit=5",
                timeout=6,
            )
            fred_ok    = r.status_code == 200
            fred_count = r.json().get("count", 0) if fred_ok else 0
            fred_error = "" if fred_ok else f"HTTP {r.status_code}"
        except Exception as e:
            fred_error = str(e)

    # Test live ForexFactory
    ff_ok    = False
    ff_count = 0
    ff_error = ""
    try:
        r = _req.get(_FF_THIS_WEEK, headers=_FF_HEADERS, timeout=8)
        if r.status_code == 429:
            ff_error = "429 Rate Limited (IP serveur bloquée)"
        elif r.status_code == 200:
            ff_ok    = True
            ff_count = len(r.json())
        else:
            ff_error = f"HTTP {r.status_code}"
    except Exception as e:
        ff_error = str(e)

    return {
        "today":         date.today().isoformat(),
        "cache_events":  len(_CACHE["data"]),
        "cache_age_sec": age,
        "cache_source":  _CACHE.get("source", "none"),
        "forexfactory": {"ok": ff_ok, "count": ff_count, "error": ff_error},
        "fred":         {"ok": fred_ok, "count": fred_count, "error": fred_error, "key_set": fred_key},
    }


@router.post("/refresh")
def force_refresh(current_user: CurrentUser):
    """Force un rechargement immédiat du cache (ignore le TTL)."""
    global _CACHE
    _CACHE["ts"] = 0  # expire le cache
    source = _refresh_cache()
    return {"source": source, "events": len(_CACHE["data"])}


@router.get("/earnings")
def get_earnings(
    ticker: str = Query(...),
    current_user: CurrentUser = None,
):
    import yfinance as yf
    sym = ticker.upper().strip()
    try:
        t = yf.Ticker(sym)
        cal = t.calendar
        if not cal:
            return {"ticker": sym, "date": None}
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date")
            if dates:
                first = dates[0] if hasattr(dates, "__iter__") else dates
                return {"ticker": sym, "date": str(first)[:10]}
        if hasattr(cal, "loc") and "Earnings Date" in cal.index:
            val   = cal.loc["Earnings Date"]
            first = val.iloc[0] if hasattr(val, "iloc") else val
            return {"ticker": sym, "date": str(first)[:10]}
        return {"ticker": sym, "date": None}
    except Exception as e:
        logger.warning("Earnings failed for %s: %s", sym, e)
        return {"ticker": sym, "date": None}
