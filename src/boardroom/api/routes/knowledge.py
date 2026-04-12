from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from boardroom.api.dependencies import get_app_config
from boardroom.knowledge.connectors.web_search import WebSearchConnector
from boardroom.knowledge.refresh import refresh_stale_agents
from boardroom.knowledge.store import KnowledgeVectorStore
from boardroom.models import AppConfig
from boardroom.registry import AgentRegistry

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/status")
def get_knowledge_status(
    app_config: AppConfig = Depends(get_app_config),
) -> dict[str, Any]:
    reg = AgentRegistry()
    store = KnowledgeVectorStore(
        persist_dir=app_config.vector_store.persist_dir / "knowledge",
    )
    now = datetime.now(timezone.utc)
    rows = []
    for agent_id in reg.list_agent_ids():
        cfg = reg.get_config(agent_id)
        last = store.last_refresh(agent_id)
        stale = True
        if last is not None:
            stamped = last if last.tzinfo is not None else last.replace(tzinfo=timezone.utc)
            stale = (now - stamped).days > cfg.staleness_threshold_days
        rows.append(
            {
                "agent_id": agent_id,
                "last_refresh": last.isoformat() if last is not None else None,
                "stale": stale,
            }
        )
    return {"items": rows}


@router.post("/refresh")
def refresh_knowledge(
    app_config: AppConfig = Depends(get_app_config),
) -> dict[str, Any]:
    reg = AgentRegistry()
    agents = [reg.get_config(agent_id) for agent_id in reg.list_agent_ids()]
    if not app_config.vector_store.enabled:
        return {
            "refreshed": [],
            "failed": [],
            "skipped": [agent.id for agent in agents],
            "reason": "vector_store_disabled",
        }

    store = KnowledgeVectorStore(
        persist_dir=app_config.vector_store.persist_dir / "knowledge",
    )
    result = refresh_stale_agents(
        agents=agents,
        store=store,
        connectors=[WebSearchConnector()],
    )
    return {
        "refreshed": result.refreshed,
        "failed": result.failed,
        "skipped": result.skipped,
    }
