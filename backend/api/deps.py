"""
JWT authentication dependency — reusable across all routers.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

SECRET_KEY  = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM   = "HS256"
EXPIRE_DAYS = 30

# Clé statique pour le skill Claude.ai (lecture seule, sans expiration)
SKILL_API_KEY = os.getenv("SKILL_API_KEY", "")

# Faux utilisateur retourné quand la clé skill est utilisée
_SKILL_USER = {
    "sub":      "skill-claude",
    "username": "claude-skill",
    "email":    "skill@finance-agents.local",
    "is_admin": False,
}

bearer_scheme = HTTPBearer()


def create_access_token(user_id: str, username: str, email: str, is_admin: bool = False) -> str:
    payload = {
        "sub":      user_id,
        "username": username,
        "email":    email,
        "is_admin": is_admin,
        "exp":      datetime.now(timezone.utc) + timedelta(days=EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    # Accepte la clé statique du skill Claude (si configurée)
    if SKILL_API_KEY and token == SKILL_API_KEY:
        return _SKILL_USER
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
        )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> dict:
    return decode_token(credentials.credentials)


CurrentUser = Annotated[dict, Depends(get_current_user)]


def get_admin_user(current_user: CurrentUser) -> dict:
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user


AdminUser = Annotated[dict, Depends(get_admin_user)]
