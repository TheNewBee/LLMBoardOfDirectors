# Boardroom

Boardroom is an open-source CLI for running autonomous adversarial debates between specialized AI agents. You bring your own API keys, choose models per agent, and keep transcripts and outputs local.

## Current status

- **Briefing & roster**: submit a briefing, select 2–6 agents with optional per-agent models and bias overrides.
- **Meetings**: run debates with live turn streaming; artifacts include transcript, kill sheet, and consensus roadmap.
- **Tools**: all agents may call **`python_exec`** (best-effort local sandbox via `python -I`, timeout, minimal env, blocked risky ops) and **`web_search`** (DDGS free search by default, optional Tavily quality backend).
- **Credentials**: optional encrypted OpenRouter key with OS keyring for the wrapping key; env vars still win.
- **History**: optional local Chroma vector store for meeting text; `boardroom history search` queries past runs.

## Principles

- Open source first
- Bring your own keys
- Local-first outputs
- Adversarial analysis over consensus

## Quick start

1. Create a virtual environment and install (with dev extras if you run tests):

```bash
python -m pip install -e .[dev]
```

2. Set **`OPENROUTER_API_KEY`** (see `.env.example` for optional variables such as Tavily or `BOARDROOM_CREDENTIAL_KEY`).
   - Typical layout: a `.env` in the directory you run commands from, and/or **`env/board.env`** next to it.

Boardroom loads **`.env`** from the current working directory, then **`env/board.env`** if it exists, without overriding variables already set in the process.

3. Optionally store an encrypted key for when the env var is unset:

```bash
boardroom agents key set --provider openrouter --validate
```

(API key is entered via **hidden prompt only**—not via CLI flags.)

4. Edit **`config.yaml`** for models, rate limiting, `vector_store`, and `web_search`.

## CLI workflow

Typical three-step flow:

**1. Briefing** — create initial meeting state:

```bash
boardroom briefing submit \
  --idea "Evaluate whether to launch to EU this quarter" \
  --objective "Find the highest-risk assumptions" \
  --objective "Propose a safer rollout" \
  --meeting-id eu-launch-review \
  --out meeting.json
```

**2. Agent selection** — pick agents and persist LLM choices:

```bash
boardroom agents select \
  --from meeting.json \
  --agent adversary \
  --agent strategist \
  --agent data_specialist \
  --agent-model strategist=openai/gpt-4o-mini \
  --out meeting.json
```

**3. Run meeting** — stream turns and write artifacts:

```bash
boardroom meet --from meeting.json --max-turns 8
```

Use **`--config path/to/config.yaml`** when your `config.yaml` is not discovered from the current directory (same for `history search`). Optional **`--outputs-dir`** overrides `paths.outputs_dir` for that run.

**Artifacts** (under `paths.outputs_dir` from config, unless overridden):

- `*_transcript.md`
- `*_kill_sheet.md`
- `*_consensus_roadmap.md`

## Tool execution

Agents are prompted to use tools only when helpful. The model emits a single fenced JSON block:

- Fence: ` ```tool ` or ` ```tools `
- Payload: one object or an array of objects: `{"name": "<tool>", "args": { ... }}`

**Built-ins**

| Tool          | Args                            | Notes                                                                                                                                                                |
| ------------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `python_exec` | `code`                          | Runs local `python -I -c` with timeout, minimal env, AST safety checks (module allowlist + blocked dangerous builtins), and output truncation (best-effort sandbox). |
| `web_search`  | `query`, optional `max_results` | Capped by `web_search.max_results_cap` (default 5, up to 20).                                                                                                        |

Parse or runtime failures are attached to `tool_results` and do not stop the meeting.

Example:

```tool
{"name":"python_exec","args":{"code":"print(2+2)"}}
```

## Encrypted credentials

- **Order of precedence**: process environment → encrypted store (`boardroom agents key set`).
- **Storage**: ciphertext in `~/.boardroom/credentials.json`; wrapping key in the OS secret store via [keyring](https://pypi.org/project/keyring/) when available (not next to the JSON).
- **Headless / CI**: set **`BOARDROOM_CREDENTIAL_KEY`** to a Fernet key (url-safe base64, same shape as `Fernet.generate_key()`).
- Stored values are never printed.

```bash
boardroom agents key check --provider openrouter
```

## History search

When **`vector_store.enabled`** is true, completed meetings are indexed after each run (same embedding backend as local search).

```bash
boardroom history search --query "pricing risk and compliance" --limit 5
```

Requires vector store paths in config; relative `vector_store.persist_dir` is resolved from the **directory containing** the loaded `config.yaml`, so runs from different working directories still use the same store when you pass the same `--config`.

## Configuration (`config.yaml`)

- **Models**: `default_model`, `agent_models`, OpenRouter under `providers.openrouter`.
- **Rate limiting**: `rate_limit_interval_seconds` spaces LLM calls (useful for free-tier models).
- **Paths**: `paths.outputs_dir` — relative paths are resolved against the config file’s directory.
- **Vector store**: `vector_store.enabled`, `persist_dir`, `collection_name`, `default_top_k`.
- **Web search** (`web_search`):
  - **`provider`**: `ddgs` (default, free/no API key) or `tavily` (optional higher-quality paid API).
  - **Strict values**: removed providers (`duckduckgo`, `google`, `parallel_cli`) are rejected with explicit validation errors.
  - **Tavily**: set API key in env var named by **`tavily_api_key_env`** (default `TAVILY_API_KEY`).
  - **Tuning**: `timeout_seconds`, `query_max_len`, `max_results_cap`, `tavily_search_depth`, optional `tavily_api_url` (must start with `https://api.tavily.com/` unless `BOARDROOM_ALLOW_CUSTOM_TAVILY_URL=1`).

**Environment**

- **`BOARDROOM_LOG_LEVEL`**: `DEBUG`, `INFO`, `WARNING`, `ERROR`.

## License

MIT
