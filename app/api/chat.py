import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.main_state import limiter
from app.models import Conversation, Document, DocumentChunk, Message
from app.schemas import ChatRequest, ChatResponse
from app.services.ai_provider import AIConfigurationError, get_ai_provider
from app.services.usage import month_usage, record_usage

router = APIRouter(prefix="/api/chat", tags=["chat"])


def compatible_chunks_query(service):
    """Materialize identity-compatible vectors before any distance operation."""
    return (
        select(DocumentChunk.content, DocumentChunk.embedding, Document.filename)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.indexing_status == "indexed",
            Document.embedding_provider == service.provider_name,
            Document.embedding_model == service.embedding_model,
            Document.embedding_dimensions == service.embedding_dimensions,
        )
        .cte("compatible_chunks")
        .prefix_with("MATERIALIZED")
    )


@router.post("", response_model=ChatResponse)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
def chat(request: Request, payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    settings = get_settings()
    conversation = db.get(Conversation, payload.conversation_id) if payload.conversation_id else None
    if payload.conversation_id and not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation is None:
        conversation = Conversation()
        db.add(conversation)
        db.flush()
    if settings.ai_provider_mode == "openai" and month_usage(db) >= settings.monthly_token_limit:
        raise HTTPException(status_code=429, detail="Monthly OpenAI usage limit reached")
    try:
        service = get_ai_provider(settings)
        vectors, embedding_tokens = service.embed([payload.message])
    except AIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Chat service is temporarily unavailable") from exc
    compatible_chunks = compatible_chunks_query(service)
    distance = compatible_chunks.c.embedding.cosine_distance(vectors[0]).label("distance")
    rows = db.execute(
        select(compatible_chunks.c.content, compatible_chunks.c.filename, distance)
        .where(distance < (0.999999 if settings.ai_provider_mode == "mock" else 0.55))
        .order_by(distance)
        .limit(settings.max_context_chunks)
    ).all()
    history_rows = db.execute(select(Message.role, Message.content).where(Message.conversation_id == conversation.id).order_by(Message.created_at.desc()).limit(6)).all()
    history = list(reversed(history_rows))
    sources = list(dict.fromkeys(row.filename for row in rows))
    if rows:
        try:
            answer, input_tokens, output_tokens = service.answer(payload.message, history, [(row.filename, row.content) for row in rows])
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Chat service is temporarily unavailable") from exc
    else:
        answer = "I don't have that information in the available company documents."
        input_tokens = output_tokens = 0
    db.add(Message(conversation_id=conversation.id, role="user", content=payload.message))
    db.add(Message(conversation_id=conversation.id, role="assistant", content=answer, sources=json.dumps(sources)))
    record_usage(db, embedding_tokens + input_tokens, output_tokens)
    db.commit()
    return ChatResponse(conversation_id=conversation.id, answer=answer, sources=sources)
