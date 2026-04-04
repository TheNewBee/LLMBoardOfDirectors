from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Any, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

_LOG = logging.getLogger(__name__)


class LLMBackendError(RuntimeError):
    """Raised when a provider call fails."""


class LLMBackend(ABC):
    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate model output for a provider-specific model."""

    @abstractmethod
    def validate_api_key(self, *, model: str) -> bool:
        """Validate provider credentials with a lightweight request."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider identifier."""


class OpenRouterBackend(LLMBackend):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.client = client or OpenAI(base_url=base_url, api_key=api_key)

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # pragma: no cover - exercised through tests
            _LOG.exception("OpenRouter generate failed model=%s", model)
            raise LLMBackendError(f"OpenRouter request failed: {exc}") from exc

        return response.choices[0].message.content or ""

    def validate_api_key(self, *, model: str) -> bool:
        try:
            self.client.chat.completions.create(
                model=model,
                messages=cast(
                    list[ChatCompletionMessageParam],
                    [{"role": "user", "content": "ping"}],
                ),
                max_tokens=1,
                temperature=0,
            )
        except Exception:
            return False
        return True

    def get_provider_name(self) -> str:
        return "openrouter"
