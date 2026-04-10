from __future__ import annotations

from boardroom.skills.base import SkillContext
from boardroom.skills.defaults import (
    CodeAnalysisSkill,
    FinancialModelingSkill,
    RiskAssessmentSkill,
    StatisticalAnalysisSkill,
)


def test_financial_modeling_skill_produces_output() -> None:
    skill = FinancialModelingSkill()
    ctx = SkillContext(arguments={"scenario": "NPV of $100k investment at 8% for 5 years"})
    result = skill.execute(ctx)
    assert result.ok
    assert result.output


def test_code_analysis_skill_produces_output() -> None:
    skill = CodeAnalysisSkill()
    ctx = SkillContext(arguments={"code": "def foo(): pass"})
    result = skill.execute(ctx)
    assert result.ok
    assert result.output


def test_statistical_analysis_skill_produces_output() -> None:
    skill = StatisticalAnalysisSkill()
    ctx = SkillContext(arguments={"data": "10, 20, 30, 40, 50"})
    result = skill.execute(ctx)
    assert result.ok
    assert result.output


def test_risk_assessment_skill_produces_output() -> None:
    skill = RiskAssessmentSkill()
    ctx = SkillContext(arguments={"scenario": "Market entry into EU with uncertain regulations"})
    result = skill.execute(ctx)
    assert result.ok
    assert result.output


def test_all_default_skills_have_names() -> None:
    skills = [
        FinancialModelingSkill(),
        CodeAnalysisSkill(),
        StatisticalAnalysisSkill(),
        RiskAssessmentSkill(),
    ]
    names = {s.name for s in skills}
    assert len(names) == 4
    for s in skills:
        assert s.description
