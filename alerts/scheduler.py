"""
Scheduler d'alertes — à lancer en arrière-plan dans un terminal séparé.

Usage :
    python alerts/scheduler.py

Le scheduler vérifie les positions toutes les X minutes (config/alerts.json → planning.intervalle_minutes).
Les alertes sont stockées dans data/alerts.json et visibles dans le dashboard.
L'email est envoyé si email.enabled = true dans config/alerts.json.

Pour arrêter : Ctrl+C
"""

import sys
import os
import json
import time
import io
from datetime import datetime
from pathlib import Path

# Encodage UTF-8 pour le terminal Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

CONFIG_PATH = Path("config/alerts.json")


def _charger_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"planning": {"intervalle_minutes": 60, "actif": True, "avec_scores": False}}


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_once() -> None:
    """Effectue une vérification complète et envoie l'email si configuré."""
    from alerts.monitor import verifier_positions, envoyer_email_si_configure

    config      = _charger_config()
    avec_scores = config.get("planning", {}).get("avec_scores", False)

    _log(f"Vérification des positions (scores={'oui' if avec_scores else 'non'})...")

    try:
        nouvelles = verifier_positions(with_scores=avec_scores)

        if nouvelles:
            _log(f"{len(nouvelles)} nouvelle(s) alerte(s) :")
            for a in nouvelles:
                icone = {"CRITIQUE": "🔴", "VENDRE": "🔴", "SURVEILLER": "🟡", "INFO": "🔵"}.get(a["niveau"], "⚪")
                _log(f"  {icone} [{a['ticker']}] {a['message']}")

            email_envoye = envoyer_email_si_configure(nouvelles)
            if email_envoye:
                _log("Email de notification envoyé.")
            else:
                _log("Email non envoyé (désactivé ou non configuré — voir config/alerts.json).")
        else:
            _log("Aucune alerte. Toutes les positions sont dans les seuils.")

    except Exception as e:
        _log(f"ERREUR lors de la vérification : {e}")


def main() -> None:
    _log("=" * 60)
    _log("Finance Agents — Scheduler d'alertes démarré")
    _log("Arrêter avec Ctrl+C")
    _log("=" * 60)

    # Première vérification immédiate au démarrage
    run_once()

    while True:
        config    = _charger_config()
        planning  = config.get("planning", {})
        actif     = planning.get("actif", True)
        intervalle = int(planning.get("intervalle_minutes", 60))

        if not actif:
            _log("Scheduler en pause (planning.actif = false dans config/alerts.json).")
            time.sleep(60)
            continue

        _log(f"Prochaine vérification dans {intervalle} minute(s)...")
        time.sleep(intervalle * 60)
        run_once()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Scheduler] Arrêté.")
