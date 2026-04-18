"""
Agent : Risque sectoriel

Principe :
  Chaque secteur a un "driver" de référence (pétrole pour énergie, NASDAQ pour
  tech, taux 10 ans pour immobilier/utilities, or pour matériaux, etc.).
  Si ce driver se dégrade fortement sur 5 jours, le multiplicateur sectoriel
  baisse et pénalise les actifs du secteur concerné.

  score_final ∈ [-1, +1]
  mult_sectoriel ∈ [0.45, 1.30]  — appliqué en plus de mult_risk et mult_macro

Retourne un dict :
  secteur, driver, driver_ticker, driver_perf_5j, score_final,
  mult_sectoriel, signal, alerte
"""

import logging
from datetime import date, timedelta

import yfinance as yf

logger = logging.getLogger(__name__)

# ── Mapping secteur → (ticker_driver, nom_lisible, inversé) ──────────────────
# inversé=True : la relation est inverse (driver↑ = bearish pour le secteur)
#   ex: taux 10 ans↑ = bon pour banques MAIS mauvais pour immobilier/utilities
SECTEUR_DRIVERS: dict[str, tuple[str, str, bool]] = {
    # Énergie — corrélé au pétrole WTI
    "Energy":                 ("CL=F",    "Pétrole WTI",        False),
    # Technologie — corrélé au NASDAQ
    "Technology":             ("QQQ",     "NASDAQ-100 ETF",     False),
    # Finance — corrélé aux taux longs (taux↑ → marges bancaires ↑)
    "Financial Services":     ("^TNX",    "Taux 10 ans US",     False),
    "Financial":              ("^TNX",    "Taux 10 ans US",     False),
    # Consommation cyclique — corrélé à l'appétit consommateur
    "Consumer Cyclical":      ("XLY",     "Conso. Discret. ETF",False),
    "Consumer Discretionary": ("XLY",     "Conso. Discret. ETF",False),
    # Santé — corrélé à l'ETF Healthcare
    "Healthcare":             ("XLV",     "Santé ETF",          False),
    # Matériaux / Mines — corrélé à l'or (proxy commodities)
    "Basic Materials":        ("GC=F",    "Or (Gold Futures)",  False),
    # Industrie / Aéro / Défense
    "Industrials":            ("XLI",     "Industriels ETF",    False),
    # Services publics — taux↑ = concurrent du dividende → bearish
    "Utilities":              ("^TNX",    "Taux 10 ans US",     True),
    # Immobilier — taux↑ = coût dette ↑ → bearish
    "Real Estate":            ("^TNX",    "Taux 10 ans US",     True),
    # Conso. défensive — resilient, corrélé à son ETF
    "Consumer Defensive":     ("XLP",     "Conso. Défens. ETF", False),
    "Consumer Staples":       ("XLP",     "Conso. Défens. ETF", False),
    # Télécoms / Médias / Internet
    "Communication Services": ("QQQ",     "NASDAQ-100 ETF",     False),
    # Crypto — BTC comme driver de marché global crypto
    "Cryptocurrency":         ("BTC-USD", "Bitcoin",            False),
}

# ── Performance → multiplicateur ─────────────────────────────────────────────
# Tableau (seuil_perf, multiplicateur) trié décroissant
_MULT_TABLE = [
    ( 10.0, 1.30),
    (  7.0, 1.20),
    (  4.0, 1.10),
    (  2.0, 1.04),
    ( -2.0, 1.00),
    ( -4.0, 0.88),
    ( -7.0, 0.75),
    (-10.0, 0.60),
    (-99.0, 0.45),
]


def _get_driver_perf(driver_ticker: str, days: int = 5) -> float | None:
    """
    Retourne la performance sur `days` séances du driver.
    Télécharge 20 jours calendaire pour avoir assez de barres (week-ends, jours fériés).
    """
    try:
        start = (date.today() - timedelta(days=days * 3)).isoformat()
        end   = date.today().isoformat()
        df    = yf.download(driver_ticker, start=start, end=end,
                            progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        closes = df["Close"].dropna()
        if len(closes) < 2:
            return None
        n     = min(days, len(closes) - 1)
        perf  = (float(closes.iloc[-1]) / float(closes.iloc[-1 - n]) - 1.0) * 100.0
        return round(perf, 2)
    except Exception as e:
        logger.warning("sector_risk: driver %s → %s", driver_ticker, e)
        return None


def _perf_to_score(perf: float, inversed: bool) -> float:
    """Convertit une performance % en score [-1, 1]."""
    p = -perf if inversed else perf
    if   p >= 7:  return  1.0
    elif p >= 4:  return  0.6
    elif p >= 2:  return  0.3
    elif p >= -2: return  0.0
    elif p >= -4: return -0.3
    elif p >= -7: return -0.6
    else:         return -1.0


def _perf_to_mult(perf: float, inversed: bool) -> float:
    """Convertit une performance % en multiplicateur [0.45, 1.30]."""
    p = -perf if inversed else perf
    for seuil, mult in _MULT_TABLE:
        if p > seuil:
            return mult
    return 0.45


def analyze_sector_risk(ticker: str) -> dict:
    """
    Analyse le risque sectoriel d'un actif.

    1. Détecte le secteur via yfinance.info
    2. Identifie le driver de référence du secteur
    3. Mesure la performance 5j du driver
    4. Retourne un multiplicateur et un score
    """
    # ── Détection secteur ────────────────────────────────────────────────────
    t_upper = ticker.upper().strip()

    # Crypto : ticker de type BASE-QUOTE (ex: BTC-USD, ETH-USDT)
    if "-" in t_upper and not t_upper.endswith("=X"):
        sector = "Cryptocurrency"
    else:
        try:
            info   = yf.Ticker(ticker).fast_info
            # fast_info ne contient pas sector → fallback sur .info
            info2  = yf.Ticker(ticker).info
            sector = info2.get("sector", "") or info2.get("quoteType", "") or ""
        except Exception:
            sector = ""

    driver_entry = SECTEUR_DRIVERS.get(sector)

    if not driver_entry:
        # Secteur inconnu / forex / non supporté → multiplicateur neutre
        return {
            "secteur":        sector or "Inconnu",
            "driver":         None,
            "driver_ticker":  None,
            "driver_perf_5j": None,
            "inversed":       False,
            "score_final":    0.0,
            "mult_sectoriel": 1.0,
            "signal":         "NEUTRE",
            "alerte":         False,
        }

    driver_ticker, driver_nom, inversed = driver_entry
    perf = _get_driver_perf(driver_ticker, days=5)

    if perf is None:
        score = 0.0
        mult  = 1.0
    else:
        score = _perf_to_score(perf, inversed)
        mult  = _perf_to_mult(perf, inversed)

    if   score >= 0.3:  signal = "ACHETER"
    elif score <= -0.3: signal = "VENDRE"
    else:               signal = "NEUTRE"

    alerte = mult < 0.80 or mult > 1.15   # signale un choc sectoriel significatif

    logger.info(
        "sector_risk %s | secteur=%s | driver=%s | perf5j=%.2f%% | mult=%.2f | %s",
        ticker, sector, driver_ticker, perf if perf else 0, mult, signal,
    )

    return {
        "secteur":        sector,
        "driver":         driver_nom,
        "driver_ticker":  driver_ticker,
        "driver_perf_5j": perf,
        "inversed":       inversed,
        "score_final":    round(score, 4),
        "mult_sectoriel": mult,
        "signal":         signal,
        "alerte":         alerte,
    }


# ── Test standalone ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    for sym in ["TTE.PA", "AAPL", "JPM", "ASML.AS", "BTC-USD", "EURUSD=X", "MC.PA"]:
        r = analyze_sector_risk(sym)
        arrow = "⚠️ " if r["alerte"] else "   "
        print(
            f"{arrow}{sym:12} | {r['secteur']:25} | driver={r['driver']} "
            f"| perf5j={r['driver_perf_5j']}% | mult={r['mult_sectoriel']} | {r['signal']}"
        )
