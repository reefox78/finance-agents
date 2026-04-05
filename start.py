"""
Lance le dashboard Streamlit ET le scheduler d'alertes en une seule commande.

Usage :
    python start.py            # dashboard + scheduler
    python start.py --no-alerts  # dashboard uniquement
"""

import subprocess
import sys
import os
import argparse
import signal
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description="Finance Agents — Démarrage")
    parser.add_argument("--no-alerts", action="store_true",
                        help="Lancer uniquement le dashboard, sans le scheduler d'alertes")
    parser.add_argument("--port", type=int, default=8501,
                        help="Port du dashboard Streamlit (défaut : 8501)")
    args = parser.parse_args()

    python = sys.executable
    processus = []

    print("=" * 55)
    print("  Finance Agents — Démarrage")
    print("=" * 55)

    # --- Dashboard Streamlit ---
    cmd_dashboard = [
        python, "-m", "streamlit", "run",
        str(ROOT / "output" / "dashboard.py"),
        "--server.port", str(args.port),
        "--server.headless", "false",
    ]
    print(f"\n▶  Dashboard    →  http://localhost:{args.port}")
    proc_dashboard = subprocess.Popen(cmd_dashboard, cwd=str(ROOT))
    processus.append(("Dashboard", proc_dashboard))

    # --- Scheduler d'alertes ---
    if not args.no_alerts:
        cmd_scheduler = [python, str(ROOT / "alerts" / "scheduler.py")]
        print("▶  Alertes      →  surveillance automatique des positions")
        proc_scheduler = subprocess.Popen(cmd_scheduler, cwd=str(ROOT))
        processus.append(("Scheduler", proc_scheduler))
    else:
        print("⏸  Alertes      →  désactivées (--no-alerts)")

    print("\nArrêter avec Ctrl+C\n")

    # Attente + arrêt propre sur Ctrl+C
    try:
        for _, proc in processus:
            proc.wait()
    except KeyboardInterrupt:
        print("\n\nArrêt en cours...")
        for nom, proc in processus:
            proc.terminate()
            print(f"  ✓ {nom} arrêté")
        print("Au revoir.")


if __name__ == "__main__":
    main()
