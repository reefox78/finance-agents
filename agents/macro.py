from data.macro_data import (
    get_macro_data, get_macro_score,
    get_macro_data_eu, get_macro_score_eu,
)


def analyze_macro(market: str = "us") -> dict:
    """
    Analyse le contexte macroéconomique.

    market = "us" → données Fed / FRED US
    market = "eu" → données BCE / FRED Europe
    """
    if market == "eu":
        data        = get_macro_data_eu()
        score_final = get_macro_score_eu(data)

        if score_final >= 0.3:
            signal        = "ACHETER"
            environnement = "FAVORABLE"
        elif score_final <= -0.3:
            signal        = "VENDRE"
            environnement = "DÉFAVORABLE"
        else:
            signal        = "NEUTRE"
            environnement = "NEUTRE"

        return {
            "market":        "eu",
            "taux_bce":      data.get("taux_bce",  {}).get("valeur"),
            "inflation":     data.get("inflation", {}).get("variation"),
            "chomage":       data.get("chomage",   {}).get("valeur"),
            "confiance":     data.get("confiance", {}).get("valeur"),
            "taux_10y":      data.get("taux_10y",  {}).get("valeur"),
            "environnement": environnement,
            "score_final":   score_final,
            "signal":        signal,
        }

    # --- US (défaut) ---
    data        = get_macro_data()
    score_final = get_macro_score(data)

    if score_final >= 0.3:
        signal        = "ACHETER"
        environnement = "FAVORABLE"
    elif score_final <= -0.3:
        signal        = "VENDRE"
        environnement = "DÉFAVORABLE"
    else:
        signal        = "NEUTRE"
        environnement = "NEUTRE"

    return {
        "market":        "us",
        "taux_fed":      data.get("taux_fed",    {}).get("valeur"),
        "inflation":     data.get("inflation",   {}).get("valeur"),
        "chomage":       data.get("chomage",     {}).get("valeur"),
        "confiance":     data.get("confiance",   {}).get("valeur"),
        "spread_10_2":   data.get("spread_10_2", {}).get("valeur"),
        "environnement": environnement,
        "score_final":   score_final,
        "signal":        signal,
    }


if __name__ == "__main__":
    for market in ["us", "eu"]:
        print(f"\n--- Agent Macro ({market.upper()}) ---")
        r = analyze_macro(market=market)
        for k, v in r.items():
            print(f"  {k:15} : {v}")
