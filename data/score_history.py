"""
Historique des scores par ticker.

Chaque analyse sauvegarde automatiquement le score final dans
data/score_history.json, horodaté à la seconde.

Structure du fichier :
{
  "AAPL": [
    {
      "ts":           "2026-04-05T14:32:00",
      "score":        0.35,
      "decision":     "ACHETER",
      "prix":         175.23,          ← prix au moment de l'analyse
      "scores_agents": {               ← score de chaque agent actif
          "technique":  0.40,
          "fondamental": 0.20,
          ...
      }
    },
    ...
  ]
}

On garde au maximum MAX_ENTRIES entrées par ticker (FIFO).
"""

import json
from datetime import datetime
from pathlib import Path

_FICHIER    = Path(__file__).parent / "score_history.json"
MAX_ENTRIES = 200   # points max conservés par ticker


# ---------------------------------------------------------------------------
# I/O bas niveau
# ---------------------------------------------------------------------------

def _charger() -> dict:
    if not _FICHIER.exists():
        return {}
    try:
        with open(_FICHIER, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _sauvegarder(data: dict) -> None:
    with open(_FICHIER, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def enregistrer_score(ticker: str, score: float, decision: str,
                      prix: float | None = None,
                      scores_agents: dict | None = None) -> None:
    """
    Ajoute un point d'historique pour le ticker donné.

    prix          : prix de l'actif au moment de l'analyse (pour calibration)
    scores_agents : dict {agent: score_continu} pour chaque agent actif
    """
    data = _charger()
    entree: dict = {
        "ts":       datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "score":    round(score, 4),
        "decision": decision,
    }
    if prix is not None:
        entree["prix"] = round(prix, 4)
    if scores_agents:
        entree["scores_agents"] = {k: round(v, 4) for k, v in scores_agents.items()}

    historique = data.get(ticker, [])
    historique.append(entree)
    data[ticker] = historique[-MAX_ENTRIES:]
    _sauvegarder(data)


def lire_historique(ticker: str) -> list[dict]:
    """
    Retourne la liste des entrées pour ce ticker, du plus ancien au plus récent.
    Chaque entrée : {"ts", "score", "decision", optionnellement "prix" et "scores_agents"}
    """
    return _charger().get(ticker, [])


def lister_tickers() -> list[str]:
    """Retourne la liste des tickers qui ont au moins un point d'historique."""
    return list(_charger().keys())
