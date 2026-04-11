"""
Alerts router — list, mark as read, delete.
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
