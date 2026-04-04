import os
from dotenv import load_dotenv
from groq import Groq

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


def run(ticker: str) -> dict:
    """
    Orchestre les 7 agents, calcule le score pondéré
    et produit un rapport de décision via LLM.
    """
    print(f"Analyse de {ticker} en cours...\n")

    # --- Collecte des signaux ---
    tech    = analyze_technical(ticker)
    fund    = analyze_fundamental(ticker)
    sent    = analyze_sentiment(ticker)
    risk    = analyze_risk(ticker)
    trends  = analyze_trends(ticker)
    insider = analyze_insider(ticker)
    macro   = analyze_macro()

    # --- Scoring pondéré ---
    scoring = calculer_score(tech, fund, sent, risk, trends, insider, macro)

    # --- Construction du prompt ---
    prompt = f"""
Tu es un assistant spécialisé en analyse financière.
Voici les résultats de 7 agents d'analyse pour l'action {ticker} :

ANALYSE TECHNIQUE :
- Prix actuel   : {tech['prix_actuel']} $
- SMA20         : {tech['sma20']}
- SMA50         : {tech['sma50']}
- RSI           : {tech['rsi']}
- MACD          : {tech['macd']}
- Signal        : {tech['signal']}

ANALYSE FONDAMENTALE :
- Nom           : {fund['nom']}
- Secteur       : {fund['secteur']}
- PER           : {fund['per']}
- Dividende     : {fund['dividende']}
- Capitalisation: {fund['capitalisation']:,} $
- Signal        : {fund['signal']}

ANALYSE SENTIMENT :
- Articles analysés : {sent['articles']}
- Positif           : {sent['positif']}
- Négatif           : {sent['negatif']}
- Neutre            : {sent['neutre']}
- Signal            : {sent['signal']}

ANALYSE RISQUE :
- Volatilité    : {risk['volatilite']} %
- Drawdown max  : {risk['drawdown_max']} %
- Niveau risque : {risk['risque']}

GOOGLE TRENDS :
- Tendance      : {trends['tendance']}
- Variation     : {trends['variation']} %
- Ratio tendance: {trends['ratio_tendance']}
- Signal        : {trends['signal']}

INSIDER TRADING :
- Nb achats     : {insider['nb_achats']} ({insider['total_achat']:,} $)
- Nb ventes     : {insider['nb_ventes']} ({insider['total_vente']:,} $)
- Ratio         : {insider['ratio']}
- Signal        : {insider['signal']}

CONTEXTE MACRO :
- Taux Fed      : {macro['taux_fed']} %
- Chômage       : {macro['chomage']} %
- Confiance     : {macro['confiance']}
- Spread 10/2   : {macro['spread_10_2']}
- Environnement : {macro['environnement']}
- Signal        : {macro['signal']}

SCORE PONDÉRÉ FINAL :
- Technique    : {scoring['scores']['technique']} × {scoring['poids']['technique']}
- Fondamental  : {scoring['scores']['fondamental']} × {scoring['poids']['fondamental']}
- Sentiment    : {scoring['scores']['sentiment']} × {scoring['poids']['sentiment']}
- Trends       : {scoring['scores']['trends']} × {scoring['poids']['trends']}
- Insider      : {scoring['scores']['insider']} × {scoring['poids']['insider']}
- Macro        : {scoring['scores']['macro']} × {scoring['poids']['macro']}
- Mult risque  : {scoring['scores']['multiplicateur']}
- Mult macro   : {scoring['scores']['mult_macro']}
- Score final  : {scoring['score_final']} / 1.0
- Décision     : {scoring['decision']}

Rédige un rapport de décision clair et structuré en français.
Mets en avant le score pondéré et explique pourquoi chaque agent a contribué positivement ou négativement.
Conclus avec la recommandation finale issue du score : {scoring['decision']}.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    return {
        "rapport":  response.choices[0].message.content or "",
        "scoring":  scoring,
        "tech":     tech,
        "fund":     fund,
        "sent":     sent,
        "risk":     risk,
        "trends":   trends,
        "insider":  insider,
        "macro":    macro,
    }


if __name__ == "__main__":
    resultat = run("AAPL")
    print(resultat["rapport"])
    print(f"\nScore final : {resultat['scoring']['score_final']}")
    print(f"Décision    : {resultat['scoring']['decision']}")