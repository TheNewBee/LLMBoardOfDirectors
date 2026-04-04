from __future__ import annotations

from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from boardroom.cli.app import app

runner = CliRunner()


class _FakeStore:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def set(self, provider: str, api_key: str) -> None:
        self.data[provider] = api_key

    def get(self, provider: str) -> str | None:
        return self.data.get(provider)


def _config_file(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "\n".join(
            [
                "providers:",
                "  openrouter:",
                "    api_key_env: OPENROUTER_API_KEY",
                "    base_url: https://openrouter.ai/api/v1",
                "default_model:",
                "  provider: openrouter",
                "  model: openai/gpt-4o-mini",
            ]
        ),
        encoding="utf-8",
    )
    return cfg


def test_agents_key_set_saves_encrypted_key_and_validates(
    tmp_path: Path, monkeypatch: Any
) -> None:
    store = _FakeStore()
    monkeypatch.setattr("boardroom.cli.agents.CredentialStore", lambda: store)

    seen: dict[str, str] = {}

    def fake_validate(**kwargs: Any) -> None:
        env = kwargs["env"]
        seen["api_key"] = env["OPENROUTER_API_KEY"]

    monkeypatch.setattr(
        "boardroom.cli.agents.validate_openrouter_for_meeting", fake_validate)
    cfg = _config_file(tmp_path)
    r = runner.invoke(
        app,
        [
            "agents",
            "key",
            "set",
            "--provider",
            "openrouter",
            "--config",
            str(cfg),
        ],
        input="sk-from-test\n",
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    assert store.get("openrouter") == "sk-from-test"
    assert seen["api_key"] == "sk-from-test"


def test_agents_key_check_reads_store_and_validates(
    tmp_path: Path, monkeypatch: Any
) -> None:
    store = _FakeStore()
    store.set("openrouter", "sk-from-store")
    monkeypatch.setattr("boardroom.cli.agents.CredentialStore", lambda: store)

    seen: dict[str, str] = {}

    def fake_validate(**kwargs: Any) -> None:
        env = kwargs["env"]
        seen["api_key"] = env["OPENROUTER_API_KEY"]

    monkeypatch.setattr(
        "boardroom.cli.agents.validate_openrouter_for_meeting", fake_validate)
    cfg = _config_file(tmp_path)
    r = runner.invoke(
        app,
        [
            "agents",
            "key",
            "check",
            "--provider",
            "openrouter",
            "--config",
            str(cfg),
        ],
    )
    assert r.exit_code == 0, r.stdout + r.stderr
    assert seen["api_key"] == "sk-from-store"


def test_agents_key_check_fails_when_key_missing(tmp_path: Path, monkeypatch: Any) -> None:
    store = _FakeStore()
    monkeypatch.setattr("boardroom.cli.agents.CredentialStore", lambda: store)
    cfg = _config_file(tmp_path)
    r = runner.invoke(
        app,
        [
            "agents",
            "key",
            "check",
            "--provider",
            "openrouter",
            "--config",
            str(cfg),
        ],
    )
    assert r.exit_code == 1
    assert "No encrypted key found" in r.stderr
