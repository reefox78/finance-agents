from data.macro_data import get_macro_data, get_macro_score


def analyze_macro() -> dict:
    """
    Analyse le contexte macroéconomique.
    Un environnement macro défavorable pénalise tous les signaux.
    """
    data        = get_macro_data()
    score_final = get_macro_score(data)

    if score_final >= 0.3:
        signal       = "ACHETER"
        environnement = "FAVORABLE"
    elif score_final <= -0.3:
        signal       = "VENDRE"
        environnement = "DÉFAVORABLE"
    else:
        signal       = "NEUTRE"
        environnement = "NEUTRE"

    return {
        "taux_fed":     data.get("taux_fed",    {}).get("valeur"),
        "inflation":    data.get("inflation",   {}).get("valeur"),
        "chomage":      data.get("chomage",     {}).get("valeur"),
        "confiance":    data.get("confiance",   {}).get("valeur"),
        "spread_10_2":  data.get("spread_10_2", {}).get("valeur"),
        "environnement": environnement,
        "score_final":  score_final,
        "signal":       signal,
    }


if __name__ == "__main__":
    resultat = analyze_macro()

    print(f"--- Agent Macro ---")
    print(f"Taux Fed       : {resultat['taux_fed']} %")
    print(f"Inflation      : {resultat['inflation']}")
    print(f"Chômage        : {resultat['chomage']} %")
    print(f"Confiance      : {resultat['confiance']}")
    print(f"Spread 10/2    : {resultat['spread_10_2']}")
    print(f"Environnement  : {resultat['environnement']}")
    print(f"Score final    : {resultat['score_final']}")
    print(f"Signal         : {resultat['signal']}")