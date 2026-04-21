"""
Scanner router — scan watchlist or custom tickers (Server-Sent Events for progress).
Exécution parallèle : jusqu'à CONCURRENCY tickers simultanément via asyncio + ThreadPoolExecutor.
"""
import asyncio
import json
import logging
import re
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from orchestrator.orchestrator import run as orchestrer
from api.deps import CurrentUser, decode_token

logger = logging.getLogger(__name__)

# ── Concurrence ──────────────────────────────────────────────────────────────
# 5 tickers en parallèle — suffisant pour x5–8 speedup sans flood yfinance/FRED
CONCURRENCY = 5
# ThreadPoolExecutor module-level pour réutilisation entre requêtes
_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="scanner")

# ── CORS for SSE (StreamingResponse bypasses the global CORSMiddleware) ─────
_ALLOWED_ORIGINS = {"http://localhost:4200", "http://localhost:80"}
_ALLOWED_RE = re.compile(r"https://(.*\.)?(vercel\.app|netlify\.app|onrender\.com)")

router = APIRouter()


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray):  return obj.tolist()
        return super().default(obj)


def _dumps(obj) -> str:
    return json.dumps(obj, cls=_NumpyEncoder)


WATCHLIST_PATH = Path(__file__).parent.parent.parent.parent / "config" / "watchlist.json"


def _load_watchlist(categorie: str | None = None) -> list[str]:
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if categorie:
        return data.get(categorie, [])
    tickers = []
    for v in data.values():
        tickers.extend(v)
    return list(dict.fromkeys(tickers))  # déduplique, préserve l'ordre


async def _scan_stream(
    tickers: list[str],
    user_id: str,
) -> AsyncGenerator[str, None]:
    """
    Génère des événements SSE — analyses exécutées en parallèle.

    Flux d'événements :
      progress  → chaque fois qu'un ticker est terminé (current/total)
      result    → résultat individuel (ok ou erreur)
      done      → résultats triés + erreurs, fin du stream
    """
    total     = len(tickers)
    resultats: list[dict] = []
    erreurs:   list[dict] = []
    completed = 0

    loop = asyncio.get_running_loop()
    sem  = asyncio.Semaphore(CONCURRENCY)
    queue: asyncio.Queue = asyncio.Queue()

    # ── Worker asynchrone pour un ticker ────────────────────────────────────
    async def _run_one(ticker: str) -> None:
        async with sem:
            try:
                # orchestrer() est synchrone (I/O bloquant) → thread pool
                r = await loop.run_in_executor(
                    _executor,
                    lambda: orchestrer(ticker, with_llm=False, user_id=user_id),
                )
                score = r["scoring"]["score_final"]
                await queue.put(("ok", ticker, {
                    "ticker":    ticker,
                    "score":     round(float(score), 4),
                    "decision":  r["scoring"]["decision"],
                    "technique": float(r["scoring"]["scores"].get("technique", 0)),
                    "risque":    float(r["scoring"]["scores"].get("multiplicateur", 1)),
                }))
            except Exception as exc:
                # L'exception est capturée ici — garantit qu'un item arrive
                # toujours dans la queue (pas de deadlock possible)
                logger.warning("Scanner FAIL: %s → %s", ticker, exc)
                await queue.put(("err", ticker, str(exc)))

    # ── Lance toutes les tâches (le semaphore régule la concurrence) ─────────
    tasks = [asyncio.create_task(_run_one(t)) for t in tickers]

    # ── Collecte les résultats dans l'ordre d'arrivée ────────────────────────
    for _ in range(total):
        status, ticker, payload = await queue.get()
        completed += 1

        # Événement de progression — ticker qui vient de terminer
        yield f"data: {_dumps({'type': 'progress', 'current': completed, 'total': total, 'ticker': ticker})}\n\n"

        if status == "ok":
            resultats.append(payload)
            logger.info("Scanner OK: %s score=%.4f", ticker, payload["score"])
            yield f"data: {_dumps({'type': 'result', 'ticker': ticker, 'score': payload['score'], 'ok': True})}\n\n"
        else:
            erreurs.append({"ticker": ticker, "error": payload})
            yield f"data: {_dumps({'type': 'result', 'ticker': ticker, 'ok': False, 'error': payload})}\n\n"

    # Attend la fin propre de toutes les tâches (normalement déjà terminées)
    await asyncio.gather(*tasks, return_exceptions=True)

    # ── Événement final ───────────────────────────────────────────────────────
    logger.info(
        "Scanner done: %d OK, %d erreurs sur %d tickers",
        len(resultats), len(erreurs), total,
    )
    yield f"data: {_dumps({'type': 'done', 'resultats': sorted(resultats, key=lambda x: x['score'], reverse=True), 'erreurs': erreurs, 'total': total})}\n\n"


@router.get("/stream")
async def scanner_stream(
    request: Request,
    categorie: str | None = Query(None),
    tickers: str | None = Query(None, description="Comma-separated tickers"),
    min_score: float = Query(0.0),   # conservé pour compatibilité (filtrage côté frontend)
    token: str = Query(..., description="JWT Bearer token"),
):
    """
    Scan en streaming (SSE).
    Analyses parallèles (CONCURRENCY={CONCURRENCY} simultanés).
    Événements : progress (par ticker terminé) + result + done final.
    """
    current_user = decode_token(token)

    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    else:
        ticker_list = _load_watchlist(categorie)

    origin = request.headers.get("origin", "")
    cors_headers: dict[str, str] = {
        "Cache-Control":     "no-cache",
        "X-Accel-Buffering": "no",
    }
    if origin in _ALLOWED_ORIGINS or (origin and _ALLOWED_RE.fullmatch(origin)):
        cors_headers["Access-Control-Allow-Origin"]      = origin
        cors_headers["Access-Control-Allow-Credentials"] = "true"

    return StreamingResponse(
        _scan_stream(ticker_list, current_user["sub"]),
        media_type="text/event-stream",
        headers=cors_headers,
    )


@router.get("/watchlist")
def get_watchlist(current_user: CurrentUser):
    """Retourne la watchlist complète par catégorie."""
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        return json.load(f)
