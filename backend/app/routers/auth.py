from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas import LoginRequest, Token
from app.security import create_access_token, require_auth, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest) -> Token:
    if not verify_password(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mot de passe incorrect")
    return Token(access_token=create_access_token())


@router.get("/me", dependencies=[Depends(require_auth)])
def me() -> dict[str, bool]:
    return {"ok": True}
