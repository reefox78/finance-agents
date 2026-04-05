"""
Agent SEC Filings NLP.

Analyse les dépôts réglementaires 8-K (événements matériels) pour détecter :
- La nature des événements déclarés (items 8-K = catégories standardisées)
- La fréquence des dépôts (activité réglementaire anormale)

Signal : positif si acquisitions/résultats, négatif si faillite/dépréciation/départs.

Disponible pour les actions US uniquement (EDGAR = SEC US).
"""

from data.sec_data import get_recent_8k


def _score_frequence(nb_filings: int, days: int = 90) -> float:
    """
    Un nombre anormalement élevé de 8-K peut signaler de l'agitation.
    Baseline : ~1 par mois = 3 sur 90 jours.
    """
    if nb_filings == 0:
        return 0.0       # pas d'événements récents = calme
    elif nb_filings <= 3:
        return 0.0       # normal
    elif nb_filings <= 6:
        return -0.20     # activité légèrement élevée
    else:
        return -0.40     # activité anormalement élevée = incertitude


def analyze_sec_filings(ticker: str) -> dict:
    """
    Analyse les dépôts 8-K des 90 derniers jours.

    Retourne un dict avec score_final [-1, +1] et signal.
    Retourne None si non disponible (ticker non US ou CIK introuvable).
    """
    data = get_recent_8k(ticker, days=90)

    if not data.get("disponible"):
        return None

    nb_filings  = data["nb_filings"]
    score_items = data["score_brut"]
    s_freq      = _score_frequence(nb_filings)

    # Score final : items (signal principal) + fréquence (signal secondaire)
    score_final = round(score_items * 0.75 + s_freq * 0.25, 4)
    score_final = max(-1.0, min(1.0, score_final))

    if score_final >= 0.15:
        signal = "ACHETER"
    elif score_final <= -0.15:
        signal = "VENDRE"
    else:
        signal = "NEUTRE"

    # Résumé des items les plus récents (dernier filing)
    last_items = data["filings"][0]["items"] if data["filings"] else []
    last_date  = data["filings"][0]["date"]  if data["filings"] else "N/A"

    return {
        "ticker":      ticker,
        "nb_filings":  nb_filings,
        "last_date":   last_date,
        "last_items":  last_items,
        "items_list":  data["items_list"],
        "scores": {
            "items":      round(score_items, 4),
            "frequence":  s_freq,
        },
        "score_final":  score_final,
        "signal":       signal,
    }


if __name__ == "__main__":
    for t in ["AAPL", "MSFT", "NVDA"]:
        r = analyze_sec_filings(t)
        if r:
            print(f"\n--- SEC Filings : {r['ticker']} ---")
            print(f"Filings 8-K (90j) : {r['nb_filings']}")
            print(f"Dernier filing    : {r['last_date']} | Items : {r['last_items']}")
            print(f"Score items       : {r['scores']['items']}")
            print(f"Score final       : {r['score_final']}")
            print(f"Signal            : {r['signal']}")
        else:
            print(f"\n{t}: Non disponible")
