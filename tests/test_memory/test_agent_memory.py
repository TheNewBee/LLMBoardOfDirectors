from __future__ import annotations

from pathlib import Path

import pytest

from boardroom.memory.agent_memory import AgentMemoryStore, MemoryItem
from boardroom.models import Message


def test_store_and_retrieve_memory(tmp_path: Path) -> None:
    store = AgentMemoryStore(persist_dir=tmp_path)
    items = [
        MemoryItem(
            agent_id="adversary",
            meeting_id="m1",
            content="Argued that market entry is premature due to regulatory risk.",
            memory_type="argument",
        ),
        MemoryItem(
            agent_id="adversary",
            meeting_id="m1",
            content="CFO agreed the costs are too uncertain.",
            memory_type="consensus",
        ),
    ]
    store.store_memories("adversary", items)
    retrieved = store.retrieve("adversary", query="market entry risk", limit=5)
    assert len(retrieved) >= 1
    assert any("market entry" in r.content for r in retrieved)


def test_retrieve_empty_returns_empty(tmp_path: Path) -> None:
    store = AgentMemoryStore(persist_dir=tmp_path)
    retrieved = store.retrieve("adversary", query="anything", limit=5)
    assert retrieved == []


def test_store_multiple_agents_isolated(tmp_path: Path) -> None:
    store = AgentMemoryStore(persist_dir=tmp_path)
    store.store_memories("agent_a", [
        MemoryItem(agent_id="agent_a", meeting_id="m1",
                   content="Agent A's private memory.", memory_type="argument"),
    ])
    store.store_memories("agent_b", [
        MemoryItem(agent_id="agent_b", meeting_id="m1",
                   content="Agent B's private memory.", memory_type="argument"),
    ])
    a_results = store.retrieve("agent_a", query="private memory", limit=5)
    b_results = store.retrieve("agent_b", query="private memory", limit=5)
    assert all(r.agent_id == "agent_a" for r in a_results)
    assert all(r.agent_id == "agent_b" for r in b_results)


def test_extract_memories_from_messages() -> None:
    messages = [
        Message(agent_id="adv", agent_name="Marcus",
                content="I believe this plan will fail due to market timing."),
        Message(agent_id="strat", agent_name="James",
                content="I agree the timing is risky but the opportunity is real."),
        Message(agent_id="adv", agent_name="Marcus",
                content="We still have unresolved disagreement on costs."),
    ]
    items = AgentMemoryStore.extract_from_messages(
        messages=messages, meeting_id="m1"
    )
    adv_items = [i for i in items if i.agent_id == "adv"]
    strat_items = [i for i in items if i.agent_id == "strat"]
    assert len(adv_items) == 2
    assert len(strat_items) == 1


def test_memory_item_fields() -> None:
    item = MemoryItem(
        agent_id="cfo",
        meeting_id="m2",
        content="Budget allocation was disputed.",
        memory_type="critique",
    )
    assert item.agent_id == "cfo"
    assert item.meeting_id == "m2"
    assert item.memory_type == "critique"


def test_token_budget_limits_retrieval(tmp_path: Path) -> None:
    store = AgentMemoryStore(persist_dir=tmp_path)
    items = [
        MemoryItem(
            agent_id="adv",
            meeting_id="m1",
            content=f"Memory item number {i} with some filler content for token counting.",
            memory_type="argument",
        )
        for i in range(50)
    ]
    store.store_memories("adv", items)
    retrieved = store.retrieve("adv", query="memory item", limit=100, max_tokens=200)
    total_chars = sum(len(r.content) for r in retrieved)
    assert total_chars <= 200 * 5  # rough char-to-token ratio safety margin


def test_long_agent_ids_do_not_collide(tmp_path: Path) -> None:
    store = AgentMemoryStore(persist_dir=tmp_path)
    prefix = "finance_department_senior_analyst_risk_assessment_"
    agent_a = f"{prefix}v1"
    agent_b = f"{prefix}v2"
    store.store_memories(agent_a, [
        MemoryItem(agent_id=agent_a, meeting_id="m1", content="only agent a", memory_type="argument")
    ])
    store.store_memories(agent_b, [
        MemoryItem(agent_id=agent_b, meeting_id="m1", content="only agent b", memory_type="argument")
    ])
    a_results = store.retrieve(agent_a, query="only agent", limit=10)
    b_results = store.retrieve(agent_b, query="only agent", limit=10)
    assert any("only agent a" in item.content for item in a_results)
    assert all("only agent b" not in item.content for item in a_results)
    assert any("only agent b" in item.content for item in b_results)
    assert all("only agent a" not in item.content for item in b_results)


def test_store_memories_reprocessing_same_meeting_keeps_unique_records(tmp_path: Path) -> None:
    store = AgentMemoryStore(persist_dir=tmp_path)
    agent_id = "adv"
    store.store_memories(agent_id, [
        MemoryItem(agent_id=agent_id, meeting_id="m1", content="first run content", memory_type="argument")
    ])
    store.store_memories(agent_id, [
        MemoryItem(agent_id=agent_id, meeting_id="m1", content="second run content", memory_type="argument")
    ])
    collection = store._collection_for(agent_id)
    assert int(collection.count()) == 2
