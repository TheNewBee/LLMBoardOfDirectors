from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from threading import Lock
from typing import Any

import httpx
import yaml

from boardroom.config import find_config_file, load_config, resolve_api_key
from boardroom.llm.router import LLMRouter
from boardroom.models import AppConfig, ModelConfig
from boardroom.secrets import CredentialStore, CredentialStoreError


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(base)
    for key, value in patch.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class ConfigService:
    _MODEL_CACHE_TTL_SECONDS = 300

    def __init__(self, explicit_path: Path | None = None) -> None:
        self._explicit_path = explicit_path
        self._write_lock = Lock()
        self._models_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
        self._models_cache_lock = Lock()

    def load(self) -> AppConfig:
        return load_config(self._explicit_path)

    def config_path(self) -> Path | None:
        return find_config_file(self._explicit_path)

    def has_provider_api_key(self, provider: str, env: Mapping[str, str]) -> bool:
        try:
            _ = resolve_api_key(provider, self.load(), env)
            return True
        except Exception:
            return False

    def set_provider_key(self, *, provider: str, api_key: str) -> None:
        try:
            CredentialStore().set(provider, api_key)
        except CredentialStoreError as exc:
            raise RuntimeError(str(exc)) from exc

    def update(self, patch: dict[str, Any]) -> AppConfig:
        config_path = self.config_path()
        if config_path is not None and config_path.exists():
            base_data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        else:
            base_data = self.load().model_dump(mode="json")

        merged = _deep_merge(base_data, patch)
        updated = AppConfig.model_validate(merged)
        target = config_path or Path("config.yaml")
        self._write_config_atomic(target, updated.model_dump(mode="json"))
        return load_config(target)

    def validate_key(
        self,
        *,
        provider: str,
        model: str | None,
        env: Mapping[str, str],
    ) -> tuple[bool, str]:
        config = self.load()
        model_name = model or config.default_model.model
        model_cfg = ModelConfig(
            provider=provider,
            model=model_name,
            temperature=config.default_model.temperature,
            max_tokens=config.default_model.max_tokens,
        )
        ok = LLMRouter().validate_model_config(
            model_config=model_cfg,
            config=config,
            env=env,
        )
        return ok, model_name

    def get_provider_models(
        self,
        *,
        provider: str,
        env: Mapping[str, str],
    ) -> tuple[list[dict[str, str]], bool]:
        config = self.load()
        key = resolve_api_key(provider, config, env)
        cache_key = f"{provider}:{key}"
        now = time.time()

        with self._models_cache_lock:
            cached = self._models_cache.get(cache_key)
            if cached is not None and now - cached[0] < self._MODEL_CACHE_TTL_SECONDS:
                return cached[1], True

        provider_cfg = config.providers[provider]
        url = f"{provider_cfg.base_url.rstrip('/')}/models"
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
        rows: list[dict[str, str]] = []
        for item in payload.get("data", []):
            model_id = str(item.get("id", "")).strip()
            if not model_id:
                continue
            rows.append({"id": model_id, "name": str(item.get("name") or model_id)})

        with self._models_cache_lock:
            self._models_cache[cache_key] = (now, rows)
        return rows, False

    def invalidate_model_cache(self) -> None:
        with self._models_cache_lock:
            self._models_cache.clear()

    def _write_config_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
        with self._write_lock:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
                prefix=f".{path.name}.",
                suffix=".tmp",
            ) as tmp:
                tmp.write(body)
                tmp_path = Path(tmp.name)
            os.replace(tmp_path, path)
