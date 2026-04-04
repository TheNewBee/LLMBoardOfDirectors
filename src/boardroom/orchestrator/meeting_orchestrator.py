from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Literal, Protocol, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from boardroom.models import AgentConfig, AppConfig, Briefing, MeetingState, Message
from boardroom.orchestrator.termination import TerminationDetector
from boardroom.transcript import TranscriptManager
from boardroom.orchestrator.turn_selector import TurnSelector
from boardroom.registry import AgentRegistry
from boardroom.vector_store import MeetingVectorStore

_LOG = logging.getLogger(__name__)


class MeetingLLM(Protocol):
    def generate_for_agent(
        self,
        *,
        agent: AgentConfig,
        config: AppConfig,
        messages: list[dict[str, str]],
        env: Mapping[str, str] | None = None,
    ) -> str: ...


class Phase2ToolHook(Protocol):
    def __call__(
        self,
        *,
        meeting: MeetingState,
        message: Message | None = None,
        agent_id: str | None = None,
        raw_content: str,
    ) -> None: ...


def phase2_tool_hook_noop(
    *,
    meeting: MeetingState,
    message: Message | None = None,
    agent_id: str | None = None,
    raw_content: str,
) -> None:
    """Placeholder seam for Phase 2 tool execution; intentionally empty."""
    return None


class MeetingGraphState(TypedDict):
    meeting: MeetingState
    agent_configs_by_id: dict[str, AgentConfig]
    system_prompts_by_agent_id: dict[str, str]
    transcript_text: str
    env: Mapping[str, str] | None


EMPTY_TRANSCRIPT_TEXT = "(no prior turns yet)"


def _chat_messages_for_turn(
    *,
    system_prompt: str,
    transcript_text: str,
) -> list[dict[str, str]]:
    user = (
        "You are the current speaker. Respond in character.\n\n"
        f"Prior turns:\n{transcript_text}\n\n"
        "Provide your contribution to the discussion."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user},
    ]


def _append_transcript_line(transcript_text: str, message: Message) -> str:
    line = f"{message.agent_name} ({message.agent_id}): {message.content}"
    if transcript_text == EMPTY_TRANSCRIPT_TEXT:
        return line
    return f"{transcript_text}\n{line}"


class MeetingOrchestrator:
    _FIXED_GRAPH_STEPS = 2
    _LOOP_STEPS_PER_TURN = 3
    _RECURSION_SLACK = 6
    _TOOL_HOOK_WITH_MESSAGE: Literal["message"] = "message"
    _TOOL_HOOK_WITH_AGENT_ID: Literal["agent_id"] = "agent_id"
    _TOOL_HOOK_MINIMAL: Literal["minimal"] = "minimal"

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        app_config: AppConfig,
        llm: MeetingLLM,
        turn_selector: TurnSelector | None = None,
        termination_detector: TerminationDetector | None = None,
        tool_hook: Phase2ToolHook | None = None,
        before_agent_turn: Callable[[str], None] | None = None,
        after_agent_message: Callable[[
            MeetingState, Message], None] | None = None,
    ) -> None:
        self._registry = registry
        self._app_config = app_config
        self._llm = llm
        self._turn_selector = turn_selector or TurnSelector()
        self._termination = termination_detector or TerminationDetector()
        self._tool_hook: Phase2ToolHook = tool_hook or phase2_tool_hook_noop
        self._tool_hook_mode = self._detect_tool_hook_mode(self._tool_hook)
        self._before_agent_turn = before_agent_turn
        self._after_agent_message = after_agent_message
        self._graph: CompiledStateGraph = self._build_graph()

    def start_meeting(
        self,
        *,
        meeting_id: str,
        briefing: Briefing,
        selected_agents: Sequence[str],
        env: Mapping[str, str] | None = None,
    ) -> MeetingState:
        meeting = MeetingState(
            meeting_id=meeting_id,
            briefing=briefing,
            selected_agents=list(selected_agents),
        )
        return self.run_meeting(meeting=meeting, env=env)

    def run_meeting(
        self,
        *,
        meeting: MeetingState,
        env: Mapping[str, str] | None = None,
    ) -> MeetingState:
        """Execute the LangGraph loop for an existing MeetingState (preserves llm overlays, etc.)."""
        _LOG.info(
            "Running meeting orchestration meeting_id=%s selected_agents=%d",
            meeting.meeting_id,
            len(meeting.selected_agents),
        )
        self._registry.validate_selection(meeting.selected_agents)
        out = cast(
            MeetingGraphState,
            self._graph.invoke(
                {
                    "meeting": meeting,
                    "agent_configs_by_id": {},
                    "system_prompts_by_agent_id": {},
                    "transcript_text": EMPTY_TRANSCRIPT_TEXT,
                    "env": env,
                },
                {"recursion_limit": self._graph_recursion_limit()},
            ),
        )
        final_meeting = out["meeting"]
        agents_by_id = out["agent_configs_by_id"]
        transcript = TranscriptManager(outputs_dir=self._app_config.paths.outputs_dir).persist(
            final_meeting, agents_by_id
        )
        if self._app_config.vector_store.enabled:
            try:
                transcript_body = transcript.path.read_text(encoding="utf-8")
                store = MeetingVectorStore(
                    persist_dir=self._app_config.vector_store.persist_dir,
                    collection_name=self._app_config.vector_store.collection_name,
                )
                store.upsert_meeting(meeting=final_meeting,
                                     transcript_markdown=transcript_body)
            except Exception:
                _LOG.exception(
                    "Vector store upsert failed meeting_id=%s",
                    final_meeting.meeting_id,
                )
        _LOG.info(
            "Meeting orchestration completed meeting_id=%s turns=%d termination=%s",
            final_meeting.meeting_id,
            final_meeting.turn_count,
            final_meeting.termination_reason.value
            if final_meeting.termination_reason is not None
            else "n/a",
        )
        return final_meeting.model_copy(update={"persisted_transcript": transcript})

    def _graph_recursion_limit(self) -> int:
        # Graph topology is initialize + (select -> turn -> check) repeated per turn + finalize.
        return (
            self._FIXED_GRAPH_STEPS
            + (self._termination.max_turns * self._LOOP_STEPS_PER_TURN)
            + self._RECURSION_SLACK
        )

    def _build_graph(self) -> CompiledStateGraph:
        graph = StateGraph(MeetingGraphState)

        def initialize(state: MeetingGraphState) -> dict[str, object]:
            meeting = state["meeting"]
            initialized = self._registry.initialize_selected(
                meeting.selected_agents,
                meeting.briefing,
                meeting=meeting,
                validate=False,
            )
            agent_configs = {row.agent_id: row.config for row in initialized}
            prompts = {row.agent_id: row.system_prompt for row in initialized}
            text = meeting.briefing.text.strip()
            topics = [text] if text else []
            next_meeting = meeting.model_copy(update={"debate_topics": topics})
            return {
                "meeting": next_meeting,
                "agent_configs_by_id": agent_configs,
                "system_prompts_by_agent_id": prompts,
            }

        def select_agent(state: MeetingGraphState) -> dict[str, object]:
            meeting = state["meeting"]
            agents_map = state["agent_configs_by_id"]
            next_id = self._turn_selector.next_speaker(meeting, agents_map)
            return {"meeting": meeting.with_current_speaker(next_id)}

        def agent_turn(state: MeetingGraphState) -> dict[str, object]:
            meeting = state["meeting"]
            agent_id = meeting.current_speaker
            if agent_id is None:
                raise RuntimeError(
                    "current_speaker must be set before agent_turn.")
            cfg = state["agent_configs_by_id"][agent_id]
            system = state["system_prompts_by_agent_id"][agent_id]
            payload = _chat_messages_for_turn(
                system_prompt=system,
                transcript_text=state["transcript_text"],
            )
            if self._before_agent_turn is not None:
                self._before_agent_turn(agent_id)
            raw = self._llm.generate_for_agent(
                agent=cfg,
                config=self._app_config,
                messages=payload,
                env=state["env"],
            )
            content = raw.strip()
            if not content:
                _LOG.error(
                    "LLM returned empty content meeting_id=%s agent_id=%s",
                    meeting.meeting_id,
                    agent_id,
                )
                raise RuntimeError(
                    f"LLM returned empty content for agent '{agent_id}'.")
            message = Message(agent_id=agent_id,
                              agent_name=cfg.name, content=content)
            next_meeting = meeting.with_appended_message(message)
            self._invoke_tool_hook(meeting=next_meeting,
                                   message=message, raw_content=content)
            next_transcript = _append_transcript_line(
                state["transcript_text"], message)
            if self._after_agent_message is not None:
                self._after_agent_message(next_meeting, message)
            return {
                "meeting": next_meeting,
                "transcript_text": next_transcript,
            }

        def check_termination(state: MeetingGraphState) -> dict[str, object]:
            meeting = state["meeting"]
            outcome = self._termination.evaluate(meeting)
            if outcome.terminate and outcome.reason is not None:
                return {"meeting": meeting.with_termination(outcome.reason)}
            return {}

        def finalize(state: MeetingGraphState) -> dict[str, object]:
            return {"meeting": state["meeting"].with_current_speaker(None)}

        graph.add_node("initialize", initialize)
        graph.add_node("select_agent", select_agent)
        graph.add_node("agent_turn", agent_turn)
        graph.add_node("check_termination", check_termination)
        graph.add_node("finalize", finalize)

        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "select_agent")
        graph.add_edge("select_agent", "agent_turn")
        graph.add_edge("agent_turn", "check_termination")

        def route_after_check(state: MeetingGraphState) -> str:
            if state["meeting"].termination_reason is not None:
                return "finalize"
            return "loop"

        graph.add_conditional_edges(
            "check_termination",
            route_after_check,
            {"finalize": "finalize", "loop": "select_agent"},
        )
        graph.add_edge("finalize", END)

        return graph.compile()

    def _invoke_tool_hook(
        self, *, meeting: MeetingState, message: Message, raw_content: str
    ) -> None:
        try:
            if self._tool_hook_mode == self._TOOL_HOOK_WITH_MESSAGE:
                self._tool_hook(meeting=meeting, message=message,
                                raw_content=raw_content)
                return
            if self._tool_hook_mode == self._TOOL_HOOK_WITH_AGENT_ID:
                self._tool_hook(
                    meeting=meeting,
                    agent_id=message.agent_id,
                    raw_content=raw_content,
                )
                return
            self._tool_hook(meeting=meeting, raw_content=raw_content)
        except Exception:
            _LOG.exception(
                "Tool hook failed meeting_id=%s agent_id=%s",
                meeting.meeting_id,
                message.agent_id,
            )
            raise

    @classmethod
    def _detect_tool_hook_mode(
        cls, tool_hook: Phase2ToolHook
    ) -> Literal["message", "agent_id", "minimal"]:
        supported_parameters = inspect.signature(tool_hook).parameters
        if "message" in supported_parameters:
            return cls._TOOL_HOOK_WITH_MESSAGE
        if "agent_id" in supported_parameters:
            return cls._TOOL_HOOK_WITH_AGENT_ID
        return cls._TOOL_HOOK_MINIMAL
