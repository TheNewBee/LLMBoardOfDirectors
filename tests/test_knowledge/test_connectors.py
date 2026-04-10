from __future__ import annotations

import pytest

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.connectors.web_search import WebSearchConnector
from boardroom.knowledge.connectors.arxiv import ArxivConnector
from boardroom.knowledge.connectors.semantic_scholar import SemanticScholarConnector
from boardroom.knowledge.connectors.reddit import RedditConnector
from boardroom.knowledge.connectors.hackernews import HackerNewsConnector
from boardroom.knowledge.connectors.stackoverflow import StackOverflowConnector
from boardroom.knowledge.connectors.rss import RSSConnector
from boardroom.knowledge.connectors.github_wiki import GitHubWikiConnector
from boardroom.knowledge.models import SourceType


def test_all_connectors_implement_interface() -> None:
    connectors: list[KnowledgeConnector] = [
        WebSearchConnector(),
        ArxivConnector(),
        SemanticScholarConnector(),
        RedditConnector(),
        HackerNewsConnector(),
        StackOverflowConnector(),
        RSSConnector(),
        GitHubWikiConnector(),
    ]
    assert len(connectors) == 8
    for c in connectors:
        assert isinstance(c.source_type, SourceType)
        assert hasattr(c, "fetch")


def test_web_search_connector_source_type() -> None:
    c = WebSearchConnector()
    assert c.source_type == SourceType.WEB_SEARCH


def test_arxiv_connector_source_type() -> None:
    c = ArxivConnector()
    assert c.source_type == SourceType.ARXIV


def test_semantic_scholar_source_type() -> None:
    c = SemanticScholarConnector()
    assert c.source_type == SourceType.SEMANTIC_SCHOLAR


def test_reddit_connector_source_type() -> None:
    c = RedditConnector()
    assert c.source_type == SourceType.REDDIT


def test_hackernews_connector_source_type() -> None:
    c = HackerNewsConnector()
    assert c.source_type == SourceType.HACKERNEWS


def test_stackoverflow_connector_source_type() -> None:
    c = StackOverflowConnector()
    assert c.source_type == SourceType.STACKOVERFLOW


def test_rss_connector_source_type() -> None:
    c = RSSConnector()
    assert c.source_type == SourceType.RSS


def test_github_wiki_connector_source_type() -> None:
    c = GitHubWikiConnector()
    assert c.source_type == SourceType.GITHUB_WIKI


def test_rss_connector_rejects_unsafe_urls_without_request(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = RSSConnector(feed_urls=["http://169.254.169.254/latest/meta-data"])

    def _fail_http_get(*args: object, **kwargs: object) -> object:
        raise AssertionError("httpx.get should not be called for unsafe RSS URLs")

    monkeypatch.setattr("boardroom.knowledge.connectors.rss.httpx.get", _fail_http_get)
    results = connector.fetch("metadata", max_items=5)
    assert results == []
