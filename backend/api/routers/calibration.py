"""
Calibration router — lecture/écriture des poids des agents.

GET  /api/calibration/status   → poids actifs, mode, labels
POST /api/calibration/run      → lance la calibration globale (admin)
POST /api/calibration/apply    → sauvegarde des poids (admin)
DELETE /api/calibration/reset  → supprime les poids custom (admin)
"""

import json
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.deps import CurrentUser, AdminUser
from calibration.calibrator import (
    calibrer_global,
    sauvegarder_poids,
    charger_poids_custom,
    supprimer_poids_custom,
)
from orchestrator.scoring import POIDS as POIDS_DEFAUT

router = APIRouter()

_EXCLUS = {"risque", "multiplicateur", "mult_macro"}

_LABELS: dict[str, str] = {
    "technique":         "Technique",
    "fondamental":       "Fondamental",
    "sentiment":         "Sentiment",
    "trends":            "Google Trends",
    "insider":           "Insider",
    "macro":             "Macro",
    "options_flow":      "Options Flow",
    "sec_filings":       "SEC Filings",
    "short_interest":    "Short Interest",
    "earnings_surprise": "Earnings Surprise",
    "volume_delta":      "Volume Delta",
}


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray):  return obj.tolist()
        return super().default(obj)


def _jsonify(data):
    return JSONResponse(content=json.loads(json.dumps(data, cls=_NumpyEncoder)))


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status")
def get_status(current_user: CurrentUser):
    """Retourne les poids actifs, le mode (default/custom) et les labels."""
    custom = charger_poids_custom()
    poids_actifs = {k: v for k, v in (custom or POIDS_DEFAUT).items() if k not in _EXCLUS}
    poids_defaut = {k: v for k, v in POIDS_DEFAUT.items() if k not in _EXCLUS}
    return _jsonify({
        "mode":         "custom" if custom else "default",
        "poids_actifs": poids_actifs,
        "poids_defaut": poids_defaut,
        "labels":       _LABELS,
    })


@router.post("/run")
def run_calibration(current_user: AdminUser):
    """
    Lance la calibration globale sur l'historique des scores.
    Peut prendre 30–60 s selon le nombre de tickers.
    """
    try:
        result = calibrer_global(user_id=current_user["sub"])
        # Ajoute les labels et poids courants pour que le frontend puisse tout afficher
        custom = charger_poids_custom()
        poids_actifs = {k: v for k, v in (custom or POIDS_DEFAUT).items() if k not in _EXCLUS}
        result["poids_actifs"] = poids_actifs
        result["poids_defaut"] = {k: v for k, v in POIDS_DEFAUT.items() if k not in _EXCLUS}
        result["labels"]       = _LABELS
        return _jsonify(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class WeightsBody(BaseModel):
    poids: dict


@router.post("/apply")
def apply_weights(body: WeightsBody, current_user: AdminUser):
    """Sauvegarde les poids approuvés dans config/weights_custom.json."""
    for agent, val in body.poids.items():
        if not isinstance(val, (int, float)) or val < 0:
            raise HTTPException(status_code=422, detail=f"Poids invalide pour {agent}: {val}")
    try:
        sauvegarder_poids(body.poids)
        return {"ok": True, "mode": "custom"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/reset")
def reset_weights(current_user: AdminUser):
    """Supprime les poids custom — retour aux poids par défaut."""
    supprimer_poids_custom()
    return {"ok": True, "mode": "default"}
