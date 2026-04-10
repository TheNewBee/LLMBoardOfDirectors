from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from boardroom.knowledge.models import KnowledgeItem, SourceType
from boardroom.knowledge.store import KnowledgeVectorStore
from boardroom.memory.agent_memory import AgentMemoryStore, MemoryItem
from boardroom.knowledge.context import build_agent_context, build_agent_context_parts


def test_build_agent_context_with_knowledge_and_memory(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb"
    mem_dir = tmp_path / "mem"

    kb_store = KnowledgeVectorStore(persist_dir=kb_dir)
    kb_store.store("adv", [
        KnowledgeItem(
            source_type=SourceType.WEB_SEARCH,
            url="https://example.com/1",
            title="Market Trends",
            content="The AI market is growing rapidly at 30% CAGR.",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
    ])

    mem_store = AgentMemoryStore(persist_dir=mem_dir)
    mem_store.store_memories("adv", [
        MemoryItem(
            agent_id="adv",
            meeting_id="m1",
            content="Previously argued that AI market entry is premature.",
            memory_type="argument",
        ),
    ])

    context = build_agent_context(
        agent_id="adv",
        briefing_text="Evaluate AI market entry strategy.",
        knowledge_store=kb_store,
        memory_store=mem_store,
        max_knowledge_tokens=5000,
        max_memory_tokens=2000,
    )
    assert "knowledge" in context.lower() or "market" in context.lower()
    assert "memory" in context.lower() or "previously" in context.lower()


def test_build_agent_context_empty_stores(tmp_path: Path) -> None:
    kb_store = KnowledgeVectorStore(persist_dir=tmp_path / "kb")
    mem_store = AgentMemoryStore(persist_dir=tmp_path / "mem")

    context = build_agent_context(
        agent_id="adv",
        briefing_text="Test briefing.",
        knowledge_store=kb_store,
        memory_store=mem_store,
    )
    assert isinstance(context, str)


def test_build_agent_context_respects_token_limits(tmp_path: Path) -> None:
    kb_store = KnowledgeVectorStore(persist_dir=tmp_path / "kb")
    items = [
        KnowledgeItem(
            source_type=SourceType.WEB_SEARCH,
            url=f"https://example.com/{i}",
            title=f"Article {i}",
            content=f"Content about topic {i} " * 50,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        for i in range(20)
    ]
    kb_store.store("adv", items)
    mem_store = AgentMemoryStore(persist_dir=tmp_path / "mem")

    context = build_agent_context(
        agent_id="adv",
        briefing_text="Test",
        knowledge_store=kb_store,
        memory_store=mem_store,
        max_knowledge_tokens=100,
    )
    assert len(context) < 100 * 6  # rough bound


def test_build_agent_context_parts_do_not_corrupt_sections_on_paragraphs(tmp_path: Path) -> None:
    kb_store = KnowledgeVectorStore(persist_dir=tmp_path / "kb")
    kb_store.store("adv", [
        KnowledgeItem(
            source_type=SourceType.WEB_SEARCH,
            url="https://example.com/k1",
            title="Knowledge with paragraphs",
            content="Paragraph one.\n\nParagraph two should stay in knowledge.",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    ])
    mem_store = AgentMemoryStore(persist_dir=tmp_path / "mem")
    mem_store.store_memories("adv", [
        MemoryItem(
            agent_id="adv",
            meeting_id="m1",
            content="This should stay in memory only.",
            memory_type="argument",
        )
    ])

    knowledge_context, memory_context = build_agent_context_parts(
        agent_id="adv",
        briefing_text="Test",
        knowledge_store=kb_store,
        memory_store=mem_store,
    )
    assert "Domain Knowledge" in knowledge_context
    assert "Paragraph two should stay in knowledge." in knowledge_context
    assert "Past Meeting Memory" in memory_context
    assert "This should stay in memory only." in memory_context
