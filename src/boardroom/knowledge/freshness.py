from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from boardroom.knowledge.store import KnowledgeVectorStore
from boardroom.models import AgentConfig

_LOG = logging.getLogger(__name__)


class KnowledgeFreshnessValidator:
    """Checks whether agents' knowledge bases are stale before meetings."""

    def __init__(self, *, store: KnowledgeVectorStore) -> None:
        self._store = store

    def check_agents(self, agents: list[AgentConfig]) -> list[AgentConfig]:
        stale: list[AgentConfig] = []
        now = datetime.now(timezone.utc)
        for agent in agents:
            last = self._store.last_refresh(agent.id)
            if last is None:
                _LOG.info("Agent %s has never been refreshed.", agent.id)
                stale.append(agent)
                continue
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            threshold = timedelta(days=agent.staleness_threshold_days)
            if now - last > threshold:
                _LOG.info(
                    "Agent %s knowledge is stale (last refresh: %s, threshold: %d days).",
                    agent.id, last.isoformat(), agent.staleness_threshold_days,
                )
                stale.append(agent)
        return stale
