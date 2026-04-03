from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from boardroom.models import AgentConfig, AgentRole, Briefing, MeetingState
from boardroom.persona.config import agent_config_to_persona
from boardroom.selection.overlay import apply_meeting_overlays_to_config
from boardroom.persona.defaults import default_agent_configs
from boardroom.persona.engine import PersonaEngine


class AgentSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class InitializedAgent:
    agent_id: str
    config: AgentConfig
    system_prompt: str


class AgentRegistry:
    def __init__(self, agents: dict[str, AgentConfig] | None = None) -> None:
        self._agents: dict[str, AgentConfig] = dict(
            agents or default_agent_configs())

    def list_agent_ids(self) -> list[str]:
        return sorted(self._agents.keys())

    def get_config(self, agent_id: str) -> AgentConfig:
        if agent_id not in self._agents:
            raise AgentSelectionError(f"Unknown agent id: {agent_id}")
        return self._agents[agent_id]

    def validate_selection(self, agent_ids: Sequence[str]) -> None:
        n = len(agent_ids)
        if n < 2 or n > 6:
            raise AgentSelectionError(
                "Select between 2 and 6 agents (inclusive).")
        if len(set(agent_ids)) != len(agent_ids):
            raise AgentSelectionError("Each selected agent must be unique.")
        for aid in agent_ids:
            if aid not in self._agents:
                raise AgentSelectionError(
                    f"Unknown agent id in selection: {aid}")
        roles = {self._agents[aid].role for aid in agent_ids}
        if AgentRole.ADVERSARY not in roles:
            raise AgentSelectionError(
                "At least one selected agent must be the adversary.")

    def initialize_selected(
        self,
        agent_ids: Sequence[str],
        briefing: Briefing,
        meeting: MeetingState | None = None,
        *,
        validate: bool = True,
    ) -> list[InitializedAgent]:
        if validate:
            self.validate_selection(agent_ids)
        engine = PersonaEngine()
        out: list[InitializedAgent] = []
        for aid in agent_ids:
            cfg = self._agents[aid]
            if meeting is not None:
                cfg = apply_meeting_overlays_to_config(cfg, meeting)
            persona = agent_config_to_persona(cfg)
            prompt = engine.apply_persona(persona, briefing=briefing)
            out.append(
                InitializedAgent(agent_id=aid, config=cfg,
                                 system_prompt=prompt),
            )
        return out
