import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.market_data import get_stock_data, get_stock_info, get_news
from agents.technical import analyze_technical
from agents.fundamental import analyze_fundamental
from agents.sentiment import analyze_sentiment
from agents.risk import analyze_risk
from agents.trends import analyze_trends
from agents.insider import analyze_insider
from agents.macro import analyze_macro
from orchestrator.orchestrator import run
from backtesting.backtest import run_backtest
from ta.trend import SMAIndicator
from ta.volatility import BollingerBands

st.set_page_config(
    page_title="Finance Agents",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Système multi-agents — Aide à la décision financière")

# --- Sidebar ---
with st.sidebar:
    st.header("Paramètres")
    ticker = st.text_input("Ticker", value="AAPL").upper()
    period = st.selectbox("Période", ["1mo", "3mo", "6mo", "1y", "2y"], index=1)
    lancer = st.button("Analyser", type="primary", use_container_width=True)
    st.divider()
    st.subheader("Backtest")
    lancer_backtest = st.checkbox("Inclure le backtest")
    debut_bt = st.text_input("Début", value="2023-01-01")
    fin_bt   = st.text_input("Fin",   value="2024-12-31")

if not lancer:
    st.info("Entre un ticker et clique sur Analyser.")
    st.stop()

# --- Chargement ---
with st.spinner("Analyse en cours..."):
    df      = get_stock_data(ticker, period=period)
    info    = get_stock_info(ticker)
    tech    = analyze_technical(ticker, period=period)
    fund    = analyze_fundamental(ticker)
    sent    = analyze_sentiment(ticker)
    risk    = analyze_risk(ticker, period=period)
    trends  = analyze_trends(ticker)
    insider = analyze_insider(ticker)
    macro   = analyze_macro()

# --- Header ---
st.subheader(f"{info['nom']} — {ticker}")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Prix actuel",    f"{tech['prix_actuel']} $")
col2.metric("Secteur",        info['secteur'])
col3.metric("Capitalisation", f"{info['capitalisation'] / 1e9:.0f} Md$")
col4.metric("PER",            f"{info['per']}")

st.divider()

# --- Contexte macro ---
st.subheader("Contexte macroéconomique")

def couleur_macro(env):
    if env == "FAVORABLE":   return "🟢"
    elif env == "DÉFAVORABLE": return "🔴"
    return "🟡"

cm1, cm2, cm3, cm4, cm5 = st.columns(5)
cm1.metric("Taux Fed",    f"{macro['taux_fed']} %")
cm2.metric("Chômage",     f"{macro['chomage']} %")
cm3.metric("Confiance",   f"{macro['confiance']}")
cm4.metric("Spread 10/2", f"{macro['spread_10_2']}")
cm5.metric("Environnement", f"{couleur_macro(macro['environnement'])} {macro['environnement']}")

st.divider()

# --- Graphique prix ---
st.subheader("Historique des prix")

fig = go.Figure()
fig.add_trace(go.Candlestick(
    x=df.index,
    open=df["Open"],
    high=df["High"],
    low=df["Low"],
    close=df["Close"],
    name="Prix"
))

sma20    = SMAIndicator(df["Close"], window=20).sma_indicator()
sma50    = SMAIndicator(df["Close"], window=50).sma_indicator()
bb       = BollingerBands(df["Close"], window=20, window_dev=2)
bb_haute = bb.bollinger_hband()
bb_basse = bb.bollinger_lband()

fig.add_trace(go.Scatter(x=df.index, y=sma20, name="SMA 20",
    line=dict(color="orange", width=1.5)))
fig.add_trace(go.Scatter(x=df.index, y=sma50, name="SMA 50",
    line=dict(color="blue", width=1.5)))
fig.add_trace(go.Scatter(x=df.index, y=bb_haute, name="BB Haute",
    line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dash")))
fig.add_trace(go.Scatter(x=df.index, y=bb_basse, name="BB Basse",
    line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dash"),
    fill="tonexty", fillcolor="rgba(150,150,150,0.05)"))

fig.update_layout(
    xaxis_rangeslider_visible=False,
    height=450,
    margin=dict(l=0, r=0, t=0, b=0)
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- Signaux des agents ---
st.subheader("Signaux des agents")

def couleur_signal(signal):
    if signal == "ACHETER": return "🟢"
    elif signal == "VENDRE": return "🔴"
    return "🟡"

def couleur_risque(risque):
    if risque == "FAIBLE": return "🟢"
    elif risque == "ELEVE": return "🔴"
    return "🟡"

c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    st.metric("Technique", f"{couleur_signal(tech['signal'])} {tech['signal']}")
    st.caption(f"RSI : {tech['rsi']} | MACD : {tech['macd']}")
    st.caption(f"BB : {tech['bb_position']}% | ATR : {tech['atr_relatif']}%")

with c2:
    st.metric("Fondamental", f"{couleur_signal(fund['signal'])} {fund['signal']}")
    st.caption(f"PER : {fund['per']} | Div : {fund['dividende']}")

with c3:
    st.metric("Sentiment", f"{couleur_signal(sent['signal'])} {sent['signal']}")
    st.caption(f"✅ {sent['positif']} | ❌ {sent['negatif']} | ➖ {sent['neutre']}")

with c4:
    st.metric("Risque", f"{couleur_risque(risk['risque'])} {risk['risque']}")
    st.caption(f"Volatilité : {risk['volatilite']}% | DD : {risk['drawdown_max']}%")

with c5:
    st.metric("Trends", f"{couleur_signal(trends['signal'])} {trends['tendance']}")
    st.caption(f"Variation : {trends['variation']}% | Ratio : {trends['ratio_tendance']}")

with c6:
    st.metric("Insider", f"{couleur_signal(insider['signal'])} {insider['signal']}")
    st.caption(f"🟢 {insider['nb_achats']} achats | 🔴 {insider['nb_ventes']} ventes")
    st.caption(f"Ratio : {insider['ratio']}")

st.divider()

# --- Score pondéré + Rapport LLM ---
with st.spinner("Génération du rapport..."):
    resultat = run(ticker)

scoring = resultat["scoring"]

st.subheader("Score pondéré")
col_s1, col_s2, col_s3, col_s4 = st.columns(4)
col_s1.metric("Score final",    f"{scoring['score_final']} / 1.0")
col_s2.metric("Décision",       scoring["decision"])
col_s3.metric("Mult risque",    scoring["scores"]["multiplicateur"])
col_s4.metric("Mult macro",     scoring["scores"]["mult_macro"])

st.divider()

st.subheader("Rapport de décision")
st.markdown(resultat["rapport"])

st.divider()

# --- Insider transactions ---
if insider["transactions"]:
    st.subheader("Transactions des dirigeants")
    df_insider = pd.DataFrame(insider["transactions"])
    df_insider["type"] = df_insider["type"].apply(
        lambda x: "🟢 ACHAT" if x == "ACHAT" else "🔴 VENTE"
    )
    st.dataframe(df_insider, use_container_width=True)
    st.divider()

# --- Backtest ---
if lancer_backtest:
    st.subheader("Backtest")

    with st.spinner("Backtest en cours..."):
        bt_result = run_backtest(ticker, debut=debut_bt, fin=fin_bt)

    col_b1, col_b2, col_b3 = st.columns(3)
    col_b1.metric("Capital final", f"{bt_result['valeur_fin']:,} $")
    col_b2.metric("Rendement",     f"{bt_result['rendement']} %")
    col_b3.metric("Nb trades",     len(bt_result["trades"]))

    if bt_result["equity"]:
        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(
            x=[e["date"]   for e in bt_result["equity"]],
            y=[e["valeur"] for e in bt_result["equity"]],
            mode="lines+markers",
            name="Capital",
            line=dict(color="green", width=2)
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

st.divider()

# --- News ---
st.subheader("Dernières news")
news = get_news(ticker)
for article in news:
    st.markdown(f"**{article['titre']}**  \n*{article['source']} — {article['date']}*")