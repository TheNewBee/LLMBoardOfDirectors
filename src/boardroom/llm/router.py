from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping

from boardroom.config import resolve_api_key
from boardroom.llm.backend import LLMBackend, OpenRouterBackend
from boardroom.models import AgentConfig, AppConfig, ModelConfig

BackendFactory = Callable[[str, str], LLMBackend]


class LLMRouter:
    def __init__(self, backend_factories: Mapping[str, BackendFactory] | None = None) -> None:
        self.backend_factories = dict(
            backend_factories or {"openrouter": self._build_openrouter})
        self._backend_cache: dict[tuple[str, str, str], LLMBackend] = {}
        self._last_generate_monotonic: float | None = None

    def generate_for_agent(
        self,
        *,
        agent: AgentConfig,
        config: AppConfig,
        messages: list[dict[str, str]],
        env: Mapping[str, str] | None = None,
    ) -> str:
        model_config = self._resolve_model_config(agent, config)
        self._wait_for_rate_limit(config.rate_limit_interval_seconds)
        backend = self._backend_for_model(
            model_config, config, env or os.environ)
        return backend.generate(
            messages,
            model=model_config.model,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
        )

    def validate_model_config(
        self,
        *,
        model_config: ModelConfig,
        config: AppConfig,
        env: Mapping[str, str] | None = None,
    ) -> bool:
        backend = self._backend_for_model(
            model_config, config, env or os.environ)
        return backend.validate_api_key(model=model_config.model)

    def _resolve_model_config(self, agent: AgentConfig, config: AppConfig) -> ModelConfig:
        if agent.model_config_override is not None:
            return agent.model_config_override
        return config.model_for_agent(agent.id, agent.role)

    def _backend_for_model(
        self,
        model_config: ModelConfig,
        config: AppConfig,
        env: Mapping[str, str],
    ) -> LLMBackend:
        provider = config.providers.get(model_config.provider)
        if provider is None:
            raise KeyError(f"Unknown provider: {model_config.provider}")

        api_key = resolve_api_key(model_config.provider, config, env)
        cache_key = (model_config.provider, provider.base_url, api_key)
        if cache_key in self._backend_cache:
            return self._backend_cache[cache_key]

        factory = self.backend_factories.get(model_config.provider)
        if factory is None:
            raise KeyError(
                f"No backend factory registered for provider: {model_config.provider}")

        backend = factory(api_key, provider.base_url)
        self._backend_cache[cache_key] = backend
        return backend

    def _wait_for_rate_limit(self, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            return
        now = time.monotonic()
        if self._last_generate_monotonic is not None:
            elapsed = now - self._last_generate_monotonic
            if elapsed < interval_seconds:
                time.sleep(interval_seconds - elapsed)
        self._last_generate_monotonic = time.monotonic()

    @staticmethod
    def _build_openrouter(api_key: str, base_url: str) -> LLMBackend:
        return OpenRouterBackend(api_key=api_key, base_url=base_url)
