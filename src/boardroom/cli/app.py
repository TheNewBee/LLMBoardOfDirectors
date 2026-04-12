from __future__ import annotations

import logging
import os
from typing import Annotated

import typer
from dotenv import load_dotenv

from boardroom import __version__
from boardroom.cli.agents import agents_app
from boardroom.cli.briefing import briefing_app
from boardroom.cli.custom import custom_app
from boardroom.cli.history import history_app
from boardroom.cli.meet import meet_command

app = typer.Typer(help="Autonomous adversarial boardroom.")
app.add_typer(briefing_app, name="briefing")
app.add_typer(agents_app, name="agents")
app.add_typer(custom_app, name="custom")
app.add_typer(history_app, name="history")
app.command(
    "meet",
    help="Run a meeting from saved MeetingState (after briefing + agents select).",
)(meet_command)

_LOG = logging.getLogger(__name__)
_LOGGING_CONFIGURED = False


def _configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return
    level_name = os.getenv("BOARDROOM_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    # Chroma may emit noisy telemetry client errors in local-only mode; suppress them.
    logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
    _LOGGING_CONFIGURED = True
    _LOG.debug("Logging configured at level=%s", logging.getLevelName(level))


@app.callback()
def main() -> None:
    """Boardroom CLI entrypoint."""
    # Load `.env` from the current working directory (e.g. repo root), if present.
    load_dotenv()
    _configure_logging()


@app.command("version")
def version() -> None:
    """Show package version."""
    typer.echo(__version__)


@app.command("serve")
def serve(
    host: Annotated[
        str,
        typer.Option("--host", help="Host to bind the web server to."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", min=1, max=65535, help="Port to bind the web server to."),
    ] = 8000,
    allow_insecure_host: Annotated[
        bool,
        typer.Option(
            "--allow-insecure-host",
            help="Allow non-localhost host binding without authentication safeguards.",
        ),
    ] = False,
) -> None:
    """Launch the Boardroom web API + UI server (localhost-only by default)."""
    import uvicorn

    if host not in {"127.0.0.1", "localhost"} and not allow_insecure_host:
        raise typer.BadParameter(
            "Non-localhost binding is unauthenticated. "
            "Use --allow-insecure-host only behind your own auth/proxy."
        )

    uvicorn.run("boardroom.api.main:app", host=host, port=port, reload=False)
