"""
Script de démarrage du backend — vérifie les tests avant de lancer uvicorn.

Usage (depuis la racine du projet) :
    python backend/start.py
    python backend/start.py --host 0.0.0.0 --port 8000
    python backend/start.py --no-reload
    python backend/start.py --skip-tests   # CI uniquement, tests déjà passés

Si les tests échouent, le serveur NE DÉMARRE PAS.
"""

import sys
import subprocess
import argparse
from pathlib import Path

ROOT    = Path(__file__).parent.parent  # finance-agents/
BACKEND = Path(__file__).parent         # finance-agents/backend/

SEP  = "=" * 60
SEP2 = "-" * 60


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_tests() -> bool:
    """Lance pytest depuis la racine du projet. Retourne True si tout passe."""
    print(f"\n{SEP}")
    print("  🧪  Vérification des tests avant démarrage...")
    print(f"{SEP}\n")

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=str(ROOT),
    )

    if result.returncode != 0:
        print(f"\n{SEP}")
        print("  ❌  TESTS KO — démarrage annulé.")
        print("  Corrige les erreurs ci-dessus puis relance le serveur.")
        print(f"{SEP}\n")
        return False

    print(f"\n{SEP}")
    print("  ✅  Tous les tests passent.")
    print(f"{SEP}\n")
    return True


# ---------------------------------------------------------------------------
# Server launcher
# ---------------------------------------------------------------------------

def start_server(host: str, port: int, reload: bool) -> None:
    """Démarre uvicorn depuis le répertoire backend."""
    import os
    # Ajoute la racine et le backend au path Python
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)

    try:
        import uvicorn
    except ImportError:
        print("❌  uvicorn n'est pas installé.")
        print("   pip install uvicorn[standard]")
        sys.exit(1)

    print(f"{SEP}")
    print(f"  🚀  Démarrage du serveur")
    print(f"      URL  → http://{host}:{port}")
    print(f"      Docs → http://{host}:{port}/docs")
    print(f"      Mode → {'développement (--reload)' if reload else 'production'}")
    print(f"{SEP}\n")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[
            str(BACKEND),
            str(ROOT / "orchestrator"),
            str(ROOT / "agents"),
            str(ROOT / "data"),
            str(ROOT / "db"),
        ],
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Finance Agents — démarre le backend FastAPI après validation des tests"
    )
    parser.add_argument("--host",       default="127.0.0.1", help="Adresse d'écoute (défaut: 127.0.0.1)")
    parser.add_argument("--port",       type=int, default=8000, help="Port (défaut: 8000)")
    parser.add_argument("--no-reload",  action="store_true",   help="Désactive le hot-reload")
    parser.add_argument("--skip-tests", action="store_true",   help="Ne pas lancer les tests (CI uniquement)")
    args = parser.parse_args()

    if not args.skip_tests:
        if not run_tests():
            sys.exit(1)

    start_server(
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
    )
