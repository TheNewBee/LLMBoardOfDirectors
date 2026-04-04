from __future__ import annotations

from boardroom.tools import PythonExecutor


def test_python_executor_runs_code_and_returns_stdout() -> None:
    result = PythonExecutor(timeout_seconds=5).execute("print(2 + 2)")
    assert result.ok is True
    assert result.stdout == "4"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.timed_out is False


def test_python_executor_rejects_empty_code() -> None:
    result = PythonExecutor().execute("  ")
    assert result.ok is False
    assert "cannot be empty" in result.stderr.lower()
    assert result.exit_code is None


def test_python_executor_reports_timeout() -> None:
    result = PythonExecutor(timeout_seconds=1).execute(
        "import time; time.sleep(2); print('done')"
    )
    assert result.ok is False
    assert result.timed_out is True
    assert "timed out" in result.stderr.lower()


def test_python_executor_reports_runtime_error() -> None:
    result = PythonExecutor(timeout_seconds=5).execute(
        "raise RuntimeError('boom')")
    assert result.ok is False
    assert result.exit_code is not None
    assert "runtimeerror" in result.stderr.lower()


def test_python_executor_blocks_disallowed_operations() -> None:
    result = PythonExecutor(timeout_seconds=5).execute(
        "import os\nprint(os.getcwd())")
    assert result.ok is False
    assert result.blocked is True
    assert "blocked operations" in result.stderr.lower()
