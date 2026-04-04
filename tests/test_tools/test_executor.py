from __future__ import annotations

from boardroom.models import AgentRole, Message
from boardroom.tools import PythonExecutionResult, ToolExecutor, WebSearchResult


class _FakePythonExecutor:
    def execute(self, code: str) -> PythonExecutionResult:
        _ = code
        return PythonExecutionResult(
            ok=True,
            stdout="42",
            stderr="",
            exit_code=0,
            timed_out=False,
        )


class _FakeWebSearchTool:
    max_results_cap = 5

    def search(self, query: str, *, max_results: int = 3) -> WebSearchResult:
        _ = max_results
        return WebSearchResult(
            query=query,
            provider="fake",
            results=[
                {"title": "Result", "url": "https://example.com", "snippet": "s"}],
        )


def test_tool_executor_parses_tool_block() -> None:
    raw = (
        "Analysis first.\n"
        "```tool\n"
        '{"name":"python_exec","args":{"code":"print(2+2)"}}'
        "\n```"
    )
    executor = ToolExecutor(
        python_executor=_FakePythonExecutor(),
        web_search_tool=_FakeWebSearchTool(),
    )
    calls, errors = executor.parse_tool_calls(raw)
    assert calls == [{"name": "python_exec", "args": {"code": "print(2+2)"}}]
    assert errors == []


def test_tool_executor_applies_calls_and_results_to_message() -> None:
    raw = (
        "Need both tools.\n"
        "```tools\n"
        '[{"name":"python_exec","args":{"code":"print(1)"}},'
        '{"name":"web_search","args":{"query":"boardroom ai"}}]'
        "\n```"
    )
    msg = Message(agent_id="data_specialist",
                  agent_name="Dana", content="Need both tools.")
    executor = ToolExecutor(
        python_executor=_FakePythonExecutor(),
        web_search_tool=_FakeWebSearchTool(),
    )
    executor.apply_to_message(
        message=msg, raw_content=raw, agent_role=AgentRole.DATA_SPECIALIST)

    assert len(msg.tool_calls) == 2
    assert len(msg.tool_results) == 2
    assert all(result["ok"] is True for result in msg.tool_results)
    assert "Tool execution summary" in msg.content


def test_tool_executor_marks_unsupported_tool_as_error() -> None:
    raw = '```tool\n{"name":"unknown_tool","args":{}}\n```'
    msg = Message(agent_id="data_specialist", agent_name="Dana",
                  content="Run unknown tool.")
    executor = ToolExecutor(
        python_executor=_FakePythonExecutor(),
        web_search_tool=_FakeWebSearchTool(),
    )
    executor.apply_to_message(
        message=msg, raw_content=raw, agent_role=AgentRole.DATA_SPECIALIST)
    assert msg.tool_results
    assert msg.tool_results[0]["ok"] is False
    assert "Unsupported tool" in str(msg.tool_results[0]["error"])


def test_tool_executor_attaches_parse_error_for_malformed_json_block() -> None:
    raw = "```tool\n{invalid-json]\n```"
    msg = Message(agent_id="data_specialist",
                  agent_name="Dana", content="Try tools.")
    executor = ToolExecutor(
        python_executor=_FakePythonExecutor(),
        web_search_tool=_FakeWebSearchTool(),
    )
    executor.apply_to_message(
        message=msg, raw_content=raw, agent_role=AgentRole.DATA_SPECIALIST)
    assert msg.tool_calls == []
    assert len(msg.tool_results) == 1
    assert msg.tool_results[0]["name"] == "tool_parse"
    assert msg.tool_results[0]["ok"] is False


def test_tool_executor_runs_tools_for_any_agent_role() -> None:
    raw = '```tool\n{"name":"python_exec","args":{"code":"print(1)"}}\n```'
    msg = Message(agent_id="adversary", agent_name="Marcus",
                  content="Using tools.")
    executor = ToolExecutor(
        python_executor=_FakePythonExecutor(),
        web_search_tool=_FakeWebSearchTool(),
    )
    executor.apply_to_message(
        message=msg, raw_content=raw, agent_role=AgentRole.ADVERSARY)
    assert msg.tool_calls == [
        {"name": "python_exec", "args": {"code": "print(1)"}}]
    assert len(msg.tool_results) == 1
    assert msg.tool_results[0]["ok"] is True
