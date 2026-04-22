"""
Journal de trading — CRUD + stats de performance.
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from api.deps import CurrentUser
import db.journal as db

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class TradeCreate(BaseModel):
    ticker:            str
    direction:         str   = "LONG"   # LONG | SHORT
    entry_price:       float
    entry_date:        str              # ISO date YYYY-MM-DD
    quantity:          float = 1.0
    strategy:          Optional[str]   = None
    score_at_entry:    Optional[float] = None
    decision_at_entry: Optional[str]   = None
    notes:             Optional[str]   = None


class TradeClose(BaseModel):
    exit_price: float
    exit_date:  str   # ISO date YYYY-MM-DD


class NotesPatch(BaseModel):
    notes: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_trades(
    current_user: CurrentUser,
    status:   Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    ticker:   Optional[str] = Query(None),
):
    """Liste les trades du journal (filtres optionnels)."""
    return db.list_trades(
        user_id  = current_user["sub"],
        status   = status,
        strategy = strategy,
        ticker   = ticker,
    )


@router.post("", status_code=201)
def create_trade(body: TradeCreate, current_user: CurrentUser):
    """Enregistre un nouveau trade (statut OPEN)."""
    direction = body.direction.upper()
    if direction not in ("LONG", "SHORT"):
        raise HTTPException(400, "direction doit être LONG ou SHORT")
    try:
        trade = db.add_trade(
            user_id           = current_user["sub"],
            ticker            = body.ticker,
            direction         = direction,
            entry_price       = body.entry_price,
            entry_date        = body.entry_date,
            quantity          = body.quantity,
            strategy          = body.strategy,
            score_at_entry    = body.score_at_entry,
            decision_at_entry = body.decision_at_entry,
            notes             = body.notes,
        )
        return trade
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/{trade_id}/close")
def close_trade(trade_id: str, body: TradeClose, current_user: CurrentUser):
    """Clôture un trade avec le prix de sortie et calcule le P&L."""
    result = db.close_trade(
        user_id    = current_user["sub"],
        trade_id   = trade_id,
        exit_price = body.exit_price,
        exit_date  = body.exit_date,
    )
    if not result:
        raise HTTPException(404, "Trade non trouvé ou déjà clôturé")
    return result


@router.patch("/{trade_id}/notes")
def patch_notes(trade_id: str, body: NotesPatch, current_user: CurrentUser):
    """Met à jour les notes d'un trade."""
    result = db.update_notes(current_user["sub"], trade_id, body.notes)
    if not result:
        raise HTTPException(404, "Trade non trouvé")
    return result


@router.delete("/{trade_id}", status_code=204)
def delete_trade(trade_id: str, current_user: CurrentUser):
    """Supprime un trade du journal."""
    ok = db.delete_trade(current_user["sub"], trade_id)
    if not ok:
        raise HTTPException(404, "Trade non trouvé")


@router.get("/stats")
def get_stats(current_user: CurrentUser):
    """
    Métriques de performance globales + par stratégie + equity curve.
    """
    return db.get_stats(current_user["sub"])
