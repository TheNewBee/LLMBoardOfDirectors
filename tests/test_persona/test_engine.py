from __future__ import annotations

import pytest

from boardroom.models import AgentRole, BiasType, Briefing
from boardroom.persona.config import PersonaConfig
from boardroom.persona.engine import PersonaConsistencyError, PersonaEngine


def make_briefing() -> Briefing:
    return Briefing(
        text="Launch a subscription analytics product.",
        objectives=["Stress-test GTM and unit economics."],
    )


def test_apply_persona_includes_identity_and_expertise() -> None:
    engine = PersonaEngine()
    persona = PersonaConfig(
        name="Marcus",
        role=AgentRole.ADVERSARY,
        expertise="strategy and failure modes",
        biases=[],
        communication_style="blunt, evidence-first",
    )
    prompt = engine.apply_persona(persona)
    assert "Marcus" in prompt
    assert "strategy" in prompt.lower() or "failure" in prompt.lower()


def test_apply_persona_injects_briefing_context() -> None:
    engine = PersonaEngine()
    persona = PersonaConfig(
        name="Alex",
        role=AgentRole.DATA_SPECIALIST,
        expertise="metrics",
        biases=[],
        communication_style="analytical",
    )
    prompt = engine.apply_persona(persona, briefing=make_briefing())
    assert "subscription" in prompt.lower()
    assert "Stress-test" in prompt or "economics" in prompt.lower()


@pytest.mark.parametrize(
    "role",
    [
        AgentRole.ADVERSARY,
        AgentRole.DATA_SPECIALIST,
        AgentRole.STRATEGIST,
        AgentRole.CFO,
        AgentRole.TECH_DIRECTOR,
        AgentRole.CUSTOM,
    ],
)
def test_all_roles_prompt_includes_tool_contract(role: AgentRole) -> None:
    engine = PersonaEngine()
    persona = PersonaConfig(
        name="Alex",
        role=role,
        expertise="metrics",
        biases=[],
        communication_style="analytical",
    )
    prompt = engine.apply_persona(persona)
    assert "```tool" in prompt
    assert "python_exec" in prompt
    assert "web_search" in prompt


def test_persona_config_json_round_trip() -> None:
    from boardroom.persona.config import persona_from_json, persona_to_json

    original = PersonaConfig(
        name="Sam",
        role=AgentRole.TECH_DIRECTOR,
        expertise="platforms",
        biases=[BiasType.OVER_ENGINEERING],
        communication_style="detail-oriented",
        bias_intensity=0.8,
    )
    restored = persona_from_json(persona_to_json(original))
    assert restored == original


def test_persona_from_json_rejects_missing_fields() -> None:
    from boardroom.persona.config import persona_from_json

    with pytest.raises(ValueError):
        persona_from_json('{"name": "Sam"}')


def test_validate_consistency_rejects_duplicate_of_prior_turn() -> None:
    engine = PersonaEngine()
    persona = PersonaConfig(
        name="Pat",
        role=AgentRole.STRATEGIST,
        expertise="synthesis",
        biases=[],
        communication_style="professional",
    )
    prior = "We should sequence EU entry after PMF in the home market."
    with pytest.raises(PersonaConsistencyError):
        engine.validate_consistency(
            persona,
            prior_turn_contents=[prior],
            candidate_turn=prior,
        )


def test_validate_consistency_rejects_duplicate_of_older_turn() -> None:
    engine = PersonaEngine()
    persona = PersonaConfig(
        name="Pat",
        role=AgentRole.STRATEGIST,
        expertise="synthesis",
        biases=[],
        communication_style="professional",
    )
    prior_turns = [
        "I think you should delay the launch until the funnel is less fragile.",
        "I disagree with the margin assumptions you used earlier.",
    ]
    with pytest.raises(PersonaConsistencyError):
        engine.validate_consistency(
            persona,
            prior_turn_contents=prior_turns,
            candidate_turn=prior_turns[0],
        )


def test_validate_consistency_rejects_leaky_turn() -> None:
    engine = PersonaEngine()
    persona = PersonaConfig(
        name="Pat",
        role=AgentRole.STRATEGIST,
        expertise="synthesis",
        biases=[],
        communication_style="professional",
    )
    bad = "As an AI, I think we should proceed."
    with pytest.raises(PersonaConsistencyError):
        engine.validate_consistency(
            persona, prior_turn_contents=[], candidate_turn=bad)


def test_validate_consistency_requires_first_and_second_person_perspective() -> None:
    engine = PersonaEngine()
    persona = PersonaConfig(
        name="Pat",
        role=AgentRole.STRATEGIST,
        expertise="synthesis",
        biases=[],
        communication_style="professional",
    )
    with pytest.raises(PersonaConsistencyError):
        engine.validate_consistency(
            persona,
            prior_turn_contents=[],
            candidate_turn="The company should reduce burn and delay launch.",
        )
