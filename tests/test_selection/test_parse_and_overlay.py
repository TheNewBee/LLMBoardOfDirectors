from __future__ import annotations

import pytest

from boardroom.models import (
    AgentConfig,
    AgentRole,
    Briefing,
    MeetingLLMSelection,
    MeetingState,
    ModelConfig,
)
from boardroom.registry import AgentRegistry
from boardroom.selection.overlay import apply_meeting_overlays_to_config
from boardroom.selection.parse import parse_key_value_floats, parse_key_value_strings


def test_parse_key_value_strings_accepts_equals() -> None:
    assert parse_key_value_strings(["a=b", "c=d=e"], name="x") == {"a": "b", "c": "d=e"}


def test_parse_key_value_strings_rejects_missing_equals() -> None:
    with pytest.raises(ValueError, match="expected KEY=value"):
        parse_key_value_strings(["nope"], name="agent-model")


def test_parse_key_value_floats() -> None:
    assert parse_key_value_floats(["x=0.5", "y=1"], name="bias") == {"x": 0.5, "y": 1.0}


def test_parse_key_value_floats_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="must be in"):
        parse_key_value_floats(["x=2"], name="bias")


def test_apply_overlay_model_and_bias() -> None:
    base = AgentConfig(
        id="cfo",
        name="Elena",
        role=AgentRole.CFO,
        expertise_domain="finance",
        personality_traits=["formal"],
        bias_intensity=0.5,
    )
    meeting = MeetingState(
        meeting_id="m1",
        briefing=Briefing(text="x", objectives=["o"]),
        selected_agents=["cfo", "adversary"],
        llm=MeetingLLMSelection(
            provider="openrouter",
            models_by_agent={"cfo": "openai/gpt-4o-mini"},
        ),
        bias_intensity_by_agent={"cfo": 0.2},
    )
    out = apply_meeting_overlays_to_config(base, meeting)
    assert out.bias_intensity == 0.2
    assert out.model_config_override == ModelConfig(
        provider="openrouter",
        model="openai/gpt-4o-mini",
    )


def test_apply_overlay_noop_when_no_meeting_llm_entry() -> None:
    base = AgentConfig(
        id="cfo",
        name="Elena",
        role=AgentRole.CFO,
        expertise_domain="finance",
        personality_traits=["formal"],
    )
    meeting = MeetingState(
        meeting_id="m1",
        briefing=Briefing(text="x", objectives=["o"]),
        selected_agents=["cfo", "adversary"],
    )
    assert apply_meeting_overlays_to_config(base, meeting) is base


def test_registry_validate_used_by_selection_flow() -> None:
    reg = AgentRegistry()
    reg.validate_selection(["adversary", "cfo"])
