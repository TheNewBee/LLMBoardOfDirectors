# AGENTS.md

## Cursor Cloud specific instructions

Boardroom is a Python (FastAPI + Typer CLI) backend under `src/boardroom` plus a
React/Vite frontend under `frontend/`. The app lives on the **`master`** branch
(the default `main` branch contains only a `LICENSE`); do development on `master`.

### Services

| Service | Dir | Dev command | Notes |
| --- | --- | --- | --- |
| Backend API + WebSocket | repo root | `source .venv/bin/activate && uvicorn boardroom.api.main:app --reload --host 0.0.0.0 --port 8000` | Serves both `/api/*`, `/ws/meeting`, and the built frontend at `/`. |
| Frontend (build) | `frontend/` | `npm --prefix frontend run build` | Outputs `frontend/dist`, which uvicorn serves. Rebuild after frontend edits. |
| CLI | repo root | `boardroom --help` (venv active) | Three-step flow: `briefing submit` → `agents select` → `meet` (see `README.md`). |

### Non-obvious caveats

- **Run the app via uvicorn, not the Vite dev server.** `frontend/vite.config.ts`
  has **no `/api` or `/ws` proxy**, and the frontend uses same-origin
  `fetch("/api/...")` / `new WebSocket(window.location.host + "/ws/meeting")`.
  So `npm run dev` (port 5173) cannot reach the backend. The full-stack dev loop
  is: `npm --prefix frontend run build` once (rebuild on frontend changes), then
  `uvicorn ... --reload` for live backend reloads.
- **The dev environment uses a virtualenv at `.venv`** (gitignored). The package
  is installed editable, so backend hot-reload picks up `src/boardroom` edits.
- **`OPENROUTER_API_KEY` is required to run an actual debate/meeting** (LLM calls
  go to OpenRouter). Without it the server, UI, `/api/*` reads, and the CLI
  `briefing submit` / `agents select` steps all still work, but starting a meeting
  (CLI `boardroom meet` or the UI chat "start") will fail on the LLM call. Set it
  in `.env` at the repo root (see `.env.example`) or export it.
- **`PUT /api/config` and settings changes rewrite `config.yaml` in place.** If
  you exercise config edits while testing, `git checkout config.yaml` afterward to
  avoid committing churn. `frontend/tsconfig.app.tsbuildinfo` is tracked and gets
  rewritten by `npm run build`; restore it too if you don't intend to commit it.

### Lint / test / build

- Backend tests: `pytest` (venv active) — ~289 tests, no network needed (LLM is mocked).
- Formatting: `black src tests` (repo currently has pre-existing formatting drift;
  `black --check` is not clean on a fresh checkout).
- Types: `mypy` per `pyproject.toml` is not clean out of the box (missing
  third-party stubs, e.g. `feedparser`/`duckduckgo_search`); treat as advisory.
- Frontend build/typecheck: `npm --prefix frontend run build` (runs `tsc -b` then `vite build`).
- Docker (full prod-style UI): `docker compose up --build`, then open the host port
  (`BOARDROOM_HOST_PORT`, default `18000`).
