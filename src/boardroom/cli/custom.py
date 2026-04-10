from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from boardroom.config import load_config
from boardroom.custom_agents.builder import CustomAgentBuilder, CustomAgentError
from boardroom.custom_agents.storage import CustomAgentStorage
from boardroom.models import AgentConfig, AgentRole, BiasType

custom_app = typer.Typer(help="Create, edit, and manage custom agent personas.")

_DEFAULT_CUSTOM_DIR = Path(".boardroom/custom_agents")


def _builder(config_path: Path | None = None) -> CustomAgentBuilder:
    cfg = load_config(config_path)
    storage_dir = _DEFAULT_CUSTOM_DIR
    if hasattr(cfg, "knowledge") and hasattr(cfg.knowledge, "custom_agents_dir"):
        storage_dir = Path(cfg.knowledge.custom_agents_dir)
    storage = CustomAgentStorage(storage_dir=storage_dir)
    return CustomAgentBuilder(storage=storage)


@custom_app.command("create")
def create_agent(
    agent_id: Annotated[str, typer.Option("--id", help="Unique agent identifier.")],
    name: Annotated[str, typer.Option("--name", help="Display name.")],
    expertise: Annotated[str, typer.Option("--expertise", help="Expertise domain.")],
    traits: Annotated[
        list[str],
        typer.Option("--trait", "-t", help="Personality trait (repeatable)."),
    ] = [],
    biases: Annotated[
        list[str],
        typer.Option("--bias", "-b", help="Bias type (repeatable). Values: risk_aversion, over_engineering, optimism_bias, pessimism_bias, cost_focus, speed_focus."),
    ] = [],
    bias_intensity: Annotated[float, typer.Option("--bias-intensity", help="Bias intensity 0-1.")] = 0.7,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True, help="Optional config.yaml."),
    ] = None,
) -> None:
    """Create a new custom agent persona."""
    if not traits:
        traits = ["analytical"]
    parsed_biases = []
    for b in biases:
        try:
            parsed_biases.append(BiasType(b))
        except ValueError:
            typer.echo(f"Unknown bias type: {b}. Valid: {[bt.value for bt in BiasType]}", err=True)
            raise typer.Exit(code=1)
    try:
        config = AgentConfig(
            id=agent_id,
            name=name,
            role=AgentRole.CUSTOM,
            expertise_domain=expertise,
            personality_traits=traits,
            biases=parsed_biases,
            bias_intensity=bias_intensity,
        )
    except ValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    builder = _builder(config_path)
    try:
        builder.create(config)
    except CustomAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Created custom agent '{agent_id}' ({name}).")


@custom_app.command("edit")
def edit_agent(
    agent_id: Annotated[str, typer.Option("--id", help="Agent id to edit.")],
    name: Annotated[str | None, typer.Option("--name")] = None,
    expertise: Annotated[str | None, typer.Option("--expertise")] = None,
    bias_intensity: Annotated[float | None, typer.Option("--bias-intensity")] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True),
    ] = None,
) -> None:
    """Edit an existing custom agent."""
    builder = _builder(config_path)
    try:
        existing = builder.get(agent_id)
    except FileNotFoundError:
        typer.echo(f"Custom agent '{agent_id}' not found.", err=True)
        raise typer.Exit(code=1)

    updates: dict[str, object] = {}
    if name is not None:
        updates["name"] = name
    if expertise is not None:
        updates["expertise_domain"] = expertise
    if bias_intensity is not None:
        updates["bias_intensity"] = bias_intensity

    if not updates:
        typer.echo("No updates provided.")
        return

    updated = existing.model_copy(update=updates)
    try:
        builder.update(updated)
    except CustomAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Updated custom agent '{agent_id}'.")


@custom_app.command("delete")
def delete_agent(
    agent_id: Annotated[str, typer.Option("--id", help="Agent id to delete.")],
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True),
    ] = None,
) -> None:
    """Delete a custom agent."""
    builder = _builder(config_path)
    try:
        builder.delete(agent_id)
    except CustomAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Deleted custom agent '{agent_id}'.")


@custom_app.command("show")
def show_agents(
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True),
    ] = None,
) -> None:
    """List all custom agents."""
    builder = _builder(config_path)
    agents = builder.list_all()
    if not agents:
        typer.echo("No custom agents defined.")
        return
    for cfg in agents:
        bias_names = ", ".join(b.value for b in cfg.biases) or "(none)"
        typer.echo(
            f"{cfg.id} — {cfg.name} (custom)\n"
            f"  Expertise: {cfg.expertise_domain}\n"
            f"  Biases: {bias_names}\n"
            f"  Bias intensity: {cfg.bias_intensity}\n"
        )
