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
from datetime import datetime, date, timedelta

import requests as _requests
import pytz
from fastapi import APIRouter, Query, HTTPException

from api.deps import CurrentUser

logger = logging.getLogger(__name__)
router = APIRouter()

_FF_THIS_WEEK = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_FF_NEXT_WEEK = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"
_TIMEOUT      = 10.0
_PARIS        = pytz.timezone("Europe/Paris")

# Flags emoji par code ISO pays
_FLAGS: dict[str, str] = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "CAD": "🇨🇦", "AUD": "🇦🇺", "NZD": "🇳🇿", "CHF": "🇨🇭",
    "CNY": "🇨🇳", "ALL": "🌐",
}


def _fetch_ff(url: str) -> list[dict]:
    """Télécharge et parse le feed Forex Factory."""
    try:
        resp = _requests.get(
            url, timeout=_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FinanceAgents/1.0)"},
            allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("Forex Factory fetch failed (%s): %s", url, e)
        return []


def _parse_event(item: dict) -> dict | None:
    """Transforme un item FF en dict normalisé. Retourne None si à ignorer."""
    impact = item.get("impact", "")
    if impact == "Non-Economic":
        return None

    date_str = item.get("date", "")
    try:
        # FF dates : ISO 8601 avec offset UTC (ex: "2024-01-05T13:30:00-0500")
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
        "impact":   impact,             # "High" | "Medium" | "Low"
        "forecast": item.get("forecast", "") or "",
        "previous": item.get("previous", "") or "",
        "actual":   item.get("actual",   "") or "",
    }


def _get_events() -> list[dict]:
    """Fusionne cette semaine + semaine suivante, triés par date/heure."""
    raw = _fetch_ff(_FF_THIS_WEEK) + _fetch_ff(_FF_NEXT_WEEK)
    events = [e for item in raw if (e := _parse_event(item)) is not None]
    events.sort(key=lambda e: (e["date"], e["time"]))
    return events


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/week")
def get_week(current_user: CurrentUser):
    """
    Retourne les événements économiques des 14 prochains jours.
    Groupés par date, triés par heure. Impact: High / Medium / Low.
    """
    today = date.today().strftime("%Y-%m-%d")
    cutoff = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
    events = [e for e in _get_events() if today <= e["date"] <= cutoff]
    return events


@router.get("/today")
def get_today(current_user: CurrentUser):
    """
    Retourne uniquement les événements HIGH et MEDIUM d'aujourd'hui.
    Utilisé par la bannière d'alerte sur la page Analyse.
    """
    today = date.today().strftime("%Y-%m-%d")
    events = [
        e for e in _get_events()
        if e["date"] == today and e["impact"] in ("High", "Medium")
    ]
    return events


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
        cal = t.calendar           # dict ou None selon la version yfinance
        if not cal:
            return {"ticker": sym, "date": None}

        # yfinance 1.x : dict avec clé "Earnings Date" → liste de Timestamps
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date")
            if dates:
                first = dates[0] if hasattr(dates, "__iter__") else dates
                return {"ticker": sym, "date": str(first)[:10]}

        # yfinance 0.x : DataFrame
        if hasattr(cal, "loc") and "Earnings Date" in cal.index:
            val = cal.loc["Earnings Date"]
            first = val.iloc[0] if hasattr(val, "iloc") else val
            return {"ticker": sym, "date": str(first)[:10]}

        return {"ticker": sym, "date": None}

    except Exception as e:
        logger.warning("Earnings fetch failed for %s: %s", sym, e)
        return {"ticker": sym, "date": None}
