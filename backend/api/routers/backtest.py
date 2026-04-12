"""
Backtest router — lance un backtest historique sur un ticker.
"""
import json
import numpy as np
from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from api.deps import CurrentUser

router = APIRouter()


# ─── Numpy serialisation ─────────────────────────────────────────────────────

class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray):  return obj.tolist()
        if isinstance(obj, (datetime, date)): return str(obj)
        return super().default(obj)


def _jsonify(data: dict) -> JSONResponse:
    return JSONResponse(content=json.loads(json.dumps(data, cls=_NumpyEncoder)))


# ─── Request schema ───────────────────────────────────────────────────────────

class BacktestRequest(BaseModel):
    ticker:  str   = "AAPL"
    debut:   str   = "2023-01-01"
    fin:     str   = "2024-12-31"
    capital: float = 10000.0
    mode:    str   = "multi"   # "multi" | "technique"

    @field_validator("ticker")
    @classmethod
    def _clean_ticker(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, v: str) -> str:
        if v not in ("multi", "technique"):
            raise ValueError("mode doit être 'multi' ou 'technique'")
        return v

    @field_validator("capital")
    @classmethod
    def _check_capital(cls, v: float) -> float:
        if v < 100 or v > 10_000_000:
            raise ValueError("capital entre 100 et 10 000 000")
        return v


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/run")
def run(req: BacktestRequest, current_user: CurrentUser):
    """
    Lance un backtest Backtrader.
    Retourne : métriques, liste des trades, courbe equity (sans DataFrame).
    Peut durer 15–60 secondes selon la période et le mode.
    """
    # Validation des dates
    try:
        d_debut = datetime.strptime(req.debut, "%Y-%m-%d").date()
        d_fin   = datetime.strptime(req.fin,   "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Format de date invalide (YYYY-MM-DD)")

    if d_debut >= d_fin:
        raise HTTPException(status_code=422, detail="La date de début doit être antérieure à la date de fin.")
    if (d_fin - d_debut).days < 30:
        raise HTTPException(status_code=422, detail="Période trop courte (min. 30 jours).")

    try:
        from backtesting.backtest import run_backtest
        result = run_backtest(
            ticker=req.ticker,
            debut=req.debut,
            fin=req.fin,
            capital=req.capital,
            mode=req.mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Extraire les prix de clôture quotidiens avant de supprimer le DataFrame
    df = result.pop("df", None)
    if df is not None:
        try:
            prices = [
                {"date": str(idx.date()), "close": round(float(row["Close"]), 4)}
                for idx, row in df.iterrows()
            ]
        except Exception:
            prices = []
    else:
        prices = []
    result["prices"] = prices

    # Stats supplémentaires
    trades    = result.get("trades", [])
    nb_trades = len(trades)
    wins      = [t for t in trades if t.get("pnlnet", 0) > 0]
    win_rate  = round(len(wins) / nb_trades * 100, 1) if nb_trades > 0 else 0
    max_gain  = max((t.get("pnlnet", 0) for t in trades), default=0)
    max_perte = min((t.get("pnlnet", 0) for t in trades), default=0)
    pnl_total = sum(t.get("pnlnet", 0) for t in trades)

    result["nb_trades"] = nb_trades
    result["win_rate"]  = win_rate
    result["max_gain"]  = round(max_gain, 2)
    result["max_perte"] = round(max_perte, 2)
    result["pnl_total"] = round(pnl_total, 2)

    return _jsonify(result)
