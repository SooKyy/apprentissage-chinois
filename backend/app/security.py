import base64
import hashlib
import hmac
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

bearer = HTTPBearer(auto_error=False)


def _sign(payload: str) -> str:
    key = get_settings().secret_key.encode("utf-8")
    digest = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def verify_password(password: str) -> bool:
    return hmac.compare_digest(password.encode("utf-8"), get_settings().admin_password.encode("utf-8"))


def create_access_token() -> str:
    expires = int(time.time()) + get_settings().access_token_expire_days * 86400
    return f"{expires}.{_sign(str(expires))}"


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    """Application mono-utilisateur : le jeton est une date d'expiration signée (HMAC-SHA256)."""
    error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton invalide ou expiré")
    if credentials is None:
        raise error
    expires, _, signature = credentials.credentials.partition(".")
    if not expires.isdigit() or not hmac.compare_digest(signature, _sign(expires)):
        raise error
    if int(expires) < time.time():
        raise error
