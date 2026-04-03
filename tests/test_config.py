from __future__ import annotations

from pathlib import Path

import pytest

from boardroom.config import find_config_file, load_config, resolve_api_key


def test_find_config_file_prefers_explicit_path(tmp_path: Path) -> None:
    config_path = tmp_path / "custom.yaml"
    config_path.write_text(
        "providers: {openrouter: {api_key_env: OPENROUTER_API_KEY, base_url: x}}"
    )

    assert find_config_file(config_path) == config_path


def test_find_config_file_returns_none_for_missing_explicit_path(tmp_path: Path) -> None:
    assert find_config_file(tmp_path / "missing.yaml") is None


def test_load_config_returns_default_openrouter_config_when_missing() -> None:
    config = load_config(Path("definitely-missing-config.yaml"))

    assert "openrouter" in config.providers
    assert config.default_model.provider == "openrouter"


def test_load_config_reads_agent_model_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
providers:
  openrouter:
    api_key_env: OPENROUTER_API_KEY
    base_url: https://openrouter.ai/api/v1
default_model:
  provider: openrouter
  model: anthropic/claude-sonnet-4
agent_models:
  adversary:
    provider: openrouter
    model: openai/gpt-4o
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.model_for_agent("adversary").model == "openai/gpt-4o"
    assert config.model_for_agent("strategist").model == "anthropic/claude-sonnet-4"


def test_resolve_api_key_uses_provider_env_mapping() -> None:
    config = load_config(Path("definitely-missing-config.yaml"))

    api_key = resolve_api_key(
        "openrouter",
        config,
        {"OPENROUTER_API_KEY": "secret-value"},
    )

    assert api_key == "secret-value"


def test_resolve_api_key_raises_for_missing_env_value() -> None:
    config = load_config(Path("definitely-missing-config.yaml"))

    with pytest.raises(KeyError):
        resolve_api_key("openrouter", config, {})
