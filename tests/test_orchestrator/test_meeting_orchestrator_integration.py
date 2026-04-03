from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from boardroom.models import (
    AgentConfig,
    AppConfig,
    Briefing,
    MeetingLLMSelection,
    MeetingState,
    Message,
    ModelConfig,
    PathsConfig,
    ProviderConfig,
    TerminationReason,
)
from boardroom.orchestrator.meeting_orchestrator import MeetingOrchestrator, phase2_tool_hook_noop
from boardroom.orchestrator.termination import TerminationDetector, TerminationDetectorConfig
from boardroom.registry import AgentRegistry


def _app_config() -> AppConfig:
    return AppConfig(
        providers={
            "openrouter": ProviderConfig(
                api_key_env="OPENROUTER_API_KEY",
                base_url="https://openrouter.ai/api/v1",
            )
        },
        default_model=ModelConfig(model="test/model"),
    )


def _briefing() -> Briefing:
    return Briefing(
        text="Should we expand into the EU market this year?",
        objectives=["Stress-test the plan.", "Surface blockers."],
    )


class FakeLLM:
    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self._i = 0
        self.calls: list[AgentConfig] = []

    def generate_for_agent(
        self,
        *,
        agent: AgentConfig,
        config: AppConfig,
        messages: list[dict[str, str]],
        env: Mapping[str, str] | None = None,
    ) -> str:
        self.calls.append(agent)
        r = self._responses[self._i % len(self._responses)]
        self._i += 1
        return r


def test_meeting_runs_until_max_turns() -> None:
    det = TerminationDetector(
        TerminationDetectorConfig(
            min_turns=1, max_turns=3, deadlock_jaccard_threshold=0.99),
        consensus_judge=lambda _m: False,
    )
    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=_app_config(),
        llm=FakeLLM(["Still debating without agreement.",
                    "More disagreement.", "Still no."]),
        termination_detector=det,
    )
    final = orch.start_meeting(
        meeting_id="int-1",
        briefing=_briefing(),
        selected_agents=["adversary", "strategist"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert final.termination_reason == TerminationReason.MAX_TURNS
    assert len(final.messages) == 3
    assert final.turn_count == 3
    assert final.current_speaker is None
    assert {m.agent_id for m in final.messages} <= {"adversary", "strategist"}


def test_meeting_terminates_on_consensus_when_judge_fires() -> None:
    agreeing = (
        "I agree we should proceed with the phased rollout timeline discussed.",
        "Finance is aligned; I see consensus to move forward.",
        "Then we are settled; ship it with the guardrails we listed.",
    )

    def judge_last_three(msgs: Sequence[object]) -> bool:
        return len(msgs) == 3

    det = TerminationDetector(
        TerminationDetectorConfig(
            min_turns=1, max_turns=20, deadlock_jaccard_threshold=0.99),
        consensus_judge=judge_last_three,
    )
    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=_app_config(),
        llm=FakeLLM(agreeing),
        termination_detector=det,
    )
    final = orch.start_meeting(
        meeting_id="int-2",
        briefing=_briefing(),
        selected_agents=["adversary", "cfo"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert final.termination_reason == TerminationReason.CONSENSUS
    assert len(final.messages) == 3


def test_meeting_terminates_on_deadlock() -> None:
    det = TerminationDetector(
        TerminationDetectorConfig(
            min_turns=3, max_turns=10, deadlock_jaccard_threshold=0.8),
        consensus_judge=lambda _m: False,
    )
    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=_app_config(),
        llm=FakeLLM(
            [
                "We should not proceed with this plan.",
                "We should not proceed with this plan.",
                "We should not proceed with this plan.",
            ]
        ),
        termination_detector=det,
    )

    final = orch.start_meeting(
        meeting_id="int-deadlock",
        briefing=_briefing(),
        selected_agents=["adversary", "strategist"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )

    assert final.termination_reason == TerminationReason.DEADLOCK
    assert len(final.messages) == 3


def test_phase2_tool_hook_is_invoked_each_turn() -> None:
    det = TerminationDetector(
        TerminationDetectorConfig(
            min_turns=1, max_turns=2, deadlock_jaccard_threshold=0.99),
        consensus_judge=lambda _m: False,
    )
    hook_calls: list[tuple[Message, str, int]] = []

    def hook(*, meeting: MeetingState, message: Message, raw_content: str) -> None:
        assert meeting.messages[-1] is message
        assert message.content == raw_content
        hook_calls.append((message, raw_content, len(meeting.messages)))

    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=_app_config(),
        llm=FakeLLM(["a1", "a2"]),
        termination_detector=det,
        tool_hook=hook,
    )
    orch.start_meeting(
        meeting_id="int-3",
        briefing=_briefing(),
        selected_agents=["adversary", "tech_director"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert len(hook_calls) == 2
    assert {message.agent_id for message, _, _ in hook_calls} <= {
        "adversary", "tech_director"}
    assert [message_count for _, _, message_count in hook_calls] == [1, 2]


def test_phase2_tool_hook_supports_legacy_agent_id_signature() -> None:
    det = TerminationDetector(
        TerminationDetectorConfig(
            min_turns=1, max_turns=2, deadlock_jaccard_threshold=0.99),
        consensus_judge=lambda _m: False,
    )
    hook_calls: list[tuple[str, str]] = []

    def legacy_hook(*, meeting: MeetingState, agent_id: str, raw_content: str) -> None:
        assert meeting.messages[-1].agent_id == agent_id
        hook_calls.append((agent_id, raw_content))

    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=_app_config(),
        llm=FakeLLM(["a1", "a2"]),
        termination_detector=det,
        tool_hook=legacy_hook,
    )
    orch.start_meeting(
        meeting_id="int-legacy-hook",
        briefing=_briefing(),
        selected_agents=["adversary", "tech_director"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )

    assert len(hook_calls) == 2
    assert {agent_id for agent_id, _ in hook_calls} <= {
        "adversary", "tech_director"}


def test_default_tool_hook_is_safe_noop() -> None:
    message = Message(agent_id="adversary",
                      agent_name="Marcus Vale", content="hello")
    phase2_tool_hook_noop(
        meeting=MeetingState(
            meeting_id="x",
            briefing=_briefing(),
            selected_agents=["adversary", "strategist"],
            messages=[message],
        ),
        message=message,
        raw_content="hello",
    )


def test_meeting_can_reach_large_max_turn_limit_without_recursion_failure() -> None:
    det = TerminationDetector(
        TerminationDetectorConfig(
            min_turns=100, max_turns=20, deadlock_jaccard_threshold=1.1),
        consensus_judge=lambda _m: False,
    )
    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=_app_config(),
        llm=FakeLLM(["Still debating with fresh wording."]),
        termination_detector=det,
    )

    final = orch.start_meeting(
        meeting_id="int-4",
        briefing=_briefing(),
        selected_agents=["adversary", "strategist"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )

    assert final.termination_reason == TerminationReason.MAX_TURNS
    assert len(final.messages) == 20


def test_meeting_raises_clear_error_on_empty_model_output() -> None:
    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=_app_config(),
        llm=FakeLLM(["   "]),
    )

    with pytest.raises(RuntimeError, match="empty content"):
        orch.start_meeting(
            meeting_id="int-empty",
            briefing=_briefing(),
            selected_agents=["adversary", "strategist"],
            env={"OPENROUTER_API_KEY": "test-key"},
        )


def test_run_meeting_from_saved_state_matches_start_meeting(tmp_path: Path) -> None:
    det = TerminationDetector(
        TerminationDetectorConfig(
            min_turns=1, max_turns=2, deadlock_jaccard_threshold=0.99),
        consensus_judge=lambda _m: False,
    )
    app = _app_config().model_copy(
        update={"paths": PathsConfig(outputs_dir=tmp_path)})
    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=app,
        llm=FakeLLM(["First turn content.", "Second turn content."]),
        termination_detector=det,
    )
    saved = MeetingState(
        meeting_id="persist-int",
        briefing=_briefing(),
        selected_agents=["adversary", "strategist"],
        llm=MeetingLLMSelection(provider="openrouter", models_by_agent={}),
    )
    final = orch.run_meeting(
        meeting=saved, env={"OPENROUTER_API_KEY": "test-key"})
    assert final.termination_reason == TerminationReason.MAX_TURNS
    assert final.persisted_transcript is not None


def test_run_meeting_applies_model_override_from_meeting_state() -> None:
    custom = "anthropic/claude-test-override"
    meeting = MeetingState(
        meeting_id="ov1",
        briefing=_briefing(),
        selected_agents=["adversary", "cfo"],
        llm=MeetingLLMSelection(provider="openrouter",
                                models_by_agent={"cfo": custom}),
    )
    det = TerminationDetector(
        TerminationDetectorConfig(
            min_turns=1, max_turns=2, deadlock_jaccard_threshold=0.99),
        consensus_judge=lambda _m: False,
    )
    fake = FakeLLM(["from adversary", "from cfo"])
    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=_app_config(),
        llm=fake,
        termination_detector=det,
    )
    orch.run_meeting(meeting=meeting, env={"OPENROUTER_API_KEY": "test-key"})
    cfo_calls = [c for c in fake.calls if c.id == "cfo"]
    assert cfo_calls and cfo_calls[0].model_config_override is not None
    assert cfo_calls[0].model_config_override.model == custom


def test_before_agent_turn_runs_before_llm(tmp_path: Path) -> None:
    order: list[str] = []

    def before(aid: str) -> None:
        order.append(f"before:{aid}")

    det = TerminationDetector(
        TerminationDetectorConfig(
            min_turns=1, max_turns=1, deadlock_jaccard_threshold=0.99),
        consensus_judge=lambda _m: False,
    )

    def after_message(meeting: MeetingState, message: Message) -> None:
        _ = meeting
        order.append(f"after:{message.agent_id}")

    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=_app_config().model_copy(
            update={"paths": PathsConfig(outputs_dir=tmp_path)}),
        llm=FakeLLM(["only turn"]),
        termination_detector=det,
        before_agent_turn=before,
        after_agent_message=after_message,
    )
    orch.start_meeting(
        meeting_id="hook-order",
        briefing=_briefing(),
        selected_agents=["adversary", "strategist"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert len(order) == 2
    assert order[0].startswith("before:")
    assert order[1].startswith("after:")
    assert order[0].split(":", 1)[1] == order[1].split(":", 1)[1]


def test_meeting_completion_persists_transcript_artifacts(tmp_path: Path) -> None:
    det = TerminationDetector(
        TerminationDetectorConfig(
            min_turns=1, max_turns=2, deadlock_jaccard_threshold=0.99),
        consensus_judge=lambda _m: False,
    )
    app = _app_config().model_copy(
        update={"paths": PathsConfig(outputs_dir=tmp_path)})
    orch = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=app,
        llm=FakeLLM(["First turn content.", "Second turn content."]),
        termination_detector=det,
    )
    final = orch.start_meeting(
        meeting_id="persist-int",
        briefing=_briefing(),
        selected_agents=["adversary", "strategist"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert final.persisted_transcript is not None
    tr = final.persisted_transcript
    assert tr.meeting_id == "persist-int"
    assert tr.message_count == 2
    assert tr.path.parent == tmp_path
    assert tr.path.exists()
    assert tr.kill_sheet_path is not None
    assert tr.kill_sheet_path.exists()
    assert tr.consensus_roadmap_path is not None
    assert tr.consensus_roadmap_path.exists()
    main = tr.path.read_text(encoding="utf-8")
    assert "## Transcript" in main
    assert "## Kill Sheet" in main
    assert "## Consensus Roadmap" in main
