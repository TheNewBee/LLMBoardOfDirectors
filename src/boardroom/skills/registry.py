from __future__ import annotations

from boardroom.skills.base import AgentSkill, SkillContext, SkillResult


class SkillRegistry:
    """Maps skill names to concrete AgentSkill instances."""

    def __init__(self) -> None:
        self._skills: dict[str, AgentSkill] = {}

    def register(self, skill: AgentSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> AgentSkill | None:
        return self._skills.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._skills.keys())

    def execute(self, name: str, context: SkillContext) -> SkillResult | None:
        skill = self.get(name)
        if skill is None:
            return None
        return skill.execute(context)

    @classmethod
    def with_defaults(cls) -> SkillRegistry:
        from boardroom.skills.defaults import DEFAULT_SKILLS

        registry = cls()
        for skill in DEFAULT_SKILLS:
            registry.register(skill)
        return registry
