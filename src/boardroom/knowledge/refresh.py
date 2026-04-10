from __future__ import annotations

import logging

from boardroom.knowledge.builder import KnowledgeBaseBuilder
from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.freshness import KnowledgeFreshnessValidator
from boardroom.knowledge.store import KnowledgeVectorStore
from boardroom.models import AgentConfig

_LOG = logging.getLogger(__name__)


class RefreshResult:
    def __init__(self) -> None:
        self.refreshed: list[str] = []
        self.failed: list[str] = []
        self.skipped: list[str] = []


def refresh_stale_agents(
    *,
    agents: list[AgentConfig],
    store: KnowledgeVectorStore,
    connectors: list[KnowledgeConnector],
    quality_threshold: float = 0.3,
    max_tokens_per_agent: int = 50000,
) -> RefreshResult:
    """Validate freshness and refresh stale agents."""
    result = RefreshResult()
    validator = KnowledgeFreshnessValidator(store=store)
    stale = validator.check_agents(agents)

    if not stale:
        result.skipped = [a.id for a in agents]
        return result

    builder = KnowledgeBaseBuilder(
        connectors=connectors,
        store=store,
        quality_threshold=quality_threshold,
        max_tokens_per_agent=max_tokens_per_agent,
    )
    stale_ids = {a.id for a in stale}
    for agent in agents:
        if agent.id not in stale_ids:
            result.skipped.append(agent.id)
            continue
        try:
            count = builder.build(agent)
            _LOG.info("Refreshed agent %s with %d items.", agent.id, count)
            result.refreshed.append(agent.id)
        except Exception:
            _LOG.warning("Failed to refresh agent %s.", agent.id, exc_info=True)
            result.failed.append(agent.id)
    return result
