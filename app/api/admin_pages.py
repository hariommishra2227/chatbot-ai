from pathlib import Path

import secrets
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api import admin
from app.api.dependencies import COOKIE_NAME, SESSION_SECONDS, create_admin_session, require_admin_session
from app.config import get_settings
from app.database import get_db
from app.schemas import DocumentResponse, ReadinessResponse, ReindexResponse, StatusResponse, UploadResponse

router = APIRouter(tags=["admin-ui"], include_in_schema=False)
ui_dir = Path(__file__).resolve().parents[1] / "admin_ui"


@router.get("/admin", dependencies=[Depends(require_admin_session)])
def admin_page():
    return FileResponse(ui_dir / "index.html")


@router.get("/admin/login")
def admin_login_page():
    return FileResponse(ui_dir / "login.html")


@router.post("/admin/login")
def admin_login(request: Request, api_key: str = Form(...)):
    expected = get_settings().admin_api_key.get_secret_value()
    if not expected or not secrets.compare_digest(api_key, expected):
        return HTMLResponse("Invalid admin credentials", status_code=401)
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        COOKIE_NAME, create_admin_session(), max_age=SESSION_SECONDS,
        httponly=True, samesite="lax",
        secure=(request.url.scheme == "https" or any(origin.lower().startswith("https://") for origin in get_settings().allowed_origins)),
        path="/",
    )
    return response


@router.post("/admin/logout")
@router.get("/admin/logout")
def admin_logout():
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


@router.get("/admin/assets/{filename}", dependencies=[Depends(require_admin_session)])
def admin_asset(filename: str):
    if filename not in {"admin.css", "admin.js"}:
        return HTMLResponse("Not found", status_code=404)
    return FileResponse(ui_dir / filename)


# Browser-facing operations use the signed session. The public admin API remains
# independently protected by X-Admin-API-Key and never redirects to HTML.
@router.get("/admin/data/documents", response_model=list[DocumentResponse], dependencies=[Depends(require_admin_session)])
def browser_list_documents(db: Session = Depends(get_db)):
    return admin.list_documents(db)


@router.get("/admin/data/readiness", response_model=ReadinessResponse, dependencies=[Depends(require_admin_session)])
def browser_readiness():
    return admin.admin_readiness()


@router.post("/admin/data/documents", response_model=UploadResponse, status_code=201, dependencies=[Depends(require_admin_session)])
def browser_upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return admin.upload_document(file, db)


@router.post("/admin/data/documents/reindex-incompatible", response_model=ReindexResponse, dependencies=[Depends(require_admin_session)])
def browser_reindex_incompatible(db: Session = Depends(get_db)):
    return admin.reindex_incompatible(db)


@router.post("/admin/data/documents/{document_id}/reindex", response_model=ReindexResponse, dependencies=[Depends(require_admin_session)])
def browser_reindex_one(document_id: uuid.UUID, db: Session = Depends(get_db)):
    return admin.reindex_one(document_id, db)


@router.delete("/admin/data/documents/{document_id}", response_model=StatusResponse, dependencies=[Depends(require_admin_session)])
def browser_delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    return admin.delete_document(document_id, db)
