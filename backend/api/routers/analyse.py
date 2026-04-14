"""
Analyse router — run full orchestrator analysis for a ticker.
"""
import json
import numpy as np
import pandas as pd
import yfinance as yf

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from orchestrator.orchestrator import run as orchestrer
from api.deps import CurrentUser

router = APIRouter()


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):  return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray):  return obj.tolist()
        return super().default(obj)


def _jsonify(data: dict) -> JSONResponse:
    return JSONResponse(content=json.loads(json.dumps(data, cls=_NumpyEncoder)))


def _safe(series: pd.Series, digits: int = 4) -> list:
    """Convert a pandas Series to a list of rounded floats (None for NaN)."""
    return [round(float(v), digits) if pd.notna(v) else None for v in series]


def _build_chart(ticker: str, period: str) -> dict:
    """Télécharge l'historique et calcule SMA, BB, RSI, MACD, Volume."""
    try:
        df = yf.download(ticker, period=period, auto_adjust=True,
                         multi_level_index=False, progress=False)
    except TypeError:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)

    # Flatten multi-level columns (yfinance < 0.2.18)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.empty:
        return {}

    close  = df["Close"].squeeze()
    volume = df["Volume"].squeeze() if "Volume" in df.columns else pd.Series(dtype=float)

    # Moving averages
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()

    # Bollinger Bands (20, ±2σ)
    bb_mid = sma20
    bb_std = close.rolling(20).std()
    bb_up  = bb_mid + 2 * bb_std
    bb_lo  = bb_mid - 2 * bb_std

    # RSI (14)
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, float("nan"))
    rsi   = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    ema12    = close.ewm(span=12, adjust=False).mean()
    ema26    = close.ewm(span=26, adjust=False).mean()
    macd_l   = ema12 - ema26
    macd_sig = macd_l.ewm(span=9, adjust=False).mean()
    macd_h   = macd_l - macd_sig

    # Volume colors: green if close > open, red otherwise
    open_  = df["Open"] if "Open" in df.columns else close.shift(1)
    vol_colors = ["rgba(46,204,113,0.6)" if c >= o else "rgba(231,76,60,0.6)"
                  for c, o in zip(close, open_)]

    dates = [str(idx.date()) for idx in df.index]

    return {
        "dates":       dates,
        "close":       _safe(close, 4),
        "open":        _safe(open_,  4),
        "sma20":       _safe(sma20,  4),
        "sma50":       _safe(sma50,  4),
        "bb_upper":    _safe(bb_up,  4),
        "bb_lower":    _safe(bb_lo,  4),
        "rsi":         _safe(rsi,    2),
        "macd":        _safe(macd_l,   4),
        "macd_signal": _safe(macd_sig, 4),
        "macd_hist":   _safe(macd_h,   4),
        "volume":      [int(v) if pd.notna(v) else 0 for v in volume],
        "vol_colors":  vol_colors,
    }


@router.get("/{ticker}")
def analyse(
    ticker:      str,
    current_user: CurrentUser,
    with_llm:    bool = Query(True,    description="Inclure le rapport LLM Groq"),
    mode_rapide: bool = Query(False,   description="Scoring uniquement, sans LLM"),
    period:      str  = Query("3mo",   description="Période historique (yfinance): 1mo,3mo,6mo,1y,2y"),
    with_chart:  bool = Query(True,    description="Inclure les données graphique"),
):
    ticker = ticker.upper().strip()
    try:
        result = orchestrer(
            ticker,
            with_llm=(with_llm and not mode_rapide),
            user_id=current_user["sub"],
        )
    except Exception as e:
        # Groq rate-limit → extraire le délai de réinitialisation depuis les headers
        try:
            from groq import RateLimitError as GroqRateLimitError
            if isinstance(e, GroqRateLimitError):
                headers = getattr(e, "response", None) and e.response.headers or {}
                reset_tokens   = headers.get("x-ratelimit-reset-tokens", "")
                reset_requests = headers.get("x-ratelimit-reset-requests", "")
                wait = reset_tokens or reset_requests or "quelques minutes"
                raise HTTPException(
                    status_code=429,
                    detail=f"Too Many Requests. Rate limited. Try after a while. Réinitialisation dans : {wait}",
                )
        except HTTPException:
            raise
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

    if with_chart:
        try:
            result["chart"] = _build_chart(ticker, period)
        except Exception as e:
            import traceback; traceback.print_exc()
            result["chart"] = {}

    return _jsonify(result)
