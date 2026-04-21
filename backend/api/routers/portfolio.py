"""
Portfolio router — positions, transactions, history, objectives.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.portfolio import (
    ajouter_achat, ajouter_vente,
    lister_positions, lister_transactions, lister_historique,
    evaluer_positions, definir_objectifs,
    supprimer_position, supprimer_vente,
)
from api.deps import CurrentUser

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AchatBody(BaseModel):
    ticker: str
    prix: float
    quantite: float
    date: str | None = None
    notes: str = ""
    frais: float = 0.0
    broker_key: str | None = None


class VenteBody(BaseModel):
    ticker: str
    prix_vente: float
    quantite: float
    date: str | None = None
    notes: str = ""
    frais: float = 0.0


class ObjectifsBody(BaseModel):
    ticker: str
    cible_pct: float | None = None
    stop_loss_pct: float | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/positions")
def positions(current_user: CurrentUser):
    return lister_positions(current_user["sub"])


@router.get("/evaluate")
def evaluate(current_user: CurrentUser, with_scores: bool = True):
    """Positions avec P&L, score agent et signal de sortie."""
    try:
        return evaluer_positions(current_user["sub"], with_scores=with_scores)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historique")
def historique(current_user: CurrentUser):
    return lister_historique(current_user["sub"])


@router.get("/transactions/{ticker}")
def transactions(ticker: str, current_user: CurrentUser):
    return lister_transactions(current_user["sub"], ticker.upper())


@router.post("/achat", status_code=201)
def achat(body: AchatBody, current_user: CurrentUser):
    try:
        return ajouter_achat(
            current_user["sub"], body.ticker, body.prix, body.quantite,
            body.date, body.notes, body.frais, body.broker_key,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vente")
def vente(body: VenteBody, current_user: CurrentUser):
    try:
        return ajouter_vente(
            current_user["sub"], body.ticker, body.prix_vente, body.quantite,
            body.date, body.notes, body.frais,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/objectifs")
def objectifs(body: ObjectifsBody, current_user: CurrentUser):
    definir_objectifs(
        current_user["sub"], body.ticker, body.cible_pct, body.stop_loss_pct
    )
    return {"ok": True}


@router.delete("/positions/{ticker}")
def supprimer(ticker: str, current_user: CurrentUser):
    supprimer_position(current_user["sub"], ticker.upper())
    return {"ok": True}


@router.delete("/ventes/{tx_id}")
def supprimer_tx(tx_id: str, current_user: CurrentUser):
    supprimer_vente(current_user["sub"], tx_id)
    return {"ok": True}


@router.get("/price/{ticker}")
def get_price(ticker: str, current_user: CurrentUser):
    """Retourne le prix actuel d'un ticker (léger, pour pré-remplir le formulaire d'achat)."""
    from data.market_data import get_ticker_raw_info, get_stock_data
    ticker = ticker.upper().strip()
    try:
        info = get_ticker_raw_info(ticker)
        prix = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
        if prix:
            return {"ticker": ticker, "prix": round(float(prix), 4)}
        df = get_stock_data(ticker, period="1d")
        if not df.empty:
            return {"ticker": ticker, "prix": round(float(df["Close"].iloc[-1]), 4)}
        raise HTTPException(status_code=404, detail=f"Prix introuvable pour {ticker}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyse-history/{ticker}")
def analyse_history(ticker: str, current_user: CurrentUser):
    """
    Retourne l'historique des analyses pour un ticker donné
    (score, décision, prix, scores_agents par agent).
    Résultats du plus récent au plus ancien.
    """
    ticker = ticker.upper().strip()
    try:
        from db.score_history import lire_historique as _db
        entries = _db(current_user["sub"], ticker)
    except Exception:
        from data.score_history import lire_historique as _local
        entries = _local(ticker)
    return list(reversed(entries))
