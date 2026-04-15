"""
Backtest pur pandas/numpy — remplace l'implémentation backtrader.

Même interface publique : run_backtest(ticker, debut, fin, capital, mode) → dict
Même logique de scoring technique + macro (FRED) + risque (rolling).
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
# Mapping des taux directeurs par devise (séries FRED)
# ---------------------------------------------------------------------------

_FOREX_RATE_SERIES = {
    "USD": "FEDFUNDS",
    "EUR": "ECBDFR",
    "GBP": "IUDSOIA",
    "JPY": "IRSTCB01JPM156N",
    "CHF": "IR3TIB01CHM156N",
    "CAD": "IRSTCB01CAM156N",
    "AUD": "IRSTCB01AUM156N",
    "NZD": "IRSTCB01NZM156N",
}


def _parse_forex_pair(ticker: str):
    code = ticker.replace("=X", "")
    if len(code) == 6:
        return code[:3].upper(), code[3:].upper()
    return None, None


# ---------------------------------------------------------------------------
# Scoring helpers
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
    if score >= 0.3:    return 1.05
    elif score >= 0:    return 1.00
    elif score >= -0.3: return 0.95
    else:               return 0.85


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

    # SMA
    out["sma20"] = close.rolling(20).mean()
    out["sma50"] = close.rolling(50).mean()

    # RSI (méthode EWM, compatible avec Wilder's smoothing)
    delta     = close.diff()
    gain      = delta.clip(lower=0)
    loss      = (-delta).clip(lower=0)
    avg_gain  = gain.ewm(com=13, min_periods=14).mean()
    avg_loss  = loss.ewm(com=13, min_periods=14).mean()
    rs        = avg_gain / avg_loss.replace(0, np.nan)
    out["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema12            = close.ewm(span=12, adjust=False).mean()
    ema26            = close.ewm(span=26, adjust=False).mean()
    out["macd"]      = ema12 - ema26
    out["macd_sig"]  = out["macd"].ewm(span=9, adjust=False).mean()

    # Bollinger Bands
    bb_mid         = close.rolling(20).mean()
    bb_std         = close.rolling(20).std()
    out["bb_top"]  = bb_mid + 2 * bb_std
    out["bb_bot"]  = bb_mid - 2 * bb_std

    return out


# ---------------------------------------------------------------------------
# Scoring technique (réplique _TechniqueMixin)
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


def _compute_score(row, mode, macro_lookup, risk_lookup, date_str) -> float:
    s_tech = _score_technique(row)

    if mode == "multi":
        s_macro, mult_macro = macro_lookup.get(date_str, (0.0, 1.0))
        _s_risk, mult_risk  = risk_lookup.get(date_str, (0.0, 1.0))
        total      = 0.25 + 0.10
        score_brut = (s_tech * 0.25 + s_macro * 0.10) / total
        return max(-1.0, min(1.0, score_brut * mult_risk * mult_macro))
    else:
        return s_tech


# ---------------------------------------------------------------------------
# Pré-calcul des lookups macro / risque (identique à l'implémentation originale)
# ---------------------------------------------------------------------------

def _build_macro_lookup(debut: str, fin: str) -> dict:
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
    if not _FRED_AVAILABLE:
        return {}
    load_dotenv("config/.env")
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        return {}
    base, quote = _parse_forex_pair(ticker)
    if not base or not quote:
        return {}
    base_series  = _FOREX_RATE_SERIES.get(base)
    quote_series = _FOREX_RATE_SERIES.get(quote)
    if not base_series or not quote_series:
        return {}
    try:
        fred = Fred(api_key=api_key)
        start_buffer = (pd.Timestamp(debut) - pd.DateOffset(months=3)).strftime("%Y-%m-%d")
        base_rate  = fred.get_series(base_series,  observation_start=start_buffer, observation_end=fin).dropna()
        quote_rate = fred.get_series(quote_series, observation_start=start_buffer, observation_end=fin).dropna()
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
# Simulateur de portefeuille (remplace Cerebro + broker + PercentSizer)
# ---------------------------------------------------------------------------

def _simulate(
    indics:       pd.DataFrame,
    macro_lookup: dict,
    risk_lookup:  dict,
    mode:         str,
    seuil_achat:  float,
    seuil_vente:  float,
    capital:      float,
    commission:   float = 0.001,
    pct_size:     float = 0.95,
) -> tuple[list, float]:
    """
    Boucle event-driven mimant le comportement de Backtrader :
    - signal émis sur la barre N → ordre exécuté à l'ouverture de la barre N+1
      (ici simplifié : exécution au close de N+1, comme BrokerFill par défaut)
    - PercentSizer 95 % du cash disponible
    - Commission 0.1 % aller et retour

    Retourne (trades, valeur_finale).
    """
    cash        = float(capital)
    shares      = 0.0
    open_trade  = None
    pending     = None          # "buy" | "sell" | None
    trades      = []

    rows = indics.reset_index()   # garantit un index entier

    for i, row in rows.iterrows():
        # Sauter les barres sans indicateurs complets
        if pd.isna(row.get("sma50")) or pd.isna(row.get("rsi")):
            pending = None
            continue

        date_str = pd.Timestamp(row["Date"] if "Date" in row else row.name).strftime("%Y-%m-%d")
        price    = float(row["close"])

        # ── Exécution de l'ordre en attente ──────────────────────────────────
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

        # ── Génération du signal ──────────────────────────────────────────────
        if pending is None:
            score = _compute_score(row, mode, macro_lookup, risk_lookup, date_str)
            if shares == 0:
                if score >= seuil_achat:
                    pending = "buy"
            else:
                if score <= seuil_vente:
                    pending = "sell"

    # Valorisation finale (position éventuellement encore ouverte)
    last_price = float(indics["close"].iloc[-1])
    valeur_fin = round(cash + shares * last_price, 2)
    return trades, valeur_fin


# ---------------------------------------------------------------------------
# Point d'entrée principal (interface publique inchangée)
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

    mode="multi"      : score combiné technique + macro (FRED) + risque (rolling)
    mode="technique"  : score technique seul
    """
    df = yf.download(ticker, start=debut, end=fin,
                     auto_adjust=True, multi_level_index=False)
    if df.empty:
        raise ValueError(f"Aucune donnée pour {ticker}")

    close  = df["Close"].squeeze()
    indics = _compute_indicators(close)

    is_forex = ticker.endswith("=X")

    if mode == "multi":
        if is_forex:
            macro_lookup = _build_forex_macro_lookup(ticker, debut, fin)
        else:
            macro_lookup = _build_macro_lookup(debut, fin)
        risk_lookup  = _build_risk_lookup(df)
        seuil_achat  = 0.05 if is_forex else 0.10
        seuil_vente  = -0.05 if is_forex else -0.10
    else:
        macro_lookup = {}
        risk_lookup  = {}
        seuil_achat  = 0.15
        seuil_vente  = -0.15

    trades, valeur_fin = _simulate(
        indics       = indics,
        macro_lookup = macro_lookup,
        risk_lookup  = risk_lookup,
        mode         = mode,
        seuil_achat  = seuil_achat,
        seuil_vente  = seuil_vente,
        capital      = capital,
    )

    rendement = round((valeur_fin - capital) / capital * 100, 2)

    equity          = [{"date": debut, "valeur": capital}]
    valeur_courante = capital
    for trade in trades:
        valeur_courante += trade["pnlnet"]
        equity.append({"date": trade["date"], "valeur": round(valeur_courante, 2)})

    return {
        "ticker":     ticker,
        "debut":      debut,
        "fin":        fin,
        "capital":    capital,
        "valeur_fin": valeur_fin,
        "rendement":  rendement,
        "trades":     trades,
        "equity":     equity,
        "df":         df,
        "mode":       mode,
    }


if __name__ == "__main__":
    import sys

    mode   = sys.argv[1] if len(sys.argv) > 1 else "multi"
    ticker = sys.argv[2] if len(sys.argv) > 2 else "AAPL"

    print(f"\n=== Backtest {ticker} — mode {mode} ===\n")
    resultat = run_backtest(ticker, mode=mode)

    print(f"\n--- Résultats ---")
    print(f"Période       : {resultat['debut']} -> {resultat['fin']}")
    print(f"Capital départ: {resultat['capital']:,.2f} $")
    print(f"Capital final : {resultat['valeur_fin']:,.2f} $")
    print(f"Rendement     : {resultat['rendement']} %")
    print(f"Nb trades     : {len(resultat['trades'])}")
    print(f"\nDétail trades :")
    for t in resultat["trades"]:
        signe = "[+]" if t["pnl"] > 0 else "[-]"
        print(f"  {signe} {t['date']} -> PnL net : {t['pnlnet']} $")
