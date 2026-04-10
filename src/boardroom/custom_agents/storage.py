from __future__ import annotations

import json
from pathlib import Path

from boardroom.models import AgentConfig


class CustomAgentStorage:
    """Filesystem-backed CRUD for custom agent definitions."""

    def __init__(self, *, storage_dir: Path) -> None:
        self._dir = storage_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, agent_id: str) -> Path:
        candidate = (self._dir / f"{agent_id}.json").resolve()
        root = self._dir.resolve()
        if not candidate.is_relative_to(root):
            raise ValueError(f"Invalid agent id path traversal attempt: {agent_id!r}")
        return candidate

    def save(self, config: AgentConfig) -> None:
        path = self._path_for(config.id)
        path.write_text(
            json.dumps(config.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )

    def load(self, agent_id: str) -> AgentConfig:
        path = self._path_for(agent_id)
        if not path.exists():
            raise FileNotFoundError(f"Custom agent '{agent_id}' not found at {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return AgentConfig.model_validate(data)

    def delete(self, agent_id: str) -> None:
        path = self._path_for(agent_id)
        if not path.exists():
            raise FileNotFoundError(f"Custom agent '{agent_id}' not found at {path}")
        path.unlink()

    def exists(self, agent_id: str) -> bool:
        return self._path_for(agent_id).exists()

    def list_ids(self) -> list[str]:
        return sorted(p.stem for p in self._dir.glob("*.json"))

    def load_all(self) -> list[AgentConfig]:
        return [self.load(aid) for aid in self.list_ids()]
