import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.config import get_settings
from app.database import get_db
from app.models import Document, DocumentChunk
from app.schemas import DocumentResponse, StatusResponse, UploadResponse
from app.services.documents import chunk_text, extract_text, sha256, validate_upload
from app.services.ai_provider import AIConfigurationError, get_ai_provider
from app.services.usage import month_usage, record_usage

router = APIRouter(prefix="/api/admin/documents", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    settings = get_settings()
    data = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    try:
        filename = validate_upload(file.filename or "", file.content_type, data, settings.max_upload_mb * 1024 * 1024)
        text = extract_text(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    digest = sha256(data)
    if db.scalar(select(Document.id).where(Document.sha256 == digest)):
        raise HTTPException(status_code=409, detail="This document has already been uploaded")
    chunks = chunk_text(text)
    if settings.ai_provider_mode == "openai" and month_usage(db) >= settings.monthly_token_limit:
        raise HTTPException(status_code=429, detail="Monthly OpenAI usage limit reached")
    try:
        embeddings, tokens = get_ai_provider(settings).embed(chunks)
    except AIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Document processing service is temporarily unavailable") from exc
    document = Document(filename=filename, content_type=file.content_type or "application/octet-stream", sha256=digest, size_bytes=len(data), content=data)
    db.add(document)
    db.flush()
    db.add_all(DocumentChunk(document_id=document.id, chunk_index=i, content=content, embedding=embedding) for i, (content, embedding) in enumerate(zip(chunks, embeddings, strict=True)))
    record_usage(db, tokens)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This document has already been uploaded") from exc
    db.refresh(document)
    return UploadResponse(
        id=document.id, filename=document.filename, content_type=document.content_type,
        size_bytes=document.size_bytes, created_at=document.created_at, chunks=len(chunks)
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


@router.delete("/{document_id}", response_model=StatusResponse)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> StatusResponse:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(document)
    db.commit()
    return StatusResponse(status="deleted")
