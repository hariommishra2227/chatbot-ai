import secrets
import hashlib
import hmac
import time

from fastapi import Header, HTTPException, Request, status

from app.config import get_settings


COOKIE_NAME = "chatbot_admin_session"
SESSION_SECONDS = 8 * 60 * 60


def create_admin_session() -> str:
    key = get_settings().admin_api_key.get_secret_value().encode()
    expires = str(int(time.time()) + SESSION_SECONDS)
    signature = hmac.new(key, expires.encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def valid_admin_session(token: str) -> bool:
    try:
        expires, signature = token.split(".", 1)
        if int(expires) < int(time.time()):
            return False
    except (ValueError, TypeError):
        return False
    key = get_settings().admin_api_key.get_secret_value().encode()
    if not key:
        return False
    expected = hmac.new(key, expires.encode(), hashlib.sha256).hexdigest()
    return secrets.compare_digest(signature, expected)


def require_admin_api_key(x_admin_api_key: str = Header(default="")) -> None:
    """Authenticate machine/API requests with the explicit admin header only."""
    expected = get_settings().admin_api_key.get_secret_value()
    if not expected or not secrets.compare_digest(x_admin_api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")


def require_admin_session(request: Request) -> None:
    """Authenticate browser pages with the signed HttpOnly session only."""
    if not valid_admin_session(request.cookies.get(COOKIE_NAME, "")):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})
