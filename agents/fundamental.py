from data.market_data import get_stock_info
from data.sector_data import get_sector_averages


def _score_per(per: float, per_moyen: float) -> float:
    """Score continu basé sur le PER vs moyenne secteur."""
    if not per or not per_moyen:
        return 0.0
    ratio = per / per_moyen
    if ratio < 0.70:
        return 1.0
    elif ratio < 0.90:
        return 0.5
    elif ratio < 1.10:
        return 0.0
    elif ratio < 1.30:
        return -0.5
    else:
        return -1.0


def _score_dividende(div: float, div_moyen: float) -> float:
    """Score continu basé sur le dividende vs moyenne secteur."""
    if not div or not div_moyen:
        return 0.0
    ratio = div / div_moyen
    if ratio >= 1.5:
        return 1.0
    elif ratio >= 1.0:
        return 0.5
    elif ratio >= 0.5:
        return 0.0
    else:
        return -0.5


def _score_capitalisation(cap: float) -> float:
    """Score basé sur la taille de l'entreprise."""
    if not cap:
        return 0.0
    if cap > 500_000_000_000:
        return 1.0
    elif cap > 100_000_000_000:
        return 0.5
    elif cap > 10_000_000_000:
        return 0.0
    else:
        return -0.5


POIDS = {
    "per":          0.50,
    "dividende":    0.25,
    "capitalisation": 0.25,
}


def analyze_fundamental(ticker: str) -> dict:
    """
    Analyse fondamentale avec scores continus.
    Compare les indicateurs à la moyenne du secteur.
    """
    info     = get_stock_info(ticker)
    secteur  = info.get("secteur", "N/A")
    moyennes = get_sector_averages(secteur) if secteur != "N/A" else {}

    per       = info.get("per")
    dividende = info.get("dividende")
    cap       = info.get("capitalisation")
    per_moyen = moyennes.get("per_moyen")
    div_moyen = moyennes.get("dividende_moyen")

    s_per  = _score_per(per, per_moyen)
    s_div  = _score_dividende(dividende, div_moyen)
    s_cap  = _score_capitalisation(cap)

    score_final = round(
        s_per  * POIDS["per"] +
        s_div  * POIDS["dividende"] +
        s_cap  * POIDS["capitalisation"],
        4
    )

    if score_final >= 0.15:
        signal = "ACHETER"
    elif score_final <= -0.15:
        signal = "VENDRE"
    else:
        signal = "NEUTRE"

    return {
        "ticker":                   ticker,
        "nom":                      info.get("nom"),
        "secteur":                  secteur,
        "per":                      per,
        "per_moyen_secteur":        per_moyen,
        "dividende":                dividende,
        "dividende_moyen_secteur":  div_moyen,
        "capitalisation":           cap,
        "scores": {
            "per":          s_per,
            "dividende":    s_div,
            "capitalisation": s_cap,
        },
        "score_final":  score_final,
        "signal":       signal,
    }


if __name__ == "__main__":
    resultat = analyze_fundamental("AAPL")

    print(f"--- Analyse fondamentale : {resultat['ticker']} ---")
    print(f"Nom                    : {resultat['nom']}")
    print(f"Secteur                : {resultat['secteur']}")
    print(f"PER                    : {resultat['per']}")
    print(f"PER moyen secteur      : {resultat['per_moyen_secteur']}")
    print(f"Dividende              : {resultat['dividende']}")
    print(f"Dividende moyen secteur: {resultat['dividende_moyen_secteur']}")
    print(f"\n--- Scores continus ---")
    print(f"PER           (×{POIDS['per']})   : {resultat['scores']['per']}")
    print(f"Dividende     (×{POIDS['dividende']})  : {resultat['scores']['dividende']}")
    print(f"Capitalisation(×{POIDS['capitalisation']})  : {resultat['scores']['capitalisation']}")
    print(f"\nScore final   : {resultat['score_final']}")
    print(f"Signal        : {resultat['signal']}")