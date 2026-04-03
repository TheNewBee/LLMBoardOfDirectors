from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from boardroom.cli.app import app

runner = CliRunner()


def _briefing_state(tmp_path: Path) -> Path:
    out = tmp_path / "meet.json"
    r = runner.invoke(
        app,
        [
            "briefing",
            "submit",
            "--idea",
            "Test idea",
            "--objective",
            "Objective one",
            "--meeting-id",
            "mid-1",
            "--out",
            str(out),
        ],
    )
    assert r.exit_code == 0
    return out


def test_agents_list_shows_adversary_and_biases(tmp_path: Path) -> None:
    result = runner.invoke(app, ["agents", "list"])
    assert result.exit_code == 0
    assert "adversary" in result.stdout
    assert "Marcus Vale" in result.stdout


def test_agents_select_writes_selection_and_llm(tmp_path: Path) -> None:
    src = _briefing_state(tmp_path)
    dst = tmp_path / "after.json"
    result = runner.invoke(
        app,
        [
            "agents",
            "select",
            "--from",
            str(src),
            "--out",
            str(dst),
            "--agent",
            "adversary",
            "--agent",
            "cfo",
            "--provider",
            "openrouter",
        ],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    data = json.loads(dst.read_text(encoding="utf-8"))
    assert data["selected_agents"] == ["adversary", "cfo"]
    assert data["llm"]["provider"] == "openrouter"
    assert data["llm"]["models_by_agent"] == {}


def test_agents_select_rejects_non_openrouter_provider(tmp_path: Path) -> None:
    src = _briefing_state(tmp_path)
    result = runner.invoke(
        app,
        [
            "agents",
            "select",
            "--from",
            str(src),
            "--out",
            str(tmp_path / "bad-provider.json"),
            "--agent",
            "adversary",
            "--agent",
            "cfo",
            "--provider",
            "other",
        ],
    )
    assert result.exit_code != 0


def test_agents_select_rejects_without_adversary(tmp_path: Path) -> None:
    src = _briefing_state(tmp_path)
    result = runner.invoke(
        app,
        [
            "agents",
            "select",
            "--from",
            str(src),
            "--out",
            str(tmp_path / "x.json"),
            "--agent",
            "cfo",
            "--agent",
            "strategist",
        ],
    )
    assert result.exit_code != 0
    combined = (result.stdout + result.stderr).lower()
    assert "adversary" in combined


def test_agents_select_agent_model_repeatable(tmp_path: Path) -> None:
    src = _briefing_state(tmp_path)
    dst = tmp_path / "after.json"
    result = runner.invoke(
        app,
        [
            "agents",
            "select",
            "--from",
            str(src),
            "--out",
            str(dst),
            "--agent",
            "adversary",
            "--agent",
            "cfo",
            "--agent-model",
            "cfo=openai/gpt-4o-mini",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(dst.read_text(encoding="utf-8"))
    assert data["llm"]["models_by_agent"]["cfo"] == "openai/gpt-4o-mini"


def test_agents_select_validate_calls_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = _briefing_state(tmp_path)
    dst = tmp_path / "after.json"

    called: dict[str, bool] = {"ok": False}

    def fake_validate(**_kwargs: Any) -> None:
        called["ok"] = True

    monkeypatch.setattr(
        "boardroom.cli.agents.validate_openrouter_for_meeting",
        fake_validate,
    )

    result = runner.invoke(
        app,
        [
            "agents",
            "select",
            "--from",
            str(src),
            "--out",
            str(dst),
            "--agent",
            "adversary",
            "--agent",
            "cfo",
            "--validate",
        ],
    )
    assert result.exit_code == 0
    assert called["ok"] is True
