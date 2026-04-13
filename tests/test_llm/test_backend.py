from __future__ import annotations

import pytest

from boardroom.llm.backend import LLMBackendError, OpenRouterBackend


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [
            type("Choice", (), {"message": type("Message", (), {"content": content})()})()
        ]


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.raise_error = False
        self.error: Exception | None = None

    def create(self, **kwargs: object) -> FakeResponse:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if self.raise_error:
            raise RuntimeError("boom")
        return FakeResponse("model-output")


class FakeClient:
    def __init__(self) -> None:
        self.chat = type("Chat", (), {"completions": FakeCompletions()})()


def test_openrouter_backend_uses_requested_model_and_parameters() -> None:
    client = FakeClient()
    backend = OpenRouterBackend(
        api_key="secret", base_url="https://openrouter.ai/api/v1", client=client
    )

    response = backend.generate(
        messages=[{"role": "user", "content": "Hello"}],
        model="openai/gpt-4o",
        temperature=0.3,
        max_tokens=123,
    )

    assert response == "model-output"
    assert client.chat.completions.calls[0]["model"] == "openai/gpt-4o"
    assert client.chat.completions.calls[0]["temperature"] == 0.3
    assert client.chat.completions.calls[0]["max_tokens"] == 123


def test_openrouter_backend_wraps_client_errors() -> None:
    client = FakeClient()
    client.chat.completions.raise_error = True
    backend = OpenRouterBackend(
        api_key="secret", base_url="https://openrouter.ai/api/v1", client=client
    )

    with pytest.raises(LLMBackendError):
        backend.generate(messages=[{"role": "user", "content": "Hello"}], model="openai/gpt-4o")


def test_openrouter_backend_classifies_rate_limit_errors() -> None:
    class RateLimitError(RuntimeError):
        status_code = 429
        code = "rate_limit_exceeded"

    client = FakeClient()
    client.chat.completions.error = RateLimitError("provider returned 429")
    backend = OpenRouterBackend(
        api_key="secret", base_url="https://openrouter.ai/api/v1", client=client
    )

    with pytest.raises(LLMBackendError) as raised:
        backend.generate(messages=[{"role": "user", "content": "Hello"}], model="openai/gpt-4o")

    assert raised.value.category == "rate_limited"
    assert raised.value.status_code == 429
    assert raised.value.provider_code == "rate_limit_exceeded"
    assert "retrying" in raised.value.safe_message.lower()


def test_openrouter_backend_classifies_provider_unavailable_errors() -> None:
    class ProviderUnavailableError(RuntimeError):
        status_code = 503

    client = FakeClient()
    client.chat.completions.error = ProviderUnavailableError("provider unavailable")
    backend = OpenRouterBackend(
        api_key="secret", base_url="https://openrouter.ai/api/v1", client=client
    )

    with pytest.raises(LLMBackendError) as raised:
        backend.generate(messages=[{"role": "user", "content": "Hello"}], model="openai/gpt-4o")

    assert raised.value.category == "provider_unavailable"
    assert raised.value.status_code == 503


def test_openrouter_backend_classifies_timeout_errors() -> None:
    client = FakeClient()
    client.chat.completions.error = TimeoutError("request timed out")
    backend = OpenRouterBackend(
        api_key="secret", base_url="https://openrouter.ai/api/v1", client=client
    )

    with pytest.raises(LLMBackendError) as raised:
        backend.generate(messages=[{"role": "user", "content": "Hello"}], model="openai/gpt-4o")

    assert raised.value.category == "timeout"


def test_openrouter_backend_classifies_auth_errors_as_missing_api_key() -> None:
    class AuthError(RuntimeError):
        status_code = 401
        body = {"error": "invalid_api_key"}

    client = FakeClient()
    client.chat.completions.error = AuthError("unauthorized")
    backend = OpenRouterBackend(
        api_key="secret", base_url="https://openrouter.ai/api/v1", client=client
    )

    with pytest.raises(LLMBackendError) as raised:
        backend.generate(messages=[{"role": "user", "content": "Hello"}], model="openai/gpt-4o")

    assert raised.value.category == "missing_api_key"
    assert raised.value.provider_code == "invalid_api_key"


def test_openrouter_backend_handles_malformed_error_body_shape() -> None:
    class MalformedBodyError(RuntimeError):
        status_code = 500
        body = {"error": "oops"}

    client = FakeClient()
    client.chat.completions.error = MalformedBodyError("bad payload")
    backend = OpenRouterBackend(
        api_key="secret", base_url="https://openrouter.ai/api/v1", client=client
    )

    with pytest.raises(LLMBackendError) as raised:
        backend.generate(messages=[{"role": "user", "content": "Hello"}], model="openai/gpt-4o")

    assert raised.value.category == "provider_unavailable"
    assert raised.value.provider_code == "oops"


def test_openrouter_backend_generate_stream_yields_chunks() -> None:
    class FakeStreamChunk:
        def __init__(self, content: str | None) -> None:
            self.choices = [
                type("Choice", (), {"delta": type("Delta", (), {"content": content})()})()
            ]

    class FakeStreamCompletions:
        def create(self, **kwargs: object) -> list[FakeStreamChunk]:
            return [
                FakeStreamChunk("Hello"),
                FakeStreamChunk(", "),
                FakeStreamChunk("world"),
                FakeStreamChunk(None),  # should be skipped
            ]

    client = type("Client", (), {"chat": type("Chat", (), {"completions": FakeStreamCompletions()})()})()
    backend = OpenRouterBackend(api_key="secret", base_url="https://openrouter.ai/api/v1", client=client)

    chunks = list(backend.generate_stream(
        messages=[{"role": "user", "content": "Hello"}],
        model="openai/gpt-4o",
    ))

    assert chunks == ["Hello", ", ", "world"]


def test_openrouter_backend_generate_stream_wraps_errors() -> None:
    class FakeStreamCompletions:
        def create(self, **kwargs: object) -> None:
            raise RuntimeError("stream failed")

    client = type("Client", (), {"chat": type("Chat", (), {"completions": FakeStreamCompletions()})()})()
    backend = OpenRouterBackend(api_key="secret", base_url="https://openrouter.ai/api/v1", client=client)

    with pytest.raises(LLMBackendError):
        list(backend.generate_stream(
            messages=[{"role": "user", "content": "Hello"}],
            model="openai/gpt-4o",
        ))


def test_openrouter_validate_api_key_returns_true_on_success() -> None:
    client = FakeClient()
    backend = OpenRouterBackend(
        api_key="secret", base_url="https://openrouter.ai/api/v1", client=client
    )

    assert backend.validate_api_key(model="anthropic/claude-sonnet-4") is True


def test_openrouter_validate_api_key_returns_false_on_failure() -> None:
    client = FakeClient()
    client.chat.completions.raise_error = True
    backend = OpenRouterBackend(
        api_key="secret", base_url="https://openrouter.ai/api/v1", client=client
    )

    assert backend.validate_api_key(model="anthropic/claude-sonnet-4") is False
