from __future__ import annotations

import logging

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem
from boardroom.knowledge.pipeline import KnowledgePipeline
from boardroom.knowledge.store import KnowledgeVectorStore
from boardroom.models import AgentConfig

_LOG = logging.getLogger(__name__)


class KnowledgeBaseBuilder:
    """Orchestrates knowledge base construction for an agent."""

    def __init__(
        self,
        *,
        connectors: list[KnowledgeConnector],
        store: KnowledgeVectorStore,
        quality_threshold: float = 0.3,
        max_tokens_per_agent: int = 50000,
    ) -> None:
        self._connectors = connectors
        self._store = store
        self._quality_threshold = quality_threshold
        self._max_tokens = max_tokens_per_agent

    def build(self, agent: AgentConfig) -> int:
        _LOG.info("Building knowledge base for agent=%s domain=%s", agent.id, agent.expertise_domain)
        pipeline = KnowledgePipeline(
            connectors=self._connectors,
            quality_threshold=self._quality_threshold,
        )
        items = pipeline.run(
            query=agent.expertise_domain,
            domain=agent.expertise_domain,
        )
        items = self._enforce_token_budget(items)
        if items:
            self._store.store(agent.id, items)
        _LOG.info("Knowledge base built for agent=%s items=%d", agent.id, len(items))
        return len(items)

    def _enforce_token_budget(self, items: list[KnowledgeItem]) -> list[KnowledgeItem]:
        kept: list[KnowledgeItem] = []
        tokens_used = 0
        for item in items:
            est = item.token_estimate
            if tokens_used + est > self._max_tokens:
                break
            kept.append(item)
            tokens_used += est
        return kept
