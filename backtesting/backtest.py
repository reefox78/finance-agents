"""
Backtest pur pandas/numpy — remplace l'implémentation backtrader.

Modes disponibles :
  "technique"  : score technique seul (RSI, MACD, BB, SMA)
  "multi"      : technique + macro FRED + risque rolling
  "agents"     : réplique des vrais agents sur données historiques
                 technique + macro FRED + risque rolling
                 + momentum court terme (rolling 5 bougies)
                 + secteur (driver ETF rolling 5j)
                 + earnings surprise (trimestriel yfinance)
                 → même poids et formules que orchestrator/scoring.py

Tous les modes calculent aussi le benchmark Buy & Hold pour comparaison.
"""

import os
import yfinance as yf
import pandas as pd
import numpy as np
from dotenv import load_dotenv

try:
    from fredapi import Fred
    _FRED_AVAILABLE = True
except ImportError:
    _FRED_AVAILABLE = False


# ---------------------------------------------------------------------------
# Scoring helpers — Macro
# ---------------------------------------------------------------------------

def _macro_score_from_values(taux, cpi_var, chomage, spread, confiance):
    score = 0.0
    n = 0
    if taux is not None and not pd.isna(taux):
        score += 1.0 if taux < 2.0 else (0.0 if taux < 4.0 else -1.0)
        n += 1
    if cpi_var is not None and not pd.isna(cpi_var):
        score += 0.5 if cpi_var < 0 else (0.0 if cpi_var < 0.3 else -0.5)
        n += 1
    if chomage is not None and not pd.isna(chomage):
        score += 1.0 if chomage < 4.0 else (0.0 if chomage < 6.0 else -1.0)
        n += 1
    if spread is not None and not pd.isna(spread):
        if spread > 0.5:    score += 1.0
        elif spread > 0:    score += 0.3
        elif spread > -0.5: score -= 0.3
        else:               score -= 1.0
        n += 1
    if confiance is not None and not pd.isna(confiance):
        score += 1.0 if confiance > 80 else (0.0 if confiance > 60 else -1.0)
        n += 1
    return round(score / n, 4) if n > 0 else 0.0


def _macro_mult_from_score(score):
    """Mirrors macro_en_multiplicateur() in orchestrator/scoring.py."""
    if score >= 0.3:    return 1.10
    elif score >= 0:    return 1.00
    elif score >= -0.3: return 0.90
    else:               return 0.75


# ---------------------------------------------------------------------------
# Scoring helpers — Risque
# ---------------------------------------------------------------------------

def _score_volatilite(vol):
    if vol < 15:   return 1.0
    elif vol < 25: return 0.5
    elif vol < 40: return 0.0
    else:          return -1.0


def _score_drawdown(dd):
    if dd > -5:    return 1.0
    elif dd > -10: return 0.5
    elif dd > -20: return 0.0
    elif dd > -30: return -0.5
    else:          return -1.0


def _score_sharpe(returns):
    std = returns.std()
    if std == 0:
        return 0.0
    sharpe = (returns.mean() / std) * (252 ** 0.5)
    if sharpe > 1.5:    return 1.0
    elif sharpe > 0.5:  return 0.5
    elif sharpe > 0:    return 0.0
    elif sharpe > -0.5: return -0.5
    else:               return -1.0


def _risk_mult_from_score(score):
    if score >= 0.25:    return 1.10
    elif score >= -0.25: return 1.00
    else:                return 0.75


# ---------------------------------------------------------------------------
# Indicateurs techniques — pure pandas
# ---------------------------------------------------------------------------

def _compute_indicators(close: pd.Series) -> pd.DataFrame:
    """Calcule SMA, RSI, MACD, Bollinger Bands sur la série de clôtures."""
    out = pd.DataFrame(index=close.index)
    out["close"] = close

    out["sma20"] = close.rolling(20).mean()
    out["sma50"] = close.rolling(50).mean()

    delta     = close.diff()
    gain      = delta.clip(lower=0)
    loss      = (-delta).clip(lower=0)
    avg_gain  = gain.ewm(com=13, min_periods=14).mean()
    avg_loss  = loss.ewm(com=13, min_periods=14).mean()
    rs        = avg_gain / avg_loss.replace(0, np.nan)
    out["rsi"] = 100 - (100 / (1 + rs))

    ema12            = close.ewm(span=12, adjust=False).mean()
    ema26            = close.ewm(span=26, adjust=False).mean()
    out["macd"]      = ema12 - ema26
    out["macd_sig"]  = out["macd"].ewm(span=9, adjust=False).mean()

    bb_mid         = close.rolling(20).mean()
    bb_std         = close.rolling(20).std()
    out["bb_top"]  = bb_mid + 2 * bb_std
    out["bb_bot"]  = bb_mid - 2 * bb_std

    return out


# ---------------------------------------------------------------------------
# Scoring technique — mirrors agents/technical.py
# ---------------------------------------------------------------------------

def _score_rsi(rsi):
    if rsi <= 30:   return 1.0
    elif rsi <= 50: return (50 - rsi) / 20 * 0.5
    elif rsi <= 70: return -(rsi - 50) / 40 * 0.5
    else:           return -0.5


def _score_macd(macd, signal):
    return max(-1.0, min(1.0, (macd - signal) / 2.0))


def _score_bb(prix, top, bot):
    largeur = top - bot
    if largeur == 0:
        return 0.0
    if prix > top:  return 0.2
    if prix < bot:  return -0.2
    return round((50 - (prix - bot) / largeur * 100) / 50, 4)


def _score_sma(prix, sma20, sma50):
    if prix > sma20 and sma20 > sma50: return 1.0
    elif prix > sma20:                 return 0.3
    elif prix > sma50:                 return -0.3
    else:                              return -1.0


def _score_technique(row) -> float:
    prix = row["close"]
    return (
        _score_macd(row["macd"], row["macd_sig"]) * 0.30 +
        _score_rsi(row["rsi"])                    * 0.25 +
        _score_bb(prix, row["bb_top"], row["bb_bot"]) * 0.25 +
        _score_sma(prix, row["sma20"], row["sma50"])  * 0.20
    )


# ---------------------------------------------------------------------------
# Lookup builders — lookups sont des dict: date_str -> valeur
# ---------------------------------------------------------------------------

def _build_macro_lookup(debut: str, fin: str) -> dict:
    """Retourne dict: date_str -> (score_macro, mult_macro)."""
    if not _FRED_AVAILABLE:
        return {}
    load_dotenv("config/.env")
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        return {}
    try:
        fred = Fred(api_key=api_key)
        start_buffer = (pd.Timestamp(debut) - pd.DateOffset(months=3)).strftime("%Y-%m-%d")

        fedfunds = fred.get_series("FEDFUNDS", observation_start=start_buffer, observation_end=fin).dropna()
        cpi      = fred.get_series("CPIAUCSL", observation_start=start_buffer, observation_end=fin).dropna()
        unrate   = fred.get_series("UNRATE",   observation_start=start_buffer, observation_end=fin).dropna()
        t10y2y   = fred.get_series("T10Y2Y",   observation_start=start_buffer, observation_end=fin).dropna()
        umcsent  = fred.get_series("UMCSENT",  observation_start=start_buffer, observation_end=fin).dropna()
        cpi_var  = cpi.diff()

        dates      = pd.date_range(start=debut, end=fin, freq="B")
        fedfunds_d = fedfunds.reindex(dates, method="ffill")
        cpi_var_d  = cpi_var.reindex(dates,  method="ffill")
        unrate_d   = unrate.reindex(dates,   method="ffill")
        t10y2y_d   = t10y2y.reindex(dates,   method="ffill")
        umcsent_d  = umcsent.reindex(dates,  method="ffill")

        lookup = {}
        for date in dates:
            score = _macro_score_from_values(
                fedfunds_d.get(date), cpi_var_d.get(date),
                unrate_d.get(date),   t10y2y_d.get(date),
                umcsent_d.get(date),
            )
            lookup[date.strftime("%Y-%m-%d")] = (score, _macro_mult_from_score(score))
        return lookup
    except Exception:
        return {}


def _build_forex_macro_lookup(ticker: str, debut: str, fin: str) -> dict:
    """Lookup macro pour les paires forex (taux directeurs différentiels)."""
    _FOREX_RATE_SERIES = {
        "USD": "FEDFUNDS", "EUR": "ECBDFR", "GBP": "IUDSOIA",
        "JPY": "IRSTCB01JPM156N", "CHF": "IR3TIB01CHM156N",
        "CAD": "IRSTCB01CAM156N", "AUD": "IRSTCB01AUM156N",
        "NZD": "IRSTCB01NZM156N",
    }
    if not _FRED_AVAILABLE:
        return {}
    load_dotenv("config/.env")
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        return {}
    code = ticker.replace("=X", "")
    if len(code) != 6:
        return {}
    base, quote = code[:3].upper(), code[3:].upper()
    base_s, quote_s = _FOREX_RATE_SERIES.get(base), _FOREX_RATE_SERIES.get(quote)
    if not base_s or not quote_s:
        return {}
    try:
        fred = Fred(api_key=api_key)
        start_buffer = (pd.Timestamp(debut) - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
        base_rate  = fred.get_series(base_s,  observation_start=start_buffer, observation_end=fin).dropna()
        quote_rate = fred.get_series(quote_s, observation_start=start_buffer, observation_end=fin).dropna()
        dates  = pd.date_range(start=debut, end=fin, freq="B")
        base_d = base_rate.reindex(dates,  method="ffill")
        quote_d = quote_rate.reindex(dates, method="ffill")
        lookup = {}
        for date in dates:
            b = base_d.get(date)
            q = quote_d.get(date)
            if b is None or q is None or pd.isna(b) or pd.isna(q):
                lookup[date.strftime("%Y-%m-%d")] = (0.0, 1.0)
                continue
            diff  = float(b) - float(q)
            score = round(max(-1.0, min(1.0, diff / 3.0)), 4)
            lookup[date.strftime("%Y-%m-%d")] = (score, _macro_mult_from_score(score))
        return lookup
    except Exception:
        return {}


def _build_risk_lookup(df: pd.DataFrame, window: int = 63) -> dict:
    """Lookup risque rolling : dict date_str -> (score_risque, mult_risque)."""
    close   = df["Close"].squeeze()
    returns = close.pct_change()
    lookup  = {}
    for i, date in enumerate(close.index):
        date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
        if i < window:
            lookup[date_str] = (0.0, 1.0)
            continue
        win_ret   = returns.iloc[i - window:i].dropna()
        win_close = close.iloc[i - window:i]
        vol = win_ret.std() * (252 ** 0.5) * 100
        dd  = ((win_close - win_close.cummax()) / win_close.cummax() * 100).min()
        score = round(
            _score_volatilite(vol) * 0.40 +
            _score_drawdown(dd)    * 0.35 +
            _score_sharpe(win_ret) * 0.25,
            4
        )
        lookup[date_str] = (score, _risk_mult_from_score(score))
    return lookup


# ---------------------------------------------------------------------------
# Agents-mode lookups (nouvelles fonctions)
# ---------------------------------------------------------------------------

# Mapping secteur → (driver_ticker, inversé) — mirrors agents/sector_risk.py
_SECTOR_DRIVERS: dict[str, tuple[str, bool]] = {
    "Energy":                 ("CL=F",    False),
    "Technology":             ("QQQ",     False),
    "Financial Services":     ("^TNX",    False),
    "Financial":              ("^TNX",    False),
    "Consumer Cyclical":      ("XLY",     False),
    "Consumer Discretionary": ("XLY",     False),
    "Healthcare":             ("XLV",     False),
    "Basic Materials":        ("GC=F",    False),
    "Industrials":            ("XLI",     False),
    "Utilities":              ("^TNX",    True),
    "Real Estate":            ("^TNX",    True),
    "Consumer Defensive":     ("XLP",     False),
    "Consumer Staples":       ("XLP",     False),
    "Communication Services": ("QQQ",     False),
    "Cryptocurrency":         ("BTC-USD", False),
}

_MULT_TABLE_SECTOR = [
    ( 10.0, 1.30), (  7.0, 1.20), (  4.0, 1.10), (  2.0, 1.04),
    ( -2.0, 1.00), ( -4.0, 0.88), ( -7.0, 0.75), (-10.0, 0.60), (-99.0, 0.45),
]


def _sector_perf_to_mult(perf: float, inversed: bool) -> float:
    """Mirrors agents/sector_risk._perf_to_mult."""
    p = -perf if inversed else perf
    for seuil, mult in _MULT_TABLE_SECTOR:
        if p > seuil:
            return mult
    return 0.45


def _build_sector_lookup(ticker: str, debut: str, fin: str) -> dict:
    """
    Lookup multiplicateur sectoriel historique.
    Pour chaque journée de trading, calcule la perf rolling 5j du driver ETF.
    dict date_str -> mult_sectoriel
    """
    t_upper = ticker.upper()
    if "-" in t_upper and not t_upper.endswith("=X"):
        sector = "Cryptocurrency"
    else:
        try:
            info   = yf.Ticker(ticker).info
            sector = info.get("sector", "") or ""
        except Exception:
            return {}

    entry = _SECTOR_DRIVERS.get(sector)
    if not entry:
        return {}

    driver_ticker, inversed = entry
    try:
        start_buffer = (pd.Timestamp(debut) - pd.DateOffset(days=30)).strftime("%Y-%m-%d")
        df_drv = yf.download(
            driver_ticker, start=start_buffer, end=fin,
            progress=False, auto_adjust=True, multi_level_index=False
        )
        if df_drv.empty:
            return {}
        closes = df_drv["Close"].squeeze().dropna()
        lookup = {}
        dates  = pd.date_range(start=debut, end=fin, freq="B")
        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            past = closes[closes.index <= date]
            if len(past) < 6:
                lookup[date_str] = 1.0
                continue
            n    = min(5, len(past) - 1)
            perf = (float(past.iloc[-1]) / float(past.iloc[-1 - n]) - 1.0) * 100.0
            lookup[date_str] = _sector_perf_to_mult(perf, inversed)
        return lookup
    except Exception:
        return {}


def _build_momentum_ct_lookup(df: pd.DataFrame, n_candles: int = 5) -> dict:
    """
    Lookup multiplicateur momentum court terme (rolling 5 bougies).
    Mirrors agents/momentum_court_terme.py.
    dict date_str -> mult_momentum
    """
    def _s_var(closes):
        var = (closes[-1] - closes[0]) / closes[0] * 100
        if var >= 5.0:    return  1.0
        elif var >= 2.0:  return  0.6
        elif var >= 0.5:  return  0.3
        elif var >= -0.5: return  0.0
        elif var >= -2.0: return -0.3
        elif var >= -5.0: return -0.6
        else:             return -1.0

    def _s_dir(opens, closes):
        h = sum(1 for o, c in zip(opens, closes) if c > o)
        return round((h / len(opens) - 0.5) * 2, 4)

    def _s_vol(vols):
        if len(vols) < 3: return 0.0
        md, mf = float(np.mean(vols[:2])), float(np.mean(vols[-2:]))
        if md == 0: return 0.0
        r = mf / md
        if r >= 1.5: return 0.8
        elif r >= 1.2: return 0.4
        elif r >= 0.9: return 0.0
        elif r >= 0.7: return -0.3
        else:          return -0.6

    def _s_accel(closes):
        if len(closes) < 4: return 0.0
        variations = [(closes[i] - closes[i-1]) / closes[i-1] * 100 for i in range(1, len(closes))]
        mi    = len(variations) // 2
        accel = float(np.mean(variations[mi:])) - float(np.mean(variations[:mi]))
        if accel >= 1.0:    return  0.8
        elif accel >= 0.3:  return  0.4
        elif accel >= -0.3: return  0.0
        elif accel >= -1.0: return -0.4
        else:               return -0.8

    def _s_force(o, c, h, l):
        corps = abs(c - o)
        r     = h - l
        if r == 0: return 0.0
        rc = corps / r
        d  = 1.0 if c >= o else -1.0
        if rc >= 0.7:   return round(0.7 * d, 4)
        elif rc >= 0.4: return round(0.3 * d, 4)
        else:           return 0.0

    def _mult(score):
        if score >= 0.35:    return 1.12
        elif score >= 0.15:  return 1.05
        elif score >= -0.15: return 1.00
        elif score >= -0.35: return 0.93
        else:                return 0.85

    closes  = df["Close"].squeeze()
    opens   = df["Open"].squeeze()
    highs   = df["High"].squeeze()
    lows    = df["Low"].squeeze()
    volumes = df["Volume"].squeeze()

    lookup = {}
    for i, date in enumerate(closes.index):
        date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
        if i < n_candles:
            lookup[date_str] = 1.0
            continue
        c_win = closes.iloc[i - n_candles:i].tolist()
        o_win = opens.iloc[i - n_candles:i].tolist()
        h_win = highs.iloc[i - n_candles:i].tolist()
        l_win = lows.iloc[i - n_candles:i].tolist()
        v_win = volumes.iloc[i - n_candles:i].tolist()

        score = (
            _s_var(c_win)                               * 0.30 +
            _s_dir(o_win, c_win)                        * 0.25 +
            _s_vol(v_win)                               * 0.20 +
            _s_accel(c_win)                             * 0.15 +
            _s_force(o_win[-1], c_win[-1], h_win[-1], l_win[-1]) * 0.10
        )
        lookup[date_str] = _mult(max(-1.0, min(1.0, score)))

    return lookup


def _build_earnings_lookup(ticker: str, debut: str, fin: str) -> dict:
    """
    Lookup earnings surprise score pour chaque journée.
    Utilise les données trimestrielles de yfinance.
    Non applicable pour crypto / forex.
    dict date_str -> score_earnings [-1, 1]
    """
    t = ticker.upper()
    if "-" in t or t.endswith("=X"):
        return {}

    def _score_surprise(pct):
        if pct is None or pd.isna(pct): return 0.0
        pct = float(pct)
        if pct > 15.0:    return  1.0
        elif pct > 5.0:   return  0.5
        elif pct > 0.0:   return  0.2
        elif pct > -5.0:  return -0.2
        elif pct > -15.0: return -0.5
        else:             return -1.0

    def _score_consistency(nb_beats, nb_total):
        if nb_total == 0: return 0.0
        ratio = nb_beats / nb_total
        if ratio >= 0.75:   return  0.5
        elif ratio >= 0.50: return  0.0
        elif ratio >= 0.25: return -0.3
        else:               return -0.6

    try:
        tk = yf.Ticker(ticker)
        earnings_df = tk.earnings_dates
        if earnings_df is None or earnings_df.empty:
            return {}

        earnings_df = earnings_df.copy()
        # Normalise l'index (peut être tz-aware)
        earnings_df.index = pd.to_datetime(earnings_df.index).tz_localize(None)
        past = earnings_df[earnings_df.index <= pd.Timestamp(fin)].dropna(
            subset=["Surprise(%)"]
        )
        if past.empty:
            return {}

        dates  = pd.date_range(start=debut, end=fin, freq="B")
        lookup = {}
        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            before = past[past.index < date].sort_index(ascending=False).head(4)
            if before.empty:
                lookup[date_str] = 0.0
                continue
            latest_pct = float(before["Surprise(%)"].iloc[0])
            avg_pct    = float(before["Surprise(%)"].mean())
            nb_beats   = int((before["Surprise(%)"] > 0).sum())
            nb_q       = len(before)

            score = round(
                _score_surprise(latest_pct)           * 0.50 +
                _score_surprise(avg_pct)              * 0.30 +
                _score_consistency(nb_beats, nb_q)    * 0.20,
                4
            )
            lookup[date_str] = max(-1.0, min(1.0, score))
        return lookup

    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Calcul du score final selon le mode
# ---------------------------------------------------------------------------

def _compute_score(
    row,
    mode: str,
    macro_lookup:    dict,
    risk_lookup:     dict,
    date_str:        str,
    sector_lookup:   dict | None = None,
    momentum_lookup: dict | None = None,
    earnings_lookup: dict | None = None,
) -> float:
    s_tech = _score_technique(row)

    if mode == "technique":
        return s_tech

    _, mult_risk  = risk_lookup.get(date_str, (0.0, 1.0))
    s_macro, mult_macro = macro_lookup.get(date_str, (0.0, 1.0))

    if mode == "multi":
        total      = 0.25 + 0.10
        score_brut = (s_tech * 0.25 + s_macro * 0.10) / total
        return max(-1.0, min(1.0, score_brut * mult_risk * mult_macro))

    if mode == "agents":
        # Multiplicateurs secteur + momentum
        mult_sector   = (sector_lookup   or {}).get(date_str, 1.0)
        mult_momentum = (momentum_lookup or {}).get(date_str, 1.0)
        s_earnings    = (earnings_lookup or {}).get(date_str, 0.0)

        # Poids actifs : technique (0.25) + macro (0.09) + earnings si dispo (0.10)
        has_earnings  = bool(earnings_lookup)
        p_earn        = 0.10 if has_earnings else 0.0
        poids_actifs  = 0.25 + 0.09 + p_earn

        score_brut = (
            s_tech     * 0.25 +
            s_macro    * 0.09 +
            s_earnings * p_earn
        ) / poids_actifs

        score_final = score_brut * mult_risk * mult_macro * mult_sector * mult_momentum
        return max(-1.0, min(1.0, score_final))

    return s_tech


# ---------------------------------------------------------------------------
# Simulateur de portefeuille (event-driven)
# ---------------------------------------------------------------------------

def _simulate(
    indics:          pd.DataFrame,
    macro_lookup:    dict,
    risk_lookup:     dict,
    mode:            str,
    seuil_achat:     float,
    seuil_vente:     float,
    capital:         float,
    commission:      float = 0.001,
    pct_size:        float = 0.95,
    sector_lookup:   dict | None = None,
    momentum_lookup: dict | None = None,
    earnings_lookup: dict | None = None,
) -> tuple[list, float]:
    """
    Boucle event-driven :
    signal émis sur la barre N → ordre exécuté sur la barre N+1
    (simplifié : exécution au close de N+1).
    PercentSizer 95 % du cash disponible, commission 0.1 %.
    """
    cash       = float(capital)
    shares     = 0.0
    open_trade = None
    pending    = None
    trades     = []

    rows = indics.reset_index()

    for i, row in rows.iterrows():
        if pd.isna(row.get("sma50")) or pd.isna(row.get("rsi")):
            pending = None
            continue

        date_str = pd.Timestamp(row["Date"] if "Date" in row else row.name).strftime("%Y-%m-%d")
        price    = float(row["close"])

        # Exécution ordre en attente
        if pending == "buy" and shares == 0:
            target_value = cash * pct_size
            n_shares     = target_value / price
            cost         = n_shares * price
            comm         = cost * commission
            cash        -= cost + comm
            shares       = n_shares
            open_trade   = {
                "date_achat": date_str,
                "prix_achat": round(price, 4),
                "_total_cost": cost + comm,
            }
            pending = None

        elif pending == "sell" and shares > 0:
            gross = shares * price
            comm  = gross * commission
            net   = gross - comm
            cash += net
            pnl    = round(gross - open_trade["prix_achat"] * shares, 2)
            pnlnet = round(net   - open_trade["_total_cost"],         2)
            trades.append({
                "date_achat": open_trade["date_achat"],
                "prix_achat": open_trade["prix_achat"],
                "date":       date_str,
                "prix_vente": round(price, 4),
                "pnl":        pnl,
                "pnlnet":     pnlnet,
            })
            shares     = 0.0
            open_trade = None
            pending    = None

        # Génération du signal
        if pending is None:
            score = _compute_score(
                row, mode, macro_lookup, risk_lookup, date_str,
                sector_lookup, momentum_lookup, earnings_lookup,
            )
            if shares == 0:
                if score >= seuil_achat:
                    pending = "buy"
            else:
                if score <= seuil_vente:
                    pending = "sell"

    last_price = float(indics["close"].iloc[-1])
    valeur_fin = round(cash + shares * last_price, 2)
    return trades, valeur_fin


# ---------------------------------------------------------------------------
# Benchmark Buy & Hold
# ---------------------------------------------------------------------------

def _compute_benchmark(df: pd.DataFrame, capital: float, debut: str, fin: str) -> list[dict]:
    """
    Simule un achat total le premier jour, vente le dernier jour.
    Retourne la courbe de valeur buy & hold pour comparaison.
    """
    close    = df["Close"].squeeze().dropna()
    close    = close[(close.index >= debut) & (close.index <= fin)]
    if close.empty:
        return []
    prix_achat = float(close.iloc[0])
    shares     = capital * 0.95 / prix_achat          # même pct_size
    cash_reste = capital - shares * prix_achat         # reste hors position

    benchmark = []
    for date, price in close.items():
        valeur = round(cash_reste + shares * float(price), 2)
        benchmark.append({"date": str(date.date()), "valeur": valeur})
    return benchmark


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def run_backtest(
    ticker:  str   = "AAPL",
    debut:   str   = "2023-01-01",
    fin:     str   = "2024-12-31",
    capital: float = 10000.0,
    mode:    str   = "multi",
) -> dict:
    """
    Lance le backtest.

    mode="technique"  : score technique seul
    mode="multi"      : technique + macro FRED + risque rolling (comportement historique)
    mode="agents"     : réplique complète des agents disponibles historiquement
                        technique + macro + risque + momentum CT + secteur + earnings
    """
    df = yf.download(ticker, start=debut, end=fin,
                     auto_adjust=True, multi_level_index=False)
    if df.empty:
        raise ValueError(f"Aucune donnée pour {ticker}")

    close  = df["Close"].squeeze()
    indics = _compute_indicators(close)

    is_forex = ticker.endswith("=X")

    # ── Lookups communs ─────────────────────────────────────────────────────
    risk_lookup = _build_risk_lookup(df)

    if mode in ("multi", "agents"):
        if is_forex:
            macro_lookup = _build_forex_macro_lookup(ticker, debut, fin)
        else:
            macro_lookup = _build_macro_lookup(debut, fin)
    else:
        macro_lookup = {}

    # ── Lookups agents (mode "agents" seulement) ────────────────────────────
    sector_lookup   = None
    momentum_lookup = None
    earnings_lookup = None
    agents_used     = ["technique", "risque", "macro"]

    if mode == "agents":
        momentum_lookup = _build_momentum_ct_lookup(df)
        agents_used.append("momentum_ct")

        if not is_forex:
            sector_lookup = _build_sector_lookup(ticker, debut, fin)
            if sector_lookup:
                agents_used.append("secteur")

            earnings_lookup = _build_earnings_lookup(ticker, debut, fin)
            if earnings_lookup:
                agents_used.append("earnings_surprise")

    # ── Seuils selon le mode ─────────────────────────────────────────────────
    if mode == "technique":
        seuil_achat, seuil_vente = 0.15, -0.15
    elif is_forex:
        seuil_achat, seuil_vente = 0.05, -0.05
    else:
        seuil_achat, seuil_vente = 0.10, -0.10

    # ── Simulation ───────────────────────────────────────────────────────────
    trades, valeur_fin = _simulate(
        indics          = indics,
        macro_lookup    = macro_lookup,
        risk_lookup     = risk_lookup,
        mode            = mode,
        seuil_achat     = seuil_achat,
        seuil_vente     = seuil_vente,
        capital         = capital,
        sector_lookup   = sector_lookup,
        momentum_lookup = momentum_lookup,
        earnings_lookup = earnings_lookup,
    )

    rendement = round((valeur_fin - capital) / capital * 100, 2)

    # ── Courbe equity (stratégie) ────────────────────────────────────────────
    equity          = [{"date": debut, "valeur": capital}]
    valeur_courante = capital
    for trade in trades:
        valeur_courante += trade["pnlnet"]
        equity.append({"date": trade["date"], "valeur": round(valeur_courante, 2)})

    # ── Benchmark Buy & Hold ─────────────────────────────────────────────────
    benchmark = _compute_benchmark(df, capital, debut, fin)
    bh_final  = benchmark[-1]["valeur"] if benchmark else capital
    bh_rend   = round((bh_final - capital) / capital * 100, 2)

    return {
        "ticker":       ticker,
        "debut":        debut,
        "fin":          fin,
        "capital":      capital,
        "valeur_fin":   valeur_fin,
        "rendement":    rendement,
        "trades":       trades,
        "equity":       equity,
        "benchmark":    benchmark,
        "bh_rendement": bh_rend,
        "agents_used":  agents_used,
        "df":           df,
        "mode":         mode,
    }


if __name__ == "__main__":
    import sys

    mode   = sys.argv[1] if len(sys.argv) > 1 else "agents"
    ticker = sys.argv[2] if len(sys.argv) > 2 else "AAPL"

    print(f"\n=== Backtest {ticker} — mode {mode} ===\n")
    resultat = run_backtest(ticker, mode=mode)

    bh = resultat.get("bh_rendement", 0)
    strat = resultat["rendement"]
    print(f"Période         : {resultat['debut']} → {resultat['fin']}")
    print(f"Capital départ  : {resultat['capital']:,.2f} $")
    print(f"Capital final   : {resultat['valeur_fin']:,.2f} $")
    print(f"Rendement strat : {strat:+.2f} %")
    print(f"Benchmark B&H   : {bh:+.2f} %")
    print(f"Alpha           : {strat - bh:+.2f} pp")
    print(f"Nb trades       : {len(resultat['trades'])}")
    print(f"Agents utilisés : {', '.join(resultat.get('agents_used', []))}")
    print(f"\nDétail trades :")
    for t in resultat["trades"]:
        signe = "[+]" if t["pnl"] > 0 else "[-]"
        print(f"  {signe} {t['date']} → PnL net : {t['pnlnet']} $")
