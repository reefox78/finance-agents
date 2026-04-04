from pytrends.request import TrendReq
import pandas as pd


def get_trends(ticker: str, nom: str = None, periode: str = "today 3-m") -> dict:
    """
    Récupère les tendances Google pour un ticker.

    ticker  : symbole boursier (ex: AAPL)
    nom     : nom de l'entreprise (ex: Apple) — enrichit la recherche
    periode : today 1-m, today 3-m, today 12-m
    """
    pytrends = TrendReq(hl="en-US", tz=360)

    # On cherche le ticker ET le nom de l'entreprise si dispo
    mots_cles = [ticker]
    if nom:
        mots_cles.append(nom)

    pytrends.build_payload(
        mots_cles[:1],  # Google Trends limite à 5 mots clés
        cat=0,
        timeframe=periode,
        geo="",
        gprop=""
    )

    df = pytrends.interest_over_time()

    if df.empty:
        return {
            "ticker":         ticker,
            "tendance":       "NEUTRE",
            "score_tendance": 0.0,
            "variation":      0.0,
            "moyenne":        0.0,
            "details":        [],
        }

    serie = df[ticker] if ticker in df.columns else df.iloc[:, 0]

    # --- Calculs ---
    moyenne       = round(serie.mean(), 2)
    derniere_val  = round(serie.iloc[-1], 2)
    val_debut     = round(serie.iloc[0], 2)
    variation     = round((derniere_val - val_debut) / (val_debut + 1) * 100, 2)

    # Tendance récente : compare les 2 dernières semaines vs les 2 premières
    moitie        = len(serie) // 2
    moy_recente   = serie.iloc[moitie:].mean()
    moy_ancienne  = serie.iloc[:moitie].mean()
    ratio_tendance = round(moy_recente / (moy_ancienne + 1), 2)

    # --- Score continu ---
    if ratio_tendance > 1.5:
        score = 1.0
    elif ratio_tendance > 1.2:
        score = 0.5
    elif ratio_tendance > 0.9:
        score = 0.0
    elif ratio_tendance > 0.7:
        score = -0.5
    else:
        score = -1.0

    if score >= 0.5:
        tendance = "HAUSSE"
    elif score <= -0.5:
        tendance = "BAISSE"
    else:
        tendance = "STABLE"

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


if __name__ == "__main__":
    resultat = get_trends("AAPL", nom="Apple")

    print(f"--- Google Trends : {resultat['ticker']} ---")
    print(f"Tendance        : {resultat['tendance']}")
    print(f"Score           : {resultat['score_tendance']}")
    print(f"Variation       : {resultat['variation']} %")
    print(f"Moyenne         : {resultat['moyenne']}")
    print(f"Ratio tendance  : {resultat['ratio_tendance']}")
    print(f"\nDernières valeurs :")
    for row in resultat["details"]:
        print(f"  {row}")