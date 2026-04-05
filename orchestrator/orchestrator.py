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
from agents.options_flow import analyze_options_flow
from agents.sec_filings import analyze_sec_filings
from agents.short_interest import analyze_short_interest
from agents.earnings_surprise import analyze_earnings_surprise
from agents.volume_delta import analyze_volume_delta
from orchestrator.scoring import calculer_score
from data.score_history import enregistrer_score

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
                  macro: dict, options_flow: dict, sec_filings: dict,
                  short_interest: dict, earnings_surprise: dict,
                  volume_delta: dict, scoring: dict) -> str:
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

    # --- Options Flow ---
    if options_flow:
        lines += [
            "OPTIONS FLOW :",
            f"- P/C ratio (vol) : {options_flow.get('pc_ratio_vol')}",
            f"- IV Skew         : {options_flow.get('skew_iv')}",
            f"- Activite anorm. : {options_flow.get('unusual_calls')} calls / {options_flow.get('unusual_puts')} puts",
            f"- Signal          : {options_flow['signal']}\n",
        ]

    # --- SEC Filings ---
    if sec_filings:
        lines += [
            "DEPOTS SEC (8-K) :",
            f"- Filings 90j     : {sec_filings.get('nb_filings')}",
            f"- Dernier depot   : {sec_filings.get('last_date')} | Items : {sec_filings.get('last_items')}",
            f"- Signal          : {sec_filings['signal']}\n",
        ]

    # --- Short Interest ---
    if short_interest:
        lines += [
            "SHORT INTEREST :",
            f"- Short % float   : {short_interest.get('short_pct')} %",
            f"- Jours couverture: {short_interest.get('days_to_cover')}",
            f"- Var. mensuelle  : {short_interest.get('mom_change_pct')} %",
            f"- Signal          : {short_interest['signal']}\n",
        ]

    # --- Earnings Surprise ---
    if earnings_surprise:
        lines += [
            "EARNINGS SURPRISE :",
            f"- Derniere surprise : {earnings_surprise.get('latest_surprise')} %",
            f"- Moyenne 4T        : {earnings_surprise.get('avg_surprise')} %",
            f"- Beats             : {earnings_surprise.get('nb_beats')}/{earnings_surprise.get('nb_quarters')}",
            f"- Prochain earnings : {earnings_surprise.get('next_earnings')}",
            f"- Signal            : {earnings_surprise['signal']}\n",
        ]

    # --- Volume Delta (crypto) ---
    if volume_delta and "erreur" not in volume_delta:
        lines += [
            "VOLUME DELTA (Binance) :",
            f"- Achat moyen {volume_delta.get('days')}j  : {volume_delta.get('delta_pct_moyen')} % du volume (50% = équilibré)",
            f"- Tendance CVD      : {volume_delta.get('cvd_tendance')}",
            f"- Signal            : {volume_delta['signal']}\n",
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
    if options_flow:
        lines.append(f"- Options    : {scoring['scores']['options_flow']} × {scoring['poids']['options_flow']}")
    if sec_filings:
        lines.append(f"- SEC 8-K    : {scoring['scores']['sec_filings']} × {scoring['poids']['sec_filings']}")
    if short_interest:
        lines.append(f"- Short Int. : {scoring['scores']['short_interest']} × {scoring['poids']['short_interest']}")
    if earnings_surprise:
        lines.append(f"- Earnings   : {scoring['scores']['earnings_surprise']} × {scoring['poids']['earnings_surprise']}")
    if volume_delta:
        lines.append(f"- Vol. Delta : {scoring['scores']['volume_delta']} × {scoring['poids']['volume_delta']}")
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


def run(ticker: str, with_llm: bool = True) -> dict:
    """
    Orchestre les agents selon le type d'actif détecté,
    calcule le score pondéré et produit un rapport LLM.

    with_llm=False : scoring uniquement, pas d'appel Groq (mode scanner rapide).
    """
    asset_type = detect_asset_type(ticker)
    config     = AGENTS_PAR_TYPE[asset_type]

    print(f"Analyse de {ticker} [{asset_type}] en cours...")

    # --- Agents toujours actifs ---
    tech = analyze_technical(ticker)
    risk = analyze_risk(ticker)
    sent = analyze_sentiment(ticker) if config["sentiment"] else None

    # --- Agents conditionnels ---
    fund             = analyze_fundamental(ticker)           if config["fondamental"]       else None
    trends           = analyze_trends(ticker)                if config["trends"]            else None
    insider          = analyze_insider(ticker)               if config["insider"]           else None
    macro            = analyze_macro(market=config["macro"]) if config["macro"]             else None
    options_flow     = analyze_options_flow(ticker)          if config["options_flow"]      else None
    sec_filings      = analyze_sec_filings(ticker)           if config["sec_filings"]       else None
    short_interest   = analyze_short_interest(ticker)        if config["short_interest"]    else None
    earnings_surprise= analyze_earnings_surprise(ticker)     if config["earnings_surprise"] else None
    volume_delta     = analyze_volume_delta(ticker)           if config["volume_delta"]      else None

    # --- Scoring (gère les None automatiquement) ---
    scoring = calculer_score(
        tech, fund, sent, risk, trends, insider, macro,
        options_flow, sec_filings, short_interest, earnings_surprise,
        volume_delta
    )

    # --- Rapport LLM (optionnel) ---
    rapport = ""
    if with_llm:
        prompt = _build_prompt(ticker, asset_type, tech, fund, sent,
                               risk, trends, insider, macro,
                               options_flow, sec_filings, short_interest,
                               earnings_surprise, volume_delta, scoring)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        rapport = response.choices[0].message.content or ""

    # --- Sauvegarde historique du score ---
    try:
        enregistrer_score(ticker, scoring["score_final"], scoring["decision"])
    except Exception:
        pass   # non bloquant

    return {
        "ticker":           ticker,
        "asset_type":       asset_type,
        "rapport":          rapport,
        "scoring":          scoring,
        "tech":             tech,
        "fund":             fund,
        "sent":             sent,
        "risk":             risk,
        "trends":           trends,
        "insider":          insider,
        "macro":            macro,
        "options_flow":     options_flow,
        "sec_filings":      sec_filings,
        "short_interest":   short_interest,
        "earnings_surprise":earnings_surprise,
        "volume_delta":     volume_delta,
    }


if __name__ == "__main__":
    for ticker in ["AAPL", "MC.PA", "BTC-USD", "EURUSD=X"]:
        r = run(ticker)
        print(f"\n[{r['asset_type']}] {ticker} → {r['scoring']['decision']} ({r['scoring']['score_final']})")
