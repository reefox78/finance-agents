"""
FastAPI backend — Finance Agents
Exposes all analysis, scanner, portfolio and auth capabilities as REST endpoints.
"""
import sys
from pathlib import Path

_root    = Path(__file__).parent.parent  # finance-agents/
_backend = Path(__file__).parent         # finance-agents/backend/

# project root → agents/, db/, orchestrator/ importables
sys.path.insert(0, str(_root))
# backend dir → api/ importable
sys.path.insert(0, str(_backend))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, analyse, scanner, portfolio, alerts, admin, logs, backtest

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
        "http://localhost:4200",   # Angular dev
        "https://*.vercel.app",    # Vercel preview
        "https://*.netlify.app",   # Netlify preview
    ],
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
app.include_router(backtest.router,  prefix="/api/backtest",  tags=["backtest"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
