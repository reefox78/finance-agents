import os
import backtrader as bt
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv

try:
    from fredapi import Fred
    _FRED_AVAILABLE = True
except ImportError:
    _FRED_AVAILABLE = False


# ---------------------------------------------------------------------------
# Scoring helpers (réplique la logique des agents sans les dépendances réseau)
# ---------------------------------------------------------------------------

def _macro_score_from_values(taux, cpi_var, chomage, spread, confiance):
    """Réplique get_macro_score() sur des valeurs ponctuelles historiques."""
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
    """
    Multiplicateur macro adouci : amplitude réduite pour ne pas bloquer
    des signaux techniques forts dans un environnement macro défavorable.
    Avant : 0.75 / 0.90 / 1.0 / 1.10  → amplitude ×1.47
    Après : 0.85 / 0.95 / 1.0 / 1.05  → amplitude ×1.24
    """
    if score >= 0.3:    return 1.05
    elif score >= 0:    return 1.00
    elif score >= -0.3: return 0.95
    else:               return 0.85


def _score_volatilite(vol):
    if vol < 15:  return 1.0
    elif vol < 25: return 0.5
    elif vol < 40: return 0.0
    else:          return -1.0


def _score_drawdown(dd):
    if dd > -5:   return 1.0
    elif dd > -10: return 0.5
    elif dd > -20: return 0.0
    elif dd > -30: return -0.5
    else:          return -1.0


def _score_sharpe(returns):
    if returns.std() == 0:
        return 0.0
    sharpe = (returns.mean() / returns.std()) * (252 ** 0.5)
    if sharpe > 1.5:    return 1.0
    elif sharpe > 0.5:  return 0.5
    elif sharpe > 0:    return 0.0
    elif sharpe > -0.5: return -0.5
    else:               return -1.0


def _risk_mult_from_score(score):
    if score >= 0.25:   return 1.10   # FAIBLE
    elif score >= -0.25: return 1.00  # MODERE
    else:               return 0.75   # ELEVE


# ---------------------------------------------------------------------------
# Pré-calcul des scores historiques
# ---------------------------------------------------------------------------

def _build_macro_lookup(debut: str, fin: str) -> dict:
    """
    Télécharge l'historique FRED et retourne un dict date_str → (score, mult).
    Forward-fill des données mensuelles/hebdo vers une fréquence journalière.
    Retourne {} si FRED n'est pas disponible ou si la clé est absente.
    """
    if not _FRED_AVAILABLE:
        return {}

    load_dotenv("config/.env")
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        return {}

    try:
        fred = Fred(api_key=api_key)

        # Buffer de 3 mois avant le début pour avoir des valeurs dès le premier jour
        start_buffer = (pd.Timestamp(debut) - pd.DateOffset(months=3)).strftime("%Y-%m-%d")

        fedfunds = fred.get_series("FEDFUNDS",  observation_start=start_buffer, observation_end=fin).dropna()
        cpi      = fred.get_series("CPIAUCSL",  observation_start=start_buffer, observation_end=fin).dropna()
        unrate   = fred.get_series("UNRATE",    observation_start=start_buffer, observation_end=fin).dropna()
        t10y2y   = fred.get_series("T10Y2Y",    observation_start=start_buffer, observation_end=fin).dropna()
        umcsent  = fred.get_series("UMCSENT",   observation_start=start_buffer, observation_end=fin).dropna()

        cpi_var = cpi.diff()  # variation mensuelle CPI (proxy inflation)

        dates = pd.date_range(start=debut, end=fin, freq="B")

        fedfunds_d = fedfunds.reindex(dates, method="ffill")
        cpi_var_d  = cpi_var.reindex(dates,  method="ffill")
        unrate_d   = unrate.reindex(dates,   method="ffill")
        t10y2y_d   = t10y2y.reindex(dates,   method="ffill")
        umcsent_d  = umcsent.reindex(dates,  method="ffill")

        lookup = {}
        for date in dates:
            score = _macro_score_from_values(
                fedfunds_d.get(date),
                cpi_var_d.get(date),
                unrate_d.get(date),
                t10y2y_d.get(date),
                umcsent_d.get(date),
            )
            lookup[date.strftime("%Y-%m-%d")] = (score, _macro_mult_from_score(score))

        return lookup

    except Exception:
        return {}


def _build_risk_lookup(df: pd.DataFrame, window: int = 63) -> dict:
    """
    Calcule les scores de risque sur fenêtre glissante (≈3 mois).
    Retourne un dict date_str → (risk_score, risk_mult).
    Pas de données secteur disponibles en backtest → scoring absolu.
    """
    close   = df["Close"]
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

        s_vol    = _score_volatilite(vol)
        s_dd     = _score_drawdown(dd)
        s_sharpe = _score_sharpe(win_ret)

        score = round(s_vol * 0.40 + s_dd * 0.35 + s_sharpe * 0.25, 4)
        lookup[date_str] = (score, _risk_mult_from_score(score))

    return lookup


# ---------------------------------------------------------------------------
# Stratégies Backtrader
# ---------------------------------------------------------------------------

class _TechniqueMixin:
    """Indicateurs et scores techniques partagés entre les deux stratégies."""

    def _init_indicators(self):
        self.sma20 = bt.indicators.SMA(self.data.close, period=20)
        self.sma50 = bt.indicators.SMA(self.data.close, period=50)
        self.rsi   = bt.indicators.RSI(self.data.close, period=14)
        self.macd  = bt.indicators.MACD(self.data.close)
        self.bb    = bt.indicators.BollingerBands(self.data.close, period=20)

    def _score_rsi(self, rsi):
        """
        Scoring RSI compatible tendance.
        RSI élevé = momentum haussier, pas nécessairement surachat à vendre.
        RSI 50-70 : légèrement négatif (×0.5 vs original)
        RSI > 70  : pénalité plafonnée à -0.5 (vs -1.0 original)
        """
        if rsi <= 30:   return 1.0
        elif rsi <= 50: return (50 - rsi) / 20 * 0.5
        elif rsi <= 70: return -(rsi - 50) / 40 * 0.5   # pente moitié
        else:           return -0.5                       # cap à -0.5

    def _score_macd(self, macd, signal):
        return max(-1.0, min(1.0, (macd - signal) / 2.0))

    def _score_bb(self, prix, top, bot):
        """
        Scoring BB avec gestion des breakouts.
        Prix au-dessus des BB = signal de breakout haussier (+0.2).
        Prix en dessous = breakout baissier (-0.2).
        Évite les scores extrêmes non clampés du code original.
        """
        largeur = top - bot
        if largeur == 0:
            return 0.0
        if prix > top:
            return 0.2    # breakout haussier
        if prix < bot:
            return -0.2   # breakout baissier
        return round((50 - (prix - bot) / largeur * 100) / 50, 4)

    def _score_sma(self, prix, sma20, sma50):
        if prix > sma20 and sma20 > sma50: return 1.0
        elif prix > sma20:                 return 0.3
        elif prix > sma50:                 return -0.3
        else:                              return -1.0

    def _score_technique(self):
        prix = self.data.close[0]
        return (
            self._score_macd(self.macd.macd[0], self.macd.signal[0]) * 0.30 +
            self._score_rsi(self.rsi[0])                              * 0.25 +
            self._score_bb(prix, self.bb.top[0], self.bb.bot[0])     * 0.25 +
            self._score_sma(prix, self.sma20[0], self.sma50[0])      * 0.20
        )


class StrategieScoreContinue(_TechniqueMixin, bt.Strategy):
    """Stratégie technique seule (mode 'technique')."""

    params = (
        ("seuil_achat",  0.15),
        ("seuil_vente", -0.15),
    )

    def __init__(self):
        self._init_indicators()
        self.order = None

    def next(self):
        if self.order:
            return
        score = self._score_technique()
        if not self.position:
            if score >= self.params.seuil_achat:
                self.order = self.buy()
        else:
            if score <= self.params.seuil_vente:
                self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.order = None


class StrategieMultiAgent(_TechniqueMixin, bt.Strategy):
    """
    Stratégie combinant technique + macro + risque.

    Score brut  = (s_tech × 0.25 + s_macro × 0.10) / 0.35
    Score final = score_brut × mult_risque × mult_macro

    Seuil calé sur SEUIL_ACHAT de l'orchestrateur (0.10),
    plus bas que le mode technique seul (0.15) car les
    multiplicateurs macro/risque compriment naturellement le score.
    """

    params = (
        ("seuil_achat",   0.10),
        ("seuil_vente",  -0.10),
        ("macro_lookup",  None),   # dict date_str → (score, mult)
        ("risk_lookup",   None),   # dict date_str → (score, mult)
    )

    POIDS_TECH  = 0.25
    POIDS_MACRO = 0.10

    def __init__(self):
        self._init_indicators()
        self.order = None

    def _calculer_score(self):
        s_tech = self._score_technique()

        date_str = self.data.datetime.date().strftime("%Y-%m-%d")

        if self.params.macro_lookup:
            s_macro, mult_macro = self.params.macro_lookup.get(date_str, (0.0, 1.0))
        else:
            s_macro, mult_macro = 0.0, 1.0

        if self.params.risk_lookup:
            _s_risk, mult_risk = self.params.risk_lookup.get(date_str, (0.0, 1.0))
        else:
            mult_risk = 1.0

        total      = self.POIDS_TECH + self.POIDS_MACRO
        score_brut = (s_tech * self.POIDS_TECH + s_macro * self.POIDS_MACRO) / total
        score_final = max(-1.0, min(1.0, score_brut * mult_risk * mult_macro))
        return score_final

    def next(self):
        if self.order:
            return
        score = self._calculer_score()
        if not self.position:
            if score >= self.params.seuil_achat:
                self.order = self.buy()
        else:
            if score <= self.params.seuil_vente:
                self.order = self.sell()

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.order = None


# ---------------------------------------------------------------------------
# Analyser de trades
# ---------------------------------------------------------------------------

class TradeLogger(bt.Analyzer):
    """Enregistre chaque trade (entrée + sortie) pour affichage dans le dashboard."""

    def start(self):
        self.trades      = []
        self._open_price = None
        self._open_date  = None

    def next(self):
        pos = self.strategy.position
        if pos.size > 0 and self._open_price is None:
            self._open_price = pos.price
            self._open_date  = self.strategy.datetime.date().strftime("%Y-%m-%d")
        elif pos.size == 0 and self._open_price is not None:
            close_price = self.strategy.data.close[0]
            pnl = round((close_price - self._open_price) * 10, 2)
            self.trades.append({
                "date_achat":  self._open_date,
                "prix_achat":  round(self._open_price, 2),
                "date":        self.strategy.datetime.date().strftime("%Y-%m-%d"),
                "prix_vente":  round(close_price, 2),
                "pnl":         pnl,
                "pnlnet":      round(pnl * 0.999, 2),
            })
            self._open_price = None
            self._open_date  = None

    def get_analysis(self):
        return self.trades


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def run_backtest(
    ticker:  str   = "AAPL",
    debut:   str   = "2023-01-01",
    fin:     str   = "2024-12-31",
    capital: float = 10000.0,
    mode:    str   = "multi",       # "multi" | "technique"
) -> dict:
    """
    Lance le backtest.

    mode="multi"      : score combiné technique + macro (FRED) + risque (rolling)
    mode="technique"  : score technique seul (comportement original)
    """

    df = yf.download(ticker, start=debut, end=fin,
                     auto_adjust=True, multi_level_index=False)
    if df.empty:
        raise ValueError(f"Aucune donnée pour {ticker}")

    cerebro = bt.Cerebro()
    cerebro.addanalyzer(TradeLogger, _name="trades")

    if mode == "multi":
        print("Calcul des scores macro (FRED)...")
        macro_lookup = _build_macro_lookup(debut, fin)
        print(f"  -> {len(macro_lookup)} jours charges" if macro_lookup else "  -> FRED non disponible, macro ignoree")

        print("Calcul des scores risque (rolling 63j)...")
        risk_lookup = _build_risk_lookup(df)

        cerebro.addstrategy(
            StrategieMultiAgent,
            macro_lookup=macro_lookup,
            risk_lookup=risk_lookup,
        )
    else:
        cerebro.addstrategy(StrategieScoreContinue)

    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)
    cerebro.broker.setcash(capital)
    cerebro.broker.setcommission(commission=0.001)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)

    valeur_debut = cerebro.broker.getvalue()
    results      = cerebro.run()
    valeur_fin   = cerebro.broker.getvalue()
    rendement    = round((valeur_fin - valeur_debut) / valeur_debut * 100, 2)
    trades       = results[0].analyzers.trades.get_analysis()

    # Pas de cerebro.plot() — le graphique est construit en Plotly dans le dashboard

    equity          = [{"date": debut, "valeur": capital}]
    valeur_courante = capital
    for trade in trades:
        valeur_courante += trade["pnlnet"]
        equity.append({
            "date":   trade["date"],
            "valeur": round(valeur_courante, 2)
        })

    return {
        "ticker":     ticker,
        "debut":      debut,
        "fin":        fin,
        "capital":    capital,
        "valeur_fin": round(valeur_fin, 2),
        "rendement":  rendement,
        "trades":     trades,
        "equity":     equity,
        "df":         df,       # données OHLCV pour graphique Plotly
        "mode":       mode,
    }


if __name__ == "__main__":
    import sys

    mode   = sys.argv[1] if len(sys.argv) > 1 else "multi"
    ticker = sys.argv[2] if len(sys.argv) > 2 else "AAPL"

    print(f"\n=== Backtest {ticker} — mode {mode} ===\n")
    resultat = run_backtest(ticker, mode=mode)

    print(f"\n--- Résultats ---")
    print(f"Periode       : {resultat['debut']} -> {resultat['fin']}")
    print(f"Capital départ: {resultat['capital']:,} $")
    print(f"Capital final : {resultat['valeur_fin']:,} $")
    print(f"Rendement     : {resultat['rendement']} %")
    print(f"Nb trades     : {len(resultat['trades'])}")
    print(f"\nDétail trades :")
    for t in resultat["trades"]:
        signe = "[+]" if t["pnl"] > 0 else "[-]"
        print(f"  {signe} {t['date']} -> PnL : {t['pnlnet']} $")
