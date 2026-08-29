from types import SimpleNamespace

from app.config import Settings
from app.services.openai_service import OpenAIService


class FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0] * 1024)], usage=SimpleNamespace(total_tokens=2))


def test_openai_embeddings_are_mocked_and_explicitly_request_1024(monkeypatch):
    embeddings = FakeEmbeddings()
    fake_client = SimpleNamespace(embeddings=embeddings)
    monkeypatch.setattr("app.services.openai_service.OpenAI", lambda **kwargs: fake_client)
    provider = OpenAIService(Settings(_env_file=None, openai_api_key="test-only", admin_api_key="a" * 24))
    vectors, tokens = provider.embed(["hello"])
    assert len(vectors[0]) == 1024 and tokens == 2
    assert embeddings.calls == [{"model": "text-embedding-3-small", "input": ["hello"], "dimensions": 1024}]
