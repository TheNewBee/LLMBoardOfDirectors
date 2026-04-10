from __future__ import annotations

from boardroom.custom_agents.storage import CustomAgentStorage
from boardroom.models import AgentConfig, AgentRole
from boardroom.persona.defaults import default_agent_configs


class CustomAgentError(ValueError):
    pass


_BUILTIN_IDS: frozenset[str] = frozenset(default_agent_configs().keys())


class CustomAgentBuilder:
    """Validates and orchestrates CRUD for user-defined agents."""

    def __init__(self, *, storage: CustomAgentStorage) -> None:
        self._storage = storage

    def create(self, config: AgentConfig) -> AgentConfig:
        if config.role != AgentRole.CUSTOM:
            raise CustomAgentError(
                f"Custom agents must have role=CUSTOM, got {config.role}"
            )
        if config.id in _BUILTIN_IDS:
            raise CustomAgentError(
                f"Agent id '{config.id}' collides with a built-in agent."
            )
        if self._storage.exists(config.id):
            raise CustomAgentError(
                f"Custom agent '{config.id}' already exists."
            )
        self._storage.save(config)
        return config

    def update(self, config: AgentConfig) -> AgentConfig:
        if config.role != AgentRole.CUSTOM:
            raise CustomAgentError(
                f"Custom agents must have role=CUSTOM, got {config.role}"
            )
        if not self._storage.exists(config.id):
            raise CustomAgentError(
                f"Custom agent '{config.id}' does not exist."
            )
        self._storage.save(config)
        return config

    def delete(self, agent_id: str) -> None:
        if not self._storage.exists(agent_id):
            raise CustomAgentError(
                f"Custom agent '{agent_id}' does not exist."
            )
        self._storage.delete(agent_id)

    def get(self, agent_id: str) -> AgentConfig:
        return self._storage.load(agent_id)

    def exists(self, agent_id: str) -> bool:
        return self._storage.exists(agent_id)

    def list_ids(self) -> list[str]:
        return self._storage.list_ids()

    def list_all(self) -> list[AgentConfig]:
        return self._storage.load_all()
