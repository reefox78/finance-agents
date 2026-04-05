"""
Calcul des frais broker et de la fiscalité française sur les plus-values.
Module pur (sans Streamlit) — importable dans les tests et le dashboard.
"""

import json
from pathlib import Path

BROKERS_PATH = Path("config/brokers.json")


def charger_brokers() -> dict:
    """Charge la configuration des brokers depuis config/brokers.json."""
    try:
        with open(BROKERS_PATH, encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    except Exception:
        return {
            "personnalise": {
                "nom": "Personnalisé", "type_frais": "fixe",
                "frais_achat": 0.0, "frais_vente": 0.0,
                "note": "", "url_tarifs": "", "mis_a_jour": "2026-01-01",
            }
        }


def calculer_frais(montant: float, broker: dict, operation: str = "achat") -> float:
    """
    Calcule les frais selon le type de broker et le montant de l'opération.

    Types supportés :
        fixe  : frais_achat / frais_vente fixe en €, indépendant du montant
        pct   : max(frais_min, montant × taux_pct / 100)
        mixte : frais_fixe + montant × taux_pct / 100  (ex: DEGIRO)

    Args:
        montant   : montant total de l'opération (prix × quantité)
        broker    : dict de configuration du broker (issu de brokers.json)
        operation : "achat" ou "vente"

    Returns:
        Frais en euros (float, >= 0)
    """
    t = broker.get("type_frais", "fixe")
    if t == "fixe":
        return float(broker.get(f"frais_{operation}", 0.0))
    elif t == "pct":
        taux = broker.get("taux_pct", 0.0)
        mini = broker.get("frais_min", 0.0)
        return max(float(mini), round(montant * taux / 100, 4))
    elif t == "mixte":
        fixe = float(broker.get(f"frais_{operation}", 0.0))
        taux = broker.get("taux_pct", 0.0)
        return round(fixe + montant * taux / 100, 4)
    return 0.0


def calculer_impots(pnl_net: float, regime: str, tmi: int = 30) -> dict:
    """
    Estime l'impôt français sur une plus-value nette (après frais).

    Régimes disponibles :
        pfu    : PFU 30% = 12.8% IR + 17.2% prélèvements sociaux (défaut)
        bareme : Barème progressif = TMI% IR + 17.2% PS
        pea    : PEA après 5 ans = 17.2% PS uniquement (exonéré d'IR)

    ATTENTION : estimation par trade — en réalité les pertes compensent les gains
    à l'échelle de l'année fiscale (déclaration 2047).

    Args:
        pnl_net : plus-value nette en € (après frais broker). Si <= 0, impôt = 0.
        regime  : "pfu", "bareme" ou "pea"
        tmi     : Tranche Marginale d'Imposition en % (utilisée si regime="bareme")

    Returns:
        dict avec : impots (€), pnl_apres_impots (€), taux_effectif (%)
    """
    if pnl_net <= 0:
        return {"impots": 0.0, "pnl_apres_impots": pnl_net, "taux_effectif": 0.0}

    if regime == "pea":
        taux = 0.172                        # 17.2% PS uniquement
    elif regime == "bareme":
        taux = round(tmi / 100 + 0.172, 4)  # TMI + 17.2% PS
    else:                                   # pfu (défaut)
        taux = 0.30                         # 12.8% IR + 17.2% PS

    impots = round(pnl_net * taux, 2)
    return {
        "impots":           impots,
        "pnl_apres_impots": round(pnl_net - impots, 2),
        "taux_effectif":    round(taux * 100, 1),
    }
