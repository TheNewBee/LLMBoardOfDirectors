from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from boardroom.models import AgentConfig, AgentRole, MeetingState, Message, Transcript

Severity = Literal["high", "medium", "low"]

_HIGH = (
    "fatal",
    "blocker",
    "critical",
    "catastrophic",
    "showstopper",
    "must reject",
    "dead on arrival",
    "severe",
)
_MEDIUM = (
    "risk",
    "concern",
    "fragile",
    "expensive",
    "warning",
    "unlikely",
    "gap",
    "compliance",
    "security issue",
    "breach",
)

_ROADMAP_HINTS = (
    "recommend",
    "should",
    "next step",
    "phased",
    "milestone",
    "proposal",
    "ship",
    "launch",
    "plan",
    "pilot",
    "rollout",
    "roadmap",
    "consensus",
    "align",
    "iterate",
)

_KILL_ROLES = frozenset(
    {
        AgentRole.ADVERSARY,
        AgentRole.CFO,
        AgentRole.TECH_DIRECTOR,
    }
)

_ROADMAP_ROLES = frozenset(
    {
        AgentRole.STRATEGIST,
        AgentRole.DATA_SPECIALIST,
        AgentRole.CFO,
    }
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize_meeting_id(meeting_id: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", meeting_id)
    return cleaned.strip("_") or "meeting"


def _artifact_timestamp(when: datetime) -> str:
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)
    return when.strftime("%Y%m%dT%H%M%SZ")


def _fmt_message_ts(ts: datetime) -> str:
    if ts.tzinfo is None:
        return ts.strftime("%Y-%m-%d %H:%M:%S") + " UTC"
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _role_label(role: AgentRole | None) -> str:
    if role is None:
        return "unknown"
    return role.value


def _json_block(label: str, data: Any) -> str:
    body = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return f"**{label}**\n\n```json\n{body}\n```"


def _format_tool_execution(message: Message) -> str:
    if not message.tool_calls and not message.tool_results:
        return ""
    parts = ["#### Tool execution", ""]
    if message.tool_calls:
        parts.append(_json_block("tool_calls", message.tool_calls))
        parts.append("")
    if message.tool_results:
        parts.append(_json_block("tool_results", message.tool_results))
    return "\n".join(parts).rstrip()


def format_turn_markdown(message: Message, agent: AgentConfig | None) -> str:
    role = agent.role if agent else None
    name = message.agent_name
    aid = message.agent_id
    ts = _fmt_message_ts(message.timestamp)
    role_s = _role_label(role)

    header = f"### {name} (`{aid}`)\n\n**Role:** {role_s}  \n**Time:** {ts}\n"
    body = f"\n{message.content.strip()}\n"
    tools = _format_tool_execution(message)
    if tools:
        body = f"{body}\n\n---\n\n{tools}\n"
    return header + body


def _split_evidence_chunks(content: str) -> list[str]:
    text = content.strip()
    if not text:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        return lines
    # Single paragraph: split into rough sentences for long text
    if len(text) > 200 and ". " in text:
        return [s.strip() for s in text.split(". ") if s.strip()]
    return [text]


def _severity_for_chunk(lower: str) -> Severity | None:
    if any(k in lower for k in _HIGH):
        return "high"
    if any(k in lower for k in _MEDIUM):
        return "medium"
    return None


def _collect_kill_items(
    meeting: MeetingState,
    agents_by_id: Mapping[str, AgentConfig],
) -> dict[Severity, list[str]]:
    buckets: dict[Severity, list[str]] = {"high": [], "medium": [], "low": []}
    for msg in meeting.messages:
        cfg = agents_by_id.get(msg.agent_id)
        role = cfg.role if cfg else None
        if role is None:
            continue
        for chunk in _split_evidence_chunks(msg.content):
            lower = chunk.lower()
            sev = _severity_for_chunk(lower)
            if role in _KILL_ROLES:
                if sev is None and len(chunk) >= 12:
                    sev = "low"
                if sev is None:
                    continue
            elif role is AgentRole.DATA_SPECIALIST:
                if sev is None:
                    continue
            else:
                continue
            agent_name = msg.agent_name
            role_s = _role_label(role)
            line = (
                f"- **Finding:** {chunk}  \n"
                f"  **Evidence:** {agent_name} ({role_s}) — excerpt from turn at "
                f"{_fmt_message_ts(msg.timestamp)}."
            )
            buckets[sev].append(line)
    return buckets


def _render_kill_sheet_md(items: dict[Severity, list[str]]) -> str:
    lines = ["## Kill Sheet", ""]
    if not any(items.values()):
        lines.append(
            "_No structured flaws were extracted under Phase 1 heuristics "
            "(adversary / CFO / tech director turns, plus specialist high-signal risks)._"
        )
        return "\n".join(lines)

    order: list[tuple[str, Severity]] = [
        ("### High severity", "high"),
        ("### Medium severity", "medium"),
        ("### Low severity / watch items", "low"),
    ]
    for heading, key in order:
        block = items[key]
        if not block:
            continue
        lines.append(heading)
        lines.append("")
        lines.extend(block)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _roadmap_lines(meeting: MeetingState, agents_by_id: Mapping[str, AgentConfig]) -> list[str]:
    out: list[str] = []
    for msg in meeting.messages:
        cfg = agents_by_id.get(msg.agent_id)
        role = cfg.role if cfg else None
        if role not in _ROADMAP_ROLES:
            continue
        for chunk in _split_evidence_chunks(msg.content):
            lower = chunk.lower()
            if not any(h in lower for h in _ROADMAP_HINTS):
                continue
            out.append(
                f"- **Proposal / next step:** {chunk}  \n"
                f"  **Reasoning:** {msg.agent_name} ({_role_label(role)}) — "
                f"{_fmt_message_ts(msg.timestamp)}."
            )
    return out


def _render_roadmap_md(lines: list[str]) -> str:
    header = "## Consensus Roadmap\n\n"
    if not lines:
        return (
            header + "_No explicit consensus-style proposals were detected in strategist / "
            "specialist / CFO language (Phase 1 keyword heuristics). Review transcript "
            "turns manually._\n"
        )
    return header + "\n".join(lines) + "\n"


def _meeting_summary_md(meeting: MeetingState, agents_by_id: Mapping[str, AgentConfig]) -> str:
    lines = [
        "## Meeting summary",
        "",
        f"- **Meeting ID:** `{meeting.meeting_id}`",
        f"- **Started:** {_fmt_message_ts(meeting.start_time)}",
        f"- **Turns recorded:** {meeting.turn_count}",
        f"- **Messages:** {len(meeting.messages)}",
        f"- **Termination:** {meeting.termination_reason.value if meeting.termination_reason else 'n/a'}",
        "",
        "### Briefing",
        "",
        meeting.briefing.text.strip(),
        "",
        "### Objectives",
        "",
    ]
    for obj in meeting.briefing.objectives:
        lines.append(f"- {obj}")
    lines.append("")
    lines.append("### Agents")
    lines.append("")
    for aid in meeting.selected_agents:
        cfg = agents_by_id.get(aid)
        if cfg is None:
            lines.append(f"- `{aid}` _(config not provided)_")
        else:
            lines.append(f"- **{cfg.name}** (`{aid}`) — {_role_label(cfg.role)}")
    lines.append("")
    return "\n".join(lines)


class TranscriptStreamBuffer:
    """Incremental transcript body for streaming UIs (append per turn).

    Callers may batch or throttle writes (e.g. ~2s) at the integration layer; this
    class only formats and accumulates markdown fragments deterministically.
    """

    def __init__(self, agents_by_id: Mapping[str, AgentConfig]) -> None:
        self._agents = agents_by_id
        self._fragments: list[str] = []

    def append_turn(self, message: Message) -> str:
        cfg = self._agents.get(message.agent_id)
        fragment = format_turn_markdown(message, cfg)
        self._fragments.append(fragment)
        return fragment

    def as_markdown_body(self) -> str:
        return "\n\n---\n\n".join(self._fragments)


class TranscriptManager:
    def __init__(
        self,
        *,
        outputs_dir: Path | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._outputs_dir = outputs_dir
        self._now_fn = now_fn or _utc_now

    def build_kill_sheet_markdown(
        self,
        meeting: MeetingState,
        agents_by_id: Mapping[str, AgentConfig],
    ) -> str:
        items = _collect_kill_items(meeting, agents_by_id)
        return _render_kill_sheet_md(items)

    def build_consensus_roadmap_markdown(
        self,
        meeting: MeetingState,
        agents_by_id: Mapping[str, AgentConfig],
    ) -> str:
        return _render_roadmap_md(_roadmap_lines(meeting, agents_by_id))

    def _transcript_core_markdown(
        self,
        meeting: MeetingState,
        agents_by_id: Mapping[str, AgentConfig],
    ) -> str:
        summary = _meeting_summary_md(meeting, agents_by_id)
        parts = [summary, "## Transcript", ""]
        for msg in meeting.messages:
            cfg = agents_by_id.get(msg.agent_id)
            parts.append(format_turn_markdown(msg, cfg))
            parts.append("")
            parts.append("---")
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def format_transcript_markdown(
        self,
        meeting: MeetingState,
        agents_by_id: Mapping[str, AgentConfig],
    ) -> str:
        body = self._transcript_core_markdown(meeting, agents_by_id)
        kill = self.build_kill_sheet_markdown(meeting, agents_by_id)
        road = self.build_consensus_roadmap_markdown(meeting, agents_by_id)
        return f"{body}\n{kill}\n{road}"

    def format_full_document_markdown(
        self,
        meeting: MeetingState,
        agents_by_id: Mapping[str, AgentConfig],
    ) -> str:
        title = f"# Meeting transcript — `{meeting.meeting_id}`\n\n"
        return title + self.format_transcript_markdown(meeting, agents_by_id)

    def persist(
        self,
        meeting: MeetingState,
        agents_by_id: Mapping[str, AgentConfig],
        *,
        outputs_dir: Path | None = None,
    ) -> Transcript:
        base = outputs_dir or self._outputs_dir
        if base is None:
            raise ValueError("outputs_dir is required for persist() (pass to constructor or call).")

        base.mkdir(parents=True, exist_ok=True)
        when = self._now_fn()
        ts = _artifact_timestamp(when)
        safe_id = _sanitize_meeting_id(meeting.meeting_id)
        stem = f"{safe_id}_{ts}"

        core_md = self._transcript_core_markdown(meeting, agents_by_id)
        kill_md = self.build_kill_sheet_markdown(meeting, agents_by_id)
        road_md = self.build_consensus_roadmap_markdown(meeting, agents_by_id)
        title = f"# Meeting transcript — `{meeting.meeting_id}`\n\n"
        full_md = f"{title}{core_md}\n{kill_md}\n{road_md}"

        path = base / f"{stem}_transcript.md"
        kill_path = base / f"{stem}_kill_sheet.md"
        road_path = base / f"{stem}_consensus_roadmap.md"

        path.write_text(full_md, encoding="utf-8")
        kill_path.write_text(kill_md, encoding="utf-8")
        road_path.write_text(road_md, encoding="utf-8")

        return Transcript(
            meeting_id=meeting.meeting_id,
            created_at=when,
            path=path,
            kill_sheet_path=kill_path,
            consensus_roadmap_path=road_path,
            message_count=len(meeting.messages),
        )
