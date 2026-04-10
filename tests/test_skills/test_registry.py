from __future__ import annotations

import pytest

from boardroom.skills.base import AgentSkill, SkillContext, SkillResult
from boardroom.skills.registry import SkillRegistry


class _DummySkill(AgentSkill):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy skill."

    def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult(ok=True, output="done")


def test_registry_register_and_get() -> None:
    reg = SkillRegistry()
    skill = _DummySkill()
    reg.register(skill)
    assert reg.get("dummy") is skill


def test_registry_get_unknown_returns_none() -> None:
    reg = SkillRegistry()
    assert reg.get("nonexistent") is None


def test_registry_list_names() -> None:
    reg = SkillRegistry()
    reg.register(_DummySkill())
    assert "dummy" in reg.list_names()


def test_registry_loads_defaults() -> None:
    reg = SkillRegistry.with_defaults()
    names = reg.list_names()
    assert "financial_modeling" in names
    assert "code_analysis" in names
    assert "statistical_analysis" in names
    assert "risk_assessment" in names


def test_registry_execute() -> None:
    reg = SkillRegistry()
    reg.register(_DummySkill())
    ctx = SkillContext()
    result = reg.execute("dummy", ctx)
    assert result is not None
    assert result.ok


def test_registry_execute_unknown_returns_none() -> None:
    reg = SkillRegistry()
    ctx = SkillContext()
    result = reg.execute("nonexistent", ctx)
    assert result is None
