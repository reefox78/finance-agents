"""
FastAPI backend — Finance Agents
Exposes all analysis, scanner, portfolio and auth capabilities as REST endpoints.
"""
import sys
import logging
from datetime import datetime
from pathlib import Path

_root    = Path(__file__).parent.parent  # finance-agents/
_backend = Path(__file__).parent         # finance-agents/backend/

# Load .env from project root (works regardless of cwd when uvicorn is launched)
try:
    from dotenv import load_dotenv
    load_dotenv(_root / "config" / ".env")
except ImportError:
    pass

# project root → agents/, db/, orchestrator/ importables
sys.path.insert(0, str(_root))
# backend dir → api/ importable
sys.path.insert(0, str(_backend))

# ---------------------------------------------------------------------------
# Logging — stdout + fichier dans logs/ (lu par la page Logs admin)
# basicConfig est un no-op si uvicorn a déjà configuré le logging →
# on ajoute le FileHandler directement sur le root logger.
# ---------------------------------------------------------------------------
_LOGS_DIR = _root / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

_log_filename = _LOGS_DIR / f"api_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
_formatter    = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_file_handler = logging.FileHandler(_log_filename, encoding="utf-8")
_file_handler.setFormatter(_formatter)
_file_handler.setLevel(logging.INFO)

_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.addHandler(_file_handler)          # toujours ajouté, même après uvicorn

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)   # moins de bruit HTTP
logging.getLogger("httpx").setLevel(logging.WARNING)

logging.info("=== Finance Agents API démarrée — log : %s ===", _log_filename.name)

import re as _re
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import auth, analyse, scanner, portfolio, alerts, admin, logs, backtest, calendar, dashboard, journal, coach
from db.alert_rules import init_table as _init_alert_rules
from db.journal import init_table as _init_journal

# Initialisation BD — try/except pour ne pas crasher au démarrage si Supabase est
# temporairement indisponible (ex: cold start Render + DNS Supabase lent).
# Les tables seront créées à la première requête qui en a besoin.
try:
    _init_alert_rules()
except Exception as _e:
    logging.warning("DB alert_rules init échouée au démarrage (sera retentée) : %s", _e)

try:
    _init_journal()
except Exception as _e:
    logging.warning("DB journal init échouée au démarrage (sera retentée) : %s", _e)

# ── CORS helpers (partagés avec le handler global) ────────────────────────────
_CORS_ORIGINS = {
    "http://localhost:4200",
    "http://localhost:80",
    "https://finance-agents-one.vercel.app",
    "https://finance-agents-api.onrender.com",
}
_CORS_RE = _re.compile(r"https://(.*\.)?(vercel\.app|netlify\.app|onrender\.com)")

try:
    from api.routers import calibration as _calibration_mod
    _calibration_ok = True
except Exception as _e:
    print(f"[WARNING] Calibration router failed to load: {_e}")
    _calibration_mod = None
    _calibration_ok = False

app = FastAPI(
    title="Finance Agents API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow Angular dev server + production domain
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",       # Angular dev
        "http://localhost:80",         # Docker local
        "https://finance-agents-one.vercel.app",   # frontend Vercel prod
        "https://finance-agents-api.onrender.com",  # backend Render
    ],
    allow_origin_regex=r"https://(.*\.)?(vercel\.app|netlify\.app|onrender\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_api_logger = logging.getLogger("api")

# ---------------------------------------------------------------------------
# Middleware — log toutes les requêtes + CORS headers sur erreurs non catchées
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_logger(request: Request, call_next):
    try:
        response = await call_next(request)
        _api_logger.info("%s %s → %d", request.method, request.url.path, response.status_code)
        return response
    except Exception as exc:
        # L'exception a traversé tous les handlers (ex: PoolError, crash ASGI).
        # On renvoie une réponse JSON avec CORS headers pour éviter l'erreur CORS
        # opaque côté browser (sinon le browser voit status 0 sans CORS headers).
        _api_logger.error("Exception non rattrapée dans %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
            headers=_cors_headers(request),
        )


def _cors_headers(request: Request) -> dict:
    """Retourne les headers CORS appropriés selon l'origin de la requête."""
    origin = request.headers.get("origin", "")
    if origin in _CORS_ORIGINS or (origin and _CORS_RE.fullmatch(origin)):
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    return {}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Garantit les headers CORS sur toutes les réponses HTTP (4xx/5xx inclus).
    Sans ce handler, CORSMiddleware peut être court-circuité par le proxy Render
    sur les réponses d'erreur, laissant le frontend sans Access-Control-Allow-Origin."""
    _api_logger.warning("HTTP %d sur %s: %s", exc.status_code, request.url.path, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=_cors_headers(request),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all : garantit les headers CORS même sur erreurs non catchées."""
    _api_logger.error("Exception non gérée sur %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers=_cors_headers(request),
    )

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router,      prefix="/api/auth",      tags=["auth"])
app.include_router(analyse.router,   prefix="/api/analyse",   tags=["analyse"])
app.include_router(scanner.router,   prefix="/api/scanner",   tags=["scanner"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(alerts.router,    prefix="/api/alerts",    tags=["alerts"])
app.include_router(admin.router,     prefix="/api/admin",     tags=["admin"])
app.include_router(logs.router,      prefix="/api/logs",      tags=["logs"])
app.include_router(backtest.router,  prefix="/api/backtest",  tags=["backtest"])
app.include_router(calendar.router,   prefix="/api/calendar",   tags=["calendar"])
app.include_router(dashboard.router,  prefix="/api/dashboard",  tags=["dashboard"])
app.include_router(journal.router,    prefix="/api/journal",    tags=["journal"])
app.include_router(coach.router,      prefix="/api/coach",      tags=["coach"])
if _calibration_ok and _calibration_mod:
    app.include_router(_calibration_mod.router, prefix="/api/calibration", tags=["calibration"])


@app.get("/")
@app.head("/")
def root():
    return {"status": "ok", "service": "Finance Agents API"}


@app.get("/api/health")
def health():
    return {"status": "ok"}
