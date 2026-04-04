import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import json
import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.market_data import get_stock_data, get_stock_info, get_news
from data.asset_type import detect_asset_type
from orchestrator.orchestrator import run
from backtesting.backtest import run_backtest
from ta.trend import SMAIndicator
from ta.volatility import BollingerBands

st.set_page_config(
    page_title="Finance Agents",
    page_icon="📈",
    layout="wide"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _icone_signal(signal):
    return {"ACHETER": "🟢", "VENDRE": "🔴"}.get(signal, "🟡")

def _icone_risque(risque):
    return {"FAIBLE": "🟢", "ELEVE": "🔴"}.get(risque, "🟡")

def _badge(label, value, color="normal"):
    colors = {"green": "#1a7a4a", "red": "#c0392b", "normal": "#333"}
    bg     = {"green": "#d4edda", "red":  "#f8d7da", "normal": "#f0f0f0"}
    return (f'<span style="background:{bg[color]};color:{colors[color]};'
            f'padding:3px 10px;border-radius:12px;font-weight:600">{label}: {value}</span>')


# ---------------------------------------------------------------------------
# Onglets principaux
# ---------------------------------------------------------------------------

st.title("📈 Finance Agents — Aide à la décision")
tab_analyse, tab_scanner, tab_backtest = st.tabs(["🔍 Analyse", "📋 Scanner", "📊 Backtest"])


# ===========================================================================
# ONGLET 1 — ANALYSE
# ===========================================================================

with tab_analyse:

    # --- Sidebar ---
    with st.sidebar:
        st.header("Paramètres")
        ticker = st.text_input("Ticker", value="AAPL",
                               help="AAPL, MC.PA, BTC-USD, EURUSD=X …").upper().strip()
        period = st.selectbox("Période graphique", ["1mo", "3mo", "6mo", "1y", "2y"], index=1)
        lancer = st.button("Analyser", type="primary", use_container_width=True)

    if not lancer:
        st.info("Entre un ticker dans la sidebar et clique sur **Analyser**.\n\n"
                "Exemples : `AAPL` (US), `MC.PA` (Paris), `BTC-USD` (crypto), `EURUSD=X` (forex)")
        st.stop()

    asset_type = detect_asset_type(ticker)

    # --- Analyse complète ---
    with st.spinner(f"Analyse de {ticker} en cours..."):
        resultat = run(ticker, with_llm=True)

    tech    = resultat["tech"]
    fund    = resultat["fund"]
    sent    = resultat["sent"]
    risk    = resultat["risk"]
    trends  = resultat["trends"]
    insider = resultat["insider"]
    macro   = resultat["macro"]
    scoring = resultat["scoring"]

    # --- Header ---
    try:
        info = get_stock_info(ticker)
        nom  = info.get("nom", ticker)
        cap  = info.get("capitalisation", 0)
        cap_str = f"{cap/1e9:.0f} Md$" if cap else "N/A"
    except Exception:
        nom, cap_str = ticker, "N/A"

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
        c4.metric("Secteur", info.get("secteur", "N/A") if 'info' in dir() else "N/A")

    st.divider()

    # --- Contexte macro ---
    if macro:
        st.subheader("Contexte macroéconomique")
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

    # --- Graphique prix (uniquement pour les actifs avec OHLCV) ---
    try:
        df = get_stock_data(ticker, period=period)
        if not df.empty:
            st.subheader("Historique des prix")

            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name="Prix"
            ))

            sma20    = SMAIndicator(df["Close"], window=20).sma_indicator()
            sma50    = SMAIndicator(df["Close"], window=50).sma_indicator()
            bb_ind   = BollingerBands(df["Close"], window=20, window_dev=2)

            fig.add_trace(go.Scatter(x=df.index, y=sma20, name="SMA 20",
                                     line=dict(color="orange", width=1.5)))
            fig.add_trace(go.Scatter(x=df.index, y=sma50, name="SMA 50",
                                     line=dict(color="blue", width=1.5)))
            fig.add_trace(go.Scatter(x=df.index, y=bb_ind.bollinger_hband(),
                                     name="BB Haute",
                                     line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dash")))
            fig.add_trace(go.Scatter(x=df.index, y=bb_ind.bollinger_lband(),
                                     name="BB Basse",
                                     line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dash"),
                                     fill="tonexty", fillcolor="rgba(150,150,150,0.05)"))

            fig.update_layout(xaxis_rangeslider_visible=False, height=450,
                              margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)
            st.divider()
    except Exception:
        pass

    # --- Signaux des agents ---
    st.subheader("Signaux des agents")

    agents_affiches = []

    agents_affiches.append(("Technique", tech["signal"],
                             f"RSI : {tech['rsi']} | MACD : {tech['macd']}",
                             f"Score : {tech.get('score_final', 'N/A')}"))

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

    cols = st.columns(len(agents_affiches))
    for col, (nom_agent, signal, ligne1, ligne2) in zip(cols, agents_affiches):
        icone = _icone_signal(signal) if nom_agent != "Risque" else _icone_risque(signal)
        with col:
            st.metric(nom_agent, f"{icone} {signal}")
            st.caption(ligne1)
            st.caption(ligne2)

    st.divider()

    # --- Score pondéré ---
    st.subheader("Score pondéré final")

    decision = scoring["decision"]
    score    = scoring["score_final"]
    couleur  = "green" if decision == "ACHETER" else ("red" if decision == "VENDRE" else "normal")

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Score final",  f"{score} / 1.0")
    sc2.metric("Décision",     f"{_icone_signal(decision)} {decision}")
    sc3.metric("Mult risque",  scoring["scores"]["multiplicateur"])
    sc4.metric("Mult macro",   scoring["scores"]["mult_macro"])

    # Barre de score visuelle
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

            st.dataframe(
                df_scan.style.applymap(style_decision, subset=["Décision"]),
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
# ONGLET 3 — BACKTEST
# ===========================================================================

with tab_backtest:
    st.subheader("Backtest")

    bt1, bt2 = st.columns(2)
    with bt1:
        bt_ticker = st.text_input("Ticker", value="AAPL", key="bt_ticker").upper()
        bt_debut  = st.text_input("Début",  value="2023-01-01", key="bt_debut")
        bt_fin    = st.text_input("Fin",    value="2024-12-31", key="bt_fin")
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
        col_b1.metric("Capital final",  f"{bt_result['valeur_fin']:,} $")
        col_b2.metric("Rendement",      f"{bt_result['rendement']} %")
        col_b3.metric("Nb trades",      len(bt_result["trades"]))
        col_b4.metric("Mode",           bt_result["mode"])

        if bt_result["equity"]:
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=[e["date"]   for e in bt_result["equity"]],
                y=[e["valeur"] for e in bt_result["equity"]],
                mode="lines+markers",
                name="Capital",
                line=dict(color="#2ecc71", width=2)
            ))
            fig_eq.update_layout(
                title="Courbe d'équité",
                height=300,
                margin=dict(l=0, r=0, t=30, b=0)
            )
            st.plotly_chart(fig_eq, use_container_width=True)

        if bt_result["trades"]:
            st.markdown("**Détail des trades**")
            df_trades = pd.DataFrame(bt_result["trades"])
            df_trades["résultat"] = df_trades["pnl"].apply(
                lambda x: "✅" if x > 0 else "❌"
            )
            st.dataframe(df_trades, use_container_width=True)
