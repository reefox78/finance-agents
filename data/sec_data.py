"""
Données EDGAR (SEC) pour les dépôts réglementaires US.

Sources :
  - https://www.sec.gov/files/company_tickers.json  → ticker → CIK
  - https://data.sec.gov/submissions/CIK{cik}.json  → historique des dépôts

Les dépôts 8-K contiennent un champ "items" listant les sections déclarées.
Ce champ est la meilleure source structurée pour détecter la nature de l'événement.
"""

import requests
import json
from datetime import datetime, timedelta
from pathlib import Path

_USER_AGENT = "finance-agents research@finance-agents.local"
_HEADERS    = {"User-Agent": _USER_AGENT}

# Cache local du fichier company_tickers (mis à jour si > 7 jours)
_CACHE_PATH = Path("data/cache/company_tickers.json")

# Mapping item 8-K → score [-1, +1]
# Source : SEC Form 8-K item numbering (https://www.sec.gov/fast-answers/answers-form8khtm.html)
_ITEM_SCORES = {
    # Accords et transactions
    "1.01":  0.10,   # Nouvel accord matériel
    "1.02": -0.20,   # Résiliation d'accord
    "1.03": -1.00,   # Faillite / redressement judiciaire
    "1.04":  0.00,   # Résultats mine (secteur spécifique)
    "1.05": -0.50,   # Incident cybersécurité majeur
    # Finances
    "2.01":  0.50,   # Acquisition complétée
    "2.02":  0.15,   # Publication des résultats (earnings)
    "2.03": -0.10,   # Engagement de dette directe
    "2.04": -0.50,   # Événement déclencheur d'une obligation
    "2.05": -0.20,   # Coûts de restructuration
    "2.06": -0.70,   # Dépréciation d'actifs
    # Titres
    "3.01": -1.00,   # Avis de radiation (delisting)
    "3.02": -0.20,   # Ventes non enregistrées de titres
    "3.03": -0.10,   # Modification des droits des actionnaires
    # Comptabilité
    "4.01": -0.40,   # Changement d'auditeur
    "4.02": -0.80,   # Non-conformité des états financiers antérieurs
    # Gouvernance
    "5.01":  0.00,   # Changement de contrôle
    "5.02": -0.25,   # Départ de dirigeants / administrateurs
    "5.03":  0.00,   # Modification des statuts
    "5.05":  0.10,   # Adoption / modification d'un plan d'incitation
    "5.07":  0.05,   # Vote des actionnaires
    "5.08":  0.00,   # Nominations au conseil
    # Divers
    "7.01":  0.00,   # Regulation FD (information non matérielle)
    "8.01":  0.00,   # Autres événements
    "9.01":  0.00,   # Pièces jointes / états financiers
}


def _get_cik_map() -> dict:
    """Retourne le mapping ticker → CIK (avec cache local 7 jours)."""
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if _CACHE_PATH.exists():
        age_days = (datetime.now() - datetime.fromtimestamp(_CACHE_PATH.stat().st_mtime)).days
        if age_days < 7:
            with open(_CACHE_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            return {v["ticker"].upper(): v["cik_str"] for v in raw.values()}

    r = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers=_HEADERS, timeout=15
    )
    r.raise_for_status()
    raw = r.json()
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f)

    return {v["ticker"].upper(): v["cik_str"] for v in raw.values()}


def get_recent_8k(ticker: str, days: int = 90) -> dict:
    """
    Récupère les dépôts 8-K des `days` derniers jours pour le ticker.

    Retourne :
    {
        "disponible": bool,
        "nb_filings": int,
        "items_list": list[str],   # tous les items des filings récents
        "filings":    list[dict],  # date + items par filing
        "score_brut": float,       # score agrégé basé sur les items
    }
    """
    try:
        cik_map = _get_cik_map()
        cik = cik_map.get(ticker.upper().split(".")[0].split("-")[0])

        if cik is None:
            return {"disponible": False, "raison": "CIK non trouvé"}

        url = f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json"
        r   = requests.get(url, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()

        recent  = data["filings"]["recent"]
        cutoff  = datetime.now() - timedelta(days=days)
        filings = []

        for form, date_str, items_str in zip(
            recent["form"], recent["filingDate"], recent["items"]
        ):
            if form != "8-K":
                continue
            try:
                filing_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if filing_date < cutoff:
                break

            items = [it.strip() for it in items_str.split(",") if it.strip()]
            filings.append({"date": date_str, "items": items})

        if not filings:
            return {
                "disponible": True,
                "nb_filings": 0,
                "items_list": [],
                "filings":    [],
                "score_brut": 0.0,
            }

        # Agrégation des scores : derniers filings pondérés plus fortement (décroissant)
        all_items = []
        weighted_score = 0.0
        weight_total   = 0.0

        for idx, filing in enumerate(filings):
            weight = 1.0 / (idx + 1)   # 1, 0.5, 0.33, ...
            for item in filing["items"]:
                all_items.append(item)
                item_score = _ITEM_SCORES.get(item, 0.0)
                weighted_score += item_score * weight
                weight_total   += weight

        score_brut = round(weighted_score / weight_total, 4) if weight_total > 0 else 0.0
        score_brut = max(-1.0, min(1.0, score_brut))

        return {
            "disponible": True,
            "nb_filings": len(filings),
            "items_list": all_items,
            "filings":    filings,
            "score_brut": score_brut,
        }

    except Exception as e:
        return {"disponible": False, "raison": str(e)}
