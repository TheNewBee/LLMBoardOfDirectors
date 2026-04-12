from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from boardroom.models import (
    AgentConfig,
    AppConfig,
    Briefing,
    ModelConfig,
    PathsConfig,
    ProviderConfig,
    VectorStoreConfig,
)


class FakeLLM:
    def __init__(self, responses: Sequence[str | Exception]) -> None:
        self._responses = list(responses)
        self._index = 0
        self.calls: list[dict[str, Any]] = []

    def generate_for_agent(
        self,
        *,
        agent: AgentConfig,
        config: AppConfig,
        messages: list[dict[str, str]],
        env: Mapping[str, str] | None = None,
    ) -> str:
        self.calls.append(
            {
                "agent": agent,
                "config": config,
                "messages": messages,
                "env": dict(env or {}),
            }
        )
        response = self._responses[self._index % len(self._responses)]
        self._index += 1
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def fake_llm_cls() -> type[FakeLLM]:
    return FakeLLM


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def briefing() -> Briefing:
    return Briefing(
        text="Should we launch the AI pricing boardroom in the EU market this year?",
        objectives=["Stress-test the rollout plan.", "Surface the biggest failure modes."],
    )


@pytest.fixture
def app_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        providers={
            "openrouter": ProviderConfig(
                api_key_env="OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1",
            )
        },
        default_model=ModelConfig(model="test/model"),
        paths=PathsConfig(outputs_dir=tmp_path / "outputs"),
        vector_store=VectorStoreConfig(
            enabled=True,
            persist_dir=tmp_path / "vector_store",
            collection_name="boardroom_meetings",
        ),
    )


@pytest.fixture
def write_config(tmp_path: Path) -> Any:
    def _write_config(*, enabled: bool = True) -> Path:
        config_path = tmp_path / "config.yaml"
        lines = [
            "providers:",
            "  openrouter:",
            "    api_key_env: OPENROUTER_API_KEY",
            "    base_url: https://openrouter.ai/api/v1",
            "default_model:",
            "  provider: openrouter",
            "  model: openai/gpt-4o-mini",
            "paths:",
            f"  outputs_dir: {tmp_path / 'outputs'}",
            "vector_store:",
            f"  enabled: {'true' if enabled else 'false'}",
            f"  persist_dir: {tmp_path / 'vector_store'}",
            "  collection_name: boardroom_meetings",
        ]
        config_path.write_text("\n".join(lines), encoding="utf-8")
        return config_path

    return _write_config
