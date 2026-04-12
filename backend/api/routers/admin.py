"""
Admin router — gestion des utilisateurs (réservé is_admin=True).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.admin import (
    lister_utilisateurs, get_utilisateur,
    reset_password, toggle_actif, toggle_admin, supprimer_utilisateur,
)
from api.deps import AdminUser

router = APIRouter()


class ResetPasswordBody(BaseModel):
    new_password: str


@router.get("/users")
def list_users(admin: AdminUser):
    return lister_utilisateurs()


@router.get("/users/{user_id}")
def get_user(user_id: str, admin: AdminUser):
    user = get_utilisateur(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return user


@router.post("/users/{user_id}/reset-password")
def reset_pwd(user_id: str, body: ResetPasswordBody, admin: AdminUser):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (min 8 caractères)")
    reset_password(user_id, body.new_password)
    return {"ok": True}


@router.post("/users/{user_id}/toggle-active")
def toggle_active(user_id: str, admin: AdminUser):
    # Empêche l'admin de se désactiver lui-même
    if user_id == admin["sub"]:
        raise HTTPException(status_code=400, detail="Impossible de modifier son propre statut")
    new_val = toggle_actif(user_id)
    return {"is_active": new_val}


@router.post("/users/{user_id}/toggle-admin")
def toggle_admin_role(user_id: str, admin: AdminUser):
    if user_id == admin["sub"]:
        raise HTTPException(status_code=400, detail="Impossible de modifier son propre rôle")
    new_val = toggle_admin(user_id)
    return {"is_admin": new_val}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, admin: AdminUser):
    if user_id == admin["sub"]:
        raise HTTPException(status_code=400, detail="Impossible de supprimer son propre compte")
    supprimer_utilisateur(user_id)
    return {"ok": True}
