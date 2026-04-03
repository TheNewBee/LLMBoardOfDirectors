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

    def create(self, **kwargs: object) -> FakeResponse:
        self.calls.append(kwargs)
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
