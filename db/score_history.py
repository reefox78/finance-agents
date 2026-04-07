"""
Historique des scores — PostgreSQL.
Interface identique à data/score_history.py, avec user_id en plus.
"""

import json
from db.client import execute

MAX_ENTRIES = 200


def enregistrer_score(user_id: str, ticker: str, score: float, decision: str,
                      prix: float | None = None,
                      scores_agents: dict | None = None) -> None:
    """Enregistre un point d'historique. Garde les MAX_ENTRIES derniers."""
    execute(
        """
        INSERT INTO score_history (user_id, ticker, score, decision, prix, scores_agents)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (user_id, ticker.upper().strip(), round(score, 4), decision,
         round(float(prix), 4) if prix else None,
         json.dumps(scores_agents) if scores_agents else None)
    )

    # Nettoyage FIFO : garde les MAX_ENTRIES derniers par ticker/user
    execute(
        """
        DELETE FROM score_history
        WHERE user_id = %s AND ticker = %s
          AND id NOT IN (
              SELECT id FROM score_history
              WHERE user_id = %s AND ticker = %s
              ORDER BY ts DESC
              LIMIT %s
          )
        """,
        (user_id, ticker.upper().strip(),
         user_id, ticker.upper().strip(), MAX_ENTRIES)
    )


def lire_historique(user_id: str, ticker: str) -> list[dict]:
    """Retourne les entrées du plus ancien au plus récent."""
    rows = execute(
        """
        SELECT ts, score, decision, prix, scores_agents
        FROM score_history
        WHERE user_id = %s AND ticker = %s
        ORDER BY ts ASC
        """,
        (user_id, ticker.upper().strip()), fetch="all"
    )
    if not rows:
        return []
    result = []
    for r in rows:
        entry = {
            "ts":       r["ts"].strftime("%Y-%m-%dT%H:%M:%S"),
            "score":    float(r["score"]),
            "decision": r["decision"],
        }
        if r["prix"]:
            entry["prix"] = float(r["prix"])
        if r["scores_agents"]:
            sa = r["scores_agents"]
            entry["scores_agents"] = sa if isinstance(sa, dict) else json.loads(sa)
        result.append(entry)
    return result


def lister_tickers(user_id: str) -> list[str]:
    rows = execute(
        "SELECT DISTINCT ticker FROM score_history WHERE user_id = %s ORDER BY ticker",
        (user_id,), fetch="all"
    )
    return [r["ticker"] for r in rows] if rows else []
