from __future__ import annotations

import pytest

from boardroom.llm.router import LLMRouter
from boardroom.models import AppConfig, ModelConfig, ProviderConfig
from boardroom.selection.providers import (
    ProviderValidationError,
    UnsupportedProviderError,
    validate_openrouter_for_meeting,
)


def make_config() -> AppConfig:
    return AppConfig(
        providers={
            "openrouter": ProviderConfig(
                api_key_env="OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1",
            )
        },
        default_model=ModelConfig(model="anthropic/claude-sonnet-4"),
    )


class FakeBackend:
    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid

    def validate_api_key(self, *, model: str) -> bool:
        return self.valid

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        return ""

    def get_provider_name(self) -> str:
        return "openrouter"


def test_validate_rejects_non_openrouter() -> None:
    router = LLMRouter(backend_factories={"openrouter": lambda k, u: FakeBackend()})
    with pytest.raises(UnsupportedProviderError):
        validate_openrouter_for_meeting(
            provider="other",
            app_config=make_config(),
            env={"OPENROUTER_API_KEY": "x"},
            router=router,
            validation_model="anthropic/claude-sonnet-4",
        )


def test_validate_requires_api_key_env() -> None:
    router = LLMRouter(backend_factories={"openrouter": lambda k, u: FakeBackend()})
    with pytest.raises(KeyError, match="OPENROUTER_API_KEY"):
        validate_openrouter_for_meeting(
            provider="openrouter",
            app_config=make_config(),
            env={},
            router=router,
            validation_model="anthropic/claude-sonnet-4",
        )


def test_validate_raises_when_backend_returns_false() -> None:
    router = LLMRouter(backend_factories={"openrouter": lambda k, u: FakeBackend(valid=False)})
    with pytest.raises(ProviderValidationError):
        validate_openrouter_for_meeting(
            provider="openrouter",
            app_config=make_config(),
            env={"OPENROUTER_API_KEY": "x"},
            router=router,
            validation_model="anthropic/claude-sonnet-4",
        )


def test_validate_succeeds() -> None:
    router = LLMRouter(backend_factories={"openrouter": lambda k, u: FakeBackend(valid=True)})
    validate_openrouter_for_meeting(
        provider="openrouter",
        app_config=make_config(),
        env={"OPENROUTER_API_KEY": "x"},
        router=router,
        validation_model="anthropic/claude-sonnet-4",
    )
