from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.api.dependencies import COOKIE_NAME, SESSION_SECONDS, create_admin_session, require_admin, valid_admin_session
from app.config import get_settings

router = APIRouter(tags=["admin-ui"], include_in_schema=False)
ui_dir = Path(__file__).resolve().parents[1] / "admin_ui"


@router.get("/admin")
def admin_page(request: Request):
    if not valid_admin_session(request.cookies.get(COOKIE_NAME, "")):
        return FileResponse(ui_dir / "login.html")
    return FileResponse(ui_dir / "index.html")


@router.post("/admin/login")
def admin_login(api_key: str = Form(...)):
    expected = get_settings().admin_api_key.get_secret_value()
    import secrets
    if not expected or not secrets.compare_digest(api_key, expected):
        return HTMLResponse("Invalid admin credentials", status_code=401)
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        COOKIE_NAME, create_admin_session(), max_age=SESSION_SECONDS,
        httponly=True, samesite="strict",
        secure=any(origin.lower().startswith("https://") for origin in get_settings().allowed_origins), path="/",
    )
    return response


@router.post("/admin/logout")
def admin_logout():
    response = RedirectResponse("/admin", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@router.get("/admin/assets/{filename}", dependencies=[Depends(require_admin)])
def admin_asset(filename: str):
    if filename not in {"admin.css", "admin.js"}:
        return HTMLResponse("Not found", status_code=404)
    return FileResponse(ui_dir / filename)
