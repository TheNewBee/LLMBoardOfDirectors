from __future__ import annotations

from datetime import datetime
from pathlib import Path

from boardroom.models import Briefing, MeetingState, TerminationReason
from boardroom.vector_store import MeetingVectorStore
from boardroom.vector_store.store import HashEmbeddingFunction


def _meeting(meeting_id: str) -> MeetingState:
    return MeetingState(
        meeting_id=meeting_id,
        briefing=Briefing(
            text="Evaluate EU expansion strategy.",
            objectives=["Find key risks", "Propose mitigations"],
        ),
        selected_agents=["adversary", "strategist"],
        turn_count=5,
        termination_reason=TerminationReason.MAX_TURNS,
        start_time=datetime.utcnow(),
    )


def test_vector_store_upsert_and_search(tmp_path: Path) -> None:
    store = MeetingVectorStore(persist_dir=tmp_path / "vec")
    meeting = _meeting("m-eu-1")
    store.upsert_meeting(
        meeting=meeting,
        transcript_markdown="EU expansion has pricing risk and compliance concerns.",
    )

    rows = store.search(query="compliance risk", limit=3)
    assert rows
    assert rows[0]["id"] == "m-eu-1"
    assert rows[0]["metadata"]["meeting_id"] == "m-eu-1"


def test_vector_store_upsert_is_idempotent_by_meeting_id(tmp_path: Path) -> None:
    store = MeetingVectorStore(persist_dir=tmp_path / "vec")
    meeting = _meeting("m-idempotent")
    store.upsert_meeting(meeting=meeting, transcript_markdown="First summary")
    store.upsert_meeting(
        meeting=meeting, transcript_markdown="Updated summary")

    rows = store.search(query="updated", limit=5)
    matches = [row for row in rows if row["id"] == "m-idempotent"]
    assert len(matches) == 1
    assert "Updated summary" in matches[0]["document"]


def test_hash_embedding_is_process_stable_and_deterministic() -> None:
    embed = HashEmbeddingFunction(dimensions=256)
    a = embed(["same text twice"])[0]
    b = embed(["same text twice"])[0]
    assert a == b
    assert len(a) == 256
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6


def test_vector_store_search_returns_empty_for_blank_query(tmp_path: Path) -> None:
    store = MeetingVectorStore(persist_dir=tmp_path / "vec")
    assert store.search(query="   ", limit=5) == []
