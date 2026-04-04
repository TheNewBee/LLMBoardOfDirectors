from __future__ import annotations

import re
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


_BLOCKED_PATTERN = re.compile(
    r"\b(import\s+(os|sys|subprocess|socket|pathlib|shutil|ctypes)|"
    r"from\s+(os|sys|subprocess|socket|pathlib|shutil|ctypes)\s+import|"
    r"__import__|open\(|eval\(|exec\()",
    re.IGNORECASE,
)


class PythonExecutor:
    def __init__(self, *, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

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
        if _BLOCKED_PATTERN.search(snippet):
            return PythonExecutionResult(
                ok=False,
                stdout="",
                stderr="Python code uses blocked operations for this tool runner.",
                exit_code=None,
                timed_out=False,
                blocked=True,
            )

        with tempfile.TemporaryDirectory(prefix="boardroom-tool-") as temp_dir:
            try:
                completed = subprocess.run(
                    [sys.executable, "-c", snippet],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                    cwd=temp_dir,
                )
            except subprocess.TimeoutExpired as exc:
                return PythonExecutionResult(
                    ok=False,
                    stdout=exc.stdout or "",
                    stderr=(exc.stderr or "") + "\nExecution timed out.",
                    exit_code=None,
                    timed_out=True,
                )

        return PythonExecutionResult(
            ok=completed.returncode == 0,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
            exit_code=completed.returncode,
            timed_out=False,
        )
