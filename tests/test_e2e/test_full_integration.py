from __future__ import annotations

from pathlib import Path

import pytest

from boardroom.custom_agents.builder import CustomAgentBuilder
from boardroom.custom_agents.storage import CustomAgentStorage
from boardroom.knowledge.models import KnowledgeItem, SourceType
from boardroom.knowledge.store import KnowledgeVectorStore
from boardroom.llm.backend import LLMBackendError
from boardroom.memory.agent_memory import AgentMemoryStore, MemoryItem
from boardroom.models import AgentConfig, AgentRole, AppConfig, BiasType, Briefing, Message, TerminationReason
from boardroom.orchestrator.meeting_orchestrator import MeetingOrchestrator
from boardroom.orchestrator.termination import TerminationDetector, TerminationDetectorConfig
from boardroom.registry import AgentRegistry
from boardroom.tools import ToolExecutor
from boardroom.vector_store import MeetingVectorStore


class FixedTurnSelector:
    def __init__(self, sequence: list[str]) -> None:
        self._sequence = sequence
        self._index = 0

    def next_speaker(self, meeting: object, agents_map: dict[str, AgentConfig]) -> str:
        _ = meeting
        _ = agents_map
        speaker = self._sequence[min(self._index, len(self._sequence) - 1)]
        self._index += 1
        return speaker


def _termination(*, max_turns: int) -> TerminationDetector:
    return TerminationDetector(
        TerminationDetectorConfig(
            min_turns=1,
            max_turns=max_turns,
            deadlock_jaccard_threshold=1.1,
        ),
        consensus_judge=lambda _messages: False,
    )


def test_full_meeting_with_tools_knowledge_memory_and_vector_store(
    app_config: AppConfig,
    briefing: Briefing,
    fake_llm_cls: type[object],
) -> None:
    knowledge_store = KnowledgeVectorStore(
        persist_dir=app_config.vector_store.persist_dir / "knowledge"
    )
    knowledge_store.store(
        "data_specialist",
        [
            KnowledgeItem(
                source_type=SourceType.WEB_SEARCH,
                url="https://example.com/pricing-risk",
                title="German market pricing risk",
                content="Pricing risk in Germany is highest when discounts exceed 20 percent.",
            )
        ],
    )
    memory_store = AgentMemoryStore(persist_dir=app_config.vector_store.persist_dir / "memory")
    memory_store.store_memories(
        "data_specialist",
        [
            MemoryItem(
                agent_id="data_specialist",
                meeting_id="prior-meeting",
                content="I previously argued that pricing risk needs a sensitivity model.",
            )
        ],
    )

    llm = fake_llm_cls(
        [
            (
                "Need a quick pricing model before we commit.\n"
                "```tool\n"
                '{"name":"python_exec","args":{"code":"print(3 * 7)"}}'
                "\n```"
            ),
            "The board should assume Germany is the first margin failure point.",
            "A phased rollout still works if pricing guardrails are explicit.",
        ]
    )
    tools = ToolExecutor()

    def tool_hook(*, meeting: object, message: Message, raw_content: str) -> None:
        _ = meeting
        tools.apply_to_message(
            message=message,
            raw_content=raw_content,
            agent_role=AgentRole.DATA_SPECIALIST,
        )

    orchestrator = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=app_config,
        llm=llm,
        turn_selector=FixedTurnSelector(["data_specialist", "adversary", "strategist"]),
        termination_detector=_termination(max_turns=3),
        tool_hook=tool_hook,
    )

    final = orchestrator.start_meeting(
        meeting_id="e2e-full",
        briefing=briefing,
        selected_agents=["adversary", "data_specialist", "strategist"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )

    assert final.termination_reason == TerminationReason.MAX_TURNS
    assert final.persisted_transcript is not None
    assert final.messages[0].agent_id == "data_specialist"
    assert final.messages[0].tool_calls
    assert final.messages[0].tool_results
    assert final.messages[0].tool_results[0]["ok"] is True
    first_prompt = llm.calls[0]["messages"][0]["content"]
    assert "## Domain Knowledge" in first_prompt
    assert "German market pricing risk" in first_prompt
    assert "## Past Meeting Memory" in first_prompt
    assert "sensitivity model" in first_prompt

    transcript_text = final.persisted_transcript.path.read_text(encoding="utf-8")
    assert "#### Tool execution" in transcript_text

    meeting_store = MeetingVectorStore(
        persist_dir=app_config.vector_store.persist_dir,
        collection_name=app_config.vector_store.collection_name,
    )
    results = meeting_store.search(query="pricing risk", limit=5)
    assert any(row["metadata"].get("meeting_id") == "e2e-full" for row in results)

    stored_memories = AgentMemoryStore(
        persist_dir=app_config.vector_store.persist_dir / "memory"
    ).retrieve("data_specialist", query="quick pricing model", limit=10)
    assert any(item.meeting_id == "e2e-full" for item in stored_memories)


def test_custom_agent_participates_in_meeting(
    app_config: AppConfig,
    briefing: Briefing,
    fake_llm_cls: type[object],
    tmp_path: Path,
) -> None:
    custom_dir = tmp_path / "custom_agents"
    builder = CustomAgentBuilder(storage=CustomAgentStorage(storage_dir=custom_dir))
    builder.create(
        AgentConfig(
            id="market_analyst",
            name="Market Analyst",
            role=AgentRole.CUSTOM,
            expertise_domain="market entry analysis",
            personality_traits=["skeptical", "commercial"],
            biases=[BiasType.COST_FOCUS],
            bias_intensity=0.5,
        )
    )

    orchestrator = MeetingOrchestrator(
        registry=AgentRegistry(custom_agents_dir=custom_dir),
        app_config=app_config,
        llm=fake_llm_cls(
            [
                "I see margin pressure before I see upside.",
                "The adversary is right to question the launch timing.",
            ]
        ),
        turn_selector=FixedTurnSelector(["market_analyst", "adversary"]),
        termination_detector=_termination(max_turns=2),
    )

    final = orchestrator.start_meeting(
        meeting_id="e2e-custom-agent",
        briefing=briefing,
        selected_agents=["adversary", "market_analyst"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )

    assert any(message.agent_id == "market_analyst" for message in final.messages)
    assert final.persisted_transcript is not None
    transcript_text = final.persisted_transcript.path.read_text(encoding="utf-8")
    assert "Market Analyst" in transcript_text


def test_meeting_recovery_on_llm_failure_mid_debate(
    app_config: AppConfig,
    briefing: Briefing,
    fake_llm_cls: type[object],
) -> None:
    orchestrator = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=app_config,
        llm=fake_llm_cls(
            [
                "The first objection is margin compression.",
                "The second objection is execution complexity.",
                LLMBackendError("synthetic provider failure"),
            ]
        ),
        turn_selector=FixedTurnSelector(["adversary", "strategist", "adversary"]),
        termination_detector=_termination(max_turns=4),
    )

    with pytest.raises(LLMBackendError, match="synthetic provider failure"):
        orchestrator.start_meeting(
            meeting_id="e2e-llm-failure",
            briefing=briefing,
            selected_agents=["adversary", "strategist"],
            env={"OPENROUTER_API_KEY": "test-key"},
        )

    assert not list(app_config.paths.outputs_dir.glob("*_transcript.md"))


def test_meeting_with_empty_knowledge_and_memory_degrades_gracefully(
    app_config: AppConfig,
    briefing: Briefing,
    fake_llm_cls: type[object],
) -> None:
    llm = fake_llm_cls(
        [
            "I want to pressure-test the launch assumptions.",
            "I want to preserve the option value with smaller bets.",
        ]
    )
    orchestrator = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=app_config,
        llm=llm,
        turn_selector=FixedTurnSelector(["adversary", "strategist"]),
        termination_detector=_termination(max_turns=2),
    )

    final = orchestrator.start_meeting(
        meeting_id="e2e-empty-context",
        briefing=briefing,
        selected_agents=["adversary", "strategist"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )

    assert final.termination_reason == TerminationReason.MAX_TURNS
    assert final.persisted_transcript is not None
    assert all("## Domain Knowledge" not in call["messages"][0]["content"] for call in llm.calls)
    assert all("## Past Meeting Memory" not in call["messages"][0]["content"] for call in llm.calls)


def test_consecutive_meetings_share_memory(
    app_config: AppConfig,
    fake_llm_cls: type[object],
) -> None:
    first_briefing = Briefing(
        text="Review the pricing strategy for the EU launch.",
        objectives=["Capture the strongest objections."],
    )
    second_briefing = Briefing(
        text="Revisit the pricing strategy for the EU launch.",
        objectives=["Use prior debate context."],
    )

    first_orchestrator = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=app_config,
        llm=fake_llm_cls(
            [
                "The pricing strategy is too aggressive for year one.",
                "We should stage the rollout over two quarters.",
            ]
        ),
        turn_selector=FixedTurnSelector(["adversary", "strategist"]),
        termination_detector=_termination(max_turns=2),
    )
    first_orchestrator.start_meeting(
        meeting_id="memory-seed",
        briefing=first_briefing,
        selected_agents=["adversary", "strategist"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )

    second_llm = fake_llm_cls(
        [
            "I still think the rollout is fragile without pricing guardrails.",
            "Then we should define narrower launch criteria.",
        ]
    )
    second_orchestrator = MeetingOrchestrator(
        registry=AgentRegistry(),
        app_config=app_config,
        llm=second_llm,
        turn_selector=FixedTurnSelector(["adversary", "strategist"]),
        termination_detector=_termination(max_turns=2),
    )
    second_orchestrator.start_meeting(
        meeting_id="memory-followup",
        briefing=second_briefing,
        selected_agents=["adversary", "strategist"],
        env={"OPENROUTER_API_KEY": "test-key"},
    )

    first_prompt = second_llm.calls[0]["messages"][0]["content"]
    assert "## Past Meeting Memory" in first_prompt
    assert "pricing strategy is too aggressive for year one" in first_prompt.lower()
