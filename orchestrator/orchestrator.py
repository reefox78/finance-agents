import os
from dotenv import load_dotenv
from groq import Groq

from data.asset_type import detect_asset_type, AGENTS_PAR_TYPE
from agents.technical import analyze_technical
from agents.fundamental import analyze_fundamental
from agents.sentiment import analyze_sentiment
from agents.risk import analyze_risk
from agents.trends import analyze_trends
from agents.insider import analyze_insider
from agents.macro import analyze_macro
from orchestrator.scoring import calculer_score

load_dotenv("config/.env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Labels lisibles pour le prompt LLM
_ASSET_LABELS = {
    "us_stock": "action américaine",
    "eu_stock":  "action européenne",
    "crypto":    "cryptomonnaie",
    "forex":     "paire de devises (forex)",
}


def _build_prompt(ticker: str, asset_type: str, tech: dict, fund: dict,
                  sent: dict, risk: dict, trends: dict, insider: dict,
                  macro: dict, scoring: dict) -> str:
    """Construit le prompt LLM en n'incluant que les agents actifs."""

    label = _ASSET_LABELS.get(asset_type, asset_type)
    lines = [
        f"Tu es un assistant spécialisé en analyse financière.",
        f"Voici les résultats d'analyse pour {ticker} ({label}) :\n",
    ]

    # --- Technique (toujours présent) ---
    lines += [
        "ANALYSE TECHNIQUE :",
        f"- Prix actuel : {tech['prix_actuel']}",
        f"- SMA20       : {tech['sma20']}",
        f"- SMA50       : {tech['sma50']}",
        f"- RSI         : {tech['rsi']}",
        f"- MACD        : {tech['macd']}",
        f"- Signal      : {tech['signal']}\n",
    ]

    # --- Fondamental (actions uniquement) ---
    if fund:
        lines += [
            "ANALYSE FONDAMENTALE :",
            f"- Nom           : {fund['nom']}",
            f"- Secteur       : {fund['secteur']}",
            f"- PER           : {fund['per']}",
            f"- Dividende     : {fund['dividende']}",
            f"- Capitalisation: {fund.get('capitalisation', 'N/A')}",
            f"- Signal        : {fund['signal']}\n",
        ]

    # --- Sentiment ---
    if sent:
        lines += [
            "ANALYSE SENTIMENT :",
            f"- Articles analysés : {sent['articles']}",
            f"- Positif / Négatif / Neutre : {sent['positif']} / {sent['negatif']} / {sent['neutre']}",
            f"- Signal            : {sent['signal']}\n",
        ]

    # --- Risque (toujours présent) ---
    lines += [
        "ANALYSE RISQUE :",
        f"- Volatilité    : {risk['volatilite']} %",
        f"- Drawdown max  : {risk['drawdown_max']} %",
        f"- Niveau risque : {risk['risque']}\n",
    ]

    # --- Trends ---
    if trends:
        lines += [
            "GOOGLE TRENDS :",
            f"- Tendance : {trends['tendance']}",
            f"- Variation: {trends['variation']} %",
            f"- Signal   : {trends['signal']}\n",
        ]

    # --- Insider (actions US uniquement) ---
    if insider:
        lines += [
            "INSIDER TRADING :",
            f"- Achats : {insider['nb_achats']} ({insider['total_achat']:,} $)",
            f"- Ventes : {insider['nb_ventes']} ({insider['total_vente']:,} $)",
            f"- Signal : {insider['signal']}\n",
        ]

    # --- Macro ---
    if macro:
        lines.append("CONTEXTE MACRO :")
        if macro.get("market") == "eu":
            lines += [
                f"- Taux BCE   : {macro.get('taux_bce')} %",
                f"- Chômage EU : {macro.get('chomage')} %",
                f"- Confiance  : {macro.get('confiance')}",
                f"- Taux 10 ans: {macro.get('taux_10y')} %",
            ]
        else:
            lines += [
                f"- Taux Fed    : {macro.get('taux_fed')} %",
                f"- Chômage US  : {macro.get('chomage')} %",
                f"- Confiance   : {macro.get('confiance')}",
                f"- Spread 10/2 : {macro.get('spread_10_2')}",
            ]
        lines += [
            f"- Environnement : {macro['environnement']}",
            f"- Signal        : {macro['signal']}\n",
        ]

    # --- Score final ---
    lines += [
        "SCORE PONDÉRÉ FINAL :",
        f"- Technique  : {scoring['scores']['technique']} × {scoring['poids']['technique']}",
    ]
    if fund:
        lines.append(f"- Fondamental: {scoring['scores']['fondamental']} × {scoring['poids']['fondamental']}")
    if sent:
        lines.append(f"- Sentiment  : {scoring['scores']['sentiment']} × {scoring['poids']['sentiment']}")
    if trends:
        lines.append(f"- Trends     : {scoring['scores']['trends']} × {scoring['poids']['trends']}")
    if insider:
        lines.append(f"- Insider    : {scoring['scores']['insider']} × {scoring['poids']['insider']}")
    if macro:
        lines.append(f"- Macro      : {scoring['scores']['macro']} × {scoring['poids']['macro']}")
    lines += [
        f"- Mult risque: {scoring['scores']['multiplicateur']}",
        f"- Mult macro : {scoring['scores']['mult_macro']}",
        f"- Score final: {scoring['score_final']} / 1.0",
        f"- Décision   : {scoring['decision']}\n",
    ]

    lines += [
        "Rédige un rapport de décision clair et structuré en français.",
        "Explique la contribution de chaque agent au score final.",
        f"Conclus avec la recommandation : {scoring['decision']}.",
    ]

    return "\n".join(lines)


def run(ticker: str) -> dict:
    """
    Orchestre les agents selon le type d'actif détecté,
    calcule le score pondéré et produit un rapport LLM.
    """
    asset_type = detect_asset_type(ticker)
    config     = AGENTS_PAR_TYPE[asset_type]

    print(f"Analyse de {ticker} [{asset_type}] en cours...\n")

    # --- Agents toujours actifs ---
    tech = analyze_technical(ticker)
    risk = analyze_risk(ticker)
    sent = analyze_sentiment(ticker) if config["sentiment"] else None

    # --- Agents conditionnels ---
    fund    = analyze_fundamental(ticker)             if config["fondamental"] else None
    trends  = analyze_trends(ticker)                  if config["trends"]      else None
    insider = analyze_insider(ticker)                 if config["insider"]     else None
    macro   = analyze_macro(market=config["macro"])   if config["macro"]       else None

    # --- Scoring (gère les None automatiquement) ---
    scoring = calculer_score(tech, fund, sent, risk, trends, insider, macro)

    # --- Rapport LLM ---
    prompt = _build_prompt(ticker, asset_type, tech, fund, sent,
                           risk, trends, insider, macro, scoring)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    return {
        "ticker":     ticker,
        "asset_type": asset_type,
        "rapport":    response.choices[0].message.content or "",
        "scoring":    scoring,
        "tech":       tech,
        "fund":       fund,
        "sent":       sent,
        "risk":       risk,
        "trends":     trends,
        "insider":    insider,
        "macro":      macro,
    }


if __name__ == "__main__":
    for ticker in ["AAPL", "MC.PA", "BTC-USD", "EURUSD=X"]:
        r = run(ticker)
        print(f"\n[{r['asset_type']}] {ticker} → {r['scoring']['decision']} ({r['scoring']['score_final']})")
