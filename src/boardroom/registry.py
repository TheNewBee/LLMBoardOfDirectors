from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from boardroom.models import AgentConfig, AgentRole, Briefing, MeetingState
from boardroom.persona.config import agent_config_to_persona
from boardroom.selection.overlay import apply_meeting_overlays_to_config
from boardroom.persona.defaults import default_agent_configs
from boardroom.persona.engine import PersonaEngine

_LOG = logging.getLogger(__name__)

_DEFAULT_CUSTOM_DIR = Path(".boardroom/custom_agents")


class AgentSelectionError(ValueError):
    pass


@dataclass(frozen=True)
class InitializedAgent:
    agent_id: str
    config: AgentConfig
    system_prompt: str


class AgentRegistry:
    def __init__(
        self,
        agents: dict[str, AgentConfig] | None = None,
        *,
        custom_agents_dir: Path | None = None,
    ) -> None:
        self._agents: dict[str, AgentConfig] = dict(
            agents or default_agent_configs())
        self._load_custom_agents(custom_agents_dir or _DEFAULT_CUSTOM_DIR)

    def _load_custom_agents(self, custom_dir: Path) -> None:
        if not custom_dir.exists():
            return
        from boardroom.custom_agents.storage import CustomAgentStorage

        try:
            storage = CustomAgentStorage(storage_dir=custom_dir)
            for cfg in storage.load_all():
                if cfg.id not in self._agents:
                    self._agents[cfg.id] = cfg
        except Exception:
            _LOG.warning("Failed to load custom agents from %s", custom_dir, exc_info=True)

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
        knowledge_by_agent: dict[str, str] | None = None,
        memory_by_agent: dict[str, str] | None = None,
    ) -> list[InitializedAgent]:
        if validate:
            self.validate_selection(agent_ids)
        engine = PersonaEngine()
        kb = knowledge_by_agent or {}
        mem = memory_by_agent or {}
        out: list[InitializedAgent] = []
        for aid in agent_ids:
            cfg = self._agents[aid]
            if meeting is not None:
                cfg = apply_meeting_overlays_to_config(cfg, meeting)
            persona = agent_config_to_persona(cfg)
            prompt = engine.apply_persona(
                persona,
                briefing=briefing,
                knowledge_context=kb.get(aid, ""),
                memory_context=mem.get(aid, ""),
            )
            out.append(
                InitializedAgent(agent_id=aid, config=cfg,
                                 system_prompt=prompt),
            )
        return out
