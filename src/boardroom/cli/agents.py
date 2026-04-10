from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from boardroom.config import load_config
from boardroom.llm.router import LLMRouter
from boardroom.models import AgentRole, AppConfig, MeetingLLMSelection, MeetingState
from boardroom.registry import AgentRegistry, AgentSelectionError
from boardroom.secrets import CredentialStore, CredentialStoreError
from boardroom.selection.parse import parse_key_value_floats, parse_key_value_strings
from boardroom.selection.providers import (
    ProviderValidationError,
    UnsupportedProviderError,
    validate_openrouter_for_meeting,
)

agents_app = typer.Typer(help="Agent roster and chairman selection.")
key_app = typer.Typer(help="Manage encrypted provider API keys.")
agents_app.add_typer(key_app, name="key")


@agents_app.command("list")
def list_agents() -> None:
    """Print all agents (built-in + custom) with roles, expertise, and biases."""
    reg = AgentRegistry()
    lines: list[str] = []
    for aid in reg.list_agent_ids():
        cfg = reg.get_config(aid)
        bias_names = ", ".join(b.value for b in cfg.biases) or "(none)"
        tag = "custom" if cfg.role == AgentRole.CUSTOM else cfg.role.value
        lines.append(
            f"{aid} — {cfg.name} ({tag})\n"
            f"  Expertise: {cfg.expertise_domain}\n"
            f"  Biases: {bias_names}\n"
            f"  Default bias intensity: {cfg.bias_intensity}\n",
        )
    typer.echo("\n".join(lines).rstrip())


@agents_app.command("select")
def select_agents(
    from_path: Annotated[
        Path,
        typer.Option(
            "--from",
            exists=True,
            dir_okay=False,
            readable=True,
            help="MeetingState JSON from briefing (or prior step).",
        ),
    ],
    agent: Annotated[
        list[str],
        typer.Option(
            "--agent",
            "-a",
            help="Agent id to include (repeatable, 2–6 total, order preserved).",
        ),
    ],
    out: Annotated[
        Path | None,
        typer.Option(
            "--out", help="Write updated MeetingState JSON (default: overwrite --from)."),
    ] = None,
    provider: Annotated[
        str,
        typer.Option(
            "--provider", help='LLM provider (Phase 1: "openrouter" only).'),
    ] = "openrouter",
    validate: Annotated[
        bool,
        typer.Option(
            "--validate", help="Ping OpenRouter to verify the API key before saving."),
    ] = False,
    agent_model: Annotated[
        list[str],
        typer.Option(
            "--agent-model",
            help="Per-agent OpenRouter model id, e.g. --agent-model cfo=openai/gpt-4o-mini",
        ),
    ] = [],
    bias: Annotated[
        list[str],
        typer.Option(
            "--bias",
            help="Per-agent bias intensity 0–1, e.g. --bias cfo=0.4 (overrides --bias-intensity).",
        ),
    ] = [],
    bias_intensity: Annotated[
        float | None,
        typer.Option(
            "--bias-intensity",
            help="If set, apply this bias intensity to every selected agent (opt-in).",
        ),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True,
                     help="Optional config.yaml path."),
    ] = None,
    validation_model: Annotated[
        str | None,
        typer.Option(
            "--validation-model",
            help="Model id used for the API key ping (default: default_model from config).",
        ),
    ] = None,
) -> None:
    """Select 2–6 agents (≥1 adversary) and persist LLM/bias choices into MeetingState."""
    try:
        raw = json.loads(from_path.read_text(encoding="utf-8"))
        state = MeetingState.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if not agent:
        typer.echo("Provide at least two --agent ids (2–6 total).", err=True)
        raise typer.Exit(code=1)

    if provider != "openrouter":
        typer.echo(
            "Phase 1 supports only --provider openrouter (use `boardroom agents select --help`).",
            err=True,
        )
        raise typer.Exit(code=1)

    reg = AgentRegistry()
    try:
        reg.validate_selection(agent)
    except AgentSelectionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    models_by_agent: dict[str, str] = {}
    if agent_model:
        try:
            models_by_agent = parse_key_value_strings(
                agent_model, name="--agent-model")
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        unknown_m = set(models_by_agent) - set(agent)
        if unknown_m:
            typer.echo(
                f"--agent-model keys must be selected agents; unknown: {sorted(unknown_m)}",
                err=True,
            )
            raise typer.Exit(code=1)

    bias_by_agent: dict[str, float] = {}
    if bias_intensity is not None:
        if bias_intensity < 0.0 or bias_intensity > 1.0:
            typer.echo("--bias-intensity must be between 0 and 1.", err=True)
            raise typer.Exit(code=1)
        bias_by_agent = {aid: bias_intensity for aid in agent}
    if bias:
        try:
            parsed_bias = parse_key_value_floats(bias, name="--bias")
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        bias_by_agent.update(parsed_bias)
    if bias_by_agent:
        unknown_b = set(bias_by_agent) - set(agent)
        if unknown_b:
            typer.echo(
                f"--bias / --bias-intensity keys must be selected agents; unknown: {sorted(unknown_b)}",
                err=True,
            )
            raise typer.Exit(code=1)

    app_config = load_config(config_path)
    router = LLMRouter()
    ping_model = validation_model or app_config.default_model.model

    if validate:
        try:
            validate_openrouter_for_meeting(
                provider=provider,
                app_config=app_config,
                env=os.environ,
                router=router,
                validation_model=ping_model,
            )
        except UnsupportedProviderError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        except KeyError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        except ProviderValidationError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    updated = state.model_copy(
        update={
            "selected_agents": list(agent),
            "llm": MeetingLLMSelection(provider=provider, models_by_agent=models_by_agent),
            "bias_intensity_by_agent": bias_by_agent,
        },
    )

    dest = out or from_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(updated.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    typer.echo(
        f"Selected {len(agent)} agents for meeting {updated.meeting_id}; "
        f"provider={provider!r}. Saved to {dest}",
    )


def _provider_env_name(provider: str, app_config: AppConfig) -> str:
    config = app_config.providers.get(provider)
    if config is None:
        raise KeyError(f"Unknown provider: {provider}")
    return config.api_key_env


@key_app.command("set")
def set_key(
    provider: Annotated[
        str,
        typer.Option(
            "--provider", help='Provider id (Phase 2 currently uses "openrouter").'),
    ] = "openrouter",
    validate: Annotated[
        bool,
        typer.Option(
            "--validate", help="Validate the key against provider after saving."),
    ] = True,
    validation_model: Annotated[
        str | None,
        typer.Option(
            "--validation-model",
            help="Model id used for validation (default: config default_model).",
        ),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True,
                     help="Optional config.yaml path."),
    ] = None,
) -> None:
    """Save/update an encrypted API key for a provider (hidden prompt; no argv secret)."""
    app_config = load_config(config_path)
    secret = typer.prompt("API key", hide_input=True)
    store = CredentialStore()
    try:
        store.set(provider, secret)
    except CredentialStoreError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Saved encrypted key for provider {provider!r}.")

    if not validate:
        return
    model = validation_model or app_config.default_model.model
    env_name = _provider_env_name(provider, app_config)
    validate_env = dict(os.environ)
    validate_env[env_name] = secret
    router = LLMRouter()
    try:
        validate_openrouter_for_meeting(
            provider=provider,
            app_config=app_config,
            env=validate_env,
            router=router,
            validation_model=model,
        )
    except (UnsupportedProviderError, ProviderValidationError, KeyError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Validation succeeded for provider {provider!r}.")


@key_app.command("check")
def check_key(
    provider: Annotated[
        str,
        typer.Option(
            "--provider", help='Provider id (Phase 2 currently uses "openrouter").'),
    ] = "openrouter",
    validation_model: Annotated[
        str | None,
        typer.Option(
            "--validation-model",
            help="Model id used for validation (default: config default_model).",
        ),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True,
                     help="Optional config.yaml path."),
    ] = None,
) -> None:
    """Check that an encrypted key exists and validates for a provider."""
    app_config = load_config(config_path)
    store = CredentialStore()
    try:
        secret = store.get(provider)
    except CredentialStoreError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if not secret:
        typer.echo(
            f"No encrypted key found for provider {provider!r}. Run `boardroom agents key set`.",
            err=True,
        )
        raise typer.Exit(code=1)

    env_name = _provider_env_name(provider, app_config)
    validate_env = dict(os.environ)
    validate_env[env_name] = secret
    model = validation_model or app_config.default_model.model
    router = LLMRouter()
    try:
        validate_openrouter_for_meeting(
            provider=provider,
            app_config=app_config,
            env=validate_env,
            router=router,
            validation_model=model,
        )
    except (UnsupportedProviderError, ProviderValidationError, KeyError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"Encrypted key is present and valid for provider {provider!r}.")
