from __future__ import annotations

import pytest

from boardroom.models import AgentRole, Briefing, MeetingState
from boardroom.registry import AgentRegistry, AgentSelectionError


def make_briefing() -> Briefing:
    return Briefing(
        text="Evaluate entering the EU market next quarter.",
        objectives=["Identify regulatory and GTM risks."],
    )


def test_registry_lists_default_agents() -> None:
    reg = AgentRegistry()
    ids = reg.list_agent_ids()
    assert "adversary" in ids
    assert "cfo" in ids
    assert len(ids) >= 5


def test_registry_retrieves_agent_config() -> None:
    reg = AgentRegistry()
    cfg = reg.get_config("adversary")
    assert cfg.role == AgentRole.ADVERSARY


def test_registry_get_config_uses_domain_error_for_unknown_agent() -> None:
    reg = AgentRegistry()
    with pytest.raises(AgentSelectionError):
        reg.get_config("missing")


def test_selection_rejects_too_few_agents() -> None:
    reg = AgentRegistry()
    with pytest.raises(AgentSelectionError):
        reg.validate_selection(["adversary"])


def test_selection_rejects_too_many_agents() -> None:
    reg = AgentRegistry()
    ids = [f"agent_{i}" for i in range(7)]
    with pytest.raises(AgentSelectionError):
        reg.validate_selection(ids)


def test_selection_requires_at_least_one_adversary() -> None:
    reg = AgentRegistry()
    with pytest.raises(AgentSelectionError):
        reg.validate_selection(["strategist", "cfo", "tech_director"])


def test_selection_rejects_unknown_id() -> None:
    reg = AgentRegistry()
    with pytest.raises(AgentSelectionError):
        reg.validate_selection(["adversary", "unknown_agent"])


def test_selection_rejects_duplicate_ids() -> None:
    reg = AgentRegistry()
    with pytest.raises(AgentSelectionError):
        reg.validate_selection(["adversary", "adversary"])


def test_initialize_with_briefing_returns_prompts_and_configs() -> None:
    reg = AgentRegistry()
    briefing = make_briefing()
    agents = reg.initialize_selected(["adversary", "cfo"], briefing)
    assert len(agents) == 2
    assert agents[0].agent_id != agents[1].agent_id
    for a in agents:
        assert a.config.name
        assert "Evaluate entering" in a.system_prompt or "EU" in a.system_prompt
        assert a.system_prompt


def test_initialize_applies_meeting_bias_overlay() -> None:
    reg = AgentRegistry()
    briefing = make_briefing()
    meeting = MeetingState(
        meeting_id="m",
        briefing=briefing,
        selected_agents=["adversary", "cfo"],
        bias_intensity_by_agent={"cfo": 0.11},
    )
    agents = reg.initialize_selected(["adversary", "cfo"], briefing, meeting=meeting)
    by_id = {a.agent_id: a for a in agents}
    assert by_id["cfo"].config.bias_intensity == 0.11
    assert by_id["adversary"].config.bias_intensity != 0.11
