from __future__ import annotations

from collections.abc import Mapping

from boardroom.config import resolve_api_key
from boardroom.llm.router import LLMRouter
from boardroom.models import AppConfig, ModelConfig


class UnsupportedProviderError(ValueError):
    """Raised when the meeting requests a provider that Phase 1 does not expose."""


class ProviderValidationError(RuntimeError):
    """Raised when the provider rejects credentials (e.g. invalid API key)."""


def validate_openrouter_for_meeting(
    *,
    provider: str,
    app_config: AppConfig,
    env: Mapping[str, str],
    router: LLMRouter,
    validation_model: str,
) -> None:
    if provider != "openrouter":
        raise UnsupportedProviderError(
            f'Phase 1 supports only provider "openrouter" (got {provider!r}).',
        )
    resolve_api_key(provider, app_config, env)
    model_config = ModelConfig(provider=provider, model=validation_model)
    if not router.validate_model_config(
        model_config=model_config,
        config=app_config,
        env=env,
    ):
        raise ProviderValidationError("OpenRouter API key validation failed.")
