from __future__ import annotations

from pathlib import Path
from typing import Mapping

import yaml

from boardroom.models import AppConfig, PathsConfig, ProviderConfig
from boardroom.secrets import CredentialStore, CredentialStoreError


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
    config = AppConfig.model_validate(raw)
    return _resolve_paths_relative_to_config(config, config_path.resolve().parent)


def _resolve_paths_relative_to_config(config: AppConfig, config_dir: Path) -> AppConfig:
    """Anchor relative paths in YAML to the config file directory (stable cwd)."""
    paths = config.paths
    vs = config.vector_store
    outputs = (
        paths.outputs_dir
        if paths.outputs_dir.is_absolute()
        else (config_dir / paths.outputs_dir).resolve()
    )
    persist = (
        vs.persist_dir
        if vs.persist_dir.is_absolute()
        else (config_dir / vs.persist_dir).resolve()
    )
    return config.model_copy(
        update={
            "paths": PathsConfig(outputs_dir=outputs),
            "vector_store": vs.model_copy(update={"persist_dir": persist}),
        }
    )


def resolve_api_key(
    provider_name: str,
    config: AppConfig,
    env: Mapping[str, str],
    *,
    credential_store: CredentialStore | None = None,
) -> str:
    provider = config.providers.get(provider_name)
    if provider is None:
        raise KeyError(f"Unknown provider: {provider_name}")

    # Explicit process environment always takes precedence over stored credentials.
    api_key = env.get(provider.api_key_env)
    if api_key:
        return api_key

    store = credential_store or CredentialStore()
    stored = store.get(provider_name)
    if stored:
        return stored
    raise KeyError(
        f"Missing API key environment variable: {provider.api_key_env}. "
        "Set it in env or save an encrypted key via `boardroom agents key set`."
    )
