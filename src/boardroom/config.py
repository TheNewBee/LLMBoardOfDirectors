from __future__ import annotations

from pathlib import Path
from typing import Mapping

import yaml

from boardroom.models import AppConfig, ProviderConfig


DEFAULT_CONFIG_LOCATIONS = (
    Path("config.yaml"),
    Path.home() / ".boardroom" / "config.yaml",
)


def find_config_file(explicit_path: Path | None = None) -> Path | None:
    if explicit_path is not None:
        return explicit_path if explicit_path.exists() else None

    for candidate in DEFAULT_CONFIG_LOCATIONS:
        if candidate.exists():
            return candidate
    return None


def load_config(explicit_path: Path | None = None) -> AppConfig:
    config_path = find_config_file(explicit_path)
    if config_path is None:
        return AppConfig(
            providers={
                "openrouter": ProviderConfig(
                    api_key_env="OPENROUTER_API_KEY",
                    base_url="https://openrouter.ai/api/v1",
                )
            }
        )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)


def resolve_api_key(provider_name: str, config: AppConfig, env: Mapping[str, str]) -> str:
    provider = config.providers.get(provider_name)
    if provider is None:
        raise KeyError(f"Unknown provider: {provider_name}")

    api_key = env.get(provider.api_key_env)
    if not api_key:
        raise KeyError(f"Missing API key environment variable: {provider.api_key_env}")
    return api_key
