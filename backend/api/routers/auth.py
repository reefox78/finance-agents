"""
Auth router — register, login, me.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from db.auth import inscrire, connecter, get_user
from api.deps import create_access_token, CurrentUser

router = APIRouter()


class RegisterBody(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    email: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterBody):
    try:
        user = inscrire(body.username, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = create_access_token(str(user["id"]), user["username"], user["email"])
    return TokenResponse(
        access_token=token,
        user_id=str(user["id"]),
        username=user["username"],
        email=user["email"],
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginBody):
    try:
        user = connecter(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    token = create_access_token(user["id"], user["username"], user["email"])
    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        username=user["username"],
        email=user["email"],
    )


@router.get("/me")
def me(current_user: CurrentUser):
    user = get_user(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return {
        "id":       str(user["id"]),
        "username": user["username"],
        "email":    user["email"],
    }
