from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from collections.abc import Iterator
from typing import Any, Literal, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

_LOG = logging.getLogger(__name__)

LLMErrorCategory = Literal[
    "rate_limited",
    "provider_unavailable",
    "timeout",
    "missing_api_key",
    "unknown",
]


class LLMBackendError(RuntimeError):
    """Raised when a provider call fails with structured, UI-safe metadata."""

    def __init__(
        self,
        message: str,
        *,
        category: LLMErrorCategory = "unknown",
        provider: str = "openrouter",
        status_code: int | None = None,
        provider_code: str | None = None,
        retry_after_ms: int | None = None,
        safe_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.provider = provider
        self.status_code = status_code
        self.provider_code = provider_code
        self.retry_after_ms = retry_after_ms
        self.safe_message = safe_message or _safe_message_for_category(category)


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
    def generate_stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        """Yield partial content chunks from the model."""

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
            raise _classify_openrouter_error(exc) from exc

        return response.choices[0].message.content or ""

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
        except Exception as exc:
            _LOG.exception("OpenRouter generate_stream failed model=%s", model)
            raise _classify_openrouter_error(exc) from exc

        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

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


def _classify_openrouter_error(exc: Exception) -> LLMBackendError:
    status_code = _status_code_from_exception(exc)
    provider_code = _provider_code_from_exception(exc)
    retry_after_ms = _retry_after_ms_from_exception(exc)
    text = str(exc)
    lower_text = text.lower()

    category: LLMErrorCategory = "unknown"
    if status_code == 429:
        category = "rate_limited"
    elif status_code in {401, 403}:
        category = "missing_api_key"
    elif status_code is not None and 500 <= status_code <= 599:
        category = "provider_unavailable"
    elif "timeout" in lower_text or "timed out" in lower_text:
        category = "timeout"
    elif provider_code is not None and _is_auth_provider_code(provider_code):
        category = "missing_api_key"

    return LLMBackendError(
        f"OpenRouter request failed: {text}",
        category=category,
        provider="openrouter",
        status_code=status_code,
        provider_code=provider_code,
        retry_after_ms=retry_after_ms,
        safe_message=_safe_message_for_category(category),
    )


def _status_code_from_exception(exc: Exception) -> int | None:
    raw = getattr(exc, "status_code", None)
    if isinstance(raw, int):
        return raw
    response = getattr(exc, "response", None)
    raw = getattr(response, "status_code", None)
    return raw if isinstance(raw, int) else None


def _provider_code_from_exception(exc: Exception) -> str | None:
    raw = getattr(exc, "code", None)
    if isinstance(raw, str):
        return raw
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        code = body.get("code")
        if code is None and isinstance(error, dict):
            code = error.get("code")
        if code is None and isinstance(error, str):
            code = error
        if isinstance(code, str):
            return code
    return None


def _is_auth_provider_code(provider_code: str) -> bool:
    normalized = provider_code.lower()
    return any(token in normalized for token in ("auth", "api_key", "unauthorized", "forbidden"))


def _retry_after_ms_from_exception(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    retry_after = None
    try:
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
    except AttributeError:
        return None
    if retry_after is None:
        return None
    try:
        seconds = float(retry_after)
    except (TypeError, ValueError):
        return None
    return max(0, int(seconds * 1000))


def _safe_message_for_category(category: LLMErrorCategory) -> str:
    return {
        "rate_limited": "The provider is rate limited. The meeting is retrying shortly.",
        "provider_unavailable": "The provider is temporarily unavailable. The meeting is retrying shortly.",
        "timeout": "The provider request timed out. The meeting is retrying shortly.",
        "missing_api_key": "The provider API key is missing or invalid. Update settings before retrying.",
        "unknown": "The provider request failed. The meeting will try one safe recovery step.",
    }[category]
