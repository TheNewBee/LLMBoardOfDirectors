from __future__ import annotations

import pytest

from boardroom.llm.router import LLMRouter
from boardroom.models import AgentConfig, AgentRole, AppConfig, ModelConfig, ProviderConfig


class FakeBackend:
    def __init__(self) -> None:
        self.generate_calls: list[dict[str, object]] = []
        self.validate_calls: list[str] = []

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        self.generate_calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return f"response:{model}"

    def validate_api_key(self, *, model: str) -> bool:
        self.validate_calls.append(model)
        return True

    def get_provider_name(self) -> str:
        return "openrouter"


def make_config() -> AppConfig:
    return AppConfig(
        providers={
            "openrouter": ProviderConfig(
                api_key_env="OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1",
            )
        },
        default_model=ModelConfig(model="anthropic/claude-sonnet-4"),
        agent_models={"data_specialist": ModelConfig(
            model="google/gemini-2.0-flash")},
    )


def make_agent() -> AgentConfig:
    return AgentConfig(
        id="agent-1",
        name="Sarah",
        role=AgentRole.DATA_SPECIALIST,
        expertise_domain="analytics",
        personality_traits=["precise"],
    )


def test_router_uses_role_based_model_mapping_when_agent_has_no_override() -> None:
    backend = FakeBackend()
    router = LLMRouter(
        backend_factories={"openrouter": lambda api_key, base_url: backend},
    )

    result = router.generate_for_agent(
        agent=make_agent(),
        config=make_config(),
        messages=[{"role": "user", "content": "Analyze this"}],
        env={"OPENROUTER_API_KEY": "secret"},
    )

    assert result == "response:google/gemini-2.0-flash"
    assert backend.generate_calls[0]["model"] == "google/gemini-2.0-flash"


def test_router_prefers_agent_override_over_config_mapping() -> None:
    backend = FakeBackend()
    router = LLMRouter(
        backend_factories={"openrouter": lambda api_key, base_url: backend},
    )
    agent = make_agent().model_copy(
        update={"model_config_override": ModelConfig(
            model="openai/gpt-4o-mini")}
    )

    result = router.generate_for_agent(
        agent=agent,
        config=make_config(),
        messages=[{"role": "user", "content": "Analyze this"}],
        env={"OPENROUTER_API_KEY": "secret"},
    )

    assert result == "response:openai/gpt-4o-mini"
    assert backend.generate_calls[0]["model"] == "openai/gpt-4o-mini"


def test_router_reuses_provider_backend_instances() -> None:
    backend = FakeBackend()
    factory_calls: list[tuple[str, str]] = []

    def build_backend(api_key: str, base_url: str) -> FakeBackend:
        factory_calls.append((api_key, base_url))
        return backend

    router = LLMRouter(backend_factories={"openrouter": build_backend})
    config = make_config()
    env = {"OPENROUTER_API_KEY": "secret"}

    router.generate_for_agent(
        agent=make_agent(), config=config, messages=[], env=env)
    router.generate_for_agent(
        agent=make_agent(), config=config, messages=[], env=env)

    assert factory_calls == [("secret", "https://openrouter.ai/api/v1")]


def test_router_rate_limit_interval_sleeps_between_generate_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("boardroom.llm.router.time.sleep",
                        lambda s: sleeps.append(s))

    times = iter([100.0, 100.0, 100.1, 100.5])
    monkeypatch.setattr(
        "boardroom.llm.router.time.monotonic", lambda: next(times))

    backend = FakeBackend()
    router = LLMRouter(backend_factories={
                       "openrouter": lambda api_key, base_url: backend})
    cfg = make_config().model_copy(update={"rate_limit_interval_seconds": 0.5})
    env = {"OPENROUTER_API_KEY": "secret"}
    agent = make_agent()

    router.generate_for_agent(agent=agent, config=cfg, messages=[], env=env)
    router.generate_for_agent(agent=agent, config=cfg, messages=[], env=env)

    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(0.4)
    assert len(backend.generate_calls) == 2


def test_router_can_validate_provider_credentials() -> None:
    backend = FakeBackend()
    router = LLMRouter(backend_factories={
                       "openrouter": lambda api_key, base_url: backend})

    valid = router.validate_model_config(
        model_config=ModelConfig(
            provider="openrouter", model="anthropic/claude-sonnet-4"),
        config=make_config(),
        env={"OPENROUTER_API_KEY": "secret"},
    )

    assert valid is True
    assert backend.validate_calls == ["anthropic/claude-sonnet-4"]
