from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from boardroom.briefing.io import build_briefing
from boardroom.models import MeetingState

briefing_app = typer.Typer(help="Chairman briefing phase.")


@briefing_app.command("submit")
def submit(
    idea: Annotated[str, typer.Option("--idea", "-i", help="Briefing idea / instructions.")],
    objective: Annotated[
        list[str],
        typer.Option(
            "--objective",
            "-o",
            help="Meeting objective (repeatable). At least one required.",
        ),
    ] = [],
    file: Annotated[
        list[Path],
        typer.Option(
            "--file",
            "-f",
            help="Path to Alpha material (repeatable). Text-like types only.",
        ),
    ] = [],
    meeting_id: Annotated[
        str | None,
        typer.Option("--meeting-id", help="Meeting id (default: random UUID)."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write MeetingState JSON (briefing-only: no agents yet)."),
    ] = None,
) -> None:
    """Submit a briefing: idea, objectives, optional Alpha files."""
    mid = meeting_id or str(uuid.uuid4())
    try:
        briefing = build_briefing(idea, objective, file)
    except (ValidationError, ValueError, FileNotFoundError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    state = MeetingState(meeting_id=mid, briefing=briefing, selected_agents=[])
    typer.echo(f"Briefing complete for meeting {mid}. Ready for agent selection (next phase).")
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(state.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        typer.echo(f"Saved meeting state to {out}")
