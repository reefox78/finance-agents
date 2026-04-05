"""
Données de surprise sur bénéfices via yfinance.

Source : yf.Ticker.earnings_dates
  - EPS Estimate  : consensus Wall Street
  - Reported EPS  : EPS publié
  - Surprise(%)   : (Reported - Estimate) / |Estimate| × 100

Le post-earnings drift est une des anomalies les plus documentées en finance :
les actions qui battent les attentes continuent de monter 1 à 3 mois après
la publication. Celles qui déçoivent continuent de baisser.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime


def get_earnings_surprise(ticker: str, quarters: int = 4) -> dict:
    """
    Récupère les données de surprise bénéfice des `quarters` derniers trimestres.

    Retourne un dict avec :
      - surprises      : liste des surprises % (du plus récent au plus ancien)
      - latest_surprise: surprise du dernier trimestre
      - avg_surprise   : moyenne sur les derniers trimestres
      - nb_beats       : nombre de trimestres où l'EPS > estimate
      - next_earnings  : date du prochain earnings (si disponible)
    """
    try:
        stock = yf.Ticker(ticker)
        df    = stock.earnings_dates

        if df is None or df.empty:
            return {"disponible": False, "raison": "Pas de données earnings"}

        # Séparer passé (Reported EPS non nul) et futur
        today       = pd.Timestamp.now(tz=df.index.tz)
        past_df     = df[df.index <= today].dropna(subset=["Reported EPS"]).head(quarters)
        future_df   = df[df.index > today]
        next_earning = future_df.index[-1].strftime("%Y-%m-%d") if not future_df.empty else None

        if past_df.empty:
            return {"disponible": False, "raison": "Pas d'earnings historiques"}

        surprises = []
        for _, row in past_df.iterrows():
            reported = row.get("Reported EPS")
            estimate = row.get("EPS Estimate")
            surprise_col = row.get("Surprise(%)")

            # Priorité à la colonne Surprise(%) si disponible
            if pd.notna(surprise_col):
                surprises.append(round(float(surprise_col), 2))
            elif pd.notna(reported) and pd.notna(estimate) and estimate != 0:
                pct = (float(reported) - float(estimate)) / abs(float(estimate)) * 100
                surprises.append(round(pct, 2))

        if not surprises:
            return {"disponible": False, "raison": "Impossible de calculer les surprises"}

        nb_beats = sum(1 for s in surprises if s > 0)

        return {
            "disponible":      True,
            "surprises":       surprises,
            "latest_surprise": surprises[0],
            "avg_surprise":    round(sum(surprises) / len(surprises), 2),
            "nb_beats":        nb_beats,
            "nb_quarters":     len(surprises),
            "next_earnings":   next_earning,
        }

    except Exception as e:
        return {"disponible": False, "raison": str(e)}
