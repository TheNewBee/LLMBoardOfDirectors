from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from boardroom.api.dependencies import get_meeting_service
from boardroom.api.schemas import (
    ActiveMeetingResponse,
    MeetingPreviewResponse,
    MeetingStartPayload,
    MeetingsResponse,
)
from boardroom.api.services.meeting_service import MeetingService
from boardroom.registry import AgentRegistry, AgentSelectionError

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.post("", response_model=MeetingPreviewResponse)
def create_meeting_preview(payload: MeetingStartPayload) -> MeetingPreviewResponse:
    reg = AgentRegistry()
    try:
        reg.validate_selection(payload.agents)
    except AgentSelectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    models_keys = set(payload.models_by_agent)
    unknown = sorted(models_keys - set(payload.agents))
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"models_by_agent keys must be selected agents; unknown: {unknown}",
        )
    meeting_id = payload.meeting_id or str(uuid.uuid4())
    return MeetingPreviewResponse(
        meeting_id=meeting_id,
        agents=payload.agents,
        can_start=True,
    )


@router.get("", response_model=MeetingsResponse)
def list_meetings(
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> MeetingsResponse:
    rows = []
    for session in meeting_service.list_sessions():
        turn_count = session.last_state.turn_count if session.last_state is not None else 0
        current = session.last_state.current_speaker if session.last_state is not None else None
        rows.append(
            ActiveMeetingResponse(
                meeting_id=session.meeting_id,
                status=session.status,
                turn_count=turn_count,
                current_speaker=current,
                started_at=session.started_at,
                selected_agents=session.selected_agents,
            )
        )
    return MeetingsResponse(meetings=rows)


@router.get("/{meeting_id}", response_model=ActiveMeetingResponse)
def get_meeting(
    meeting_id: str,
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> ActiveMeetingResponse:
    session = meeting_service.get(meeting_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    turn_count = session.last_state.turn_count if session.last_state is not None else 0
    current = session.last_state.current_speaker if session.last_state is not None else None
    return ActiveMeetingResponse(
        meeting_id=session.meeting_id,
        status=session.status,
        turn_count=turn_count,
        current_speaker=current,
        started_at=session.started_at,
        selected_agents=session.selected_agents,
    )
