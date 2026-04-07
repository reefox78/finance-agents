"""
Authentification Google OAuth 2.0.

Flow :
  1. generate_state()            → token signé HMAC (anti-CSRF sans session)
  2. get_auth_url(state)         → URL de redirection vers Google
  3. exchange_code(code)         → échange le code contre les infos utilisateur Google
  4. connecter_ou_inscrire(...)  → trouve ou crée le compte dans public.users

Variables d'environnement requises (dans config/.env) :
  GOOGLE_CLIENT_ID      → OAuth 2.0 Client ID (Google Cloud Console)
  GOOGLE_CLIENT_SECRET  → OAuth 2.0 Client Secret
  APP_URL               → URL de l'app, ex: http://localhost:8501
  SECRET_KEY            → clé secrète pour signer le state (min. 32 chars aléatoires)
"""

import os
import hmac
import hashlib
import secrets
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

from db.client import execute

load_dotenv("config/.env")

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_INFO_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"

# L'URI de redirection doit être identique à celle enregistrée dans Google Cloud Console
APP_URL      = os.getenv("APP_URL", "http://localhost:8501").rstrip("/")
REDIRECT_URI = APP_URL


# ---------------------------------------------------------------------------
# State HMAC (protection CSRF sans session côté serveur)
# ---------------------------------------------------------------------------

def _sign(nonce: str) -> str:
    secret = os.getenv("SECRET_KEY", "change_me_please_use_a_real_secret")
    return hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()


def generate_state() -> str:
    """Génère un token state signé — peut être vérifié sans session."""
    nonce = secrets.token_hex(16)
    return f"{nonce}.{_sign(nonce)}"


def verify_state(state: str) -> bool:
    """Vérifie la signature HMAC du state reçu depuis Google."""
    try:
        nonce, sig = state.split(".", 1)
        return hmac.compare_digest(sig, _sign(nonce))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------

def get_auth_url(state: str) -> str:
    """Construit l'URL d'autorisation Google."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        raise ValueError("GOOGLE_CLIENT_ID manquant dans config/.env")

    params = {
        "client_id":     client_id,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "offline",
        "prompt":        "select_account",   # toujours montrer le sélecteur de compte
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """
    Échange le code d'autorisation contre les informations du compte Google.
    Retourne un dict avec : sub, email, name, picture.
    """
    client_id     = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET manquants dans config/.env")

    # 1. Échange code → access_token
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "code":          code,
        "client_id":     client_id,
        "client_secret": client_secret,
        "redirect_uri":  REDIRECT_URI,
        "grant_type":    "authorization_code",
    }, timeout=10)
    resp.raise_for_status()
    tokens = resp.json()

    # 2. Récupère les infos utilisateur
    info_resp = requests.get(
        GOOGLE_INFO_URL,
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        timeout=10,
    )
    info_resp.raise_for_status()
    return info_resp.json()   # {sub, email, name, picture, email_verified, ...}


# ---------------------------------------------------------------------------
# Trouve ou crée le compte
# ---------------------------------------------------------------------------

def connecter_ou_inscrire(google_id: str, email: str, name: str) -> dict:
    """
    Recherche le compte par email (identifiant unique).
    - Email déjà inscrit (même sans Google) → connexion directe, google_id mémorisé
    - Email inconnu → création d'un compte Google sans mot de passe
    """
    email = email.strip().lower()

    existing = execute(
        "SELECT id, username, email FROM users WHERE email = %s AND is_active = TRUE",
        (email,), fetch="one"
    )

    if existing:
        # Associe le google_id si ce n'est pas encore fait (compte créé localement)
        execute(
            "UPDATE users SET google_id = COALESCE(google_id, %s), auth_provider = COALESCE(NULLIF(auth_provider,'local'), auth_provider) WHERE email = %s",
            (google_id, email)
        )
        return {
            "id":       str(existing["id"]),
            "username": existing["username"],
            "email":    existing["email"],
        }

    # Nouveau compte : dériver un username depuis le nom complet ou l'email
    base = (name.replace(" ", "_") or email.split("@")[0])[:48]
    base = "".join(c for c in base if c.isalnum() or c == "_") or "user"
    username = base
    counter  = 1
    while execute("SELECT id FROM users WHERE username = %s", (username,), fetch="one"):
        username = f"{base}_{counter}"
        counter += 1

    user = execute(
        """
        INSERT INTO users (username, email, google_id, auth_provider, password_hash)
        VALUES (%s, %s, %s, 'google', NULL)
        RETURNING id, username, email
        """,
        (username, email, google_id),
        fetch="one"
    )
    return {
        "id":       str(user["id"]),
        "username": user["username"],
        "email":    user["email"],
    }
