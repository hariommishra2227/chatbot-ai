import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_api_key
from app.config import get_settings
from app.database import get_db
from app.models import Document, DocumentChunk
from app.schemas import DocumentResponse, ReadinessResponse, ReindexResponse, StatusResponse, UploadResponse
from app.services.documents import chunk_text, extract_text, sha256, validate_upload
from app.services.ai_provider import AIConfigurationError, get_ai_provider
from app.services.indexing import is_compatible, mark_indexing_error, reindex_document
from app.services.usage import month_usage, record_usage

router = APIRouter(prefix="/api/admin/documents", tags=["admin"], dependencies=[Depends(require_admin_api_key)])


@router.get("/readiness", response_model=ReadinessResponse)
def admin_readiness() -> ReadinessResponse:
    settings = get_settings()
    try:
        get_ai_provider(settings)
    except AIConfigurationError as exc:
        return ReadinessResponse(ai_mode=settings.ai_provider_mode, status="not ready", detail=str(exc))
    except Exception:
        return ReadinessResponse(ai_mode=settings.ai_provider_mode, status="not ready", detail="Provider client is unavailable")
    return ReadinessResponse(ai_mode=settings.ai_provider_mode, status="ready", detail="Provider configuration is present; connectivity is not checked")


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
        provider = get_ai_provider(settings)
        embeddings, tokens = provider.embed(chunks)
    except AIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Document processing service is temporarily unavailable") from exc
    if any(len(vector) != provider.embedding_dimensions for vector in embeddings):
        raise HTTPException(status_code=503, detail="Document processing returned incompatible embeddings")
    document = Document(
        filename=filename, content_type=file.content_type or "application/octet-stream", sha256=digest,
        size_bytes=len(data), content=data, embedding_provider=provider.provider_name,
        embedding_model=provider.embedding_model, embedding_dimensions=provider.embedding_dimensions,
        indexing_status="indexed",
    )
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
        size_bytes=document.size_bytes, created_at=document.created_at, chunks=len(chunks),
        embedding_provider=document.embedding_provider, embedding_model=document.embedding_model,
        embedding_dimensions=document.embedding_dimensions, indexing_status=document.indexing_status,
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    rows = db.execute(
        select(Document, func.count(DocumentChunk.id)).outerjoin(DocumentChunk).group_by(Document.id).order_by(Document.created_at.desc())
    ).all()
    settings = get_settings()
    try:
        provider = get_ai_provider(settings)
    except AIConfigurationError:
        provider = None
    result = []
    for document, count in rows:
        status_value = document.indexing_status
        if provider and not is_compatible(document, provider):
            status_value = "requires_reindex"
        result.append(DocumentResponse(
            id=document.id, filename=document.filename, content_type=document.content_type,
            size_bytes=document.size_bytes, created_at=document.created_at, chunks=count,
            embedding_provider=document.embedding_provider, embedding_model=document.embedding_model,
            embedding_dimensions=document.embedding_dimensions, indexing_status=status_value,
            indexing_error=document.indexing_error, indexing_error_at=document.indexing_error_at,
        ))
    return result


@router.post("/{document_id}/reindex", response_model=ReindexResponse)
def reindex_one(document_id: uuid.UUID, db: Session = Depends(get_db)) -> ReindexResponse:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        provider = get_ai_provider(get_settings())
        _, tokens = reindex_document(db, document, provider)
        record_usage(db, tokens)
        db.commit()
    except AIConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        preserved = db.get(Document, document_id)
        if preserved:
            mark_indexing_error(preserved)
            db.commit()
        raise HTTPException(status_code=503, detail="Document reindexing failed; the existing index was preserved") from exc
    return ReindexResponse(status="reindexed", succeeded=1, failed=0)


@router.post("/reindex-incompatible", response_model=ReindexResponse)
def reindex_incompatible(db: Session = Depends(get_db)) -> ReindexResponse:
    settings = get_settings()
    try:
        provider = get_ai_provider(settings)
    except AIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    document_ids = list(db.scalars(select(Document.id).order_by(Document.created_at)))
    succeeded = failed = 0
    for document_id in document_ids:
        document = db.get(Document, document_id)
        if document and not is_compatible(document, provider):
            try:
                _, tokens = reindex_document(db, document, provider)
                record_usage(db, tokens)
                db.commit()
                succeeded += 1
            except Exception:
                db.rollback()
                preserved = db.get(Document, document_id)
                if preserved:
                    mark_indexing_error(preserved)
                    db.commit()
                failed += 1
    status_value = "completed" if not failed else "completed with failures"
    return ReindexResponse(status=status_value, succeeded=succeeded, failed=failed)


@router.delete("/{document_id}", response_model=StatusResponse)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> StatusResponse:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(document)
    db.commit()
    return StatusResponse(status="deleted")
