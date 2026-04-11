"""
Scanner router — scan watchlist or custom tickers (Server-Sent Events for progress).
"""
import json
import numpy as np
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from orchestrator.orchestrator import run as orchestrer
from api.deps import CurrentUser, decode_token

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
    min_score: float,
) -> AsyncGenerator[str, None]:
    """Génère des événements SSE — un par ticker analysé."""
    total = len(tickers)
    resultats = []

    for i, ticker in enumerate(tickers):
        # Événement de progression
        progress_event = {
            "type":    "progress",
            "current": i + 1,
            "total":   total,
            "ticker":  ticker,
        }
        yield f"data: {_dumps(progress_event)}\n\n"

        try:
            r = orchestrer(ticker, with_llm=False, user_id=user_id)
            score = r["scoring"]["score_final"]
            if score >= min_score:
                resultats.append({
                    "ticker":    ticker,
                    "score":     round(score, 4),
                    "decision":  r["scoring"]["decision"],
                    "technique": r["scoring"]["scores"].get("technique", 0),
                    "risque":    r["scoring"]["scores"].get("multiplicateur", 1),
                })
            result_event = {
                "type":   "result",
                "ticker": ticker,
                "score":  round(score, 4),
                "ok":     True,
            }
        except Exception as e:
            result_event = {"type": "result", "ticker": ticker, "ok": False, "error": str(e)}

        yield f"data: {_dumps(result_event)}\n\n"

    # Événement final avec tous les résultats triés
    done_event = {
        "type":      "done",
        "resultats": sorted(resultats, key=lambda x: x["score"], reverse=True),
    }
    yield f"data: {_dumps(done_event)}\n\n"


@router.get("/stream")
async def scanner_stream(
    categorie: str | None = Query(None),
    tickers: str | None = Query(None, description="Comma-separated tickers"),
    min_score: float = Query(0.0),
    # EventSource doesn't support headers → token passed as query param
    token: str = Query(..., description="JWT Bearer token"),
):
    """
    Scan en streaming (SSE).
    Chaque ticker envoie 2 événements : progress + result.
    Un événement 'done' final contient tous les résultats triés.
    """
    current_user = decode_token(token)

    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    else:
        ticker_list = _load_watchlist(categorie)

    return StreamingResponse(
        _scan_stream(ticker_list, current_user["sub"], min_score),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/watchlist")
def get_watchlist(current_user: CurrentUser):
    """Retourne la watchlist complète par catégorie."""
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        return json.load(f)
