import secrets
import hashlib
import hmac
import time

from fastapi import Cookie, Header, HTTPException, status

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


def require_admin(
    x_admin_api_key: str = Header(default=""),
    chatbot_admin_session: str = Cookie(default="", alias=COOKIE_NAME),
) -> None:
    expected = get_settings().admin_api_key.get_secret_value()
    header_valid = bool(expected) and secrets.compare_digest(x_admin_api_key, expected)
    if not header_valid and not valid_admin_session(chatbot_admin_session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")
