from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from boardroom.models import (
    AgentConfig,
    AgentRole,
    AppConfig,
    BiasType,
    Briefing,
    MeetingState,
    Message,
    ModelConfig,
    ProviderConfig,
    WebSearchConfig,
)


def make_briefing() -> Briefing:
    return Briefing(text="Test the idea.", objectives=["Find weak points."])


def test_agent_config_requires_personality_traits() -> None:
    with pytest.raises(ValidationError):
        AgentConfig(
            id="adversary",
            name="Marcus",
            role=AgentRole.ADVERSARY,
            expertise_domain="strategy",
            personality_traits=[],
        )


def test_agent_config_accepts_model_override() -> None:
    agent = AgentConfig(
        id="strategist",
        name="James",
        role=AgentRole.STRATEGIST,
        expertise_domain="operations",
        personality_traits=["decisive"],
        biases=[BiasType.OPTIMISM_BIAS],
        model_config_override=ModelConfig(model="openai/gpt-4o"),
    )

    assert agent.model_config_override is not None
    assert agent.model_config_override.model == "openai/gpt-4o"


def test_agent_config_rejects_unsafe_id_characters() -> None:
    with pytest.raises(ValidationError, match="letters, numbers, underscores, or hyphens"):
        AgentConfig(
            id="../escape",
            name="Unsafe",
            role=AgentRole.CUSTOM,
            expertise_domain="security",
            personality_traits=["careful"],
        )


def test_briefing_rejects_alpha_content_without_files() -> None:
    with pytest.raises(ValidationError):
        Briefing(
            text="Review this plan.",
            objectives=["Break it."],
            alpha_content={"plan.md": "content"},
        )


def test_meeting_state_allows_empty_selected_agents_for_briefing_phase() -> None:
    state = MeetingState(
        meeting_id="m1", briefing=make_briefing(), selected_agents=[])
    assert state.selected_agents == []


def test_meeting_state_rejects_single_selected_agent() -> None:
    with pytest.raises(ValidationError):
        MeetingState(meeting_id="m1", briefing=make_briefing(),
                     selected_agents=["only-one"])


def test_meeting_state_rejects_more_than_six_agents() -> None:
    with pytest.raises(ValidationError):
        MeetingState(
            meeting_id="m1",
            briefing=make_briefing(),
            selected_agents=[f"a{i}" for i in range(7)],
        )


def test_message_serializes_timestamp() -> None:
    message = Message(agent_id="a1", agent_name="Marcus",
                      content="This breaks fast.")
    payload = message.model_dump(mode="json")

    assert payload["agent_id"] == "a1"
    assert isinstance(payload["timestamp"], str)


def test_app_config_returns_agent_specific_model() -> None:
    config = AppConfig(
        providers={
            "openrouter": ProviderConfig(
                api_key_env="OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1",
            )
        },
        default_model=ModelConfig(model="anthropic/claude-sonnet-4"),
        agent_models={"cfo": ModelConfig(model="openai/gpt-4o-mini")},
    )

    assert config.model_for_agent("cfo").model == "openai/gpt-4o-mini"
    assert config.model_for_agent(
        "adversary").model == "anthropic/claude-sonnet-4"


def test_provider_config_requires_uppercase_env_name() -> None:
    with pytest.raises(ValidationError):
        ProviderConfig(api_key_env="openrouter_api_key",
                       base_url="https://example.com")


def test_transcript_paths_can_round_trip_in_models() -> None:
    config = AppConfig(
        providers={
            "openrouter": ProviderConfig(
                api_key_env="OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1",
            )
        }
    )

    assert config.paths.outputs_dir == Path("transcripts")


def test_web_search_config_rejects_non_tavily_urls_by_default() -> None:
    with pytest.raises(ValidationError, match="https://api.tavily.com/"):
        WebSearchConfig(provider="tavily",
                        tavily_api_url="https://example.com/search")


def test_web_search_config_allows_custom_tavily_url_with_escape_hatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOARDROOM_ALLOW_CUSTOM_TAVILY_URL", "1")
    config = WebSearchConfig(
        provider="tavily", tavily_api_url="https://proxy.local/search")
    assert config.tavily_api_url == "https://proxy.local/search"
