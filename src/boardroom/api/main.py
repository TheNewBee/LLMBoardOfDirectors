from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from boardroom.api.routes import agents, config, history, knowledge, meetings
from boardroom.api.ws import meeting as ws_meeting


def _resolve_frontend_dist() -> Path | None:
    candidates = [
        Path.cwd() / "frontend" / "dist",
        Path(__file__).resolve().parents[3] / "frontend" / "dist",
        Path(__file__).resolve().parents[4] / "frontend" / "dist",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def create_app() -> FastAPI:
    app = FastAPI(title="Boardroom API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(agents.router)
    app.include_router(config.router)
    app.include_router(history.router)
    app.include_router(knowledge.router)
    app.include_router(meetings.router)
    app.include_router(ws_meeting.router)

    frontend_dist = _resolve_frontend_dist()
    if frontend_dist is not None:
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    else:

        @app.get("/")
        def root() -> JSONResponse:
            return JSONResponse(
                {
                    "status": "ok",
                    "message": "Boardroom API is running. Frontend build not found.",
                }
            )

    return app


app = create_app()
