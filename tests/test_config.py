from app.config import Settings
from app.services.ai_provider import AIConfigurationError, MockAIProvider, get_ai_provider


def test_comma_separated_origins():
    settings = Settings(allowed_origins="https://one.example, https://two.example", admin_api_key="a" * 24)
    assert settings.allowed_origins == ["https://one.example", "https://two.example"]


def test_mock_is_default_and_needs_no_key():
    settings = Settings(_env_file=None, openai_api_key="", admin_api_key="a" * 24)
    assert settings.ai_provider_mode == "mock"
    assert isinstance(get_ai_provider(settings), MockAIProvider)


def test_mock_response_uses_retrieved_document_text():
    provider = MockAIProvider(Settings(_env_file=None, embedding_dimensions=256, admin_api_key="a" * 24))
    answer, input_tokens, output_tokens = provider.answer("What?", [], [("faq.txt", "We provide local support.")])
    assert "Mock mode" in answer
    assert "We provide local support." in answer
    assert (input_tokens, output_tokens) == (0, 0)


def test_openai_mode_without_key_has_safe_configuration_error():
    settings = Settings(_env_file=None, ai_provider_mode="openai", openai_api_key="", admin_api_key="a" * 24)
    try:
        get_ai_provider(settings)
    except AIConfigurationError as exc:
        assert str(exc) == "OPENAI_API_KEY is required when AI_PROVIDER_MODE=openai"
    else:
        raise AssertionError("Expected a configuration error")


def test_openai_mode_uses_ready_integration_when_key_is_present():
    settings = Settings(_env_file=None, ai_provider_mode="openai", openai_api_key="configured-later", admin_api_key="a" * 24)
    provider = get_ai_provider(settings)
    assert provider.__class__.__name__ == "OpenAIService"
