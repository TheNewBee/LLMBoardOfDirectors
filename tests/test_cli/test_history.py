from __future__ import annotations

from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from boardroom.cli.app import app

runner = CliRunner()


def _config_file(tmp_path: Path, *, enabled: bool) -> Path:
    cfg = tmp_path / "config.yaml"
    lines = [
        "providers:",
        "  openrouter:",
        "    api_key_env: OPENROUTER_API_KEY",
        "    base_url: https://openrouter.ai/api/v1",
        "default_model:",
        "  provider: openrouter",
        "  model: openai/gpt-4o-mini",
        "vector_store:",
        f"  enabled: {'true' if enabled else 'false'}",
        f"  persist_dir: {str(tmp_path / 'vec')}",
        "  collection_name: boardroom_meetings",
    ]
    cfg.write_text("\n".join(lines), encoding="utf-8")
    return cfg


def test_history_search_prints_results(tmp_path: Path, monkeypatch: Any) -> None:
    class FakeStore:
        def __init__(self, **kwargs: Any) -> None:
            _ = kwargs

        def search(self, *, query: str, limit: int) -> list[dict[str, Any]]:
            _ = query
            _ = limit
            return [
                {
                    "id": "m1",
                    "document": "This meeting discussed EU pricing risks.",
                    "metadata": {"meeting_id": "m1", "termination_reason": "max_turns"},
                    "distance": 0.12,
                }
            ]

    monkeypatch.setattr("boardroom.cli.history.MeetingVectorStore", FakeStore)
    cfg = _config_file(tmp_path, enabled=True)
    r = runner.invoke(
        app,
        ["history", "search", "--query", "pricing risk", "--config", str(cfg)],
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    assert "Found 1 matching meeting(s)" in r.stdout
    assert "m1" in r.stdout


def test_history_search_requires_enabled_vector_store(tmp_path: Path) -> None:
    cfg = _config_file(tmp_path, enabled=False)
    r = runner.invoke(
        app,
        ["history", "search", "--query", "pricing risk", "--config", str(cfg)],
    )
    assert r.exit_code == 1
    assert "Vector store is disabled" in r.stderr
