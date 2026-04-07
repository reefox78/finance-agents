import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import json
import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.market_data import get_stock_data, get_stock_info, get_news
from data.asset_type import detect_asset_type
from data.score_history import lire_historique
from data.portfolio import (ajouter_achat, ajouter_vente, supprimer_position,
                            supprimer_vente, evaluer_positions, definir_objectifs,
                            lister_historique, lister_transactions)
from data.alerts_store import (lister_alertes, compter_non_lues,
                                marquer_lue, tout_marquer_lu, supprimer_alerte)
from orchestrator.orchestrator import run
from backtesting.backtest import run_backtest
from ta.trend import SMAIndicator
from ta.volatility import BollingerBands

from datetime import date as _date_cls

# ---------------------------------------------------------------------------
# Helpers frais & fiscalité
# ---------------------------------------------------------------------------

from data.fees_tax import charger_brokers, calculer_frais, calculer_impots

@st.cache_data(ttl=3600)
def _load_brokers() -> dict:
    return charger_brokers()


def _calculer_frais_broker(montant: float, broker: dict, operation: str = "achat") -> float:
    return calculer_frais(montant, broker, operation)


@st.cache_data(ttl=300)
def _fetch_prix_actuel(ticker: str) -> float | None:
    """Récupère le dernier prix connu via yfinance (cache 5 min)."""
    if not ticker:
        return None
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        prix = info.get("regularMarketPrice") or info.get("currentPrice")
        if prix:
            return float(prix)
        hist = yf.Ticker(ticker).history(period="1d")
        return float(hist["Close"].iloc[-1]) if not hist.empty else None
    except Exception:
        return None


# Définitions affichées en tooltip sur les termes techniques
_TOOLTIPS = {
    "ticker":        "Symbole boursier de l'actif. Ex : AAPL = Apple, BTC-USD = Bitcoin, EURUSD=X = paire de devises Euro/Dollar.",
    "cump":          "Coût Unitaire Moyen Pondéré — ton prix de revient moyen par unité, frais d'achat inclus. Recalculé à chaque achat.",
    "pnl_brut":      "Profit & Loss brut = (prix de vente − CUMP) × quantité. Ne tient pas encore compte des frais de vente.",
    "pnl_net":       "P&L net = P&L brut − frais de vente. C'est ce que tu as réellement gagné ou perdu sur ce trade.",
    "pnl_pct":       "Rendement en % = P&L net ÷ (CUMP × quantité vendue) × 100. Mesure la performance relative de ton investissement.",
    "pnl_latent":    "Gain ou perte non encore réalisé(e) sur ta position ouverte = (prix actuel − CUMP) × quantité. Devient réel à la vente.",
    "frais":         "Frais de courtage payés à ton broker pour passer l'ordre. Inclus dans le CUMP à l'achat, déduits du P&L à la vente.",
    "prix_moyen":    "Prix moyen d'achat = CUMP (Coût Unitaire Moyen Pondéré). Reflète tous tes achats, frais inclus.",
    "valeur_totale": "Valeur actuelle de ta position = prix du marché × nombre d'unités détenues.",
    "score":         "Score de conviction calculé par les agents d'analyse (technique, macro, sentiment…). De -1 (très négatif) à +1 (très positif).",
    "signal_sortie": "Recommandation de l'app : 🟢 TENIR (position saine), 🟡 SURVEILLER (attention), 🔴 VENDRE (stop-loss ou score négatif).",
    "win_rate":      "Pourcentage de trades gagnants = nombre de ventes avec P&L positif ÷ total des ventes × 100.",
}


def _net_apres_impots(pnl_net_frais: float, regime: str, tmi: int = 30) -> tuple:
    r = calculer_impots(pnl_net_frais, regime, tmi)
    return r["impots"], r["pnl_apres_impots"], r["taux_effectif"]


st.set_page_config(
    page_title="Finance Agents",
    page_icon="📈",
    layout="wide"
)

# ---------------------------------------------------------------------------
# Tickers prédéfinis par catégorie
# ---------------------------------------------------------------------------

TICKERS_PRESET = {
    "🇺🇸 Actions US":  ["AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","JPM","XOM","SPY"],
    "🇪🇺 Actions EU":  ["MC.PA","TTE.PA","SAN.PA","BNP.PA","OR.PA","AI.PA","SAF.PA","ASML.AS","SAP.DE","SIE.DE"],
    "₿ Crypto":        ["BTC-USD","ETH-USD","SOL-USD","BNB-USD","XRP-USD","ADA-USD","DOGE-USD","DOT-USD","AVAX-USD","LINK-USD"],
    "💱 Forex":        ["EURUSD=X","GBPUSD=X","USDJPY=X","USDCHF=X","AUDUSD=X","USDCAD=X","NZDUSD=X","EURGBP=X","EURJPY=X","GBPJPY=X"],
}

# Noms courts des tickers pour l'affichage (max ~13 chars)
_TICKER_NOMS = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "GOOGL": "Alphabet",
    "META": "Meta", "AMZN": "Amazon", "TSLA": "Tesla", "JPM": "JPMorgan",
    "XOM": "ExxonMobil", "SPY": "S&P 500 ETF",
    "MC.PA": "LVMH", "TTE.PA": "TotalEnergies", "SAN.PA": "Sanofi",
    "BNP.PA": "BNP Paribas", "OR.PA": "L'Oréal", "AI.PA": "Air Liquide",
    "SAF.PA": "Safran", "ASML.AS": "ASML", "SAP.DE": "SAP", "SIE.DE": "Siemens",
    "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana",
    "BNB-USD": "BNB Chain", "XRP-USD": "XRP", "ADA-USD": "Cardano",
    "DOGE-USD": "Dogecoin", "DOT-USD": "Polkadot", "AVAX-USD": "Avalanche",
    "LINK-USD": "Chainlink",
    "EURUSD=X": "€/Dollar", "GBPUSD=X": "£/Dollar", "USDJPY=X": "$/Yen",
    "USDCHF=X": "$/CHF", "AUDUSD=X": "AUD/Dollar", "USDCAD=X": "$/CAD",
    "NZDUSD=X": "NZD/Dollar", "EURGBP=X": "€/£", "EURJPY=X": "€/Yen",
    "GBPJPY=X": "£/Yen",
}
_NOM_MAX = 13  # longueur max du nom entre parenthèses


def _ticker_label(ticker: str) -> str:
    """Renvoie 'AAPL (Apple)' ou 'AAPL' si pas de nom défini."""
    nom = _TICKER_NOMS.get(ticker, "")
    if not nom:
        return ticker
    if len(nom) > _NOM_MAX:
        nom = nom[:_NOM_MAX - 1] + "…"
    return f"{ticker} ({nom})"


def _build_options():
    """Liste plate avec séparateurs de catégorie, libellés avec noms."""
    opts = ["Personnalisé..."]
    for cat, tickers in TICKERS_PRESET.items():
        opts.append(f"── {cat} ──")
        opts.extend(_ticker_label(t) for t in tickers)
    return opts


def _ticker_selectbox(label, key, default="AAPL"):
    """Selectbox groupée avec noms. Retourne le ticker brut (sans le nom)."""
    opts        = _build_options()
    default_lbl = _ticker_label(default)
    idx  = next((i for i, o in enumerate(opts) if o == default_lbl), 0)
    choix = st.selectbox(label, opts, index=idx, key=key)
    if choix.startswith("──"):
        choix = "Personnalisé..."
    if choix == "Personnalisé...":
        return st.text_input("Ticker personnalisé", value=default,
                             key=f"{key}_custom").upper().strip()
    return choix.split(" (")[0]   # extrait le ticker avant " (Nom)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _icone_signal(signal):
    return {"ACHETER": "🟢", "VENDRE": "🔴"}.get(signal, "🟡")

def _icone_risque(risque):
    return {"FAIBLE": "🟢", "ELEVE": "🔴"}.get(risque, "🟡")


# ---------------------------------------------------------------------------
# Onglets principaux
# ---------------------------------------------------------------------------

st.title("📈 Finance Agents — Aide à la décision")

# Badge de notification sur l'onglet Portefeuille
_nb_alertes = compter_non_lues()
_label_portfolio = f"💼 Portefeuille {'🔔 ' + str(_nb_alertes) if _nb_alertes else ''}"

tab_analyse, tab_scanner, tab_portfolio, tab_backtest, tab_calib = st.tabs(
    ["🔍 Analyse", "📋 Scanner", _label_portfolio, "📊 Backtest", "⚙️ Calibration"]
)


# ===========================================================================
# ONGLET 1 — ANALYSE
# ===========================================================================

with tab_analyse:

    # --- Sidebar ---
    with st.sidebar:
        st.header("Paramètres")
        ticker = _ticker_selectbox("Ticker", key="ticker_analyse")
        period = st.selectbox("Période graphique", ["1mo", "3mo", "6mo", "1y", "2y"], index=1)
        lancer = st.button("Analyser", type="primary", use_container_width=True)

    if not lancer:
        st.info("Entre un ticker dans la sidebar et clique sur **Analyser**.\n\n"
                "Exemples : `AAPL` (US), `MC.PA` (Paris), `BTC-USD` (crypto), `EURUSD=X` (forex)")

    if lancer:
        asset_type = detect_asset_type(ticker)

        # --- Analyse complète ---
        try:
            with st.spinner(f"Analyse de {ticker} en cours..."):
                resultat = run(ticker, with_llm=True)
        except Exception as e:
            st.error(f"Erreur lors de l'analyse de **{ticker}** : {e}")
            st.stop()

        tech    = resultat["tech"]
        fund    = resultat["fund"]
        sent    = resultat["sent"]
        risk    = resultat["risk"]
        trends           = resultat["trends"]
        insider          = resultat["insider"]
        macro            = resultat["macro"]
        options_flow     = resultat.get("options_flow")
        sec_filings      = resultat.get("sec_filings")
        short_interest   = resultat.get("short_interest")
        earnings_surprise= resultat.get("earnings_surprise")
        volume_delta     = resultat.get("volume_delta")
        scoring          = resultat["scoring"]

        # --- Header ---
        try:
            info = get_stock_info(ticker)
            nom  = info.get("nom", ticker)
            cap  = info.get("capitalisation", 0)
            cap_str = f"{cap/1e9:.0f} Md$" if cap else "N/A"
        except Exception:
            info, nom, cap_str = {}, ticker, "N/A"

        asset_labels = {
            "us_stock": "🇺🇸 Action US",
            "eu_stock":  "🇪🇺 Action EU",
            "crypto":    "₿ Crypto",
            "forex":     "💱 Forex",
        }

        st.subheader(f"{nom} — {ticker}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Prix actuel",  f"{tech['prix_actuel']}")
        c2.metric("Type d'actif", asset_labels.get(asset_type, asset_type))
        c3.metric("Capitalisation", cap_str)
        if fund:
            c4.metric("PER", f"{fund['per']}")
        else:
            c4.metric("Secteur", info.get("secteur", "N/A"))

        st.divider()

        # --- Contexte macro ---
        if macro:
            st.subheader("Contexte macroéconomique",
                         help="Indicateurs économiques globaux qui influencent les marchés : "
                              "taux d'intérêt directeur (fixé par la banque centrale), "
                              "taux de chômage, confiance des consommateurs et spread obligataire. "
                              "Un environnement favorable pousse les marchés à la hausse ; "
                              "un environnement défavorable (taux élevés, chômage en hausse) "
                              "les pèse à la baisse.")
            env   = macro["environnement"]
            icone = _icone_signal(macro["signal"])

            if macro.get("market") == "eu":
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Taux BCE",    f"{macro.get('taux_bce', 'N/A')} %")
                m2.metric("Chômage EU",  f"{macro.get('chomage', 'N/A')} %")
                m3.metric("Confiance",   f"{macro.get('confiance', 'N/A')}")
                m4.metric("Taux 10 ans", f"{macro.get('taux_10y', 'N/A')} %")
                m5.metric("Environnement", f"{icone} {env}")
            else:
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Taux Fed",    f"{macro.get('taux_fed', 'N/A')} %")
                m2.metric("Chômage US",  f"{macro.get('chomage', 'N/A')} %")
                m3.metric("Confiance",   f"{macro.get('confiance', 'N/A')}")
                m4.metric("Spread 10/2", f"{macro.get('spread_10_2', 'N/A')}")
                m5.metric("Environnement", f"{icone} {env}")

            st.divider()

        # --- Graphique prix + volume ---
        try:
            df = get_stock_data(ticker, period=period)
            if not df.empty:
                st.subheader("Historique des prix")

                sma20  = SMAIndicator(df["Close"], window=20).sma_indicator()
                sma50  = SMAIndicator(df["Close"], window=50).sma_indicator()
                bb_ind = BollingerBands(df["Close"], window=20, window_dev=2)

                # Couleur des barres de volume : vert si bougie haussière, rouge sinon
                vol_colors = [
                    "rgba(46,204,113,0.7)" if c >= o else "rgba(231,76,60,0.7)"
                    for c, o in zip(df["Close"], df["Open"])
                ]

                fig = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    row_heights=[0.72, 0.28],
                    vertical_spacing=0.02,
                )

                # Ligne 1 — chandeliers + indicateurs
                fig.add_trace(go.Candlestick(
                    x=df.index, open=df["Open"], high=df["High"],
                    low=df["Low"], close=df["Close"], name="Prix",
                    increasing_line_color="#2ecc71", decreasing_line_color="#e74c3c",
                ), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=sma20, name="SMA 20",
                                         line=dict(color="orange", width=1.5)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=sma50, name="SMA 50",
                                         line=dict(color="#5b9bd5", width=1.5)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=bb_ind.bollinger_hband(),
                                         name="BB Haute",
                                         line=dict(color="rgba(150,150,150,0.5)", width=1, dash="dash"),
                                         showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=bb_ind.bollinger_lband(),
                                         name="BB",
                                         line=dict(color="rgba(150,150,150,0.5)", width=1, dash="dash"),
                                         fill="tonexty", fillcolor="rgba(150,150,150,0.05)"), row=1, col=1)

                # Ligne 2 — volume (vert/rouge selon direction)
                fig.add_trace(go.Bar(
                    x=df.index, y=df["Volume"],
                    name="Volume",
                    marker_color=vol_colors,
                    showlegend=False,
                ), row=2, col=1)

                fig.update_layout(
                    xaxis_rangeslider_visible=False,
                    height=520,
                    margin=dict(l=0, r=0, t=0, b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
                )
                fig.update_yaxes(title_text="Volume", fixedrange=True, row=2, col=1)

                st.plotly_chart(fig, use_container_width=True)
                st.divider()
        except Exception:
            pass

        # --- Signaux des agents ---
        st.subheader("Signaux des agents")
        agents_affiches = []
        agents_affiches.append(("Technique", tech["signal"],
                                 f"RSI : {tech['rsi']} | CMF : {tech.get('cmf', 'N/A')} | OBV↗" if tech.get('scores', {}).get('obv', 0) > 0 else f"RSI : {tech['rsi']} | CMF : {tech.get('cmf', 'N/A')} | OBV↘",
                                 f"VWAP : {tech.get('vwap', 'N/A')} | Vol×{tech.get('vol_ratio', 'N/A')}"))
        if fund:
            agents_affiches.append(("Fondamental", fund["signal"],
                                     f"PER : {fund['per']} | Div : {fund['dividende']}",
                                     f"Score : {fund.get('score_final', 'N/A')}"))
        if sent:
            agents_affiches.append(("Sentiment", sent["signal"],
                                     f"+{sent['positif']} / -{sent['negatif']} / ~{sent['neutre']}",
                                     f"{sent['articles']} articles analysés"))
        agents_affiches.append(("Risque", risk["risque"],
                                 f"Vol : {risk['volatilite']}% | DD : {risk['drawdown_max']}%",
                                 f"Score : {risk.get('score_final', 'N/A')}"))
        if trends:
            agents_affiches.append(("Trends", trends["signal"],
                                     f"Tendance : {trends['tendance']}",
                                     f"Variation : {trends['variation']}%"))
        if insider:
            agents_affiches.append(("Insider", insider["signal"],
                                     f"Achats : {insider['nb_achats']} | Ventes : {insider['nb_ventes']}",
                                     f"Ratio : {insider['ratio']}"))
        if macro:
            agents_affiches.append(("Macro", macro["signal"],
                                     f"Environnement : {macro['environnement']}",
                                     f"Score : {macro.get('score_final', 'N/A')}"))
        if options_flow:
            agents_affiches.append(("Options Flow", options_flow["signal"],
                                     f"P/C ratio : {options_flow.get('pc_ratio_vol')}",
                                     f"IV Skew : {options_flow.get('skew_iv')}"))
        if sec_filings:
            agents_affiches.append(("SEC 8-K", sec_filings["signal"],
                                     f"Filings 90j : {sec_filings.get('nb_filings')}",
                                     f"Dernier : {sec_filings.get('last_date')}"))
        if short_interest:
            agents_affiches.append(("Short Int.", short_interest["signal"],
                                     f"Short % : {short_interest.get('short_pct')} %",
                                     f"Var. mois : {short_interest.get('mom_change_pct')} %"))
        if earnings_surprise:
            agents_affiches.append(("Earnings", earnings_surprise["signal"],
                                     f"Surprise : {earnings_surprise.get('latest_surprise')} %",
                                     f"Beats : {earnings_surprise.get('nb_beats')}/{earnings_surprise.get('nb_quarters')}"))
        if volume_delta and "erreur" not in volume_delta:
            agents_affiches.append(("Vol. Delta", volume_delta["signal"],
                                     f"Achat moyen : {volume_delta.get('delta_pct_moyen')} % du vol.",
                                     f"CVD : {volume_delta.get('cvd_tendance')}"))

        _AGENT_DESC = {
            "Technique":    "Analyse les graphiques de prix : tendance (moyennes mobiles), "
                            "momentum (RSI), signaux de retournement (MACD), "
                            "et bandes de Bollinger. Ne regarde que le passé du cours.",
            "Fondamental":  "Évalue la santé financière de l'entreprise : PER (cherté vs bénéfices), "
                            "dividende versé, valorisation. Ignore la crypto et le forex.",
            "Sentiment":    "Analyse le ton des actualités récentes autour du ticker. "
                            "Si la majorité des articles est positive → signal haussier, négative → baissier.",
            "Risque":       "Mesure la dangerosité de l'actif : volatilité (amplitude des variations), "
                            "drawdown maximum (pire chute passée). Plus c'est élevé, plus c'est risqué.",
            "Trends":       "Mesure l'intérêt des internautes via Google Trends. "
                            "Un pic soudain peut signaler un engouement ou une panique.",
            "Insider":      "Suit les achats et ventes d'actions par les dirigeants de la société. "
                            "Un dirigeant qui achète massivement est souvent un bon signe.",
            "Macro":        "Évalue si l'environnement économique global (taux, chômage, confiance) "
                            "est favorable ou défavorable aux marchés.",
            "Options Flow": "Analyse le marché des options : rapport puts/calls (P/C ratio) "
                            "et asymétrie de volatilité implicite. Révèle les paris des gros investisseurs.",
            "SEC 8-K":      "Surveille les dépôts réglementaires SEC (formulaire 8-K) : "
                            "fusions, litiges, changements de direction. Beaucoup de filings = événement majeur.",
            "Short Int.":   "Mesure le pourcentage d'actions vendues à découvert. "
                            "Un short élevé et croissant = pression baissière ; une couverture des shorts = rebond possible.",
            "Earnings":     "Analyse les surprises de résultats trimestriels : "
                            "si l'entreprise bat régulièrement les attentes, c'est positif pour le cours.",
            "Vol. Delta":   "Volume Delta (crypto uniquement) — mesure la pression réelle des acheteurs vs vendeurs "
                            "via l'API Binance. >50% = acheteurs dominants, <50% = vendeurs. "
                            "CVD croissant = accumulation = haussier.",
        }

        NB_PAR_LIGNE = 4
        for debut in range(0, len(agents_affiches), NB_PAR_LIGNE):
            chunk = agents_affiches[debut:debut + NB_PAR_LIGNE]
            cols  = st.columns(NB_PAR_LIGNE)
            for col, (nom_agent, signal, ligne1, ligne2) in zip(cols, chunk):
                icone = _icone_signal(signal) if nom_agent != "Risque" else _icone_risque(signal)
                with col:
                    st.metric(nom_agent, f"{icone} {signal}",
                              help=_AGENT_DESC.get(nom_agent, ""))
                    st.caption(ligne1)
                    st.caption(ligne2)

        st.divider()

        # --- Score pondéré ---
        st.subheader("Score pondéré final")
        decision = scoring["decision"]
        score    = scoring["score_final"]
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Score final", f"{score} / 1.0",
                   help="Score de conviction global calculé par tous les agents actifs.\n\n"
                        "🟢 ≥ +0.10 → ACHETER\n"
                        "🟡 entre −0.10 et +0.10 → NEUTRE\n"
                        "🔴 ≤ −0.10 → VENDRE\n\n"
                        "Exemple : +0.85 = signal d'achat très fort et convergent. "
                        "−0.02 = agents en désaccord, pas de signal clair.")
        sc2.metric("Décision",    f"{_icone_signal(decision)} {decision}")
        sc3.metric("Mult risque", scoring["scores"]["multiplicateur"])
        sc4.metric("Mult macro",  scoring["scores"]["mult_macro"])

        fig_score = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            gauge={
                "axis": {"range": [-1, 1]},
                "bar":  {"color": "#2ecc71" if score > 0.1 else ("#e74c3c" if score < -0.1 else "#f39c12")},
                "steps": [
                    {"range": [-1, -0.1],  "color": "rgba(231,76,60,0.15)"},
                    {"range": [-0.1, 0.1], "color": "rgba(243,156,18,0.15)"},
                    {"range": [0.1, 1],    "color": "rgba(46,204,113,0.15)"},
                ],
                "threshold": {"line": {"color": "black", "width": 2}, "value": score}
            },
            number={"suffix": " / 1.0", "font": {"size": 28}},
        ))
        fig_score.update_layout(height=200, margin=dict(l=20, r=20, t=20, b=0))
        st.plotly_chart(fig_score, use_container_width=True)

        # --- Historique du score ---
        historique = lire_historique(ticker)
        if len(historique) >= 2:
            st.subheader("Évolution du score",
                         help="Chaque point correspond à une analyse lancée. "
                              "Une dégradation progressive du score avant une chute de cours "
                              "est souvent un signal d'alerte précoce.")
            df_hist = pd.DataFrame(historique)
            df_hist["ts"] = pd.to_datetime(df_hist["ts"])

            couleurs_dec = {"ACHETER": "#2ecc71", "NEUTRE": "#f39c12", "VENDRE": "#e74c3c"}

            fig_hist = go.Figure()

            # Zones colorées de fond
            fig_hist.add_hrect(y0=0.10,  y1=1.0,   fillcolor="rgba(46,204,113,0.07)",  line_width=0)
            fig_hist.add_hrect(y0=-0.10, y1=0.10,  fillcolor="rgba(243,156,18,0.07)",  line_width=0)
            fig_hist.add_hrect(y0=-1.0,  y1=-0.10, fillcolor="rgba(231,76,60,0.07)",   line_width=0)

            # Lignes de seuil
            fig_hist.add_hline(y=0.10,  line_dash="dot", line_color="rgba(46,204,113,0.5)",  line_width=1)
            fig_hist.add_hline(y=-0.10, line_dash="dot", line_color="rgba(231,76,60,0.5)",   line_width=1)
            fig_hist.add_hline(y=0,     line_dash="dot", line_color="rgba(150,150,150,0.3)", line_width=1)

            # Courbe principale
            fig_hist.add_trace(go.Scatter(
                x=df_hist["ts"],
                y=df_hist["score"],
                mode="lines+markers",
                name="Score",
                line=dict(color="#5b9bd5", width=2),
                marker=dict(
                    color=[couleurs_dec.get(d, "#aaa") for d in df_hist["decision"]],
                    size=8,
                    line=dict(color="white", width=1),
                ),
                hovertemplate="<b>%{x|%d/%m %H:%M}</b><br>Score : %{y:.4f}<extra></extra>",
            ))

            fig_hist.update_layout(
                height=260,
                margin=dict(l=0, r=0, t=10, b=0),
                yaxis=dict(range=[-1.05, 1.05], title="Score",
                           tickvals=[-1, -0.5, -0.1, 0, 0.1, 0.5, 1]),
                xaxis=dict(title=""),
                showlegend=False,
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        elif len(historique) == 1:
            st.caption("📈 Historique du score — lance une 2ᵉ analyse pour voir l'évolution.")

        st.divider()

        # --- Rapport LLM ---
        st.subheader("Rapport de décision (IA)")
        if resultat["rapport"]:
            st.markdown(resultat["rapport"])
        else:
            st.info("Rapport non généré (mode rapide).")

        st.divider()

        # --- Insider transactions ---
        if insider and insider.get("transactions"):
            st.subheader("Transactions des dirigeants")
            df_insider = pd.DataFrame(insider["transactions"])
            df_insider["type"] = df_insider["type"].apply(
                lambda x: "🟢 ACHAT" if x == "ACHAT" else "🔴 VENTE"
            )
            st.dataframe(df_insider, use_container_width=True)
            st.divider()

        # --- News ---
        st.subheader("Dernières news")
        try:
            news = get_news(ticker)
            if news:
                for article in news:
                    st.markdown(f"**{article['titre']}**  \n*{article['source']} — {article['date']}*")
            else:
                st.info("Aucune news disponible.")
        except Exception:
            st.info("News non disponibles pour ce type d'actif.")


# ===========================================================================
# ONGLET 2 — SCANNER
# ===========================================================================

with tab_scanner:
    st.subheader("Scanner de marché")

    WATCHLIST_PATH = Path("config/watchlist.json")

    # Chargement de la watchlist
    try:
        with open(WATCHLIST_PATH, encoding="utf-8") as f:
            watchlist = json.load(f)
        categories = list(watchlist.keys())
    except Exception:
        st.error("Impossible de lire config/watchlist.json")
        st.stop()

    col_wl1, col_wl2 = st.columns([2, 1])
    with col_wl1:
        categorie_sel = st.multiselect(
            "Catégories à scanner",
            options=categories,
            default=categories[:1],
        )
    with col_wl2:
        min_score = st.number_input("Score minimum", value=0.0, step=0.05, format="%.2f")

    tickers_sel = []
    for cat in categorie_sel:
        tickers_sel.extend(watchlist.get(cat, []))

    st.caption(f"{len(tickers_sel)} tickers sélectionnés : {', '.join(tickers_sel)}")

    lancer_scan = st.button("Lancer le scan", type="primary")

    if lancer_scan and tickers_sel:
        resultats_scan = []
        progress = st.progress(0, text="Démarrage...")

        for i, t in enumerate(tickers_sel):
            progress.progress((i) / len(tickers_sel), text=f"Analyse {t}…")
            try:
                r = run(t, with_llm=False)
                s = r["scoring"]
                resultats_scan.append({
                    "Ticker":   t,
                    "Type":     r["asset_type"],
                    "Décision": s["decision"],
                    "Score":    s["score_final"],
                    "Technique": r["tech"].get("score_final", 0.0),
                    "Risque":   r["risk"]["risque"] if r["risk"] else "N/A",
                    "Sentiment": r["sent"]["signal"] if r["sent"] else "N/A",
                    "Macro":    r["macro"]["score_final"] if r["macro"] else "N/A",
                    "Insider":  r["insider"]["signal"] if r["insider"] else "N/A",
                    "Options":  r["options_flow"]["signal"]      if r.get("options_flow")      else "-",
                    "SEC 8-K":  r["sec_filings"]["signal"]       if r.get("sec_filings")       else "-",
                    "Short %":  r["short_interest"]["short_pct"] if r.get("short_interest")    else "-",
                    "Earnings": r["earnings_surprise"]["signal"] if r.get("earnings_surprise") else "-",
                })
            except Exception as e:
                st.warning(f"{t} : {e}")

        progress.progress(1.0, text="Terminé")

        if resultats_scan:
            df_scan = pd.DataFrame(resultats_scan)
            df_scan = df_scan.sort_values("Score", ascending=False)

            if min_score != 0.0:
                df_scan = df_scan[df_scan["Score"] >= min_score]

            # Colorisation de la colonne Décision
            def style_decision(val):
                if val == "ACHETER": return "background-color:#d4edda;color:#155724;font-weight:bold"
                if val == "VENDRE":  return "background-color:#f8d7da;color:#721c24;font-weight:bold"
                return ""

            _styler = df_scan.style
            try:
                _styler = _styler.map(style_decision, subset=["Décision"])
            except AttributeError:
                _styler = _styler.applymap(style_decision, subset=["Décision"])

            st.dataframe(
                _styler,
                use_container_width=True,
                hide_index=True,
            )

            acheter = (df_scan["Décision"] == "ACHETER").sum()
            neutre  = (df_scan["Décision"] == "NEUTRE").sum()
            vendre  = (df_scan["Décision"] == "VENDRE").sum()

            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("🟢 ACHETER", acheter)
            sc2.metric("🟡 NEUTRE",  neutre)
            sc3.metric("🔴 VENDRE",  vendre)

            # Export CSV
            csv_data = df_scan.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Télécharger CSV",
                data=csv_data,
                file_name=f"scan_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )


# ===========================================================================
# ONGLET 3 — PORTEFEUILLE
# ===========================================================================

with tab_portfolio:
    st.subheader("💼 Mon portefeuille")

    # -----------------------------------------------------------------------
    # Panneau d'alertes
    # -----------------------------------------------------------------------
    alertes_actives = lister_alertes(non_lues_seulement=True)
    if alertes_actives:
        ICONE_NIVEAU = {"CRITIQUE": "🔴", "VENDRE": "🔴", "SURVEILLER": "🟡", "INFO": "🔵"}

        with st.container(border=True):
            al_titre, al_tout_lu = st.columns([4, 1])
            al_titre.markdown(f"### 🔔 {len(alertes_actives)} alerte(s) non lue(s)")
            if al_tout_lu.button("✅ Tout marquer lu", key="tout_lu"):
                tout_marquer_lu()
                st.rerun()

            for alerte in alertes_actives:
                icone = ICONE_NIVEAU.get(alerte["niveau"], "⚪")
                with st.container():
                    col_msg, col_date, col_actions = st.columns([5, 1.5, 1.5])
                    col_msg.markdown(f"{icone} **[{alerte['ticker']}]** {alerte['message']}")
                    col_date.caption(alerte["date"])
                    with col_actions:
                        btn_lu  = st.button("Lu ✓",  key=f"lu_{alerte['id']}",  use_container_width=True)
                        btn_del = st.button("🗑️",    key=f"dal_{alerte['id']}", use_container_width=True)
                    if btn_lu:
                        marquer_lue(alerte["id"])
                        st.rerun()
                    if btn_del:
                        supprimer_alerte(alerte["id"])
                        st.rerun()
                st.divider()

        # Bouton pour vérifier maintenant
        if st.button("🔄 Vérifier maintenant", key="check_now",
                      help="Relance une vérification des seuils sur toutes les positions"):
            with st.spinner("Vérification en cours..."):
                from alerts.monitor import verifier_positions
                nouvelles = verifier_positions(with_scores=False)
            if nouvelles:
                st.success(f"{len(nouvelles)} nouvelle(s) alerte(s) générée(s).")
            else:
                st.success("Aucune nouvelle alerte. Toutes les positions sont dans les seuils.")
            st.rerun()
    else:
        col_ok, col_check = st.columns([4, 1])
        col_ok.success("✅ Aucune alerte active — toutes les positions sont dans les seuils.")
        if col_check.button("🔄 Vérifier", key="check_now_ok",
                             help="Relance une vérification des seuils"):
            with st.spinner("Vérification..."):
                from alerts.monitor import verifier_positions
                nouvelles = verifier_positions(with_scores=False)
            if nouvelles:
                st.warning(f"{len(nouvelles)} nouvelle(s) alerte(s) détectée(s).")
            else:
                st.success("Aucune alerte. Tout va bien.")
            st.rerun()

    st.divider()

    SIGNAL_ICONE = {"TENIR": "🟢", "SURVEILLER": "🟡", "VENDRE": "🔴"}
    REGIME_LABELS = {
        "pfu":    "PFU 30 % — Flat tax (défaut)",
        "bareme": "Barème progressif (IR + 17.2 % PS)",
        "pea":    "PEA après 5 ans (17.2 % PS uniquement)",
    }

    # -----------------------------------------------------------------------
    # Paramètres broker & fiscalité
    # -----------------------------------------------------------------------
    brokers = _load_brokers()
    broker_options = {v["nom"]: k for k, v in brokers.items()}

    with st.expander("⚙️ Broker & Fiscalité", expanded=False):
        cfg1, cfg2 = st.columns(2)

        with cfg1:
            st.markdown("**Broker**")
            broker_nom_sel = st.selectbox(
                "Sélectionner un broker",
                list(broker_options.keys()),
                key="broker_sel",
                label_visibility="collapsed",
            )
            broker_key    = broker_options[broker_nom_sel]
            broker_config = brokers[broker_key]

            st.caption(f"💰 {broker_config['note']}")

            # Avertissement si tarifs anciens
            try:
                maj = _date_cls.fromisoformat(broker_config["mis_a_jour"])
                jours_old = (_date_cls.today() - maj).days
                if jours_old > 30:
                    st.warning(
                        f"⚠️ Tarifs vérifiés il y a **{jours_old} jours**. "
                        + (f"[Vérifier sur le site]({broker_config['url_tarifs']})"
                           if broker_config.get("url_tarifs") else "Mettre à jour config/brokers.json.")
                    )
                else:
                    st.success(f"✅ Tarifs vérifiés il y a {jours_old} jours")
            except Exception:
                pass

            if broker_key == "personnalise":
                st.info("Les frais seront saisis manuellement à chaque transaction.")

        with cfg2:
            st.markdown("**Régime fiscal France**")
            regime_label = st.selectbox(
                "Régime fiscal",
                list(REGIME_LABELS.values()),
                key="tax_regime_label",
                label_visibility="collapsed",
            )
            tax_regime = {v: k for k, v in REGIME_LABELS.items()}[regime_label]

            tmi_val = 30
            if tax_regime == "bareme":
                tmi_val = st.selectbox(
                    "Tranche marginale d'imposition (TMI)",
                    [0, 11, 30, 41, 45],
                    index=2,
                    key="tmi_sel",
                    format_func=lambda x: f"{x} %",
                )
                taux_total = tmi_val + 17.2
                st.caption(f"Taux effectif : {tmi_val} % + 17.2 % PS = **{taux_total:.1f} %**")
            elif tax_regime == "pfu":
                st.caption("12.8 % IR + 17.2 % prélèvements sociaux = **30 %**")
                st.caption("Les moins-values compensent les plus-values sur l'année fiscale.")
            elif tax_regime == "pea":
                st.caption("Exonéré d'IR après 5 ans. Seuls **17.2 % de PS** restent dus.")
                st.caption("Attention : retraits avant 5 ans entraînent la clôture du PEA.")

            st.caption("⚠️ Les impôts affichés sont des **estimations** par trade. "
                       "Le calcul réel s'effectue à l'année sur l'ensemble des plus/moins-values.")

    # -----------------------------------------------------------------------
    # Enregistrer un achat
    # -----------------------------------------------------------------------
    with st.expander("➕ Enregistrer un achat", expanded=False):
        # Sélecteur de ticker (même liste que l'onglet Analyse, avec noms)
        pf_ticker = _ticker_selectbox("Ticker à acheter", key="pf_buy_ticker")

        c2, c3, c4 = st.columns(3)

        # Prix auto-rempli au dernier cours (clé inclut le ticker → reset si ticker change)
        prix_marche = _fetch_prix_actuel(pf_ticker) if pf_ticker else None
        prix_defaut = prix_marche if prix_marche else 100.0
        pf_prix = c2.number_input(
            "Prix d'achat",
            min_value=0.0001, value=prix_defaut,
            format="%.4f", key=f"pf_prix_{pf_ticker}",
            help="Prix unitaire payé. Pré-rempli au dernier cours connu (mis à jour toutes les 5 min).",
        )
        if prix_marche:
            c2.caption(f"Dernier cours : {prix_marche:.4f}")
        else:
            c2.caption("Prix non disponible — saisie manuelle")

        pf_qty  = c3.number_input(
            "Quantité",
            min_value=0.0001, value=1.0,
            format="%.6f", key="pf_qty",
            help="Nombre d'unités achetées (actions, fractions, cryptos…).",
        )
        pf_date = c4.date_input("Date", key="pf_date",
                                 help="Date de l'achat. Par défaut : aujourd'hui.")

        # Frais calculés selon broker (clé inclut broker_key → reset si broker change)
        frais_auto = _calculer_frais_broker(pf_prix * pf_qty, broker_config, "achat")
        pf_frais = st.number_input(
            f"Frais broker ({broker_nom_sel})",
            min_value=0.0, value=frais_auto, format="%.4f",
            key=f"pf_frais_{broker_key}",
            help=_TOOLTIPS["frais"],
        )
        pf_notes = st.text_input("Notes (optionnel)", key="pf_notes",
                                  placeholder="Ex: signal ACHETER score +0.32")

        # Récapitulatif avant confirmation
        cout_total   = round(pf_prix * pf_qty + pf_frais, 4)
        cump_preview = round(cout_total / pf_qty, 6) if pf_qty else 0
        st.caption(
            f"Coût total : **{cout_total:.4f}** | "
            f"CUMP résultant : **{cump_preview:.4f}** / unité (si 1ère position)",
            help=_TOOLTIPS["cump"],
        )

        if st.button("Enregistrer l'achat", type="primary", key="pf_ajouter"):
            pos = ajouter_achat(pf_ticker, pf_prix, pf_qty,
                                pf_date.strftime("%Y-%m-%d"), pf_notes, frais=pf_frais)
            st.success(f"✅ Achat enregistré — {pf_ticker} : {pos['quantite']} unités "
                       f"@ CUMP {pos['prix_moyen']:.4f} (frais inclus)")
            if "pf_positions" in st.session_state:
                del st.session_state["pf_positions"]
            st.rerun()

    st.divider()

    # --- Monitoring ---
    col_refresh, col_mode = st.columns([3, 1])
    lancer_eval = col_refresh.button("🔄 Analyser mes positions", type="primary", key="pf_eval")
    mode_rapide = col_mode.checkbox("Mode rapide", value=True, key="pf_rapide",
                                     help="P&L uniquement (instantané). Décocher pour le scoring multi-agent complet.")

    positions_raw = evaluer_positions(with_scores=False)

    if lancer_eval:
        with st.spinner("Analyse en cours..."):
            positions_eval = evaluer_positions(with_scores=not mode_rapide)
        st.session_state["pf_positions"] = positions_eval

    positions_eval = st.session_state.get("pf_positions", positions_raw)

    if not positions_eval:
        st.info("Aucune position ouverte. Enregistre ton premier achat ci-dessus.")
    else:
        # Résumé global
        total_investi = sum(p["investi"] for p in positions_eval if p["investi"])
        total_valeur  = sum(p["valeur"]  for p in positions_eval if p["valeur"])
        total_pnl     = round(total_valeur - total_investi, 2) if total_valeur else None
        total_pnl_pct = round(total_pnl / total_investi * 100, 2) if total_pnl and total_investi else None
        nb_vendre     = sum(1 for p in positions_eval if p["signal_sortie"] == "VENDRE")
        nb_surveiller = sum(1 for p in positions_eval if p["signal_sortie"] == "SURVEILLER")

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Positions", len(positions_eval))
        r2.metric("Investi", f"{total_investi:,.2f}")
        if total_valeur and total_pnl is not None:
            r3.metric("Valeur actuelle", f"{total_valeur:,.2f}",
                       delta=f"{total_pnl:+.2f} ({total_pnl_pct:+.2f}%)")
        else:
            r3.metric("Valeur actuelle", "N/A")
        r4.metric("🔴 Alertes vente", nb_vendre,
                   delta=f"{nb_surveiller} à surveiller" if nb_surveiller else None,
                   delta_color="off")

        st.divider()

        # Carte par position
        for pos in sorted(positions_eval, key=lambda x: x["signal_sortie"], reverse=True):
            signal = pos["signal_sortie"]
            icone  = SIGNAL_ICONE.get(signal, "⚪")
            ticker = pos["ticker"]

            with st.container(border=True):
                h1, h2, h3, h4, h5, h6, h7 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.2])

                with h1:
                    st.markdown(f"### {icone} {ticker}")
                    st.caption(f"{pos['quantite']} unités · CUMP {pos['prix_moyen']:.4f}",
                               help=_TOOLTIPS["ticker"] + " | " + _TOOLTIPS["cump"])
                    if pos["date_achat"]:
                        st.caption(f"Premier achat : {pos['date_achat']}"
                                   + (f" ({pos['jours']} j)" if pos["jours"] else ""))
                h2.metric("CUMP (prix moyen)", f"{pos['prix_moyen']:.4f}",
                           help=_TOOLTIPS["cump"])
                h3.metric("Prix actuel",
                           f"{pos['prix_actuel']:.4f}" if pos["prix_actuel"] else "N/A",
                           help="Dernier cours connu du marché pour cet actif.")
                if pos["pnl_eur"] is not None:
                    h4.metric("P&L latent", f"{pos['pnl_eur']:+.2f}",
                               delta=f"{pos['pnl_pct']:+.2f}%",
                               help=_TOOLTIPS["pnl_latent"])
                else:
                    h4.metric("P&L latent", "N/A", help=_TOOLTIPS["pnl_latent"])
                h5.metric("Valeur totale",
                           f"{pos['valeur']:,.2f}" if pos["valeur"] else "N/A",
                           delta=f"{pos['quantite']} unités", delta_color="off",
                           help=_TOOLTIPS["valeur_totale"])
                h6.metric("Score agents", f"{pos['score']:+.4f}" if pos["score"] else "—",
                           help=_TOOLTIPS["score"])
                h6.caption(f"**{icone} {signal}**", help=_TOOLTIPS["signal_sortie"])

                # Affichage des objectifs sous la ligne de métriques
                cible_pct     = pos.get("cible_pct")
                stop_loss_pct = pos.get("stop_loss_pct", -8.0)
                prix_cible    = pos.get("prix_cible")
                prix_stop     = pos.get("prix_stop")
                obj_parts = []
                obj_parts.append(f"🛑 Stop : **{stop_loss_pct:+.1f}%**"
                                  + (f" ({prix_stop:.2f})" if prix_stop else ""))
                if cible_pct:
                    obj_parts.append(f"🎯 Cible : **+{cible_pct:.1f}%**"
                                      + (f" ({prix_cible:.2f})" if prix_cible else ""))
                else:
                    obj_parts.append("🎯 Cible : *non définie*")
                st.caption("  ·  ".join(obj_parts))

                with h7:
                    if st.button("💰 Vendre", key=f"sell_{ticker}"):
                        st.session_state[f"vendre_{ticker}"] = True
                    if st.button("🎯 Objectifs", key=f"obj_{ticker}"):
                        st.session_state[f"objectifs_{ticker}"] = not st.session_state.get(f"objectifs_{ticker}", False)
                    if st.button("🗑️ Suppr.", key=f"del_{ticker}",
                                  help="Supprimer sans historique"):
                        supprimer_position(ticker)
                        if "pf_positions" in st.session_state:
                            del st.session_state["pf_positions"]
                        st.rerun()

                # Formulaire objectifs (cible + stop-loss)
                if st.session_state.get(f"objectifs_{ticker}"):
                    with st.form(key=f"form_obj_{ticker}"):
                        st.markdown(f"**🎯 Objectifs pour {ticker}** — CUMP : {pos['prix_moyen']:.4f}")
                        oj1, oj2 = st.columns(2)

                        obj_stop = oj1.number_input(
                            "Stop-loss (%)",
                            value=float(pos.get("stop_loss_pct") or -8.0),
                            min_value=-50.0, max_value=-0.5, step=0.5, format="%.1f",
                            help="Perte maximale tolérée. Ex : -8 → vendre si -8% depuis le CUMP.",
                            key=f"obj_stop_{ticker}",
                        )
                        prix_stop_prev = round(pos["prix_moyen"] * (1 + obj_stop / 100), 2)
                        oj1.caption(f"= {prix_stop_prev:.2f} en valeur absolue")

                        obj_cible = oj2.number_input(
                            "Cible de gain (%)",
                            value=float(pos.get("cible_pct") or 15.0),
                            min_value=0.5, max_value=500.0, step=0.5, format="%.1f",
                            help="Gain visé. Ex : 15 → vendre si +15% depuis le CUMP.",
                            key=f"obj_cible_{ticker}",
                        )
                        prix_cible_prev = round(pos["prix_moyen"] * (1 + obj_cible / 100), 2)
                        oj2.caption(f"= {prix_cible_prev:.2f} en valeur absolue")

                        sauv = st.form_submit_button("💾 Enregistrer", type="primary")
                        annuler_obj = st.form_submit_button("Annuler")

                    if sauv:
                        definir_objectifs(ticker, cible_pct=obj_cible, stop_loss_pct=obj_stop)
                        st.success(f"✅ Objectifs enregistrés — Stop : {obj_stop:+.1f}% ({prix_stop_prev:.2f})  ·  Cible : +{obj_cible:.1f}% ({prix_cible_prev:.2f})")
                        st.session_state[f"objectifs_{ticker}"] = False
                        if "pf_positions" in st.session_state:
                            del st.session_state["pf_positions"]
                        st.rerun()
                    if annuler_obj:
                        st.session_state[f"objectifs_{ticker}"] = False
                        st.rerun()

                # Formulaire de vente partielle ou totale
                if st.session_state.get(f"vendre_{ticker}"):
                    with st.form(key=f"form_vente_{ticker}"):
                        st.markdown(f"**Vendre {ticker}** — tu as **{pos['quantite']}** unités "
                                    f"· CUMP {pos['prix_moyen']:.4f}")
                        vc1, vc2, vc3, vc4 = st.columns(4)
                        qty_vente  = vc1.number_input(
                            "Quantité à vendre", min_value=0.0001,
                            max_value=float(pos["quantite"]),
                            value=float(pos["quantite"]),
                            format="%.6f", key=f"qv_{ticker}")
                        px_vente   = vc2.number_input(
                            "Prix de vente", min_value=0.0001,
                            value=float(pos["prix_actuel"] or pos["prix_moyen"]),
                            format="%.4f", key=f"pv_{ticker}")
                        date_vente = vc3.date_input("Date", key=f"dv_{ticker}")
                        notes_v    = vc4.text_input("Notes", key=f"nv_{ticker}",
                                                     placeholder="signal VENDRE atteint")

                        # Frais de vente selon broker
                        frais_v_auto = _calculer_frais_broker(
                            px_vente * qty_vente, broker_config, "vente")
                        frais_v = st.number_input(
                            f"Frais broker ({broker_nom_sel})",
                            min_value=0.0, value=frais_v_auto, format="%.4f",
                            key=f"fv_{ticker}_{broker_key}")

                        # Aperçu P&L avant confirmation
                        pnl_brut    = round((px_vente - pos["prix_moyen"]) * qty_vente, 2)
                        pnl_net     = round(pnl_brut - frais_v, 2)
                        base        = pos["prix_moyen"] * qty_vente
                        pnl_pct_pr  = round(pnl_net / base * 100, 2) if base else 0.0
                        impots, pnl_fi, taux_eff = _net_apres_impots(pnl_net, tax_regime, tmi_val)

                        col_pv1, col_pv2, col_pv3 = st.columns(3)
                        col_pv1.metric("P&L brut",          f"{pnl_brut:+.2f}")
                        col_pv2.metric("P&L net (après frais)", f"{pnl_net:+.2f}",
                                        delta=f"{pnl_pct_pr:+.2f}%")
                        col_pv3.metric(f"Après impôts (~{taux_eff:.0f}%)",
                                        f"{pnl_fi:+.2f}",
                                        delta=f"− {impots:.2f} estimés",
                                        delta_color="inverse")

                        confirmer = st.form_submit_button("✅ Confirmer", type="primary")
                        annuler   = st.form_submit_button("Annuler")

                    if confirmer:
                        try:
                            trade = ajouter_vente(ticker, px_vente, qty_vente,
                                                   date_vente.strftime("%Y-%m-%d"),
                                                   notes_v, frais=frais_v)
                            st.success(f"✅ Vente enregistrée — P&L net : "
                                       f"{trade['pnl_eur']:+.2f} ({trade['pnl_pct']:+.2f}%)")
                            del st.session_state[f"vendre_{ticker}"]
                            if "pf_positions" in st.session_state:
                                del st.session_state["pf_positions"]
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                    if annuler:
                        del st.session_state[f"vendre_{ticker}"]
                        st.rerun()

                # Journal des transactions (expandable)
                with st.expander(f"📋 Journal des transactions {ticker}"):
                    txs = lister_transactions(ticker)
                    if txs:
                        df_tx = pd.DataFrame([{
                            "Date":     t["date"],
                            "Type":     "🟢 Achat" if t["type"] == "achat" else "🔴 Vente",
                            "Prix":     t["prix"],
                            "Qté":      t["quantite"],
                            "Frais":    t.get("frais", 0.0),
                            "P&L net":  t.get("pnl_eur", ""),
                            "CUMP réf": t.get("prix_moyen_achat", ""),
                            "Notes":    t.get("notes", ""),
                        } for t in txs])
                        st.dataframe(df_tx, use_container_width=True, hide_index=True,
                            column_config={
                                "Prix":     st.column_config.NumberColumn(
                                    "Prix", format="%.4f",
                                    help="Prix unitaire auquel l'ordre a été exécuté."),
                                "Qté":      st.column_config.NumberColumn(
                                    "Qté", format="%.6f",
                                    help="Nombre d'unités achetées ou vendues."),
                                "Frais":    st.column_config.NumberColumn(
                                    "Frais", format="%.4f €",
                                    help=_TOOLTIPS["frais"]),
                                "P&L net":  st.column_config.NumberColumn(
                                    "P&L net", format="%.2f",
                                    help=_TOOLTIPS["pnl_net"]),
                                "CUMP réf": st.column_config.NumberColumn(
                                    "CUMP réf", format="%.4f",
                                    help="CUMP au moment de la vente — sert de base au calcul du P&L."),
                            })

    # --- Note ---
    with st.expander("ℹ️ Signaux de sortie & méthode CUMP"):
        st.markdown("""
**Méthode de calcul : CUMP** (Coût Unitaire Moyen Pondéré)
À chaque achat, le prix moyen est recalculé. Le P&L de chaque vente est calculé sur ce prix moyen.
C'est la méthode standard utilisée par les brokers français (Boursorama, Trade Republic…).

| Signal | Condition | Action suggérée |
|--------|-----------|-----------------|
| 🟢 **TENIR** | Score > +0.05 ET perte < 4% | Conserver |
| 🟡 **SURVEILLER** | Score entre -0.10 et +0.05 OU perte entre 4% et 8% | Attention |
| 🔴 **VENDRE** | Score < -0.10 OU perte > 8% (stop-loss) | Sortir |
""")

    st.divider()

    # --- Historique des ventes (toujours visible) ---
    historique = lister_historique()
    if historique:
        st.subheader("📜 Historique des ventes")

        total_trades  = len(historique)
        trades_gains  = [t for t in historique if t["pnl_eur"] > 0]
        pnl_total     = round(sum(t["pnl_eur"] for t in historique), 2)
        win_rate      = round(len(trades_gains) / total_trades * 100) if total_trades else 0

        # Totaux avec frais
        total_frais = round(sum(t.get("frais", 0.0) for t in historique), 2)
        ha1, ha2, ha3, ha4 = st.columns(4)
        ha1.metric("Trades", f"{total_trades}  ({len(trades_gains)}✅ / {total_trades - len(trades_gains)}❌)")
        ha2.metric("Win rate", f"{win_rate} %")
        ha3.metric("P&L net total (après frais)", f"{pnl_total:+.2f}")
        ha4.metric("Frais broker payés", f"{total_frais:.2f}")

        # Impôts estimés sur l'ensemble (gains uniquement)
        gains_total = sum(t["pnl_eur"] for t in historique if t["pnl_eur"] > 0)
        _, _, taux_glob = _net_apres_impots(gains_total, tax_regime, tmi_val)
        impots_glob = round(gains_total * taux_glob / 100, 2) if gains_total > 0 else 0.0
        if gains_total > 0:
            st.caption(f"🧾 Impôts estimés sur les gains ({taux_glob:.0f}% {regime_label.split('—')[0].strip()}) "
                       f": **{impots_glob:.2f}** · "
                       f"P&L net après impôts estimé : **{pnl_total - impots_glob:+.2f}**  "
                       f"*(estimation par trade — les pertes compensent les gains à l'année)*")

        # Construction du tableau avec colonne de suppression
        df_hist = pd.DataFrame([{
            "🗑️":               False,          # colonne de sélection pour suppression
            "_id":              t["id"],         # identifiant interne (caché)
            "Ticker":           t["ticker"],
            "Date":             t["date"],
            "Prix vente":       t.get("prix_vente", t.get("prix", "")),
            "Qté":              t["quantite"],
            "CUMP achat":       t["prix_moyen_achat"],
            "Frais":            t.get("frais", 0.0),
            "P&L brut":         t.get("pnl_brut", t["pnl_eur"]),
            "P&L net":          t["pnl_eur"],
            "P&L (%)":          t["pnl_pct"],
            "Notes":            t.get("notes", ""),
        } for t in historique])

        edited_hist = st.data_editor(
            df_hist.drop(columns=["_id"]),
            use_container_width=True,
            hide_index=True,
            key="hist_editor",
            column_config={
                "🗑️":          st.column_config.CheckboxColumn(
                    "🗑️", width="small",
                    help="Cocher pour marquer la ligne à supprimer, puis cliquer sur le bouton rouge."),
                "Ticker":      st.column_config.TextColumn("Ticker", help=_TOOLTIPS["ticker"]),
                "Prix vente":  st.column_config.NumberColumn(
                    "Prix vente", format="%.4f", disabled=True,
                    help="Prix unitaire auquel tu as vendu."),
                "Qté":         st.column_config.NumberColumn(
                    "Qté", format="%.6f", disabled=True,
                    help="Nombre d'unités vendues."),
                "CUMP achat":  st.column_config.NumberColumn(
                    "CUMP achat", format="%.4f", disabled=True,
                    help=_TOOLTIPS["cump"]),
                "Frais":       st.column_config.NumberColumn(
                    "Frais", format="%.4f", disabled=True,
                    help=_TOOLTIPS["frais"]),
                "P&L brut":    st.column_config.NumberColumn(
                    "P&L brut", format="%.2f", disabled=True,
                    help=_TOOLTIPS["pnl_brut"]),
                "P&L net":     st.column_config.NumberColumn(
                    "P&L net", format="%.2f", disabled=True,
                    help=_TOOLTIPS["pnl_net"]),
                "P&L (%)":     st.column_config.NumberColumn(
                    "P&L (%)", format="%.2f %%", disabled=True,
                    help=_TOOLTIPS["pnl_pct"]),
                "Date":        st.column_config.TextColumn("Date", disabled=True),
                "Notes":       st.column_config.TextColumn("Notes", disabled=True),
            },
        )

        # Lignes cochées pour suppression
        ids_a_supprimer = [
            df_hist.iloc[i]["_id"]
            for i, row in edited_hist.iterrows()
            if row["🗑️"]
        ]

        del_col, csv_col = st.columns([1, 3])
        if ids_a_supprimer:
            if del_col.button(
                f"🗑️ Supprimer {len(ids_a_supprimer)} ligne(s)",
                type="primary",
                key="suppr_hist",
            ):
                for vid in ids_a_supprimer:
                    supprimer_vente(vid)
                st.rerun()
        else:
            del_col.caption("Cocher une ligne pour la supprimer")

        csv_hist = df_hist.drop(columns=["🗑️", "_id"]).to_csv(index=False).encode("utf-8")
        csv_col.download_button("📥 Exporter CSV", data=csv_hist,
                                 file_name="historique_ventes.csv", mime="text/csv")


# ===========================================================================
# ONGLET 4 — BACKTEST
# ===========================================================================

with tab_backtest:
    st.subheader("Backtest")

    bt1, bt2 = st.columns(2)
    with bt1:
        bt_ticker  = _ticker_selectbox("Ticker", key="ticker_backtest")
        bt_debut   = st.text_input("Début", value="2023-01-01", key="bt_debut")
        bt_fin     = st.text_input("Fin",   value="2024-12-31", key="bt_fin")
    with bt2:
        bt_mode    = st.radio("Mode", ["multi", "technique"],
                              help="multi = technique + macro + risque | technique = technique seul")
        bt_capital = st.number_input("Capital ($)", value=10000, step=1000)

    lancer_bt = st.button("Lancer le backtest", type="primary", key="lancer_bt")

    if lancer_bt:
        with st.spinner("Backtest en cours..."):
            bt_result = run_backtest(
                bt_ticker, debut=bt_debut, fin=bt_fin,
                capital=float(bt_capital), mode=bt_mode
            )

        col_b1, col_b2, col_b3, col_b4 = st.columns(4)
        col_b1.metric("Capital final", f"{bt_result['valeur_fin']:,} $")
        col_b2.metric("Rendement",     f"{bt_result['rendement']} %")
        col_b3.metric("Nb trades",     len(bt_result["trades"]))
        col_b4.metric("Mode",          bt_result["mode"])

        # --- Graphique prix + signaux buy/sell (Plotly) ---
        df_bt = bt_result.get("df")
        if df_bt is not None and not df_bt.empty:
            trades = bt_result["trades"]
            achats = {t["date_achat"]: t["prix_achat"] for t in trades}
            ventes = {t["date"]:       t["prix_vente"]  for t in trades}

            dates_idx = [str(d)[:10] for d in df_bt.index]

            fig_bt = go.Figure()
            fig_bt.add_trace(go.Candlestick(
                x=df_bt.index,
                open=df_bt["Open"], high=df_bt["High"],
                low=df_bt["Low"],   close=df_bt["Close"],
                name="Prix", increasing_line_color="#2ecc71",
                decreasing_line_color="#e74c3c"
            ))

            # Signaux achat (triangles verts)
            if achats:
                fig_bt.add_trace(go.Scatter(
                    x=list(achats.keys()), y=list(achats.values()),
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=14,
                                color="#27ae60", line=dict(width=1, color="white")),
                    name="Achat"
                ))
            # Signaux vente (triangles rouges)
            if ventes:
                fig_bt.add_trace(go.Scatter(
                    x=list(ventes.keys()), y=list(ventes.values()),
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=14,
                                color="#e74c3c", line=dict(width=1, color="white")),
                    name="Vente"
                ))

            fig_bt.update_layout(
                title=f"Prix + signaux — {bt_ticker}",
                xaxis_rangeslider_visible=False,
                height=420,
                margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(orientation="h", y=1.08)
            )
            st.plotly_chart(fig_bt, use_container_width=True)

        # --- Courbe d'équité ---
        if bt_result["equity"]:
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=[e["date"]   for e in bt_result["equity"]],
                y=[e["valeur"] for e in bt_result["equity"]],
                mode="lines+markers", name="Capital",
                line=dict(color="#2ecc71", width=2),
                fill="tozeroy", fillcolor="rgba(46,204,113,0.08)"
            ))
            fig_eq.update_layout(title="Courbe d'équité", height=260,
                                 margin=dict(l=0, r=0, t=35, b=0))
            st.plotly_chart(fig_eq, use_container_width=True)

        # --- Détail des trades ---
        if bt_result["trades"]:
            st.markdown("**Détail des trades**")
            df_trades = pd.DataFrame(bt_result["trades"])
            df_trades["résultat"] = df_trades["pnl"].apply(
                lambda x: "✅" if x > 0 else "❌"
            )
            cols_ordre = ["résultat", "date_achat", "prix_achat",
                          "date", "prix_vente", "pnl", "pnlnet"]
            cols_ordre = [c for c in cols_ordre if c in df_trades.columns]
            st.dataframe(df_trades[cols_ordre], use_container_width=True, hide_index=True)

# ===========================================================================
# Onglet Calibration
# ===========================================================================

with tab_calib:
    from calibration.calibrator import (
        calibrer_global, charger_poids_custom,
        sauvegarder_poids, supprimer_poids_custom, HORIZON_JOURS,
    )
    from orchestrator.scoring import POIDS as POIDS_DEFAUT

    st.subheader("Calibration des poids des agents",
                 help="Mesure la précision de chaque agent sur tes analyses passées. "
                      "Un agent qui prédit bien la direction du cours mérite un poids plus élevé. "
                      "Les poids suggérés sont calculés automatiquement — tu peux les appliquer ou garder les défauts.")

    st.markdown(
        "**Comment ça marche :** à chaque analyse, l'app enregistre le score de chaque agent "
        "et le prix courant. "
        f"Après **{HORIZON_JOURS} jours**, elle vérifie si le cours a bien bougé dans le sens prédit. "
        "Plus un agent est précis, plus son poids est augmenté."
    )

    poids_custom = charger_poids_custom()
    if poids_custom:
        st.success("✅ Poids custom actifs — les poids par défaut ont été remplacés par tes poids calibrés.")
        if st.button("↩️ Revenir aux poids par défaut"):
            supprimer_poids_custom()
            st.success("Poids réinitialisés aux valeurs par défaut.")
            st.rerun()

    st.divider()

    with st.spinner("Calcul de la calibration en cours…"):
        res = calibrer_global()

    nb_points = res.get("nb_points_total", 0)
    nb_tickers = res.get("nb_tickers", 0)

    col_i1, col_i2 = st.columns(2)
    col_i1.metric("Points évaluables", nb_points,
                  help=f"Analyses de plus de {HORIZON_JOURS} jours avec prix enregistré")
    col_i2.metric("Tickers couverts", nb_tickers)

    MIN_REQUIS = 5
    if nb_points < MIN_REQUIS:
        jours_restants = HORIZON_JOURS
        st.info(
            f"📊 Pas encore assez de données pour calibrer ({nb_points}/{MIN_REQUIS} points évaluables).\n\n"
            f"Lance **plusieurs analyses** sur les prochains jours — "
            f"les résultats apparaîtront automatiquement après **{jours_restants} jours**."
        )
    else:
        agents       = res["agents"]
        poids_sugg   = res["poids_suggeres"]

        # --- Tableau comparatif ---
        st.subheader("Précision par agent")
        lignes = []
        for agent in sorted(POIDS_DEFAUT.keys()):
            if agent in ("risque",):
                continue
            s    = agents.get(agent, {})
            ex   = s.get("exactitude")
            nb   = s.get("nb_predictions", 0)
            corr = s.get("nb_correctes", 0)
            p_def = POIDS_DEFAUT.get(agent, 0)
            p_sug = poids_sugg.get(agent, p_def)
            p_cur = poids_custom.get(agent, p_def) if poids_custom else p_def

            if ex is None:
                ex_str    = "—"
                tendance  = "📊 Données insuffisantes"
            elif ex >= 0.65:
                ex_str   = f"{ex*100:.1f}%"
                tendance = "🟢 Fiable"
            elif ex >= 0.55:
                ex_str   = f"{ex*100:.1f}%"
                tendance = "🟡 Correct"
            elif ex >= 0.45:
                ex_str   = f"{ex*100:.1f}%"
                tendance = "🟠 Aléatoire"
            else:
                ex_str   = f"{ex*100:.1f}%"
                tendance = "🔴 Contre-productif"

            lignes.append({
                "Agent":         agent,
                "Prédictions":   nb,
                "Correctes":     corr,
                "Exactitude":    ex_str,
                "Appréciation":  tendance,
                "Poids actuel":  round(p_cur, 4),
                "Poids suggéré": round(p_sug, 4),
            })

        df_calib = pd.DataFrame(lignes)
        st.dataframe(df_calib, use_container_width=True, hide_index=True)

        # --- Graphique comparaison poids ---
        st.subheader("Comparaison des poids")
        agents_labels  = df_calib["Agent"].tolist()
        poids_actuels  = df_calib["Poids actuel"].tolist()
        poids_suggeres = df_calib["Poids suggéré"].tolist()

        fig_poids = go.Figure()
        fig_poids.add_trace(go.Bar(
            name="Poids actuel",
            x=agents_labels, y=poids_actuels,
            marker_color="rgba(91,155,213,0.8)",
        ))
        fig_poids.add_trace(go.Bar(
            name="Poids suggéré",
            x=agents_labels, y=poids_suggeres,
            marker_color="rgba(46,204,113,0.8)",
        ))
        fig_poids.update_layout(
            barmode="group", height=320,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", y=1.05),
            yaxis_title="Poids",
        )
        st.plotly_chart(fig_poids, use_container_width=True)

        # --- Bouton appliquer ---
        st.divider()
        col_btn1, col_btn2 = st.columns([1, 3])
        if col_btn1.button("✅ Appliquer les poids suggérés", type="primary"):
            sauvegarder_poids(poids_sugg)
            st.success(
                "Poids sauvegardés dans `config/weights_custom.json`. "
                "Ils seront utilisés dès la prochaine analyse."
            )
            st.rerun()
        col_btn2.caption(
            "Les poids suggérés remplacent les poids par défaut pour toutes les analyses futures. "
            "Tu peux revenir aux défauts à tout moment avec le bouton en haut de page."
        )
