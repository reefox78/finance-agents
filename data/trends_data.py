from pytrends.request import TrendReq
import pandas as pd
import time


def _neutre(ticker: str) -> dict:
    return {
        "ticker":         ticker,
        "tendance":       "NEUTRE",
        "score_tendance": 0.0,
        "variation":      0.0,
        "moyenne":        0.0,
        "ratio_tendance": 1.0,
        "details":        [],
    }


def get_trends(ticker: str, nom: str = None, periode: str = "today 3-m",
               delai: float = 2.0) -> dict:
    """
    Récupère les tendances Google pour un ticker.

    ticker  : symbole boursier (ex: AAPL)
    nom     : nom de l'entreprise (ex: Apple)
    periode : today 1-m, today 3-m, today 12-m
    delai   : pause avant la requête pour éviter le rate-limit 429 Google
              (mettre 0 pour une analyse unique, 2.0+ pour les scans)
    """
    try:
        if delai > 0:
            time.sleep(delai)

        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload(
            [ticker],
            cat=0,
            timeframe=periode,
            geo="",
            gprop=""
        )

        df = pytrends.interest_over_time()

        if df.empty:
            return _neutre(ticker)

        serie = df[ticker] if ticker in df.columns else df.iloc[:, 0]

        moyenne      = round(serie.mean(), 2)
        derniere_val = round(serie.iloc[-1], 2)
        val_debut    = round(serie.iloc[0], 2)
        variation    = round((derniere_val - val_debut) / (val_debut + 1) * 100, 2)

        moitie         = len(serie) // 2
        moy_recente    = serie.iloc[moitie:].mean()
        moy_ancienne   = serie.iloc[:moitie].mean()
        ratio_tendance = round(moy_recente / (moy_ancienne + 1), 2)

        if ratio_tendance > 1.5:    score = 1.0
        elif ratio_tendance > 1.2:  score = 0.5
        elif ratio_tendance > 0.9:  score = 0.0
        elif ratio_tendance > 0.7:  score = -0.5
        else:                       score = -1.0

        if score >= 0.5:    tendance = "HAUSSE"
        elif score <= -0.5: tendance = "BAISSE"
        else:               tendance = "STABLE"

        return {
            "ticker":         ticker,
            "tendance":       tendance,
            "score_tendance": score,
            "variation":      variation,
            "moyenne":        moyenne,
            "ratio_tendance": ratio_tendance,
            "details":        serie.tail(10).reset_index().rename(
                columns={"date": "date", ticker: "interet"}
            ).to_dict("records"),
        }

    except Exception:
        # 429 rate-limit, timeout réseau ou tout autre erreur Google → signal neutre
        return _neutre(ticker)


if __name__ == "__main__":
    resultat = get_trends("AAPL", nom="Apple", delai=0)

    print(f"--- Google Trends : {resultat['ticker']} ---")
    print(f"Tendance        : {resultat['tendance']}")
    print(f"Score           : {resultat['score_tendance']}")
    print(f"Variation       : {resultat['variation']} %")
    print(f"Moyenne         : {resultat['moyenne']}")
    print(f"Ratio tendance  : {resultat['ratio_tendance']}")
