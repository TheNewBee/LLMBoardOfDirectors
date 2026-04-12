from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from boardroom.api.dependencies import get_app_config
from boardroom.models import AppConfig
from boardroom.vector_store import MeetingVectorStore

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/search")
def search_history(
    query: str = Query(min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    app_config: AppConfig = Depends(get_app_config),
) -> dict[str, Any]:
    if not app_config.vector_store.enabled:
        return {"results": []}

    store = MeetingVectorStore(
        persist_dir=app_config.vector_store.persist_dir,
        collection_name=app_config.vector_store.collection_name,
    )
    return {"results": store.search(query=query, limit=limit)}
