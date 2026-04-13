from __future__ import annotations

import pytest

from boardroom.llm.backend import LLMBackendError
from boardroom.llm.router import LLMRouter
from boardroom.models import AgentConfig, AgentRole, AppConfig, ModelConfig, ProviderConfig


from collections.abc import Iterator


class FakeBackend:
    def __init__(self) -> None:
        self.generate_calls: list[dict[str, object]] = []
        self.validate_calls: list[str] = []
        self.stream_chunks: list[str] = ["token1", " token2"]

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

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        yield from self.stream_chunks

    def validate_api_key(self, *, model: str) -> bool:
        self.validate_calls.append(model)
        return True

    def get_provider_name(self) -> str:
        return "openrouter"


class RecoveringBackend(FakeBackend):
    def __init__(self) -> None:
        super().__init__()
        self.failures_remaining = 1

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise LLMBackendError(
                "OpenRouter request failed: synthetic 429",
                category="rate_limited",
                status_code=429,
                retry_after_ms=10,
            )
        return super().generate(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        )

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise LLMBackendError(
                "OpenRouter request failed: synthetic 429",
                category="rate_limited",
                status_code=429,
                retry_after_ms=10,
            )
        yield from self.stream_chunks


class FailingBackend(FakeBackend):
    def __init__(self, error: LLMBackendError) -> None:
        super().__init__()
        self.error = error
        self.calls = 0

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        _ = messages
        _ = model
        _ = temperature
        _ = max_tokens
        self.calls += 1
        raise self.error

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        _ = messages
        _ = model
        _ = temperature
        _ = max_tokens
        self.calls += 1
        raise self.error
        yield  # make it a generator


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


def test_router_retries_recoverable_provider_errors() -> None:
    backend = RecoveringBackend()
    recoveries: list[tuple[str, int, int, int | None]] = []
    sleeps: list[float] = []
    router = LLMRouter(
        backend_factories={"openrouter": lambda api_key, base_url: backend},
        recovery_callback=lambda error, attempt, max_attempts, next_retry_ms: recoveries.append(
            (error.category, attempt, max_attempts, next_retry_ms)
        ),
        sleep=lambda seconds: sleeps.append(seconds),
    )

    result = router.generate_for_agent(
        agent=make_agent(),
        config=make_config(),
        messages=[{"role": "user", "content": "Analyze this"}],
        env={"OPENROUTER_API_KEY": "secret"},
    )

    assert result == "response:google/gemini-2.0-flash"
    assert recoveries == [("rate_limited", 1, 3, 10)]
    assert sleeps == [0.01]


def test_router_does_not_retry_missing_api_key_errors() -> None:
    backend = FailingBackend(
        LLMBackendError("missing", category="missing_api_key", status_code=401)
    )
    recoveries: list[tuple[str, int, int, int | None]] = []
    router = LLMRouter(
        backend_factories={"openrouter": lambda api_key, base_url: backend},
        recovery_callback=lambda error, attempt, max_attempts, next_retry_ms: recoveries.append(
            (error.category, attempt, max_attempts, next_retry_ms)
        ),
        sleep=lambda _seconds: None,
    )

    with pytest.raises(LLMBackendError):
        router.generate_for_agent(
            agent=make_agent(),
            config=make_config(),
            messages=[{"role": "user", "content": "Analyze this"}],
            env={"OPENROUTER_API_KEY": "secret"},
        )

    assert backend.calls == 1
    assert recoveries == []


def test_router_retries_unknown_once_before_terminal_failure() -> None:
    backend = FailingBackend(LLMBackendError("unknown", category="unknown"))
    recoveries: list[tuple[str, int, int, int | None]] = []
    sleeps: list[float] = []
    router = LLMRouter(
        backend_factories={"openrouter": lambda api_key, base_url: backend},
        recovery_callback=lambda error, attempt, max_attempts, next_retry_ms: recoveries.append(
            (error.category, attempt, max_attempts, next_retry_ms)
        ),
        sleep=lambda seconds: sleeps.append(seconds),
    )

    with pytest.raises(LLMBackendError):
        router.generate_for_agent(
            agent=make_agent(),
            config=make_config(),
            messages=[{"role": "user", "content": "Analyze this"}],
            env={"OPENROUTER_API_KEY": "secret"},
        )

    assert backend.calls == 2
    assert recoveries == [("unknown", 1, 2, 250)]
    assert sleeps == [0.25]


def test_router_retries_provider_unavailable_once_before_terminal_failure() -> None:
    backend = FailingBackend(
        LLMBackendError("unavailable", category="provider_unavailable", status_code=503)
    )
    recoveries: list[tuple[str, int, int, int | None]] = []
    router = LLMRouter(
        backend_factories={"openrouter": lambda api_key, base_url: backend},
        recovery_callback=lambda error, attempt, max_attempts, next_retry_ms: recoveries.append(
            (error.category, attempt, max_attempts, next_retry_ms)
        ),
        sleep=lambda _seconds: None,
    )

    with pytest.raises(LLMBackendError):
        router.generate_for_agent(
            agent=make_agent(),
            config=make_config(),
            messages=[{"role": "user", "content": "Analyze this"}],
            env={"OPENROUTER_API_KEY": "secret"},
        )

    assert backend.calls == 2
    assert recoveries == [("provider_unavailable", 1, 2, 1000)]


def test_router_retries_timeout_once_before_terminal_failure() -> None:
    backend = FailingBackend(LLMBackendError("timeout", category="timeout"))
    recoveries: list[tuple[str, int, int, int | None]] = []
    router = LLMRouter(
        backend_factories={"openrouter": lambda api_key, base_url: backend},
        recovery_callback=lambda error, attempt, max_attempts, next_retry_ms: recoveries.append(
            (error.category, attempt, max_attempts, next_retry_ms)
        ),
        sleep=lambda _seconds: None,
    )

    with pytest.raises(LLMBackendError):
        router.generate_for_agent(
            agent=make_agent(),
            config=make_config(),
            messages=[{"role": "user", "content": "Analyze this"}],
            env={"OPENROUTER_API_KEY": "secret"},
        )

    assert backend.calls == 2
    assert recoveries == [("timeout", 1, 2, 500)]


def test_router_generate_for_agent_stream_yields_chunks() -> None:
    backend = FakeBackend()
    backend.stream_chunks = ["Hello", " world"]
    router = LLMRouter(
        backend_factories={"openrouter": lambda api_key, base_url: backend},
        sleep=lambda _: None,
    )

    chunks = list(router.generate_for_agent_stream(
        agent=make_agent(),
        config=make_config(),
        messages=[{"role": "user", "content": "Hi"}],
        env={"OPENROUTER_API_KEY": "secret"},
    ))

    assert chunks == ["Hello", " world"]


def test_router_generate_for_agent_stream_retries_on_rate_limit() -> None:
    backend = RecoveringBackend()
    recoveries: list[tuple[str, int, int, int | None]] = []
    router = LLMRouter(
        backend_factories={"openrouter": lambda api_key, base_url: backend},
        recovery_callback=lambda error, attempt, max_attempts, next_retry_ms: recoveries.append(
            (error.category, attempt, max_attempts, next_retry_ms)
        ),
        sleep=lambda _: None,
    )

    chunks = list(router.generate_for_agent_stream(
        agent=make_agent(),
        config=make_config(),
        messages=[{"role": "user", "content": "Hi"}],
        env={"OPENROUTER_API_KEY": "secret"},
    ))

    assert chunks == backend.stream_chunks
    assert recoveries == [("rate_limited", 1, 3, 10)]


def test_router_generate_for_agent_stream_raises_after_max_retries() -> None:
    backend = FailingBackend(LLMBackendError("rate limit", category="rate_limited"))
    router = LLMRouter(
        backend_factories={"openrouter": lambda api_key, base_url: backend},
        sleep=lambda _: None,
    )

    with pytest.raises(LLMBackendError):
        list(router.generate_for_agent_stream(
            agent=make_agent(),
            config=make_config(),
            messages=[{"role": "user", "content": "Hi"}],
            env={"OPENROUTER_API_KEY": "secret"},
        ))

    assert backend.calls == 3  # rate_limited policy max_attempts=3
