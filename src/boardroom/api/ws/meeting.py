from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from boardroom.api.dependencies import get_app_config, get_meeting_service
from boardroom.api.schemas import MeetingStartPayload
from boardroom.api.services.meeting_service import MeetingService
from boardroom.models import AppConfig

router = APIRouter(tags=["ws"])

_TERMINAL_EVENTS = {"meeting_complete", "meeting_cancelled", "error"}


def _payload_from_message(message: dict[str, Any]) -> MeetingStartPayload:
    if message.get("type") == "start_meeting":
        raw = dict(message)
        raw.pop("type", None)
        return MeetingStartPayload.model_validate(raw)
    return MeetingStartPayload.model_validate(message)


@router.websocket("/ws/meeting")
async def ws_meeting(
    websocket: WebSocket,
    meeting_service: MeetingService = Depends(get_meeting_service),
    app_config: AppConfig = Depends(get_app_config),
) -> None:
    await websocket.accept()
    session = None
    try:
        first_message = await websocket.receive_json()
        payload = _payload_from_message(first_message)
        session = await meeting_service.start_meeting(payload=payload, config=app_config)

        async def drain_events() -> None:
            while True:
                event = await session.event_queue.get()
                await websocket.send_json(event)
                if event.get("type") in _TERMINAL_EVENTS:
                    break

        async def listen_for_cancel() -> None:
            while True:
                incoming = await websocket.receive_json()
                if incoming.get("type") == "cancel":
                    await meeting_service.cancel_meeting(session.meeting_id)
                    return

        cancel_task = asyncio.create_task(listen_for_cancel())
        try:
            await drain_events()
        finally:
            cancel_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cancel_task
    except ValidationError as exc:
        await websocket.send_json(
            {
                "type": "error",
                "code": "invalid_config",
                "message": str(exc),
                "fatal": True,
            }
        )
    except WebSocketDisconnect:
        if session is not None:
            meeting_service.mark_disconnected(session.meeting_id)
    finally:
        if session is not None and session.status in {"completed", "cancelled", "error"}:
            meeting_service.forget_meeting(session.meeting_id)
        with contextlib.suppress(Exception):
            await websocket.close()
