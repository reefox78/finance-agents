"""
Alerts router — list, mark as read, delete + alert rules management.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.alerts_store import (
    lister_alertes, compter_non_lues,
    marquer_lue, tout_marquer_lu, supprimer_alerte,
)
from api.deps import CurrentUser

router = APIRouter()


@router.get("/")
def alertes(current_user: CurrentUser, non_lues_seulement: bool = False):
    return lister_alertes(current_user["sub"], non_lues_seulement)


@router.get("/count")
def count(current_user: CurrentUser):
    return {"count": compter_non_lues(current_user["sub"])}


@router.put("/{alerte_id}/read")
def mark_read(alerte_id: str, current_user: CurrentUser):
    marquer_lue(current_user["sub"], alerte_id)
    return {"ok": True}


@router.put("/read-all")
def mark_all_read(current_user: CurrentUser):
    tout_marquer_lu(current_user["sub"])
    return {"ok": True}


@router.delete("/{alerte_id}")
def delete(alerte_id: str, current_user: CurrentUser):
    supprimer_alerte(current_user["sub"], alerte_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Alert Rules
# ---------------------------------------------------------------------------

from db.alert_rules import (  # noqa: E402
    ajouter_regle,
    lister_regles,
    supprimer_regle,
    toggle_regle,
    checker_regles,
)


class RegleCreate(BaseModel):
    ticker: str
    condition: str
    valeur: float
    notif_email: bool = False


@router.get("/rules")
def get_rules(current_user: CurrentUser):
    return lister_regles(current_user["sub"])


@router.post("/rules")
def create_rule(body: RegleCreate, current_user: CurrentUser):
    try:
        return ajouter_regle(
            user_id=current_user["sub"],
            ticker=body.ticker,
            condition=body.condition,
            valeur=body.valeur,
            notif_email=body.notif_email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/rules/{regle_id}")
def delete_rule(regle_id: str, current_user: CurrentUser):
    supprimer_regle(current_user["sub"], regle_id)
    return {"ok": True}


@router.put("/rules/{regle_id}/toggle")
def toggle_rule(regle_id: str, current_user: CurrentUser):
    try:
        return toggle_regle(current_user["sub"], regle_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/check")
def check_rules(current_user: CurrentUser):
    """Déclenche une vérification immédiate de toutes les règles actives."""
    triggered = checker_regles(current_user["sub"])
    return {"triggered": triggered, "count": len(triggered)}
