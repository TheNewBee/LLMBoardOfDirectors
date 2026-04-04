from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from boardroom.config import load_config
from boardroom.vector_store import MeetingVectorStore

history_app = typer.Typer(help="Search persisted meeting history.")


@history_app.command("search")
def search_history(
    query: Annotated[
        str,
        typer.Option("--query", "-q", help="Search query for past meetings."),
    ],
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=20, help="Maximum results."),
    ] = 5,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True,
                     help="Optional config.yaml path."),
    ] = None,
) -> None:
    """Search prior meeting transcripts from the local vector store."""
    app_config = load_config(config_path)
    if not app_config.vector_store.enabled:
        typer.echo(
            "Vector store is disabled in config. Enable vector_store.enabled first.",
            err=True,
        )
        raise typer.Exit(code=1)

    store = MeetingVectorStore(
        persist_dir=app_config.vector_store.persist_dir,
        collection_name=app_config.vector_store.collection_name,
    )
    results = store.search(query=query, limit=limit)
    if not results:
        typer.echo("No matching meeting history found.")
        return
    typer.echo(f"Found {len(results)} matching meeting(s):")
    for row in results:
        metadata = row.get("metadata", {})
        meeting_id = metadata.get("meeting_id", row.get("id", "unknown"))
        reason = metadata.get("termination_reason", "n/a")
        distance = row.get("distance")
        distance_label = f"{distance:.3f}" if isinstance(
            distance, float) else "n/a"
        snippet = str(row.get("document", "")).replace("\n", " ")[:140]
        typer.echo(
            f"- {meeting_id} (termination={reason}, distance={distance_label})")
        if snippet:
            typer.echo(f"  {snippet}...")
