from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass


@dataclass(frozen=True)
class PythonExecutionResult:
    ok: bool
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    blocked: bool = False


_ALLOWED_IMPORT_MODULES = frozenset(
    {
        "collections",
        "datetime",
        "decimal",
        "fractions",
        "functools",
        "itertools",
        "json",
        "math",
        "operator",
        "random",
        "re",
        "statistics",
        "string",
        "textwrap",
        "time",
        "typing",
    }
)
_BLOCKED_CALL_NAMES = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "dir",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "open",
        "setattr",
        "vars",
    }
)


class PythonExecutor:
    def __init__(
        self,
        *,
        timeout_seconds: int = 30,
        max_code_chars: int = 4000,
        max_output_chars: int = 8000,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_code_chars = max_code_chars
        self.max_output_chars = max_output_chars

    def execute(self, code: str) -> PythonExecutionResult:
        snippet = code.strip()
        if not snippet:
            return PythonExecutionResult(
                ok=False,
                stdout="",
                stderr="Python code cannot be empty.",
                exit_code=None,
                timed_out=False,
            )
        if len(snippet) > self.max_code_chars:
            return PythonExecutionResult(
                ok=False,
                stdout="",
                stderr=f"Python code exceeds max length of {self.max_code_chars} characters.",
                exit_code=None,
                timed_out=False,
            )
        blocked_reason = self._blocked_reason(snippet)
        if blocked_reason is not None:
            return PythonExecutionResult(
                ok=False,
                stdout="",
                stderr=(
                    "Python code uses blocked operations for this tool runner. "
                    f"{blocked_reason}"
                ),
                exit_code=None,
                timed_out=False,
                blocked=True,
            )

        with tempfile.TemporaryDirectory(prefix="boardroom-tool-") as temp_dir:
            try:
                completed = subprocess.run(
                    [sys.executable, "-I", "-c", snippet],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                    cwd=temp_dir,
                    env=self._sandbox_env(),
                )
            except subprocess.TimeoutExpired as exc:
                return PythonExecutionResult(
                    ok=False,
                    stdout=self._truncate_output(exc.stdout or ""),
                    stderr=self._truncate_output(
                        (exc.stderr or "") + "\nExecution timed out."),
                    exit_code=None,
                    timed_out=True,
                )

        return PythonExecutionResult(
            ok=completed.returncode == 0,
            stdout=self._truncate_output((completed.stdout or "").strip()),
            stderr=self._truncate_output((completed.stderr or "").strip()),
            exit_code=completed.returncode,
            timed_out=False,
        )

    def _truncate_output(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        return text[: self.max_output_chars] + "\n...[truncated]"

    @staticmethod
    def _blocked_reason(snippet: str) -> str | None:
        try:
            tree = ast.parse(snippet, mode="exec")
        except SyntaxError:
            # Preserve python's native syntax error output from subprocess execution.
            return None

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".", 1)[0]
                    if module not in _ALLOWED_IMPORT_MODULES:
                        return f"Import '{alias.name}' is not allowed."
            if isinstance(node, ast.ImportFrom):
                if node.level > 0 or node.module is None:
                    return "Relative imports are not allowed."
                module = node.module.split(".", 1)[0]
                if module not in _ALLOWED_IMPORT_MODULES:
                    return f"Import from '{node.module}' is not allowed."
            if isinstance(node, ast.Call):
                blocked_name = PythonExecutor._blocked_call_name(node.func)
                if blocked_name is not None:
                    return f"Call to '{blocked_name}' is not allowed."
        return None

    @staticmethod
    def _blocked_call_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name) and node.id in _BLOCKED_CALL_NAMES:
            return node.id
        if (
            isinstance(node, ast.Attribute)
            and node.attr in _BLOCKED_CALL_NAMES
            and isinstance(node.value, ast.Name)
            and node.value.id in {"builtins", "__builtins__"}
        ):
            return node.attr
        return None

    @staticmethod
    def _sandbox_env() -> dict[str, str]:
        # Keep execution environment intentionally minimal.
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
            value = os.environ.get(key)
            if value:
                env[key] = value
        return env
