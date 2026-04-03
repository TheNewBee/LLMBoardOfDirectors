from __future__ import annotations

from boardroom.models import AgentRole, BiasType
from boardroom.persona.bias import BiasApplicator
from boardroom.persona.config import PersonaConfig


def test_bias_applicator_includes_risk_aversion_with_intensity() -> None:
    ba = BiasApplicator()
    persona = PersonaConfig(
        name="CFO",
        role=AgentRole.CFO,
        expertise="finance",
        biases=[BiasType.RISK_AVERSION],
        communication_style="precise, formal",
        bias_intensity=0.9,
    )
    fragment = ba.bias_prompt_fragment(persona)
    assert "risk" in fragment.lower()
    assert "0.9" in fragment or "90" in fragment


def test_bias_applicator_stacks_multiple_biases() -> None:
    ba = BiasApplicator()
    persona = PersonaConfig(
        name="X",
        role=AgentRole.STRATEGIST,
        expertise="ops",
        biases=[BiasType.COST_FOCUS, BiasType.SPEED_FOCUS],
        communication_style="direct",
        bias_intensity=0.5,
    )
    fragment = ba.bias_prompt_fragment(persona)
    lower = fragment.lower()
    assert "economics" in lower or "capital" in lower
    assert "shipping" in lower or "time-to-learning" in lower
