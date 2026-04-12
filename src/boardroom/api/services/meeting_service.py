from __future__ import annotations

import asyncio
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from boardroom.api.errors import MeetingCancelledError
from boardroom.api.schemas import MeetingStartPayload
from boardroom.llm.backend import LLMBackendError
from boardroom.llm.router import LLMRouter
from boardroom.models import (
    AppConfig,
    Briefing,
    MeetingLLMSelection,
    MeetingState,
    Message,
)
from boardroom.orchestrator.meeting_orchestrator import MeetingOrchestrator
from boardroom.orchestrator.termination import (
    TerminationDetector,
    TerminationDetectorConfig,
)
from boardroom.registry import AgentRegistry
from boardroom.tools import ToolExecutor, WebSearchTool
from boardroom.tools.registry import PYTHON_EXEC_TOOL, WEB_SEARCH_TOOL
from boardroom.transcript import TranscriptManager


def _termination_for_max_turns(max_turns: int | None) -> TerminationDetector:
    base = TerminationDetectorConfig()
    if max_turns is None:
        return TerminationDetector()
    min_turns = base.min_turns if max_turns >= base.min_turns else 1
    return TerminationDetector(
        TerminationDetectorConfig(
            min_turns=min_turns,
            max_turns=max_turns,
            deadlock_jaccard_threshold=base.deadlock_jaccard_threshold,
        )
    )


@dataclass
class MeetingSession:
    meeting_id: str
    selected_agents: list[str]
    loop: asyncio.AbstractEventLoop
    event_queue: asyncio.Queue[dict[str, Any]]
    cancel_event: threading.Event
    started_at: datetime
    status: str = "running"
    last_state: MeetingState | None = None
    task: asyncio.Task[None] | None = None
    disconnected_at: datetime | None = None
    reaper_task: asyncio.Task[None] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MeetingService:
    _REAPER_TIMEOUT_SECONDS = 30
    _POST_CANCEL_WAIT_SECONDS = 8

    def __init__(self, *, max_workers: int = 3) -> None:
        self._sessions: dict[str, MeetingSession] = {}
        self._semaphore = asyncio.Semaphore(max_workers)

    async def start_meeting(
        self,
        *,
        payload: MeetingStartPayload,
        config: AppConfig,
    ) -> MeetingSession:
        meeting_id = payload.meeting_id or str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        session = MeetingSession(
            meeting_id=meeting_id,
            selected_agents=list(payload.agents),
            loop=loop,
            event_queue=asyncio.Queue(),
            cancel_event=threading.Event(),
            started_at=datetime.now(timezone.utc),
        )
        self._sessions[meeting_id] = session
        await self._emit(session, {"type": "meeting_started", "meeting_id": meeting_id})
        session.task = asyncio.create_task(self._run_in_background(session, payload, config))
        return session

    async def _run_in_background(
        self,
        session: MeetingSession,
        payload: MeetingStartPayload,
        config: AppConfig,
    ) -> None:
        async with self._semaphore:
            try:
                await asyncio.to_thread(self._run_sync_meeting, session, payload, config)
            finally:
                if session.disconnected_at is not None:
                    self._sessions.pop(session.meeting_id, None)

    async def cancel_meeting(self, meeting_id: str) -> bool:
        session = self._sessions.get(meeting_id)
        if session is None:
            return False
        session.cancel_event.set()
        return True

    def get(self, meeting_id: str) -> MeetingSession | None:
        return self._sessions.get(meeting_id)

    def list_sessions(self) -> list[MeetingSession]:
        return list(self._sessions.values())

    def forget_meeting(self, meeting_id: str) -> None:
        self._sessions.pop(meeting_id, None)

    def mark_disconnected(self, meeting_id: str) -> None:
        session = self._sessions.get(meeting_id)
        if session is None:
            return
        session.disconnected_at = datetime.now(timezone.utc)
        if session.reaper_task is None or session.reaper_task.done():
            session.reaper_task = asyncio.create_task(self._reap_if_orphaned(meeting_id))

    async def _reap_if_orphaned(self, meeting_id: str) -> None:
        await asyncio.sleep(self._REAPER_TIMEOUT_SECONDS)
        session = self._sessions.get(meeting_id)
        if session is None or session.disconnected_at is None:
            return
        session.cancel_event.set()
        if session.task is not None:
            try:
                await asyncio.wait_for(session.task, timeout=self._POST_CANCEL_WAIT_SECONDS)
            except asyncio.TimeoutError:
                pass
        self._sessions.pop(meeting_id, None)

    def _run_sync_meeting(
        self,
        session: MeetingSession,
        payload: MeetingStartPayload,
        config: AppConfig,
    ) -> None:
        reg = AgentRegistry()
        reg.validate_selection(payload.agents)
        disabled_tools = {PYTHON_EXEC_TOOL.name}
        if not payload.enable_web_search:
            disabled_tools.add(WEB_SEARCH_TOOL.name)
        tools = ToolExecutor(
            web_search_tool=WebSearchTool(config=config.web_search, env=os.environ),
            disabled_tools=disabled_tools,
        )
        router = LLMRouter()
        termination = _termination_for_max_turns(payload.max_turns)

        def before_turn(agent_id: str) -> None:
            if session.cancel_event.is_set():
                raise MeetingCancelledError("Meeting cancelled by user.")
            cfg = reg.get_config(agent_id)
            turn_number = (session.last_state.turn_count if session.last_state else 0) + 1
            self._emit_threadsafe(
                session,
                {
                    "type": "turn_start",
                    "meeting_id": session.meeting_id,
                    "agent_id": cfg.id,
                    "agent_name": cfg.name,
                    "role": cfg.role.value,
                    "turn_number": turn_number,
                },
            )

        def after_message(meeting: MeetingState, message: Message) -> None:
            session.last_state = meeting
            self._emit_threadsafe(
                session,
                {
                    "type": "turn_complete",
                    "meeting_id": meeting.meeting_id,
                    "agent_id": message.agent_id,
                    "agent_name": message.agent_name,
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat(),
                    "tool_results": message.tool_results,
                },
            )

        def tool_hook(*, meeting: MeetingState, message: Message, raw_content: str) -> None:
            _ = meeting
            tools.apply_to_message(message=message, raw_content=raw_content)

        orch = MeetingOrchestrator(
            registry=reg,
            app_config=config,
            llm=router,
            termination_detector=termination,
            tool_hook=tool_hook,
            before_agent_turn=before_turn,
            after_agent_message=after_message,
        )

        state = MeetingState(
            meeting_id=session.meeting_id,
            briefing=Briefing(
                text=payload.briefing.text,
                objectives=payload.briefing.objectives,
            ),
            selected_agents=list(payload.agents),
            llm=MeetingLLMSelection(
                provider="openrouter",
                models_by_agent=payload.models_by_agent,
            ),
            bias_intensity_by_agent=payload.bias_intensity_by_agent,
        )

        try:
            final = orch.run_meeting(meeting=state, env=os.environ)
            session.status = "completed"
            self._emit_threadsafe(
                session,
                {
                    "type": "meeting_complete",
                    "meeting_id": final.meeting_id,
                    "termination_reason": (
                        final.termination_reason.value
                        if final.termination_reason is not None
                        else None
                    ),
                    "outputs": {
                        "transcript": (
                            str(final.persisted_transcript.path)
                            if final.persisted_transcript is not None
                            else None
                        ),
                        "kill_sheet": (
                            str(final.persisted_transcript.kill_sheet_path)
                            if final.persisted_transcript is not None
                            and final.persisted_transcript.kill_sheet_path is not None
                            else None
                        ),
                        "consensus_roadmap": (
                            str(final.persisted_transcript.consensus_roadmap_path)
                            if final.persisted_transcript is not None
                            and final.persisted_transcript.consensus_roadmap_path is not None
                            else None
                        ),
                    },
                },
            )
        except MeetingCancelledError:
            session.status = "cancelled"
            partial = self._persist_partial(session, config, reg)
            self._emit_threadsafe(
                session,
                {
                    "type": "meeting_cancelled",
                    "meeting_id": session.meeting_id,
                    "outputs": partial,
                },
            )
        except (KeyError, LLMBackendError) as exc:
            session.status = "error"
            self._emit_threadsafe(
                session,
                {
                    "type": "error",
                    "code": "missing_api_key",
                    "message": str(exc),
                    "fatal": True,
                },
            )
        except Exception as exc:
            session.status = "error"
            self._emit_threadsafe(
                session,
                {
                    "type": "error",
                    "code": "orchestrator_crash",
                    "message": str(exc),
                    "fatal": True,
                },
            )

    def _persist_partial(
        self,
        session: MeetingSession,
        config: AppConfig,
        registry: AgentRegistry,
    ) -> dict[str, str | None]:
        state = session.last_state
        if state is None or not state.messages:
            return {"transcript": None, "kill_sheet": None, "consensus_roadmap": None}
        agents_by_id = {
            agent_id: registry.get_config(agent_id) for agent_id in state.selected_agents
        }
        transcript = TranscriptManager(outputs_dir=config.paths.outputs_dir).persist(
            state,
            agents_by_id,
        )
        return {
            "transcript": str(transcript.path),
            "kill_sheet": str(transcript.kill_sheet_path) if transcript.kill_sheet_path else None,
            "consensus_roadmap": (
                str(transcript.consensus_roadmap_path)
                if transcript.consensus_roadmap_path
                else None
            ),
        }

    async def _emit(self, session: MeetingSession, event: dict[str, Any]) -> None:
        await session.event_queue.put(event)

    def _emit_threadsafe(self, session: MeetingSession, event: dict[str, Any]) -> None:
        session.loop.call_soon_threadsafe(session.event_queue.put_nowait, event)
