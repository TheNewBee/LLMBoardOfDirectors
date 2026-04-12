from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from boardroom.api.dependencies import get_config_service
from boardroom.api.schemas import (
    ConfigPatchRequest,
    ConfigResponse,
    ProviderModel,
    ProviderModelsResponse,
    StoreKeyRequest,
    StoreKeyResponse,
    ValidateKeyRequest,
    ValidateKeyResponse,
)
from boardroom.api.services.config_service import ConfigService

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
def get_config(
    config_service: ConfigService = Depends(get_config_service),
) -> ConfigResponse:
    config = config_service.load()
    path = config_service.config_path()
    return ConfigResponse(
        config=config.model_dump(mode="json"),
        config_path=str(path) if path is not None else None,
        has_openrouter_api_key=config_service.has_provider_api_key("openrouter", os.environ),
    )


@router.put("", response_model=ConfigResponse)
def update_config(
    body: ConfigPatchRequest,
    config_service: ConfigService = Depends(get_config_service),
) -> ConfigResponse:
    try:
        config = config_service.update(body.patch)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    config_service.invalidate_model_cache()
    path = config_service.config_path()
    return ConfigResponse(
        config=config.model_dump(mode="json"),
        config_path=str(path) if path is not None else None,
        has_openrouter_api_key=config_service.has_provider_api_key("openrouter", os.environ),
    )


@router.post("/validate-key", response_model=ValidateKeyResponse)
def validate_key(
    body: ValidateKeyRequest,
    config_service: ConfigService = Depends(get_config_service),
) -> ValidateKeyResponse:
    try:
        ok, model = config_service.validate_key(
            provider=body.provider,
            model=body.model,
            env=os.environ,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ValidateKeyResponse(ok=ok, provider=body.provider, model=model)


@router.post("/keys", response_model=StoreKeyResponse)
def store_key(
    body: StoreKeyRequest,
    config_service: ConfigService = Depends(get_config_service),
) -> StoreKeyResponse:
    try:
        config_service.set_provider_key(provider=body.provider, api_key=body.api_key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not body.validate_after_store:
        return StoreKeyResponse(ok=True, provider=body.provider, validated=False, model=None)

    try:
        ok, model = config_service.validate_key(
            provider=body.provider,
            model=body.model,
            env=os.environ,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return StoreKeyResponse(ok=ok, provider=body.provider, validated=True, model=model)


@router.get("/models", response_model=ProviderModelsResponse)
def list_provider_models(
    provider: str = Query(default="openrouter"),
    config_service: ConfigService = Depends(get_config_service),
) -> ProviderModelsResponse:
    try:
        rows, cached = config_service.get_provider_models(provider=provider, env=os.environ)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ProviderModelsResponse(
        provider=provider,
        models=[ProviderModel(id=row["id"], name=row["name"]) for row in rows],
        cached=cached,
    )
