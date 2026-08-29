import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    sources: list[str]


class LeadCreate(BaseModel):
    conversation_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=160)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=32, pattern=r"^[0-9+() .-]+$")
    requirement: str = Field(min_length=5, max_length=3000)


class LeadResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    chunks: int = 0
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    indexing_status: str
    indexing_error: str | None = None
    indexing_error_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class UploadResponse(DocumentResponse):
    pass


class ReadinessResponse(BaseModel):
    ai_mode: str
    status: str
    detail: str


class ReindexResponse(BaseModel):
    status: str
    succeeded: int
    failed: int


class StatusResponse(BaseModel):
    status: str
