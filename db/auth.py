"""
Authentification utilisateur — bcrypt + PostgreSQL.

Fonctions publiques :
    inscrire(username, email, password)  → dict user ou lève ValueError
    connecter(email, password)           → dict user ou lève ValueError
    get_user(user_id)                    → dict user ou None
"""

import bcrypt
from db.client import execute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Hash bcrypt (coût 12). Jamais le mot de passe en clair en base."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _valider_password(password: str) -> None:
    """Lève ValueError si le mot de passe ne respecte pas les règles."""
    if len(password) < 8:
        raise ValueError("Le mot de passe doit contenir au moins 8 caractères.")
    if not any(c.isupper() for c in password):
        raise ValueError("Le mot de passe doit contenir au moins une majuscule.")
    if not any(c.isdigit() for c in password):
        raise ValueError("Le mot de passe doit contenir au moins un chiffre.")


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def inscrire(username: str, email: str, password: str) -> dict:
    """
    Crée un compte utilisateur.
    Lève ValueError si username/email déjà pris ou mot de passe trop faible.
    """
    username = username.strip()
    email    = email.strip().lower()

    if not username or not email:
        raise ValueError("Username et email obligatoires.")

    _valider_password(password)

    # Vérifie les doublons
    existing = execute(
        "SELECT id FROM users WHERE email = %s OR username = %s",
        (email, username), fetch="one"
    )
    if existing:
        raise ValueError("Cet email ou ce nom d'utilisateur est déjà utilisé.")

    password_hash = _hash_password(password)

    user = execute(
        """
        INSERT INTO users (username, email, password_hash)
        VALUES (%s, %s, %s)
        RETURNING id, username, email, created_at
        """,
        (username, email, password_hash),
        fetch="one",
    )
    return user


def connecter(email: str, password: str) -> dict:
    """
    Vérifie les identifiants et retourne le user.
    Lève ValueError si email inconnu, mot de passe incorrect, ou compte inactif.
    """
    email = email.strip().lower()

    row = execute(
        "SELECT id, username, email, password_hash, is_active FROM users WHERE email = %s",
        (email,), fetch="one"
    )

    # Message volontairement identique pour ne pas indiquer si l'email existe
    if not row:
        raise ValueError("Email ou mot de passe incorrect.")

    if not row["is_active"]:
        raise ValueError("Ce compte est désactivé.")

    if not _verify_password(password, row["password_hash"]):
        raise ValueError("Email ou mot de passe incorrect.")

    return {
        "id":       str(row["id"]),
        "username": row["username"],
        "email":    row["email"],
    }


def get_user(user_id: str) -> dict | None:
    """Retourne les infos publiques d'un utilisateur par son UUID."""
    return execute(
        "SELECT id, username, email, created_at FROM users WHERE id = %s",
        (user_id,), fetch="one"
    )
