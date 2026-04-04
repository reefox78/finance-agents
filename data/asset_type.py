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
        "fondamental": True,
        "sentiment":   True,
        "trends":      True,
        "insider":     True,
        "macro":       "us",
    },
    "eu_stock": {
        "fondamental": True,    # données yfinance partielles mais utiles
        "sentiment":   True,    # couverture news variable selon le titre
        "trends":      True,
        "insider":     False,   # OpenInsider = SEC = US uniquement
        "macro":       "eu",    # données BCE via FRED
    },
    "crypto": {
        "fondamental": False,   # pas de PER / dividende
        "sentiment":   True,    # très pertinent pour crypto
        "trends":      True,    # Google Trends très corrélé au cycle crypto
        "insider":     False,   # pas de dirigeants déclarants
        "macro":       "us",    # crypto cotée en USD
    },
    "forex": {
        "fondamental": False,   # pas applicable
        "sentiment":   True,
        "trends":      False,   # peu signal sur les paires FX
        "insider":     False,   # pas applicable
        "macro":       "us",    # macro USD comme référence
    },
}
