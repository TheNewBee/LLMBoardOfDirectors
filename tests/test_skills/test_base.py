from __future__ import annotations

import pytest

from boardroom.skills.base import AgentSkill, SkillContext, SkillResult


class _EchoSkill(AgentSkill):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes input back."

    def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult(
            ok=True,
            output=f"echo: {context.arguments.get('text', '')}",
        )


def test_skill_execute_returns_result() -> None:
    skill = _EchoSkill()
    ctx = SkillContext(arguments={"text": "hello"})
    result = skill.execute(ctx)
    assert result.ok is True
    assert "hello" in result.output


def test_skill_context_defaults() -> None:
    ctx = SkillContext()
    assert ctx.arguments == {}
    assert ctx.briefing_excerpt == ""
    assert ctx.meeting_context == ""


def test_skill_result_error() -> None:
    result = SkillResult(ok=False, output="", error="division by zero")
    assert not result.ok
    assert result.error == "division by zero"


def test_skill_name_and_description() -> None:
    skill = _EchoSkill()
    assert skill.name == "echo"
    assert "Echo" in skill.description
