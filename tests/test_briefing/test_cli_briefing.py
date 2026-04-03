from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from boardroom.cli.app import app

runner = CliRunner()


def test_briefing_submit_requires_objective(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["briefing", "submit", "--idea", "Launch", "--out", str(tmp_path / "s.json")],
    )
    assert result.exit_code != 0


def test_briefing_submit_writes_state_and_echoes_ready(tmp_path: Path) -> None:
    out = tmp_path / "state.json"
    alpha = tmp_path / "extra.txt"
    alpha.write_text("alpha body", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "briefing",
            "submit",
            "--idea",
            "  Expand to EU  ",
            "--objective",
            "Stress-test GTM",
            "--objective",
            "  Flag regulatory gaps  ",
            "--file",
            str(alpha),
            "--meeting-id",
            "test-meeting-1",
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0
    assert "test-meeting-1" in result.stdout
    assert "agent selection" in result.stdout.lower()

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["meeting_id"] == "test-meeting-1"
    assert data["selected_agents"] == []
    assert data["briefing"]["text"] == "Expand to EU"
    assert data["briefing"]["objectives"] == ["Stress-test GTM", "Flag regulatory gaps"]
    key = alpha.resolve().as_posix()
    assert data["briefing"]["alpha_content"][key] == "alpha body"
