"""
Calendrier économique — événements macro de la semaine.

Sources :
  - Forex Factory JSON feed (gratuit, pas de clé API) → événements macro
  - yfinance → prochaine date de résultats par ticker

Endpoints :
  GET /api/calendar/week    → semaine courante + suivante
  GET /api/calendar/today   → événements HIGH/MEDIUM du jour (pour bannière Analyse)
  GET /api/calendar/earnings?ticker=AAPL → prochaine date de résultats
"""
import logging
import time
from datetime import datetime, date, timedelta

import requests as _requests
import pytz
from fastapi import APIRouter, Query

from api.deps import CurrentUser

logger = logging.getLogger(__name__)
router = APIRouter()

_FF_THIS_WEEK = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_FF_NEXT_WEEK = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"
_TIMEOUT      = 12.0
_PARIS        = pytz.timezone("Europe/Paris")

# ── Cache en mémoire (évite de spammer FF à chaque requête) ───────────────────
_CACHE: dict = {"data": [], "ts": 0.0}
_CACHE_TTL   = 3600  # 1 heure

_FF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.forexfactory.com/",
    "Origin":          "https://www.forexfactory.com",
    "Connection":      "keep-alive",
}

# Flags emoji par code ISO pays
_FLAGS: dict[str, str] = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "CAD": "🇨🇦", "AUD": "🇦🇺", "NZD": "🇳🇿", "CHF": "🇨🇭",
    "CNY": "🇨🇳", "ALL": "🌐",
}


def _fetch_ff(url: str) -> list[dict]:
    """Télécharge et parse le feed Forex Factory. Retourne [] en cas d'erreur."""
    try:
        resp = _requests.get(url, timeout=_TIMEOUT, headers=_FF_HEADERS, allow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Forex Factory OK (%s): %d events", url.split("/")[-1], len(data))
        return data
    except Exception as e:
        logger.warning("Forex Factory fetch failed (%s): %s", url.split("/")[-1], e)
        return []


def _parse_event(item: dict) -> dict | None:
    """Transforme un item FF en dict normalisé. Retourne None si à ignorer."""
    impact = item.get("impact", "")
    if impact == "Non-Economic":
        return None

    date_str = item.get("date", "")
    try:
        dt_utc   = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        dt_paris = dt_utc.astimezone(_PARIS)
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
    }


def _get_all_events() -> list[dict]:
    """
    Fusionne cette semaine + suivante, avec cache 1h.
    Utilise les données en cache si le fetch échoue.
    """
    global _CACHE
    now = time.monotonic()

    # Cache valide → retourner directement
    if _CACHE["data"] and (now - _CACHE["ts"]) < _CACHE_TTL:
        logger.debug("Calendar: using cache (%d events)", len(_CACHE["data"]))
        return _CACHE["data"]

    logger.info("Calendar: refreshing from Forex Factory…")
    raw  = _fetch_ff(_FF_THIS_WEEK) + _fetch_ff(_FF_NEXT_WEEK)
    evts = [e for item in raw if (e := _parse_event(item)) is not None]
    evts.sort(key=lambda e: (e["date"], e["time"]))

    if evts:
        # Mise à jour du cache seulement si on a des données
        _CACHE = {"data": evts, "ts": now}
        logger.info("Calendar: cache updated, %d events", len(evts))
    else:
        logger.warning("Calendar: FF returned no data — keeping stale cache if any")
        # On garde le cache précédent même s'il est expiré plutôt que de renvoyer []

    return _CACHE["data"]  # peut être [] si jamais eu de données


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/week")
def get_week(current_user: CurrentUser):
    """Événements économiques des 14 prochains jours."""
    today  = date.today().strftime("%Y-%m-%d")
    cutoff = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
    all_ev = _get_all_events()
    return [e for e in all_ev if today <= e["date"] <= cutoff]


@router.get("/today")
def get_today(current_user: CurrentUser):
    """Événements HIGH/MEDIUM d'aujourd'hui (bannière Analyse)."""
    today  = date.today().strftime("%Y-%m-%d")
    all_ev = _get_all_events()
    return [e for e in all_ev if e["date"] == today and e["impact"] in ("High", "Medium")]


@router.get("/status")
def get_status():
    """Debug — état du cache et test Forex Factory."""
    age = int(time.monotonic() - _CACHE["ts"]) if _CACHE["ts"] else None
    cached = len(_CACHE["data"])

    # Teste si FF est accessible depuis ce serveur
    try:
        r = _requests.get(_FF_THIS_WEEK, timeout=8, headers=_FF_HEADERS)
        ff_status = r.status_code
        ff_count  = len(r.json()) if r.ok else 0
    except Exception as exc:
        ff_status = str(exc)
        ff_count  = 0

    return {
        "cache_events":   cached,
        "cache_age_sec":  age,
        "ff_status":      ff_status,
        "ff_count":       ff_count,
        "today":          date.today().isoformat(),
    }


@router.get("/earnings")
def get_earnings(
    ticker: str = Query(..., description="Symbole boursier (ex: AAPL)"),
    current_user: CurrentUser = None,
):
    """Prochaine date de résultats trimestriels pour un ticker (yfinance)."""
    import yfinance as yf

    sym = ticker.upper().strip()
    try:
        t   = yf.Ticker(sym)
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
        logger.warning("Earnings fetch failed for %s: %s", sym, e)
        return {"ticker": sym, "date": None}
