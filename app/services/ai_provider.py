import hashlib
import math
import re
from typing import Protocol

from app.config import Settings


class AIConfigurationError(RuntimeError):
    """Raised when the selected AI provider is not configured."""


class AIProvider(Protocol):
    def embed(self, texts: list[str]) -> tuple[list[list[float]], int]: ...

    def answer(self, question: str, history: list[tuple[str, str]], chunks: list[tuple[str, str]]) -> tuple[str, int, int]: ...


class MockAIProvider:
    """Offline provider that keeps document retrieval functional without an API."""

    def __init__(self, settings: Settings):
        self.dimensions = settings.embedding_dimensions

    def embed(self, texts: list[str]) -> tuple[list[list[float]], int]:
        return [self._embed_one(text) for text in texts], 0

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def answer(self, question: str, history: list[tuple[str, str]], chunks: list[tuple[str, str]]) -> tuple[str, int, int]:
        if not chunks:
            return "I don't have that information in the available company documents.", 0, 0
        excerpts = "\n\n".join(content.strip() for _, content in chunks if content.strip())
        return "Mock mode (local document response):\n\n" + excerpts[:1800], 0, 0


def get_ai_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider_mode == "mock":
        return MockAIProvider(settings)
    try:
        settings.validate_ai_provider()
    except ValueError as exc:
        raise AIConfigurationError(str(exc)) from exc
    from app.services.openai_service import OpenAIService

    return OpenAIService(settings)
