from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from boardroom.cli.app import app


def _submit_briefing(runner: CliRunner, *, out: Path, alpha_file: Path | None = None) -> None:
    args = [
        "briefing",
        "submit",
        "--idea",
        "Stress-test the EU rollout and pricing plan.",
        "--objective",
        "Find the biggest market-entry risks.",
        "--meeting-id",
        "smoke-meeting",
        "--out",
        str(out),
    ]
    if alpha_file is not None:
        args.extend(["--file", str(alpha_file)])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout + result.stderr


def _select_agents(
    runner: CliRunner,
    *,
    from_path: Path,
    out: Path,
    agent_ids: list[str],
) -> None:
    args = ["agents", "select", "--from", str(from_path)]
    for agent_id in agent_ids:
        args.extend(["--agent", agent_id])
    args.extend(["--out", str(out)])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout + result.stderr


def test_smoke_full_workflow_briefing_to_history_search(
    runner: CliRunner,
    write_config: Any,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    config_path = write_config(enabled=True)
    alpha_file = tmp_path / "alpha.txt"
    alpha_file.write_text("Pricing risk is concentrated in Germany.", encoding="utf-8")
    briefing_state = tmp_path / "briefing.json"
    ready_state = tmp_path / "ready.json"
    outputs_dir = tmp_path / "outputs"

    _submit_briefing(runner, out=briefing_state, alpha_file=alpha_file)
    _select_agents(
        runner,
        from_path=briefing_state,
        out=ready_state,
        agent_ids=["adversary", "data_specialist"],
    )

    class ToolCallingRouter:
        def __init__(self) -> None:
            self._index = 0

        def generate_for_agent(self, *, agent: Any, **kwargs: Any) -> str:
            _ = kwargs
            self._index += 1
            if agent.id == "data_specialist":
                return (
                    "I need a pricing check before we commit.\n"
                    "```tool\n"
                    '{"name":"python_exec","args":{"code":"print(6 * 7)"}}'
                    "\n```"
                )
            return f"Concern {self._index}: pricing risk in Germany remains too high."

    monkeypatch.setattr("boardroom.cli.meet.LLMRouter", ToolCallingRouter)

    meet_result = runner.invoke(
        app,
        [
            "meet",
            "--from",
            str(ready_state),
            "--config",
            str(config_path),
            "--max-turns",
            "2",
            "--outputs-dir",
            str(outputs_dir),
        ],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert meet_result.exit_code == 0, meet_result.stdout + meet_result.stderr
    assert "Meeting complete" in meet_result.stdout
    assert "Tool results:" in meet_result.stdout

    transcript_files = list(outputs_dir.glob("*_transcript.md"))
    assert len(transcript_files) == 1
    transcript_text = transcript_files[0].read_text(encoding="utf-8")
    assert "#### Tool execution" in transcript_text

    history_result = runner.invoke(
        app,
        [
            "history",
            "search",
            "--query",
            "pricing risk in Germany",
            "--config",
            str(config_path),
        ],
    )
    assert history_result.exit_code == 0, history_result.stdout + history_result.stderr
    assert "Found 1 matching meeting(s):" in history_result.stdout
    assert "smoke-meeting" in history_result.stdout


def test_smoke_custom_agent_lifecycle(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.chdir(tmp_path)

    create_result = runner.invoke(
        app,
        [
            "custom",
            "create",
            "--id",
            "market_analyst",
            "--name",
            "Market Analyst",
            "--expertise",
            "fintech go-to-market",
            "--trait",
            "skeptical",
            "--bias",
            "risk_aversion",
        ],
    )
    assert create_result.exit_code == 0, create_result.stdout + create_result.stderr

    show_result = runner.invoke(app, ["custom", "show"])
    assert show_result.exit_code == 0, show_result.stdout + show_result.stderr
    assert "Market Analyst" in show_result.stdout

    edit_result = runner.invoke(
        app,
        ["custom", "edit", "--id", "market_analyst", "--name", "Edited Analyst"],
    )
    assert edit_result.exit_code == 0, edit_result.stdout + edit_result.stderr

    show_updated = runner.invoke(app, ["custom", "show"])
    assert show_updated.exit_code == 0, show_updated.stdout + show_updated.stderr
    assert "Edited Analyst" in show_updated.stdout

    delete_result = runner.invoke(app, ["custom", "delete", "--id", "market_analyst"])
    assert delete_result.exit_code == 0, delete_result.stdout + delete_result.stderr

    show_empty = runner.invoke(app, ["custom", "show"])
    assert show_empty.exit_code == 0, show_empty.stdout + show_empty.stderr
    assert "No custom agents defined." in show_empty.stdout


def test_smoke_meeting_with_custom_agent(
    runner: CliRunner,
    write_config: Any,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = write_config(enabled=True)
    briefing_state = tmp_path / "briefing.json"
    ready_state = tmp_path / "ready.json"
    outputs_dir = tmp_path / "outputs_custom"

    create_result = runner.invoke(
        app,
        [
            "custom",
            "create",
            "--id",
            "market_analyst",
            "--name",
            "Market Analyst",
            "--expertise",
            "market entry analysis",
            "--trait",
            "skeptical",
        ],
    )
    assert create_result.exit_code == 0, create_result.stdout + create_result.stderr

    _submit_briefing(runner, out=briefing_state)
    _select_agents(
        runner,
        from_path=briefing_state,
        out=ready_state,
        agent_ids=["adversary", "market_analyst"],
    )

    class RecordingRouter:
        def generate_for_agent(self, *, agent: Any, **kwargs: Any) -> str:
            _ = kwargs
            return f"{agent.name} thinks the rollout needs tighter guardrails."

    monkeypatch.setattr("boardroom.cli.meet.LLMRouter", RecordingRouter)

    meet_result = runner.invoke(
        app,
        [
            "meet",
            "--from",
            str(ready_state),
            "--config",
            str(config_path),
            "--max-turns",
            "2",
            "--outputs-dir",
            str(outputs_dir),
        ],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert meet_result.exit_code == 0, meet_result.stdout + meet_result.stderr

    transcript_files = list(outputs_dir.glob("*_transcript.md"))
    assert len(transcript_files) == 1
    transcript_text = transcript_files[0].read_text(encoding="utf-8")
    assert "Market Analyst" in transcript_text

    saved_state = json.loads(ready_state.read_text(encoding="utf-8"))
    assert saved_state["selected_agents"] == ["adversary", "market_analyst"]
