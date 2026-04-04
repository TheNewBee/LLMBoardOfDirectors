from __future__ import annotations

import pytest
import httpx

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
        self.last_params: dict[str, str] | None = None

    def get(self, url: str, params: dict[str, str]) -> _FakeResponse:
        _ = url
        self.last_params = params
        return _FakeResponse(self._payload)


class _FailingClient:
    def get(self, url: str, params: dict[str, str]) -> _FakeResponse:
        _ = url
        _ = params
        raise httpx.ReadTimeout("timeout")


def test_sanitize_search_query_collapses_whitespace_and_trims() -> None:
    cleaned = sanitize_search_query("  hello   world \n latest news  ")
    assert cleaned == "hello world latest news"


def test_sanitize_search_query_blocks_credentials() -> None:
    with pytest.raises(ValueError, match="credentials"):
        sanitize_search_query("use sk-secret-key in this query")


def test_sanitize_search_query_respects_max_len() -> None:
    long_q = "word " * 50
    assert len(sanitize_search_query(long_q, max_len=20)) <= 20


def test_web_search_tool_parses_abstract_and_related_topics() -> None:
    fake_client = _FakeClient(
        {
            "Heading": "Topic",
            "AbstractText": "Primary summary",
            "AbstractURL": "https://example.com/primary",
            "RelatedTopics": [
                {"Text": "Extra result one", "FirstURL": "https://example.com/1"},
                {"Text": "Extra result two", "FirstURL": "https://example.com/2"},
            ],
        }
    )
    tool = WebSearchTool(client=fake_client)
    out = tool.search("topic", max_results=2)

    assert out.provider == "duckduckgo"
    assert out.query == "topic"
    assert len(out.results) == 2
    assert out.results[0]["url"] == "https://example.com/primary"
    assert out.results[1]["url"] == "https://example.com/1"
    assert fake_client.last_params is not None
    assert fake_client.last_params["q"] == "topic"


def test_web_search_tool_propagates_http_client_errors() -> None:
    tool = WebSearchTool(client=_FailingClient())
    with pytest.raises(httpx.ReadTimeout):
        tool.search("topic")


def test_web_search_tool_google_parses_items() -> None:
    fake_client = _FakeClient(
        {
            "items": [
                {
                    "title": "T1",
                    "link": "https://example.com/a",
                    "snippet": "S1",
                },
                {
                    "title": "T2",
                    "link": "https://example.com/b",
                    "snippet": "S2",
                },
            ]
        }
    )
    cfg = WebSearchConfig(
        provider="google",
        google_cse_id="cx123",
        google_api_key_env="GOOGLE_CSE_API_KEY",
    )
    tool = WebSearchTool(
        config=cfg,
        env={"GOOGLE_CSE_API_KEY": "fake-key"},
        client=fake_client,
    )
    out = tool.search("hello", max_results=2)

    assert out.provider == "google"
    assert out.query == "hello"
    assert len(out.results) == 2
    assert out.results[0]["url"] == "https://example.com/a"
    assert fake_client.last_params is not None
    assert fake_client.last_params["cx"] == "cx123"
    assert fake_client.last_params["key"] == "fake-key"


def test_web_search_tool_google_requires_api_key_env() -> None:
    cfg = WebSearchConfig(
        provider="google",
        google_cse_id="cx",
        google_api_key_env="GOOGLE_CSE_API_KEY",
    )
    tool = WebSearchTool(config=cfg, env={}, client=_FakeClient({}))
    with pytest.raises(ValueError, match="GOOGLE_CSE_API_KEY"):
        tool.search("q")
