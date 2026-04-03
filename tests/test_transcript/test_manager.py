from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from boardroom.models import (
    AgentConfig,
    AgentRole,
    Briefing,
    MeetingState,
    Message,
    TerminationReason,
    Transcript,
)
from boardroom.transcript import TranscriptManager, TranscriptStreamBuffer


def _briefing() -> Briefing:
    return Briefing(text="Launch the product in Q2.", objectives=["Stress-test the plan."])


def _agent(
    agent_id: str,
    name: str,
    role: AgentRole,
) -> AgentConfig:
    return AgentConfig(
        id=agent_id,
        name=name,
        role=role,
        expertise_domain="general",
        personality_traits=["direct"],
    )


def _meeting(messages: list[Message] | None = None) -> MeetingState:
    return MeetingState(
        meeting_id="meet-01",
        briefing=_briefing(),
        selected_agents=["adv", "strat"],
        messages=messages or [],
        turn_count=len(messages or []),
        start_time=datetime(2025, 3, 25, 12, 0, 0, tzinfo=timezone.utc),
        termination_reason=TerminationReason.CONSENSUS,
    )


def test_format_message_includes_name_role_timestamp() -> None:
    agents = {"adv": _agent("adv", "Marcus", AgentRole.ADVERSARY)}
    ts = datetime(2025, 3, 25, 14, 30, 5, tzinfo=timezone.utc)
    msg = Message(
        agent_id="adv",
        agent_name="Marcus",
        content="This is a **blocker** for launch.",
        timestamp=ts,
    )
    mgr = TranscriptManager()
    md = mgr.format_transcript_markdown(_meeting([msg]), agents)

    assert "### Marcus (`adv`)" in md
    assert "**Role:** adversary" in md
    assert "2025-03-25" in md
    assert "This is a **blocker** for launch." in md


def test_tool_calls_and_results_render_in_separate_block() -> None:
    agents = {"ds": _agent("ds", "Dana", AgentRole.DATA_SPECIALIST)}
    msg = Message(
        agent_id="ds",
        agent_name="Dana",
        content="Fetching metrics.",
        tool_calls=[{"name": "lookup", "args": {"q": "x"}}],
        tool_results=[{"name": "lookup", "ok": True}],
    )
    mgr = TranscriptManager()
    md = mgr.format_transcript_markdown(_meeting([msg]), agents)

    assert "#### Tool execution" in md
    assert "tool_calls" in md
    assert "lookup" in md
    assert "tool_results" in md


def test_metadata_summary_section() -> None:
    agents = {
        "adv": _agent("adv", "Marcus", AgentRole.ADVERSARY),
        "strat": _agent("strat", "James", AgentRole.STRATEGIST),
    }
    mgr = TranscriptManager()
    md = mgr.format_transcript_markdown(_meeting([]), agents)

    assert "## Meeting summary" in md
    assert "`meet-01`" in md
    assert "consensus" in md
    assert "Stress-test the plan." in md


def test_kill_sheet_groups_by_severity_with_evidence() -> None:
    agents = {
        "adv": _agent("adv", "Marcus", AgentRole.ADVERSARY),
        "strat": _agent("strat", "James", AgentRole.STRATEGIST),
    }
    messages = [
        Message(
            agent_id="adv",
            agent_name="Marcus",
            content="Fatal flaw: we have no rollback plan.",
        ),
        Message(
            agent_id="strat",
            agent_name="James",
            content="We should ship a minimal slice first.",
        ),
    ]
    meeting = _meeting(messages)
    mgr = TranscriptManager()
    kill = mgr.build_kill_sheet_markdown(meeting, agents)

    assert "## Kill Sheet" in kill
    assert "### High severity" in kill
    assert "Fatal flaw" in kill
    assert "Marcus" in kill
    assert "Adversary" in kill or "adversary" in kill


def test_consensus_roadmap_extracts_proposal_lines() -> None:
    agents = {
        "strat": _agent("strat", "James", AgentRole.STRATEGIST),
    }
    messages = [
        Message(
            agent_id="strat",
            agent_name="James",
            content="Recommend phased rollout.\nNext step: pilot with one team.",
        ),
    ]
    meeting = _meeting(messages)
    mgr = TranscriptManager()
    road = mgr.build_consensus_roadmap_markdown(meeting, agents)

    assert "## Consensus Roadmap" in road
    assert "James" in road
    assert "Recommend" in road or "pilot" in road


def test_persist_writes_main_and_sidecar_files(tmp_path: Path) -> None:
    agents = {
        "adv": _agent("adv", "Marcus", AgentRole.ADVERSARY),
        "strat": _agent("strat", "James", AgentRole.STRATEGIST),
    }
    messages = [
        Message(
            agent_id="adv",
            agent_name="Marcus",
            content="Risk: compliance gaps remain.",
        ),
        Message(
            agent_id="strat",
            agent_name="James",
            content="We should close gaps before launch.",
        ),
    ]
    meeting = _meeting(messages)
    fixed = datetime(2025, 3, 25, 16, 1, 2, tzinfo=timezone.utc)
    mgr = TranscriptManager(outputs_dir=tmp_path, now_fn=lambda: fixed)

    tr = mgr.persist(meeting, agents)

    assert isinstance(tr, Transcript)
    assert tr.meeting_id == "meet-01"
    assert tr.message_count == 2
    assert tr.path.name == "meet-01_20250325T160102Z_transcript.md"
    assert tr.kill_sheet_path is not None
    assert tr.consensus_roadmap_path is not None
    assert tr.kill_sheet_path.name == "meet-01_20250325T160102Z_kill_sheet.md"
    assert tr.consensus_roadmap_path.name == "meet-01_20250325T160102Z_consensus_roadmap.md"

    main = tr.path.read_text(encoding="utf-8")
    assert "## Kill Sheet" in main
    assert "## Consensus Roadmap" in main
    assert "## Transcript" in main

    assert tr.kill_sheet_path.read_text(encoding="utf-8")
    assert tr.consensus_roadmap_path.read_text(encoding="utf-8")


def test_stream_buffer_append_returns_fragment_and_joins() -> None:
    agents = {
        "adv": _agent("adv", "Marcus", AgentRole.ADVERSARY),
    }
    buf = TranscriptStreamBuffer(agents)
    m = Message(agent_id="adv", agent_name="Marcus", content="Hello.")
    frag = buf.append_turn(m)
    assert "Marcus" in frag
    assert "Hello." in frag
    joined = buf.as_markdown_body()
    assert frag in joined


def test_persist_sanitizes_meeting_id_in_filename(tmp_path: Path) -> None:
    agents = {
        "a": _agent("a", "A", AgentRole.ADVERSARY),
        "b": _agent("b", "B", AgentRole.STRATEGIST),
    }
    meeting = MeetingState(
        meeting_id="weird/id\\x",
        briefing=_briefing(),
        selected_agents=["a", "b"],
    )
    fixed = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    mgr = TranscriptManager(outputs_dir=tmp_path, now_fn=lambda: fixed)
    tr = mgr.persist(meeting, agents)
    assert "weird" in tr.path.name
    assert "/" not in tr.path.name
    assert "\\" not in tr.path.name


def test_kill_sheet_json_determinism() -> None:
    """Tool JSON in transcript uses sorted keys for stable output."""
    agents = {"ds": _agent("ds", "Dana", AgentRole.DATA_SPECIALIST)}
    msg = Message(
        agent_id="ds",
        agent_name="Dana",
        content="Done.",
        tool_calls=[{"z": 1, "a": 2}],
        tool_results=[{"b": 3, "a": 4}],
    )
    md = TranscriptManager().format_transcript_markdown(_meeting([msg]), agents)
    assert '"a": 2' in md
    z_after_a = md.index('"a": 2') < md.index('"z": 1')
    assert z_after_a
