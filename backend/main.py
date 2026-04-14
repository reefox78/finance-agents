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
# ---------------------------------------------------------------------------
_LOGS_DIR = _root / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

_log_filename = _LOGS_DIR / f"api_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),                      # Render dashboard
        logging.FileHandler(_log_filename, encoding="utf-8"),   # page Logs admin
    ],
)

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # moins de bruit HTTP

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, analyse, scanner, portfolio, alerts, admin, logs, backtest

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
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
if _calibration_ok and _calibration_mod:
    app.include_router(_calibration_mod.router, prefix="/api/calibration", tags=["calibration"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
