from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from boardroom.cli.app import app
from boardroom.cli.meet import validate_meeting_ready_for_run
from boardroom.llm.backend import LLMBackendError
from boardroom.models import Briefing, MeetingLLMSelection, MeetingState, TerminationReason

runner = CliRunner()


def _briefing_state(tmp_path: Path) -> Path:
    out = tmp_path / "brief.json"
    r = runner.invoke(
        app,
        [
            "briefing",
            "submit",
            "--idea",
            "CLI meet integration",
            "--objective",
            "Verify meet command",
            "--meeting-id",
            "cli-meet-1",
            "--out",
            str(out),
        ],
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    return out


def _selected_state(tmp_path: Path) -> Path:
    src = _briefing_state(tmp_path)
    dst = tmp_path / "ready.json"
    r = runner.invoke(
        app,
        [
            "agents",
            "select",
            "--from",
            str(src),
            "--agent",
            "adversary",
            "--agent",
            "strategist",
            "--agent-model",
            "strategist=openai/gpt-4o-mini",
            "--bias",
            "adversary=0.55",
            "--out",
            str(dst),
        ],
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    return dst


def _selected_state_with_data_specialist(tmp_path: Path) -> Path:
    src = _briefing_state(tmp_path)
    dst = tmp_path / "ready-ds.json"
    r = runner.invoke(
        app,
        [
            "agents",
            "select",
            "--from",
            str(src),
            "--agent",
            "adversary",
            "--agent",
            "data_specialist",
            "--out",
            str(dst),
        ],
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    return dst


def test_validate_meeting_ready_rejects_completed_state() -> None:
    state = MeetingState(
        meeting_id="x",
        briefing=Briefing(text="t", objectives=["o"]),
        selected_agents=["adversary", "strategist"],
        llm=MeetingLLMSelection(),
        termination_reason=TerminationReason.MAX_TURNS,
    )
    with pytest.raises(ValueError, match="already completed"):
        validate_meeting_ready_for_run(state)


def test_meet_cli_runs_from_saved_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ready = _selected_state(tmp_path)

    class FakeRouter:
        def __init__(self) -> None:
            self.n = 0

        def generate_for_agent(self, **kwargs: Any) -> str:
            self.n += 1
            return f"Turn {self.n} synthetic reply with enough words to avoid deadlock heuristics."

    monkeypatch.setattr("boardroom.cli.meet.LLMRouter", FakeRouter)

    result = runner.invoke(
        app,
        [
            "meet",
            "--from",
            str(ready),
            "--max-turns",
            "2",
            "--outputs-dir",
            str(tmp_path / "out"),
        ],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "thinking" in result.stdout.lower()
    assert "Meeting complete" in result.stdout
    assert "Termination:" in result.stdout
    assert "Transcript:" in result.stdout
    assert "Kill sheet:" in result.stdout
    assert "Consensus roadmap:" in result.stdout

    artifacts_dir = tmp_path / "out"
    transcripts = list(artifacts_dir.glob("*_transcript.md"))
    kill_sheets = list(artifacts_dir.glob("*_kill_sheet.md"))
    roadmaps = list(artifacts_dir.glob("*_consensus_roadmap.md"))
    assert len(transcripts) == 1
    assert len(kill_sheets) == 1
    assert len(roadmaps) == 1
    assert "## Transcript" in transcripts[0].read_text(encoding="utf-8")
    assert "## Kill Sheet" in kill_sheets[0].read_text(encoding="utf-8")
    assert "## Consensus Roadmap" in roadmaps[0].read_text(encoding="utf-8")

    data = json.loads(ready.read_text(encoding="utf-8"))
    assert data["llm"]["models_by_agent"]["strategist"] == "openai/gpt-4o-mini"
    assert data["bias_intensity_by_agent"]["adversary"] == 0.55


def test_meet_cli_thinking_precedes_each_turn_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready = _selected_state(tmp_path)

    class FakeRouter:
        def __init__(self) -> None:
            self.i = 0

        def generate_for_agent(self, **kwargs: Any) -> str:
            self.i += 1
            return f"Unique response number {self.i} for boardroom discussion content."

    monkeypatch.setattr("boardroom.cli.meet.LLMRouter", FakeRouter)

    result = runner.invoke(
        app,
        [
            "meet",
            "--from",
            str(ready),
            "--max-turns",
            "3",
            "--outputs-dir",
            str(tmp_path / "out2"),
        ],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    text = result.stdout
    thinking_idxs = [m.start()
                     for m in re.finditer(r"thinking", text, re.IGNORECASE)]
    assert len(thinking_idxs) >= 3
    blocks = text.split("---")
    assert len(blocks) >= 4
    for i in range(1, min(4, len(blocks))):
        chunk = blocks[i]
        assert "thinking" in chunk.lower()
        assert ":" in chunk


def test_meet_cli_applies_strategist_model_from_saved_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready = _selected_state(tmp_path)
    seen: list[str | None] = []

    class RecordingRouter:
        def generate_for_agent(self, *, agent: Any, **kwargs: Any) -> str:
            override = agent.model_config_override
            seen.append(override.model if override is not None else None)
            return "Recording router reply with sufficient length for the meeting flow."

    monkeypatch.setattr("boardroom.cli.meet.LLMRouter", RecordingRouter)

    r = runner.invoke(
        app,
        [
            "meet",
            "--from",
            str(ready),
            "--max-turns",
            "2",
            "--outputs-dir",
            str(tmp_path / "out3"),
        ],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "openai/gpt-4o-mini" in seen


def test_meet_cli_exits_cleanly_when_llm_backend_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready = _selected_state(tmp_path)
    outputs = tmp_path / "out-fail"

    class FailingRouter:
        def generate_for_agent(self, **kwargs: Any) -> str:
            raise LLMBackendError("OpenRouter request failed: synthetic 429")

    monkeypatch.setattr("boardroom.cli.meet.LLMRouter", FailingRouter)

    r = runner.invoke(
        app,
        [
            "meet",
            "--from",
            str(ready),
            "--max-turns",
            "2",
            "--outputs-dir",
            str(outputs),
        ],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert r.exit_code == 1
    assert "OpenRouter request failed: synthetic 429" in r.stderr
    assert not list(outputs.glob("*_transcript.md"))


def test_meet_cli_displays_tool_results_for_data_specialist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready = _selected_state_with_data_specialist(tmp_path)
    out_dir = tmp_path / "out-tools"

    class ToolCallingRouter:
        def generate_for_agent(self, *, agent: Any, **kwargs: Any) -> str:
            if agent.id != "data_specialist":
                return "No tools requested this turn."
            return (
                "Need to run a quick check.\n"
                "```tool\n"
                '{"name":"python_exec","args":{"code":"print(7*6)"}}'
                "\n```"
            )

    monkeypatch.setattr("boardroom.cli.meet.LLMRouter", ToolCallingRouter)

    r = runner.invoke(
        app,
        [
            "meet",
            "--from",
            str(ready),
            "--max-turns",
            "2",
            "--outputs-dir",
            str(out_dir),
        ],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "Tool results:" in r.stdout
    assert "- python_exec: ok" in r.stdout
    transcript_files = list(out_dir.glob("*_transcript.md"))
    assert len(transcript_files) == 1
    transcript_text = transcript_files[0].read_text(encoding="utf-8")
    assert "#### Tool execution" in transcript_text


def test_meet_cli_handles_malformed_tool_block_as_recoverable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready = _selected_state_with_data_specialist(tmp_path)
    out_dir = tmp_path / "out-tools-malformed"

    class MalformedToolRouter:
        def generate_for_agent(self, *, agent: Any, **kwargs: Any) -> str:
            if agent.id != "data_specialist":
                return "No tools requested this turn."
            return "```tool\n{not-json}\n```"

    monkeypatch.setattr("boardroom.cli.meet.LLMRouter", MalformedToolRouter)

    r = runner.invoke(
        app,
        [
            "meet",
            "--from",
            str(ready),
            "--max-turns",
            "2",
            "--outputs-dir",
            str(out_dir),
        ],
        env={"OPENROUTER_API_KEY": "test-key"},
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "Tool results:" in r.stdout
    assert "- tool_parse: error" in r.stdout
