from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from boardroom.config import find_config_file, load_config, resolve_api_key


class _FakeCredentialStore:
    def __init__(self, value: str | None) -> None:
        self.value = value

    def get(self, provider: str) -> str | None:
        _ = provider
        return self.value


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
    assert config.web_search.provider == "ddgs"


def test_load_config_rejects_non_uppercase_tavily_env_var(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
providers:
  openrouter:
    api_key_env: OPENROUTER_API_KEY
    base_url: https://openrouter.ai/api/v1
web_search:
  provider: tavily
  tavily_api_key_env: tavily_api_key
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="tavily_api_key_env"):
        load_config(config_path)


def test_load_config_rejects_removed_web_search_provider_with_explicit_message(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
providers:
  openrouter:
    api_key_env: OPENROUTER_API_KEY
    base_url: https://openrouter.ai/api/v1
web_search:
  provider: duckduckgo
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(
        ValidationError, match="was removed|Use one of: ddgs, tavily"
    ):
        load_config(config_path)


def test_load_config_resolves_relative_paths_against_config_directory(
    tmp_path: Path,
) -> None:
    sub = tmp_path / "project"
    sub.mkdir()
    config_path = sub / "config.yaml"
    config_path.write_text(
        """
providers:
  openrouter:
    api_key_env: OPENROUTER_API_KEY
    base_url: https://openrouter.ai/api/v1
paths:
  outputs_dir: out/transcripts
vector_store:
  enabled: true
  persist_dir: data/vectors
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.paths.outputs_dir == sub / "out" / "transcripts"
    assert config.vector_store.persist_dir == sub / "data" / "vectors"


def test_load_config_leaves_absolute_paths_unchanged(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    abs_out = tmp_path / "abs_out"
    abs_vec = tmp_path / "abs_vec"
    config_path.write_text(
        f"""
providers:
  openrouter:
    api_key_env: OPENROUTER_API_KEY
    base_url: https://openrouter.ai/api/v1
paths:
  outputs_dir: {abs_out.as_posix()}
vector_store:
  persist_dir: {abs_vec.as_posix()}
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.paths.outputs_dir == abs_out.resolve()
    assert config.vector_store.persist_dir == abs_vec.resolve()


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
    assert config.model_for_agent(
        "strategist").model == "anthropic/claude-sonnet-4"


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
        resolve_api_key(
            "openrouter",
            config,
            {},
            credential_store=_FakeCredentialStore(None),
        )


def test_resolve_api_key_falls_back_to_encrypted_store() -> None:
    config = load_config(Path("definitely-missing-config.yaml"))
    api_key = resolve_api_key(
        "openrouter",
        config,
        {},
        credential_store=_FakeCredentialStore("sk-stored"),
    )
    assert api_key == "sk-stored"


def test_resolve_api_key_prefers_environment_over_encrypted_store() -> None:
    config = load_config(Path("definitely-missing-config.yaml"))
    api_key = resolve_api_key(
        "openrouter",
        config,
        {"OPENROUTER_API_KEY": "sk-env"},
        credential_store=_FakeCredentialStore("sk-stored"),
    )
    assert api_key == "sk-env"
