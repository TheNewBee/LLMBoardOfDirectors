from __future__ import annotations

import httpx
import pytest

from boardroom.models import WebSearchConfig
from boardroom.tools import WebSearchTool, sanitize_search_query


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.last_json: dict[str, object] | None = None

    def post(self, url: str, json: dict[str, object]) -> _FakeResponse:
        _ = url
        self.last_json = json
        return _FakeResponse(self._payload)


class _FailingClient:
    def post(self, url: str, json: dict[str, object]) -> _FakeResponse:
        _ = url
        _ = json
        raise httpx.ReadTimeout("timeout")


class _FakeDdgs:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self._rows = rows
        self.closed = False

    def text(self, query: str, *, max_results: int) -> list[dict[str, str]]:
        _ = query
        _ = max_results
        return self._rows

    def close(self) -> None:
        self.closed = True


def test_sanitize_search_query_collapses_whitespace_and_trims() -> None:
    cleaned = sanitize_search_query("  hello   world \n latest news  ")
    assert cleaned == "hello world latest news"


def test_sanitize_search_query_blocks_credentials() -> None:
    with pytest.raises(ValueError, match="credentials"):
        sanitize_search_query("use sk-secret-key in this query")


def test_sanitize_search_query_respects_max_len() -> None:
    long_q = "word " * 50
    assert len(sanitize_search_query(long_q, max_len=20)) <= 20


def test_web_search_tool_ddgs_parses_results() -> None:
    fake_ddgs = _FakeDdgs(
        [
            {"title": "A", "href": "https://example.com/a", "body": "alpha"},
            {"title": "B", "href": "https://example.com/b", "body": "beta"},
        ]
    )
    tool = WebSearchTool(ddgs_factory=lambda: fake_ddgs)
    out = tool.search("topic", max_results=2)

    assert out.provider == "ddgs"
    assert out.query == "topic"
    assert len(out.results) == 2
    assert out.results[0]["url"] == "https://example.com/a"
    assert out.results[1]["url"] == "https://example.com/b"
    assert fake_ddgs.closed is True


def test_web_search_tool_tavily_propagates_http_client_errors() -> None:
    cfg = WebSearchConfig(provider="tavily")
    tool = WebSearchTool(
        config=cfg, env={"TAVILY_API_KEY": "x"}, client=_FailingClient())
    with pytest.raises(httpx.ReadTimeout):
        tool.search("topic")


def test_web_search_tool_tavily_parses_results() -> None:
    fake_client = _FakeClient(
        {
            "results": [
                {
                    "title": "T1",
                    "url": "https://example.com/a",
                    "content": "S1",
                },
                {
                    "title": "T2",
                    "url": "https://example.com/b",
                    "content": "S2",
                },
            ]
        }
    )
    cfg = WebSearchConfig(
        provider="tavily",
        tavily_api_key_env="TAVILY_API_KEY",
    )
    tool = WebSearchTool(
        config=cfg,
        env={"TAVILY_API_KEY": "fake-key"},
        client=fake_client,
    )
    out = tool.search("hello", max_results=2)

    assert out.provider == "tavily"
    assert out.query == "hello"
    assert len(out.results) == 2
    assert out.results[0]["url"] == "https://example.com/a"
    assert fake_client.last_json is not None
    assert fake_client.last_json["query"] == "hello"
    assert fake_client.last_json["api_key"] == "fake-key"


def test_web_search_tool_tavily_requires_api_key_env() -> None:
    cfg = WebSearchConfig(
        provider="tavily",
        tavily_api_key_env="TAVILY_API_KEY",
    )
    tool = WebSearchTool(config=cfg, env={},
                         client=_FakeClient({"results": []}))
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        tool.search("q")
