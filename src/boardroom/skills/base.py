from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillContext:
    """Runtime context passed to a skill execution."""

    arguments: dict[str, Any] = field(default_factory=dict)
    briefing_excerpt: str = ""
    meeting_context: str = ""


@dataclass
class SkillResult:
    ok: bool
    output: str
    error: str = ""


class AgentSkill(ABC):
    """Abstract base class for executable agent capabilities."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def execute(self, context: SkillContext) -> SkillResult: ...
