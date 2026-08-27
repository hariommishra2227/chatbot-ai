import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_admin(x_admin_api_key: str = Header(default="")) -> None:
    expected = get_settings().admin_api_key.get_secret_value()
    if not expected or not secrets.compare_digest(x_admin_api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")

