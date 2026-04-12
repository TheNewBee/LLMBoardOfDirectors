from __future__ import annotations

import json
import re
from typing import Any

from boardroom.models import Message
from boardroom.tools.python_executor import PythonExecutor
from boardroom.tools.registry import PYTHON_EXEC_TOOL, WEB_SEARCH_TOOL
from boardroom.tools.web_search import WebSearchTool

_TOOL_BLOCK_RE = re.compile(r"```tools?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


class ToolExecutor:
    def __init__(
        self,
        *,
        python_executor: PythonExecutor | None = None,
        web_search_tool: WebSearchTool | None = None,
        disabled_tools: set[str] | None = None,
    ) -> None:
        self._python = python_executor or PythonExecutor()
        self._web = web_search_tool or WebSearchTool()
        self._handlers = {
            PYTHON_EXEC_TOOL.name: self._run_python_exec,
            WEB_SEARCH_TOOL.name: self._run_web_search,
        }
        for tool_name in disabled_tools or set():
            self._handlers.pop(tool_name, None)

    def apply_to_message(
        self,
        *,
        message: Message,
        raw_content: str,
    ) -> None:
        calls, parse_errors = self.parse_tool_calls(raw_content)
        if not calls and not parse_errors:
            return
        if calls:
            message.tool_calls = calls
        message.tool_results = [self._execute_single(call) for call in calls]
        for error in parse_errors:
            message.tool_results.append({"name": "tool_parse", "ok": False, "error": error})
        summary = self._summary_lines(message.tool_results)
        if summary:
            message.content = f"{message.content}\n\n{summary}"

    def parse_tool_calls(self, raw_content: str) -> tuple[list[dict[str, Any]], list[str]]:
        calls: list[dict[str, Any]] = []
        parse_errors: list[str] = []
        for block in _TOOL_BLOCK_RE.findall(raw_content):
            parsed, error = self._parse_block(block)
            calls.extend(parsed)
            if error is not None:
                parse_errors.append(error)
        return calls, parse_errors

    @staticmethod
    def _parse_block(block: str) -> tuple[list[dict[str, Any]], str | None]:
        text = block.strip()
        if not text:
            return [], "Tool block is empty."
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return [], "Tool block is not valid JSON."
        rows = payload if isinstance(payload, list) else [payload]
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            args = row.get("args", {})
            if not isinstance(name, str):
                continue
            if not isinstance(args, dict):
                args = {}
            out.append({"name": name, "args": args})
        if not out:
            return [], "Tool block contained no valid tool entries."
        return out, None

    def _execute_single(self, call: dict[str, Any]) -> dict[str, Any]:
        try:
            name = str(call.get("name"))
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            handler = self._handlers.get(name)
            if handler is None:
                return {"name": name, "ok": False, "error": f"Unsupported tool: {name}"}
            return handler(args)
        except Exception as exc:
            return {"name": str(call.get("name", "tool")), "ok": False, "error": str(exc)}

    def _run_python_exec(self, args: dict[str, Any]) -> dict[str, Any]:
        code = str(args.get("code", ""))
        result = self._python.execute(code)
        return {
            "name": PYTHON_EXEC_TOOL.name,
            "ok": result.ok,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "blocked": result.blocked,
        }

    def _run_web_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", ""))
        max_results_raw = args.get("max_results", 3)
        cap = self._web.max_results_cap
        try:
            requested = int(max_results_raw)
        except (TypeError, ValueError):
            requested = 3
        max_results = max(1, min(cap, requested))
        search = self._web.search(query, max_results=max_results)
        return {
            "name": WEB_SEARCH_TOOL.name,
            "ok": True,
            "provider": search.provider,
            "query": search.query,
            "results": search.results,
        }

    @staticmethod
    def _summary_lines(results: list[dict[str, Any]]) -> str:
        if not results:
            return ""
        lines = ["Tool execution summary:"]
        for row in results:
            name = str(row.get("name", "tool"))
            ok = bool(row.get("ok"))
            if ok:
                lines.append(f"- {name}: ok")
            else:
                lines.append(f"- {name}: error ({row.get('error', 'unknown')})")
        return "\n".join(lines)
