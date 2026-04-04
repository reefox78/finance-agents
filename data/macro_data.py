import os
from fredapi import Fred
from dotenv import load_dotenv

load_dotenv("config/.env")

fred = Fred(api_key=os.getenv("FRED_API_KEY"))

# Séries FRED qu'on utilise
SERIES = {
    "taux_fed":      "FEDFUNDS",    # Taux directeur Fed
    "inflation":     "CPIAUCSL",    # Inflation CPI
    "chomage":       "UNRATE",      # Taux de chômage
    "pib":           "GDP",         # PIB USA
    "confiance":     "UMCSENT",     # Indice confiance consommateur Michigan
    "spread_10_2":   "T10Y2Y",      # Spread 10 ans - 2 ans (indicateur récession)
}


def get_macro_data() -> dict:
    """
    Récupère les dernières valeurs des indicateurs macro FRED.
    """
    resultats = {}

    for nom, serie_id in SERIES.items():
        try:
            serie = fred.get_series(serie_id)
            serie = serie.dropna()

            valeur_actuelle  = round(float(serie.iloc[-1]), 4)
            valeur_precedente = round(float(serie.iloc[-2]), 4)
            variation        = round(valeur_actuelle - valeur_precedente, 4)

            resultats[nom] = {
                "valeur":     valeur_actuelle,
                "precedente": valeur_precedente,
                "variation":  variation,
            }
        except Exception as e:
            resultats[nom] = {
                "valeur":     None,
                "precedente": None,
                "variation":  None,
            }

    return resultats


def get_macro_score(data: dict) -> float:
    """
    Calcule un score macro entre -1 et +1.
    Environnement favorable = score positif.
    Environnement défavorable = score négatif.
    """
    score = 0.0
    poids_total = 0

    # --- Taux Fed ---
    # Taux bas = favorable aux actions, taux haut = défavorable
    taux = data.get("taux_fed", {}).get("valeur")
    if taux is not None:
        if taux < 2.0:   score += 1.0
        elif taux < 4.0: score += 0.0
        else:            score -= 1.0
        poids_total += 1

    # --- Inflation ---
    # Inflation < 3% = saine, > 5% = dangereuse
    inflation = data.get("inflation", {}).get("variation")
    if inflation is not None:
        if inflation < 0:    score += 0.5
        elif inflation < 0.3: score += 0.0
        else:                score -= 0.5
        poids_total += 1

    # --- Chômage ---
    # Chômage bas = économie forte = favorable
    chomage = data.get("chomage", {}).get("valeur")
    if chomage is not None:
        if chomage < 4.0:   score += 1.0
        elif chomage < 6.0: score += 0.0
        else:               score -= 1.0
        poids_total += 1

    # --- Spread 10/2 ans ---
    # Spread négatif = courbe inversée = signal récession
    spread = data.get("spread_10_2", {}).get("valeur")
    if spread is not None:
        if spread > 0.5:    score += 1.0
        elif spread > 0:    score += 0.3
        elif spread > -0.5: score -= 0.3
        else:               score -= 1.0
        poids_total += 1

    # --- Confiance consommateur ---
    # > 80 = optimiste, < 60 = pessimiste
    confiance = data.get("confiance", {}).get("valeur")
    if confiance is not None:
        if confiance > 80:   score += 1.0
        elif confiance > 60: score += 0.0
        else:                score -= 1.0
        poids_total += 1

    if poids_total == 0:
        return 0.0

    return round(score / poids_total, 4)


# ---------------------------------------------------------------------------
# Données macro — Zone Euro (BCE)
# ---------------------------------------------------------------------------

SERIES_EU = {
    "taux_bce":  "ECBDFR",              # Taux directeur dépôt BCE
    "inflation": "CP0000EZ19M086NEST",  # HICP zone euro (index mensuel)
    "chomage":   "LRHUTTTTEZM156S",     # Chômage harmonisé zone euro
    "confiance": "CSCICP02EZQ460S",     # Confiance consommateurs OCDE zone euro
    "taux_10y":  "IRLTLT01EZM156N",     # Taux obligation 10 ans zone euro
}


def get_macro_data_eu() -> dict:
    """
    Récupère les dernières valeurs des indicateurs macro BCE / zone euro.
    Même structure de retour que get_macro_data().
    """
    resultats = {}

    for nom, serie_id in SERIES_EU.items():
        try:
            serie = fred.get_series(serie_id).dropna()
            valeur_actuelle   = round(float(serie.iloc[-1]), 4)
            valeur_precedente = round(float(serie.iloc[-2]), 4)
            variation         = round(valeur_actuelle - valeur_precedente, 4)
            resultats[nom] = {
                "valeur":     valeur_actuelle,
                "precedente": valeur_precedente,
                "variation":  variation,
            }
        except Exception:
            resultats[nom] = {"valeur": None, "precedente": None, "variation": None}

    return resultats


def get_macro_score_eu(data: dict) -> float:
    """
    Score macro zone euro entre -1 et +1.
    Seuils adaptés aux niveaux historiques européens.
    """
    score = 0.0
    n = 0

    # Taux BCE (0 % en QE, 4 % en 2023-24)
    taux = data.get("taux_bce", {}).get("valeur")
    if taux is not None:
        if taux < 1.0:   score += 1.0
        elif taux < 3.0: score += 0.0
        else:            score -= 1.0
        n += 1

    # Inflation HICP (variation m/m, même logique que US)
    infl_var = data.get("inflation", {}).get("variation")
    if infl_var is not None:
        if infl_var < 0:     score += 0.5
        elif infl_var < 0.3: score += 0.0
        else:                score -= 0.5
        n += 1

    # Chômage zone euro (6-7 % = normal, 10 %+ = crise)
    chomage = data.get("chomage", {}).get("valeur")
    if chomage is not None:
        if chomage < 6.0:   score += 1.0
        elif chomage < 8.5: score += 0.0
        else:               score -= 1.0
        n += 1

    # Confiance OCDE (indice autour de 100 = neutre)
    confiance = data.get("confiance", {}).get("valeur")
    if confiance is not None:
        if confiance > 100:  score += 1.0
        elif confiance > 98: score += 0.0
        else:                score -= 1.0
        n += 1

    # Taux 10 ans zone euro (> 3.5 % = conditions financières tendues)
    taux_10y = data.get("taux_10y", {}).get("valeur")
    if taux_10y is not None:
        if taux_10y < 1.5:   score += 1.0
        elif taux_10y < 3.5: score += 0.0
        else:                score -= 1.0
        n += 1

    return round(score / n, 4) if n > 0 else 0.0


if __name__ == "__main__":
    print("Récupération des données macro FRED...")
    data = get_macro_data()

    print("\n--- Indicateurs macro ---")
    for nom, valeurs in data.items():
        print(f"{nom:15} : {valeurs['valeur']} (variation: {valeurs['variation']})")

    score = get_macro_score(data)
    print(f"\nScore macro : {score}")
    if score >= 0.3:
        print("Environnement : FAVORABLE")
    elif score <= -0.3:
        print("Environnement : DÉFAVORABLE")
    else:
        print("Environnement : NEUTRE")