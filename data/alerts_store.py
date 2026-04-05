"""
Persistance des alertes dans data/alerts.json.
Chaque alerte a un ID unique, un niveau, un message, et un état lu/non-lu.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

ALERTS_PATH = Path("data/alerts.json")

NIVEAUX = {
    "CRITIQUE":   "🔴",
    "VENDRE":     "🔴",
    "SURVEILLER": "🟡",
    "INFO":       "🔵",
}


def _charger() -> list:
    if ALERTS_PATH.exists():
        try:
            with open(ALERTS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _sauvegarder(alertes: list) -> None:
    ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_PATH, "w", encoding="utf-8") as f:
        json.dump(alertes, f, ensure_ascii=False, indent=2)


def creer_alerte(ticker: str, type_alerte: str, niveau: str,
                 message: str, details: dict = None) -> dict:
    """Crée une alerte et la sauvegarde. Retourne l'alerte créée."""
    alertes = _charger()

    # Évite les doublons : pas deux alertes identiques non-lues pour le même ticker/type
    for a in alertes:
        if a["ticker"] == ticker and a["type"] == type_alerte and not a["lue"]:
            return a   # alerte déjà active, on ne duplique pas

    alerte = {
        "id":      str(uuid.uuid4())[:8],
        "ticker":  ticker,
        "type":    type_alerte,
        "niveau":  niveau,
        "message": message,
        "details": details or {},
        "date":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "lue":     False,
    }
    alertes.append(alerte)
    _sauvegarder(alertes)
    return alerte


def marquer_lue(alerte_id: str) -> bool:
    alertes = _charger()
    for a in alertes:
        if a["id"] == alerte_id:
            a["lue"] = True
            _sauvegarder(alertes)
            return True
    return False


def tout_marquer_lu() -> int:
    alertes = _charger()
    nb = sum(1 for a in alertes if not a["lue"])
    for a in alertes:
        a["lue"] = True
    _sauvegarder(alertes)
    return nb


def supprimer_alerte(alerte_id: str) -> bool:
    alertes = _charger()
    avant = len(alertes)
    alertes = [a for a in alertes if a["id"] != alerte_id]
    if len(alertes) < avant:
        _sauvegarder(alertes)
        return True
    return False


def lister_alertes(non_lues_seulement: bool = False) -> list:
    alertes = _charger()
    if non_lues_seulement:
        alertes = [a for a in alertes if not a["lue"]]
    return sorted(alertes, key=lambda x: x["date"], reverse=True)


def compter_non_lues() -> int:
    return sum(1 for a in _charger() if not a["lue"])
