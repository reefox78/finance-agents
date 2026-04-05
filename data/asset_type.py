"""
Détection automatique du type d'actif à partir du symbole ticker.
"""

# Suffixes boursiers européens reconnus par yfinance
_EU_SUFFIXES = {
    ".PA",  # Euronext Paris
    ".DE",  # Frankfurt (Xetra)
    ".AS",  # Euronext Amsterdam
    ".MI",  # Borsa Italiana
    ".MC",  # Bolsa Madrid
    ".L",   # London Stock Exchange
    ".SW",  # SIX Swiss Exchange
    ".BR",  # Euronext Bruxelles
    ".CO",  # Copenhagen
    ".HE",  # Helsinki
    ".OL",  # Oslo
    ".ST",  # Stockholm
    ".LS",  # Lisbonne
    ".VI",  # Vienne
    ".WA",  # Varsovie
    ".PR",  # Prague
    ".AT",  # Athènes
}

# Suffixes crypto yfinance (ex: BTC-USD, ETH-EUR, SOL-USDT)
_CRYPTO_BASE = {
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT",
    "AVAX", "MATIC", "LINK", "UNI", "LTC", "BCH", "ATOM",
}


def detect_asset_type(ticker: str) -> str:
    """
    Détecte la classe d'actif d'un ticker.

    Retourne l'une des valeurs :
        'us_stock'  → action américaine (AAPL, MSFT…)
        'eu_stock'  → action européenne (MC.PA, BMW.DE…)
        'crypto'    → cryptomonnaie (BTC-USD, ETH-EUR…)
        'forex'     → paire de devises (EURUSD=X, GBPUSD=X…)
    """
    t = ticker.upper().strip()

    # --- Forex : format XXXXXXX=X ---
    if t.endswith("=X"):
        return "forex"

    # --- Crypto : BASE-QUOTE (ex: BTC-USD, ETH-EUR) ---
    if "-" in t:
        base = t.split("-")[0]
        if base in _CRYPTO_BASE:
            return "crypto"

    # --- Actions européennes : TICKER.SUFFIXE ---
    if "." in t:
        suffix = "." + t.rsplit(".", 1)[-1]
        if suffix in _EU_SUFFIXES:
            return "eu_stock"

    # --- Par défaut : action américaine ---
    return "us_stock"


# Agents actifs selon le type d'actif.
# macro = "us" | "eu" | None
AGENTS_PAR_TYPE = {
    "us_stock": {
        "fondamental":      True,
        "sentiment":        True,
        "trends":           True,
        "insider":          True,
        "macro":            "us",
        "options_flow":     True,   # options listées sur NYSE/NASDAQ
        "sec_filings":      True,   # EDGAR = US uniquement
        "short_interest":   True,   # yfinance : données FINRA
        "earnings_surprise":True,   # EPS surprise via yfinance
        "volume_delta":     False,  # Binance API = crypto uniquement
    },
    "eu_stock": {
        "fondamental":      True,
        "sentiment":        True,
        "trends":           True,
        "insider":          False,  # OpenInsider = SEC = US uniquement
        "macro":            "eu",
        "options_flow":     False,  # peu de données options EU sur yfinance
        "sec_filings":      False,  # EDGAR = US uniquement
        "short_interest":   True,   # yfinance en a pour certaines EU
        "earnings_surprise":True,   # yfinance en a pour la plupart des EU
        "volume_delta":     False,
    },
    "crypto": {
        "fondamental":      False,  # pas de PER / dividende
        "sentiment":        True,
        "trends":           True,
        "insider":          False,
        "macro":            "us",
        "options_flow":     False,  # pas via yfinance
        "sec_filings":      False,
        "short_interest":   False,
        "earnings_surprise":False,  # pas d'EPS
        "volume_delta":     True,   # API Binance — acheteurs vs vendeurs réels
    },
    "forex": {
        "fondamental":      False,
        "sentiment":        True,
        "trends":           False,
        "insider":          False,
        "macro":            "us",
        "options_flow":     False,
        "sec_filings":      False,
        "short_interest":   False,
        "earnings_surprise":False,
        "volume_delta":     False,
    },
}
