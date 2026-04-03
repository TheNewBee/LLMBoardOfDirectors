from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from boardroom.models import AgentConfig, AgentRole, MeetingState


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def _context_blob(state: MeetingState) -> str:
    parts: list[str] = [state.briefing.text]
    parts.extend(state.debate_topics)
    if state.messages:
        parts.append(state.messages[-1].content)
    return " ".join(parts)


def _expertise_overlap(agent: AgentConfig, context_tokens: set[str]) -> float:
    exp_tokens = _tokenize(agent.expertise_domain)
    if not exp_tokens:
        return 0.0
    hits = len(context_tokens & exp_tokens)
    return hits / max(1, len(exp_tokens))


def _adversary_silence_turns(state: MeetingState, adversary_ids: set[str]) -> int:
    if not state.messages:
        return 0
    for i, msg in enumerate(reversed(state.messages)):
        if msg.agent_id in adversary_ids:
            return i
    return len(state.messages)


@dataclass(frozen=True)
class TurnSelectorConfig:
    expertise_weight: float = 1.0
    participation_weight: float = 2.0
    adversary_silence_turns: int = 3
    adversary_boost: float = 10.0


class TurnSelector:
    def __init__(self, config: TurnSelectorConfig | None = None) -> None:
        self._config = config or TurnSelectorConfig()

    def next_speaker(self, state: MeetingState, agents: Mapping[str, AgentConfig]) -> str:
        if not state.selected_agents:
            raise ValueError("MeetingState.selected_agents must be non-empty.")
        for aid in state.selected_agents:
            if aid not in agents:
                raise ValueError(f"Missing AgentConfig for selected agent id: {aid}")

        counts: dict[str, int] = {aid: 0 for aid in state.selected_agents}
        for msg in state.messages:
            if msg.agent_id in counts:
                counts[msg.agent_id] += 1
        max_spoken = max(counts.values()) if counts else 0

        adversary_ids = {
            aid for aid in state.selected_agents if agents[aid].role == AgentRole.ADVERSARY
        }
        silence = _adversary_silence_turns(state, adversary_ids)
        context_tokens = _tokenize(_context_blob(state))
        cfg = self._config

        def score(agent_id: str) -> float:
            agent = agents[agent_id]
            exp = _expertise_overlap(agent, context_tokens)
            part = max_spoken - counts[agent_id]
            total = cfg.expertise_weight * exp + cfg.participation_weight * part
            if agent.role == AgentRole.ADVERSARY and silence >= cfg.adversary_silence_turns:
                total += cfg.adversary_boost
            return total

        ranked = sorted(state.selected_agents, key=lambda aid: (-score(aid), aid))
        return ranked[0]
