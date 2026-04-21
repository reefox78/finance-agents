"""
Dashboard router — données synthétiques pour la page d'accueil.
Aucun appel yfinance : tout vient de score_history et portfolio en DB.
"""
from fastapi import APIRouter
from api.deps import CurrentUser
from db.client import execute

router = APIRouter()


@router.get("/summary")
def get_summary(current_user: CurrentUser):
    uid = current_user["sub"]

    # ── 1. Dernière analyse par ticker (48h) ──────────────────────────────────
    rows = execute(
        """
        SELECT DISTINCT ON (ticker)
            ticker, score, decision, prix, ts,
            scores_agents
        FROM score_history
        WHERE user_id = %s
          AND ts > NOW() - INTERVAL '7 days'
        ORDER BY ticker, ts DESC
        """,
        (uid,), fetch="all"
    ) or []

    # Top 5 ACHETER (scores les plus hauts) et top 5 VENDRE (scores les plus bas)
    scored = sorted(
        [
            {
                "ticker":   r["ticker"],
                "score":    float(r["score"]),
                "decision": r["decision"],
                "prix":     float(r["prix"]) if r["prix"] else None,
                "ts":       r["ts"].strftime("%Y-%m-%dT%H:%M:%S"),
            }
            for r in rows
        ],
        key=lambda x: x["score"],
        reverse=True,
    )

    top_acheter = [x for x in scored if x["decision"] == "ACHETER"][:5]
    top_vendre  = [x for x in scored if x["decision"] == "VENDRE"][::-1][:5]

    # ── 2. Portfolio positions + dernier score connu ──────────────────────────
    positions = execute(
        "SELECT ticker, quantite, prix_moyen FROM positions WHERE user_id = %s",
        (uid,), fetch="all"
    ) or []

    # Dernier score connu pour chaque ticker du portfolio
    scores_map = {r["ticker"]: r for r in rows}

    portfolio_snapshot = []
    for p in positions:
        t = p["ticker"]
        s = scores_map.get(t)
        portfolio_snapshot.append({
            "ticker":     t,
            "quantite":   float(p["quantite"]),
            "prix_moyen": float(p["prix_moyen"]),
            "last_score":    float(s["score"])    if s else None,
            "last_decision": s["decision"]         if s else None,
            "last_ts":       s["ts"].strftime("%Y-%m-%dT%H:%M:%S") if s else None,
        })

    # ── 3. Stats générales ────────────────────────────────────────────────────
    total_analyses = execute(
        "SELECT COUNT(*) AS n FROM score_history WHERE user_id = %s",
        (uid,), fetch="one"
    )
    last_analyse = execute(
        "SELECT ticker, ts FROM score_history WHERE user_id = %s ORDER BY ts DESC LIMIT 1",
        (uid,), fetch="one"
    )

    return {
        "opportunites": {
            "acheter": top_acheter,
            "vendre":  top_vendre,
        },
        "portfolio":        portfolio_snapshot,
        "stats": {
            "total_analyses":  total_analyses["n"] if total_analyses else 0,
            "tickers_suivis":  len(scored),
            "positions":       len(positions),
            "last_ticker":     last_analyse["ticker"] if last_analyse else None,
            "last_ts":         last_analyse["ts"].strftime("%Y-%m-%dT%H:%M:%S") if last_analyse else None,
        },
    }
