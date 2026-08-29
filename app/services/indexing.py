from sqlalchemy import delete
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.services.ai_provider import AIProvider
from app.services.documents import chunk_text, extract_text


def is_compatible(document: Document, provider: AIProvider) -> bool:
    return (
        document.indexing_status == "indexed"
        and document.embedding_provider == provider.provider_name
        and document.embedding_model == provider.embedding_model
        and document.embedding_dimensions == provider.embedding_dimensions
    )


def reindex_document(db: Session, document: Document, provider: AIProvider) -> tuple[int, int]:
    """Replace vectors atomically; provider failures leave the original document and chunks untouched."""
    text = extract_text(document.filename, document.content)
    chunks = chunk_text(text)
    embeddings, tokens = provider.embed(chunks)
    if len(embeddings) != len(chunks) or any(len(vector) != provider.embedding_dimensions for vector in embeddings):
        raise RuntimeError("Embedding provider returned incompatible vectors")

    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    db.add_all(
        DocumentChunk(document_id=document.id, chunk_index=index, content=content, embedding=embedding)
        for index, (content, embedding) in enumerate(zip(chunks, embeddings, strict=True))
    )
    document.embedding_provider = provider.provider_name
    document.embedding_model = provider.embedding_model
    document.embedding_dimensions = provider.embedding_dimensions
    document.indexing_status = "indexed"
    document.indexing_error = None
    document.indexing_error_at = None
    return len(chunks), tokens


def mark_indexing_error(document: Document) -> None:
    """Store only a safe operational marker, never an SDK exception or credential detail."""
    document.indexing_error = "Embedding generation failed; existing data was preserved"
    document.indexing_error_at = datetime.now(timezone.utc)
