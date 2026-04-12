"""
⚠️  OBSOLÈTE — Ce script lançait l'ancienne interface Streamlit.
   L'interface Streamlit a été remplacée par le frontend Angular.

Pour démarrer l'application :
  → Windows : double-cliquer sur start-dev.bat
  → Terminal : make dev-back  (backend FastAPI :8000)
               make dev-front (frontend Angular :4200)
"""
import sys

print(
    "\n⚠️  start.py est obsolète.\n"
    "   L'interface Streamlit a été remplacée par le frontend Angular.\n\n"
    "   Utilise start-dev.bat ou :\n"
    "     make dev-back   → backend FastAPI  (port 8000)\n"
    "     make dev-front  → frontend Angular (port 4200)\n"
)
sys.exit(1)
