"""
Opérations admin — gestion des utilisateurs.
Toutes les fonctions requièrent d'avoir vérifié is_admin côté API.
"""
import bcrypt
from db.client import execute


def _fmt_user(row: dict | None) -> dict | None:
    if not row:
        return None
    row = dict(row)
    row["id"] = str(row["id"])
    if row.get("created_at"):
        row["created_at"] = str(row["created_at"])[:19]
    row.pop("password_hash", None)  # ne jamais exposer le hash
    return row


def lister_utilisateurs() -> list[dict]:
    rows = execute(
        """
        SELECT id, username, email, is_active, is_admin, created_at,
               (SELECT COUNT(*) FROM positions WHERE user_id = u.id AND quantite > 0) AS nb_positions,
               (SELECT COUNT(*) FROM transactions WHERE user_id = u.id)                AS nb_transactions
        FROM users u
        ORDER BY created_at
        """,
        fetch="all"
    ) or []
    result = []
    for r in rows:
        r = dict(r)
        r["id"]         = str(r["id"])
        r["nb_positions"]    = int(r["nb_positions"])
        r["nb_transactions"] = int(r["nb_transactions"])
        if r.get("created_at"):
            r["created_at"] = str(r["created_at"])[:19]
        r.pop("password_hash", None)
        result.append(r)
    return result


def get_utilisateur(user_id: str) -> dict | None:
    row = execute(
        "SELECT id, username, email, is_active, is_admin, created_at FROM users WHERE id = %s",
        (user_id,), fetch="one"
    )
    return _fmt_user(row)


def reset_password(user_id: str, new_password: str) -> None:
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=12)).decode()
    execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (hashed, user_id)
    )


def toggle_actif(user_id: str) -> bool:
    """Toggle is_active et retourne la nouvelle valeur."""
    row = execute(
        "UPDATE users SET is_active = NOT is_active WHERE id = %s RETURNING is_active",
        (user_id,), fetch="one"
    )
    return bool(row["is_active"]) if row else False


def toggle_admin(user_id: str) -> bool:
    """Toggle is_admin et retourne la nouvelle valeur."""
    row = execute(
        "UPDATE users SET is_admin = NOT is_admin WHERE id = %s RETURNING is_admin",
        (user_id,), fetch="one"
    )
    return bool(row["is_admin"]) if row else False


def supprimer_utilisateur(user_id: str) -> None:
    """Supprime l'utilisateur et toutes ses données (CASCADE)."""
    execute("DELETE FROM users WHERE id = %s", (user_id,))
