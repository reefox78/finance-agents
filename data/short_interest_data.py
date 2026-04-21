"""
Données de short interest via yfinance.

Champs utilisés depuis yf.Ticker.info :
  - shortPercentOfFloat : % du float vendu à découvert
  - shortRatio          : jours pour couvrir (sharesShort / volume moyen)
  - sharesShort         : nombre d'actions shortées actuellement
  - sharesShortPriorMonth : nombre d'actions shortées le mois précédent

Mise à jour bi-mensuelle par FINRA (yfinance reflète la dernière publication).
"""

from data.market_data import get_ticker_raw_info


def get_short_interest(ticker: str) -> dict:
    """
    Récupère les données de short interest pour un ticker.

    Retourne un dict avec les métriques brutes et la variation mensuelle.
    Utilise le cache centralisé market_data (TTL 30 min + stale 24 h).
    """
    try:
        info = get_ticker_raw_info(ticker)

        short_pct   = info.get("shortPercentOfFloat")   # ex : 0.025 = 2.5%
        days_cover  = info.get("shortRatio")             # ex : 3.5 jours
        shares_now  = info.get("sharesShort")
        shares_prev = info.get("sharesShortPriorMonth")

        # Variation mensuelle en %
        mom_change = None
        if shares_now and shares_prev and shares_prev > 0:
            mom_change = round((shares_now - shares_prev) / shares_prev * 100, 2)

        return {
            "disponible":        True,
            "short_pct":         round(short_pct * 100, 2) if short_pct is not None else None,
            "days_to_cover":     round(days_cover, 2) if days_cover is not None else None,
            "shares_short":      shares_now,
            "shares_short_prev": shares_prev,
            "mom_change_pct":    mom_change,
        }

    except Exception as e:
        return {"disponible": False, "raison": str(e)}
