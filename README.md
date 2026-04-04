# Boardroom

Boardroom is an open source CLI for running autonomous adversarial debates between specialized AI agents. You bring your own API keys, choose models per agent, and keep transcripts and outputs local.

## Current Status

Phase 1 is feature-complete and in hardening/checkpoint:

- Briefing submission CLI
- Agent selection CLI (with optional per-agent model and bias overrides)
- Meeting runner CLI with live turn streaming
- Transcript, Kill Sheet, and Consensus Roadmap artifacts

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

3. Create an env file outside this repo and set your OpenRouter key (BYOK):
   - Recommended: create `./env/board.env` in the project root and add:

```bash
OPENROUTER_API_KEY=sk-or-...
```

- Alternatively, create a standard `.env` file alongside the repo and set the same variable.

Boardroom will automatically load a `.env` in the current working directory and, if present, an additional `env/board.env` file without overriding existing environment variables.

4. Optional (recommended): store an encrypted provider key for local fallback when env vars are absent:

```bash
boardroom agents key set --provider openrouter --validate
```

5. Edit `config.yaml` to adjust models, optional rate limiting, and vector store settings.

## CLI Workflow

Run the Phase 1 flow in three commands:

1. Submit briefing and save initial state.

```bash
boardroom briefing submit \
  --idea "Evaluate whether to launch to EU this quarter" \
  --objective "Find the highest-risk assumptions" \
  --objective "Propose a safer rollout" \
  --meeting-id eu-launch-review \
  --out meeting.json
```

2. Select agents and persist meeting LLM choices.

```bash
boardroom agents select \
  --from meeting.json \
  --agent adversary \
  --agent strategist \
  --agent data_specialist \
  --agent-model strategist=openai/gpt-4o-mini \
  --out meeting.json
```

3. Run the meeting and write artifacts.

```bash
boardroom meet \
  --from meeting.json \
  --max-turns 8 \
  --outputs-dir transcripts
```

Generated artifacts:

- `*_transcript.md`
- `*_kill_sheet.md`
- `*_consensus_roadmap.md`

By default, outputs are written under `paths.outputs_dir` from `config.yaml`.

## Tool Execution (Phase 2 MVP)

- Tool execution is enabled for **every** board agent (same `python_exec` / `web_search` contract in each role prompt).
- Tool requests are parsed from fenced `tool` / `tools` JSON blocks in the model output.
- Recoverable tool failures are recorded in `tool_results` and do not terminate the meeting loop.
- Current built-ins:
  - `python_exec` with `{"code": "..."}`
  - `web_search` with `{"query": "...", "max_results": 3}` (optional; capped by `web_search.max_results_cap` in `config.yaml`, default 5, max 10)

Configure search under `web_search` in `config.yaml`:

- **`provider`**: `duckduckgo` (default, no API key) or `google` ([Programmable Search Engine](https://programmablesearchengine.google.com/) + [Custom Search JSON API](https://developers.google.com/custom-search/v1/overview)).
- **`timeout_seconds`**, **`query_max_len`**, **`max_results_cap`**, **`duckduckgo_url`**, **`google_api_url`** — optional overrides.
- For Google: set **`google_cse_id`** (the search engine “cx” id) in YAML and put the API key in the env var named by **`google_api_key_env`** (default `GOOGLE_CSE_API_KEY`).

Example tool block:

```tool
{"name":"python_exec","args":{"code":"print(2+2)"}}
```

## Encrypted Credentials

- API key precedence is: environment variable first, encrypted store fallback.
- Save/update key (interactive hidden prompt only — avoids shell history / `ps` leaks):

```bash
boardroom agents key set --provider openrouter --validate
```

- Check stored key:

```bash
boardroom agents key check --provider openrouter
```

- Ciphertext lives under `~/.boardroom/credentials.json`. The wrapping key is stored in the OS secret service (via [keyring](https://pypi.org/project/keyring/)) when available, not beside the JSON. For headless or CI, set `BOARDROOM_CREDENTIAL_KEY` to a Fernet key (same format as `Fernet.generate_key()` output). With an explicit `CredentialStore(base_dir=...)` (tests), the key file stays under that directory.
- Values are never printed.

## History Search

Meetings are persisted into a local vector store when `vector_store.enabled` is true.

```bash
boardroom history search --query "pricing risk and compliance" --limit 5
```

## Configuration

Boardroom supports:

- one OpenRouter key for all agents with different models
- different providers for different agents
- per-agent model overrides on top of a default model
- optional `rate_limit_interval_seconds` in `config.yaml` to space LLM calls (helps with free-model upstream limits)
- local vector-store persistence and query controls via `vector_store.*` in `config.yaml` (relative `paths.outputs_dir` and `vector_store.persist_dir` are resolved against the directory containing `config.yaml`)

Optional runtime knobs:

- `BOARDROOM_LOG_LEVEL` environment variable (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

## License

MIT
