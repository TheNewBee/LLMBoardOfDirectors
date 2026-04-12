from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from boardroom.api.dependencies import get_app_config, get_config_service, get_meeting_service
from boardroom.api.main import _resolve_frontend_dist, create_app
from boardroom.api.services.config_service import ConfigService
from boardroom.models import AppConfig


def _write_config(tmp_path: Path, *, vector_enabled: bool) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "\n".join(
            [
                "providers:",
                "  openrouter:",
                "    api_key_env: OPENROUTER_API_KEY",
                "    base_url: https://openrouter.ai/api/v1",
                "default_model:",
                "  provider: openrouter",
                "  model: openai/gpt-4o-mini",
                "vector_store:",
                f"  enabled: {'true' if vector_enabled else 'false'}",
                f"  persist_dir: {tmp_path / 'vec'}",
                "  collection_name: boardroom_meetings",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def _client_with_config(
    config_path: Path,
    *,
    meeting_service: Any | None = None,
    config_service: ConfigService | None = None,
) -> TestClient:
    app = create_app()
    service = config_service or ConfigService(explicit_path=config_path)
    app.dependency_overrides[get_config_service] = lambda: service
    app.dependency_overrides[get_app_config] = lambda: service.load()
    if meeting_service is not None:
        app.dependency_overrides[get_meeting_service] = lambda: meeting_service
    return TestClient(app)


def test_history_search_returns_empty_when_vector_store_disabled(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, vector_enabled=False)
    client = _client_with_config(cfg)
    resp = client.get("/api/history/search", params={"query": "pricing risk"})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


def test_meeting_preview_rejects_unknown_model_keys(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, vector_enabled=False)
    client = _client_with_config(cfg)
    resp = client.post(
        "/api/meetings",
        json={
            "briefing": {"text": "Test", "objectives": ["Check models"]},
            "agents": ["adversary", "strategist"],
            "models_by_agent": {"cfo": "openai/gpt-4o-mini"},
        },
    )
    assert resp.status_code == 400
    assert "models_by_agent keys must be selected agents" in resp.json()["detail"]


def test_ws_meeting_streams_events_from_service(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, vector_enabled=False)

    @dataclass
    class FakeSession:
        meeting_id: str
        event_queue: asyncio.Queue[dict[str, Any]]
        status: str = "completed"

    class FakeMeetingService:
        async def start_meeting(self, *, payload: Any, config: AppConfig) -> FakeSession:
            _ = payload
            _ = config
            q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            await q.put({"type": "meeting_started", "meeting_id": "m-1"})
            await q.put(
                {
                    "type": "turn_complete",
                    "meeting_id": "m-1",
                    "agent_id": "adversary",
                    "agent_name": "Adversary",
                    "content": "Message",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "tool_results": [],
                }
            )
            await q.put(
                {
                    "type": "meeting_complete",
                    "meeting_id": "m-1",
                    "termination_reason": "max_turns",
                    "outputs": {"transcript": None, "kill_sheet": None, "consensus_roadmap": None},
                }
            )
            return FakeSession(meeting_id="m-1", event_queue=q)

        async def cancel_meeting(self, meeting_id: str) -> bool:
            _ = meeting_id
            return True

        def mark_disconnected(self, meeting_id: str) -> None:
            _ = meeting_id

        def forget_meeting(self, meeting_id: str) -> None:
            _ = meeting_id

    client = _client_with_config(cfg, meeting_service=FakeMeetingService())
    with client.websocket_connect("/ws/meeting") as ws:
        ws.send_json(
            {
                "type": "start_meeting",
                "briefing": {"text": "hello", "objectives": ["obj"]},
                "agents": ["adversary", "strategist"],
            }
        )
        assert ws.receive_json()["type"] == "meeting_started"
        assert ws.receive_json()["type"] == "turn_complete"
        assert ws.receive_json()["type"] == "meeting_complete"


def test_store_key_endpoint_uses_config_service(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path, vector_enabled=False)
    service = ConfigService(explicit_path=cfg)
    called: dict[str, Any] = {}

    def fake_set_provider_key(*, provider: str, api_key: str) -> None:
        called["provider"] = provider
        called["api_key"] = api_key

    service.set_provider_key = fake_set_provider_key  # type: ignore[method-assign]
    client = _client_with_config(cfg, config_service=service)
    resp = client.post(
        "/api/config/keys",
        json={"provider": "openrouter", "api_key": "secret-key", "validate_after_store": False},
    )
    assert resp.status_code == 200
    assert called == {"provider": "openrouter", "api_key": "secret-key"}
    assert resp.json()["validated"] is False


def test_resolve_frontend_dist_prefers_cwd(tmp_path: Path, monkeypatch: Any) -> None:
    frontend_dist = tmp_path / "frontend" / "dist"
    frontend_dist.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    resolved = _resolve_frontend_dist()
    assert resolved == frontend_dist
