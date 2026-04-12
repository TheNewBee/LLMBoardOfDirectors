from __future__ import annotations

from typer.testing import CliRunner

from boardroom.cli.app import app

runner = CliRunner()


def test_serve_rejects_non_localhost_without_flag() -> None:
    result = runner.invoke(
        app,
        ["serve", "--host", "0.0.0.0"],
    )
    assert result.exit_code == 2
    assert "Non-localhost binding is unauthenticated" in result.stderr
