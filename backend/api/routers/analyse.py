"""
Analyse router — run full orchestrator analysis for a ticker.
"""
import json
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from orchestrator.orchestrator import run as orchestrer
from api.deps import CurrentUser

router = APIRouter()


class _NumpyEncoder(json.JSONEncoder):
    """Serialize numpy scalars to native Python types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def _jsonify(data: dict) -> JSONResponse:
    return JSONResponse(content=json.loads(json.dumps(data, cls=_NumpyEncoder)))


class AnalyseResponse(BaseModel):
    ticker: str
    asset_type: str
    rapport: str
    scoring: dict
    tech: dict | None = None
    fund: dict | None = None
    sent: dict | None = None
    risk: dict | None = None
    trends: dict | None = None
    insider: dict | None = None
    macro: dict | None = None
    options_flow: dict | None = None
    sec_filings: dict | None = None
    short_interest: dict | None = None
    earnings_surprise: dict | None = None
    volume_delta: dict | None = None


@router.get("/{ticker}")
def analyse(
    ticker: str,
    current_user: CurrentUser,
    with_llm: bool = Query(True, description="Inclure le rapport LLM Groq"),
    mode_rapide: bool = Query(False, description="Scoring uniquement, sans LLM"),
):
    """
    Lance l'orchestrateur complet sur un ticker.
    with_llm=false ou mode_rapide=true → scoring uniquement, réponse rapide.
    """
    ticker = ticker.upper().strip()
    try:
        result = orchestrer(
            ticker,
            with_llm=(with_llm and not mode_rapide),
            user_id=current_user["sub"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return _jsonify(result)
