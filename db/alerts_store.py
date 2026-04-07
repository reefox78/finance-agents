"""
Alertes — PostgreSQL.
Interface identique à data/alerts_store.py, avec user_id en plus.
"""

from db.client import execute

# Mapping type → niveau (pour compatibilité avec l'affichage dashboard)
_NIVEAU_PAR_TYPE = {
    "STOP_LOSS":        "CRITIQUE",
    "ALERTE_PNL":       "SURVEILLER",
    "CIBLE_ATTEINTE":   "INFO",
    "SCORE_VENDRE":     "VENDRE",
    "SCORE_SURVEILLER": "SURVEILLER",
    "info":             "INFO",
    "warn":             "SURVEILLER",
    "critical":         "CRITIQUE",
}


def _enrichir(row: dict) -> dict:
    """Ajoute les champs niveau et date pour compatibilité dashboard."""
    if row is None:
        return row
    row = dict(row)
    row["niveau"] = _NIVEAU_PAR_TYPE.get(row.get("type", ""), "INFO")
    # date lisible depuis created_at
    ca = row.get("created_at")
    if ca:
        try:
            row["date"] = ca.strftime("%Y-%m-%d")
        except Exception:
            row["date"] = str(ca)[:10]
    else:
        row["date"] = ""
    # Convertir UUID en str
    row["id"] = str(row["id"])
    return row


def ajouter_alerte(user_id: str, ticker: str, type_alerte: str, message: str) -> dict:
    row = execute(
        """
        INSERT INTO alerts (user_id, ticker, type, message)
        VALUES (%s, %s, %s, %s)
        RETURNING *
        """,
        (user_id, ticker.upper().strip(), type_alerte, message),
        fetch="one"
    )
    return _enrichir(row)


def lister_alertes(user_id: str, non_lues_seulement: bool = False) -> list[dict]:
    sql = "SELECT * FROM alerts WHERE user_id = %s"
    params = [user_id]
    if non_lues_seulement:
        sql += " AND lue = FALSE"
    sql += " ORDER BY created_at DESC"
    rows = execute(sql, tuple(params), fetch="all") or []
    return [_enrichir(r) for r in rows]


def compter_non_lues(user_id: str) -> int:
    row = execute(
        "SELECT COUNT(*) AS n FROM alerts WHERE user_id = %s AND lue = FALSE",
        (user_id,), fetch="one"
    )
    return int(row["n"]) if row else 0


def marquer_lue(user_id: str, alerte_id: str) -> None:
    execute(
        "UPDATE alerts SET lue = TRUE WHERE id = %s AND user_id = %s",
        (alerte_id, user_id)
    )


def tout_marquer_lu(user_id: str) -> None:
    execute(
        "UPDATE alerts SET lue = TRUE WHERE user_id = %s",
        (user_id,)
    )


def supprimer_alerte(user_id: str, alerte_id: str) -> None:
    execute(
        "DELETE FROM alerts WHERE id = %s AND user_id = %s",
        (alerte_id, user_id)
    )
