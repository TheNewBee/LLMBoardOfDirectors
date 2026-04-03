from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from boardroom.config import load_config
from boardroom.llm.router import LLMRouter
from boardroom.llm.backend import LLMBackendError
from boardroom.models import MeetingState, Message, TerminationReason
from boardroom.orchestrator.meeting_orchestrator import MeetingOrchestrator
from boardroom.orchestrator.termination import TerminationDetector, TerminationDetectorConfig
from boardroom.registry import AgentRegistry, AgentSelectionError


def validate_meeting_ready_for_run(state: MeetingState) -> None:
    if state.termination_reason is not None:
        raise ValueError(
            "This meeting already completed (termination_reason is set). Use a fresh state."
        )
    if state.messages:
        raise ValueError(
            "This state already has messages; use a fresh file from `agents select`.")
    n = len(state.selected_agents)
    if n == 0:
        raise ValueError(
            "No agents selected. Run `boardroom agents select` first.")
    if n == 1:
        raise ValueError(
            "At least two agents are required. Run `boardroom agents select` again.")
    if state.llm is None:
        raise ValueError(
            "Missing persisted LLM selection. Run `boardroom agents select` first.")


def _termination_for_cli_max_turns(max_turns: int | None) -> TerminationDetector:
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


def meet_command(
    from_path: Annotated[
        Path,
        typer.Option(
            "--from",
            exists=True,
            dir_okay=False,
            readable=True,
            help="MeetingState JSON from `boardroom agents select`.",
        ),
    ],
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True,
                     help="Optional config.yaml path."),
    ] = None,
    max_turns: Annotated[
        int | None,
        typer.Option(
            "--max-turns",
            min=1,
            help="Override max turns (default from termination policy).",
        ),
    ] = None,
    outputs_dir: Annotated[
        Path | None,
        typer.Option(
            "--outputs-dir",
            help="Write transcript artifacts here (default: config paths.outputs_dir).",
        ),
    ] = None,
) -> None:
    """Run the adversarial boardroom meeting and print live turns plus output paths."""
    try:
        raw = json.loads(from_path.read_text(encoding="utf-8"))
        state = MeetingState.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    try:
        validate_meeting_ready_for_run(state)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    app_config = load_config(config_path)
    if outputs_dir is not None:
        app_config = app_config.model_copy(
            update={"paths": app_config.paths.model_copy(
                update={"outputs_dir": outputs_dir})}
        )

    reg = AgentRegistry()
    router = LLMRouter()
    termination = _termination_for_cli_max_turns(max_turns)

    def before_turn(agent_id: str) -> None:
        cfg = reg.get_config(agent_id)
        typer.echo(
            f"\n---\n{cfg.name} ({cfg.role.value}) [{agent_id}] — thinking…",
        )

    def after_message(meeting: MeetingState, message: Message) -> None:
        _ = meeting
        typer.echo(
            f"\n{message.agent_name} ({message.agent_id}):\n{message.content}\n")

    orch = MeetingOrchestrator(
        registry=reg,
        app_config=app_config,
        llm=router,
        termination_detector=termination,
        before_agent_turn=before_turn,
        after_agent_message=after_message,
    )

    try:
        final = orch.run_meeting(meeting=state, env=os.environ)
    except (AgentSelectionError, KeyError, RuntimeError, LLMBackendError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    tr = final.persisted_transcript
    reason = final.termination_reason
    typer.echo("\n========== Meeting complete ==========")
    if reason is not None:
        typer.echo(f"Termination: {_termination_label(reason)}")
    if tr is not None:
        typer.echo(f"Transcript: {tr.path.resolve()}")
        if tr.kill_sheet_path is not None:
            typer.echo(f"Kill sheet: {tr.kill_sheet_path.resolve()}")
        if tr.consensus_roadmap_path is not None:
            typer.echo(
                f"Consensus roadmap: {tr.consensus_roadmap_path.resolve()}")
    typer.echo(f"Meeting id: {final.meeting_id}")


def _termination_label(reason: TerminationReason) -> str:
    return {
        TerminationReason.CONSENSUS: "consensus",
        TerminationReason.DEADLOCK: "deadlock",
        TerminationReason.MAX_TURNS: "turn limit reached",
        TerminationReason.CHAIRMAN_INTERRUPT: "chairman interrupt",
    }.get(reason, reason.value)
