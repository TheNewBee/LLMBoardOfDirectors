from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from boardroom.knowledge.builder import KnowledgeBaseBuilder
from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem, SourceType
from boardroom.knowledge.store import KnowledgeVectorStore
from boardroom.models import AgentConfig, AgentRole


class _FakeConnector(KnowledgeConnector):
    @property
    def source_type(self) -> SourceType:
        return SourceType.WEB_SEARCH

    def fetch(self, query: str, *, domain: str = "", max_items: int = 10) -> list[KnowledgeItem]:
        return [
            KnowledgeItem(
                source_type=SourceType.WEB_SEARCH,
                url=f"https://example.com/{i}",
                title=f"{domain} article {i}",
                content=f"Detailed content about {domain} topic number {i} with analysis.",
                timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
            for i in range(min(max_items, 5))
        ]


def _agent(agent_id: str = "test_agent") -> AgentConfig:
    return AgentConfig(
        id=agent_id,
        name="Test Agent",
        role=AgentRole.CUSTOM,
        expertise_domain="artificial intelligence",
        personality_traits=["analytical"],
    )


def test_builder_builds_knowledge_base(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    builder = KnowledgeBaseBuilder(
        connectors=[_FakeConnector()],
        store=store,
    )
    count = builder.build(_agent())
    assert count > 0


def test_builder_stores_in_agent_namespace(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    builder = KnowledgeBaseBuilder(connectors=[_FakeConnector()], store=store)
    builder.build(_agent("agent_a"))
    builder.build(_agent("agent_b"))

    a_items = store.retrieve("agent_a", query="artificial intelligence", limit=10)
    b_items = store.retrieve("agent_b", query="artificial intelligence", limit=10)
    assert len(a_items) > 0
    assert len(b_items) > 0


def test_builder_respects_token_budget(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    builder = KnowledgeBaseBuilder(
        connectors=[_FakeConnector()],
        store=store,
        max_tokens_per_agent=50,
    )
    count = builder.build(_agent())
    assert count >= 1


def test_builder_records_refresh_timestamp(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    builder = KnowledgeBaseBuilder(connectors=[_FakeConnector()], store=store)
    builder.build(_agent())
    ts = store.last_refresh("test_agent")
    assert ts is not None


def test_store_retrieve_returns_items(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    items = [
        KnowledgeItem(
            source_type=SourceType.WEB_SEARCH,
            url="https://example.com/1",
            title="Test Article",
            content="Content about artificial intelligence.",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    ]
    store.store("test_agent", items)
    retrieved = store.retrieve("test_agent", query="artificial intelligence", limit=5)
    assert len(retrieved) >= 1


def test_store_replaces_previous_generation_without_orphans(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    first_batch = [
        KnowledgeItem(
            source_type=SourceType.WEB_SEARCH,
            url=f"https://example.com/old-{i}",
            title=f"Old {i}",
            content=f"Old content {i}",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        for i in range(5)
    ]
    second_batch = [
        KnowledgeItem(
            source_type=SourceType.WEB_SEARCH,
            url="https://example.com/new",
            title="New",
            content="Fresh replacement content only.",
            timestamp=datetime(2026, 3, 2, tzinfo=timezone.utc),
        )
    ]
    store.store("test_agent", first_batch)
    store.store("test_agent", second_batch)
    collection = store._collection_for("test_agent")
    assert int(collection.count()) == 1


def test_store_keeps_long_agent_ids_isolated(tmp_path: Path) -> None:
    store = KnowledgeVectorStore(persist_dir=tmp_path)
    prefix = "finance_department_senior_analyst_risk_assessment_"
    agent_a = f"{prefix}v1"
    agent_b = f"{prefix}v2"
    store.store(agent_a, [
        KnowledgeItem(
            source_type=SourceType.WEB_SEARCH,
            url="https://example.com/a",
            title="Agent A",
            content="private-a",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    ])
    store.store(agent_b, [
        KnowledgeItem(
            source_type=SourceType.WEB_SEARCH,
            url="https://example.com/b",
            title="Agent B",
            content="private-b",
            timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    ])
    a = store.retrieve(agent_a, query="private", limit=5)
    b = store.retrieve(agent_b, query="private", limit=5)
    assert any("private-a" in item.content for item in a)
    assert all("private-b" not in item.content for item in a)
    assert any("private-b" in item.content for item in b)
    assert all("private-a" not in item.content for item in b)
