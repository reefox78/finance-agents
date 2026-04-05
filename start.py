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
from datetime import datetime
from pathlib import Path

ROOT     = Path(__file__).parent
LOGS_DIR = ROOT / "logs"


def main():
    parser = argparse.ArgumentParser(description="Finance Agents — Démarrage")
    parser.add_argument("--no-alerts", action="store_true",
                        help="Lancer uniquement le dashboard, sans le scheduler d'alertes")
    parser.add_argument("--port", type=int, default=8501,
                        help="Port du dashboard Streamlit (défaut : 8501)")
    args = parser.parse_args()

    python    = sys.executable
    processus = []
    fichiers_log = []

    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

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
    log_dash = LOGS_DIR / f"dashboard_{timestamp}.log"
    f_dash   = open(log_dash, "w", encoding="utf-8")
    fichiers_log.append(f_dash)

    print(f"\n▶  Dashboard    →  http://localhost:{args.port}")
    print(f"   Log          →  {log_dash.relative_to(ROOT)}")
    proc_dashboard = subprocess.Popen(cmd_dashboard, cwd=str(ROOT),
                                      stdout=f_dash, stderr=f_dash)
    processus.append(("Dashboard", proc_dashboard))

    # --- Scheduler d'alertes ---
    if not args.no_alerts:
        cmd_scheduler = [python, str(ROOT / "alerts" / "scheduler.py")]
        log_sched = LOGS_DIR / f"scheduler_{timestamp}.log"
        f_sched   = open(log_sched, "w", encoding="utf-8")
        fichiers_log.append(f_sched)

        print("▶  Alertes      →  surveillance automatique des positions")
        print(f"   Log          →  {log_sched.relative_to(ROOT)}")
        proc_scheduler = subprocess.Popen(cmd_scheduler, cwd=str(ROOT),
                                          stdout=f_sched, stderr=f_sched)
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
    finally:
        for f in fichiers_log:
            try:
                f.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
