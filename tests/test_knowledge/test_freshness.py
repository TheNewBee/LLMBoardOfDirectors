from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

from boardroom.knowledge.freshness import KnowledgeFreshnessValidator
from boardroom.knowledge.store import KnowledgeVectorStore
from boardroom.models import AgentConfig, AgentRole


def _agent(agent_id: str = "test_agent", staleness_days: int = 7) -> AgentConfig:
    return AgentConfig(
        id=agent_id,
        name="Test Agent",
        role=AgentRole.CUSTOM,
        expertise_domain="AI",
        personality_traits=["analytical"],
        staleness_threshold_days=staleness_days,
    )


def test_fresh_agent_not_flagged(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    store.set_refresh_timestamp("test_agent", datetime.now(timezone.utc))
    validator = KnowledgeFreshnessValidator(store=store)
    stale = validator.check_agents([_agent()])
    assert stale == []


def test_stale_agent_flagged(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    old = datetime.now(timezone.utc) - timedelta(days=10)
    store.set_refresh_timestamp("test_agent", old)
    validator = KnowledgeFreshnessValidator(store=store)
    stale = validator.check_agents([_agent(staleness_days=7)])
    assert len(stale) == 1
    assert stale[0].id == "test_agent"


def test_never_refreshed_agent_flagged(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    validator = KnowledgeFreshnessValidator(store=store)
    stale = validator.check_agents([_agent()])
    assert len(stale) == 1


def test_multiple_agents_mixed(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    store.set_refresh_timestamp("fresh_one", datetime.now(timezone.utc))
    old = datetime.now(timezone.utc) - timedelta(days=30)
    store.set_refresh_timestamp("stale_one", old)
    validator = KnowledgeFreshnessValidator(store=store)
    agents = [_agent("fresh_one"), _agent("stale_one")]
    stale = validator.check_agents(agents)
    stale_ids = [a.id for a in stale]
    assert "fresh_one" not in stale_ids
    assert "stale_one" in stale_ids
