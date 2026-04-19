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


@router.get("/debug")
def debug_history(current_user: CurrentUser):
    """
    Diagnostic : inspecte ce qui est en base pour cet utilisateur.
    Permet de comprendre pourquoi la calibration trouve 0 points.
    """
    from db.client import execute as db_exec
    from datetime import datetime, timedelta

    uid = current_user["sub"]
    HORIZON = 7

    try:
        # Nombre total d'entrées
        total = db_exec(
            "SELECT COUNT(*) AS n FROM score_history WHERE user_id = %s",
            (uid,), fetch="one"
        )
        # Entrées avec scores_agents renseigné
        with_agents = db_exec(
            "SELECT COUNT(*) AS n FROM score_history WHERE user_id = %s AND scores_agents IS NOT NULL",
            (uid,), fetch="one"
        )
        # Entrées avec prix renseigné
        with_prix = db_exec(
            "SELECT COUNT(*) AS n FROM score_history WHERE user_id = %s AND prix IS NOT NULL",
            (uid,), fetch="one"
        )
        # Entrées assez anciennes (> HORIZON jours)
        cutoff = (datetime.utcnow() - timedelta(days=HORIZON)).isoformat()
        old_enough = db_exec(
            "SELECT COUNT(*) AS n FROM score_history WHERE user_id = %s AND ts < %s",
            (uid, cutoff), fetch="one"
        )
        # Tickers distincts
        tickers = db_exec(
            "SELECT DISTINCT ticker FROM score_history WHERE user_id = %s ORDER BY ticker",
            (uid,), fetch="all"
        )
        # 5 entrées les plus récentes
        recents = db_exec(
            "SELECT ticker, ts, score, decision, prix, scores_agents IS NOT NULL AS has_agents "
            "FROM score_history WHERE user_id = %s ORDER BY ts DESC LIMIT 5",
            (uid,), fetch="all"
        )

        return _jsonify({
            "user_id":        uid,
            "total_entries":  total["n"] if total else 0,
            "with_agents":    with_agents["n"] if with_agents else 0,
            "with_prix":      with_prix["n"] if with_prix else 0,
            "old_enough":     old_enough["n"] if old_enough else 0,
            "horizon_jours":  HORIZON,
            "tickers":        [r["ticker"] for r in tickers] if tickers else [],
            "recents": [
                {
                    "ticker":     r["ticker"],
                    "ts":         str(r["ts"]),
                    "score":      float(r["score"]),
                    "decision":   r["decision"],
                    "prix":       float(r["prix"]) if r["prix"] else None,
                    "has_agents": r["has_agents"],
                }
                for r in (recents or [])
            ],
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur diagnostic : {e}")
