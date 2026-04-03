from __future__ import annotations

import typer
from dotenv import load_dotenv

from boardroom import __version__
from boardroom.cli.agents import agents_app
from boardroom.cli.briefing import briefing_app
from boardroom.cli.meet import meet_command

app = typer.Typer(help="Autonomous adversarial boardroom.")
app.add_typer(briefing_app, name="briefing")
app.add_typer(agents_app, name="agents")
app.command(
    "meet",
    help="Run a meeting from saved MeetingState (after briefing + agents select).",
)(meet_command)


@app.callback()
def main() -> None:
    """Boardroom CLI entrypoint."""
    load_dotenv()


@app.command("version")
def version() -> None:
    """Show package version."""
    typer.echo(__version__)
