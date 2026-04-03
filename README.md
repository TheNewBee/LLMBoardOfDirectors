# Boardroom

Boardroom is an open source CLI for running autonomous adversarial debates between specialized AI agents. You bring your own API keys, choose models per agent, and keep transcripts and outputs local.

## Current Status

Phase 1 is in progress:

- Core package scaffolding
- BYOK configuration
- Core data models
- LLM routing foundations

## Principles

- Open source first
- Bring your own keys
- Local-first outputs
- Adversarial analysis over consensus

## Quick Start

1. Create a virtual environment.
2. Install the package in editable mode with dev dependencies:

```bash
python -m pip install -e .[dev]
```

3. Copy `.env.example` to `.env` and set your API key.
4. Copy `config.example.yaml` to `config.yaml` and adjust models as needed.

## Configuration

Boardroom supports:

- one OpenRouter key for all agents with different models
- different providers for different agents
- per-agent model overrides on top of a default model
- optional `rate_limit_interval_seconds` in `config.yaml` to space LLM calls (helps with free-model upstream limits)

## License

MIT
