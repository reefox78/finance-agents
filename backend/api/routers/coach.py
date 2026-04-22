"""
Coach router — génère des insights basés sur des règles financières éprouvées.
Aucune IA externe : logique déterministe pure (Murphy, Elder, Van Tharp, Douglas…)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
from api.deps import CurrentUser
from coaching.analyse_coach import generate_coaching
from coaching.journal_coach import generate_journal_coaching
import db.journal as db_journal

router = APIRouter()


class AnalyseBody(BaseModel):
    result: dict[str, Any]  # résultat brut de l'orchestrateur


@router.post("/analyse")
def coach_analyse(body: AnalyseBody, current_user: CurrentUser):
    """
    Génère des insights de coaching à partir d'une analyse complète.
    Règles : Murphy, Elder, Van Tharp, PEAD, Weinstein…
    """
    try:
        return generate_coaching(body.result)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/journal")
def coach_journal(current_user: CurrentUser):
    """
    Génère des conseils personnalisés basés sur les stats réelles du journal.
    Règles : Van Tharp, Elder, Douglas, Steenbarger, Covel…
    """
    try:
        stats = db_journal.get_stats(current_user["sub"])
        return generate_journal_coaching(stats)
    except Exception as e:
        raise HTTPException(500, str(e))
