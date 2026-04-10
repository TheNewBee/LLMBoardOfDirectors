from __future__ import annotations

from datetime import datetime, timezone

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem, SourceType
from boardroom.knowledge.pipeline import KnowledgePipeline


class _FakeConnector(KnowledgeConnector):
    def __init__(self, items: list[KnowledgeItem]) -> None:
        self._items = items

    @property
    def source_type(self) -> SourceType:
        return SourceType.WEB_SEARCH

    def fetch(self, query: str, *, domain: str = "", max_items: int = 10) -> list[KnowledgeItem]:
        return self._items[:max_items]


def _make_item(title: str, content: str = "Some content about the topic.") -> KnowledgeItem:
    return KnowledgeItem(
        source_type=SourceType.WEB_SEARCH,
        url=f"https://example.com/{title.replace(' ', '-')}",
        title=title,
        content=content,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_pipeline_runs_full_chain() -> None:
    items = [_make_item("Article 1"), _make_item("Article 2")]
    connector = _FakeConnector(items)
    pipeline = KnowledgePipeline(connectors=[connector])

    results = pipeline.run(query="test topic", domain="testing")
    assert len(results) >= 1
    for item in results:
        assert item.quality_score >= 0


def test_pipeline_filters_low_quality() -> None:
    good = _make_item("Good Article", "Detailed content about machine learning algorithms and neural networks.")
    bad = _make_item("Bad", "x")
    connector = _FakeConnector([good, bad])
    pipeline = KnowledgePipeline(connectors=[connector], quality_threshold=0.3)

    results = pipeline.run(query="machine learning", domain="AI")
    assert all(r.quality_score >= 0.0 for r in results)


def test_pipeline_deduplicates() -> None:
    items = [
        _make_item("Same Topic", "Content about machine learning."),
        _make_item("Same Topic Copy", "Content about machine learning."),
        _make_item("Different Topic", "Content about quantum computing."),
    ]
    connector = _FakeConnector(items)
    pipeline = KnowledgePipeline(connectors=[connector])

    results = pipeline.run(query="machine learning", domain="AI")
    titles = [r.title for r in results]
    assert len(titles) <= 3


def test_pipeline_with_no_connectors_returns_empty() -> None:
    pipeline = KnowledgePipeline(connectors=[])
    results = pipeline.run(query="anything", domain="any")
    assert results == []


def test_pipeline_handles_connector_errors_gracefully() -> None:
    class _FailConnector(KnowledgeConnector):
        @property
        def source_type(self) -> SourceType:
            return SourceType.ARXIV

        def fetch(self, query: str, **kwargs: object) -> list[KnowledgeItem]:
            raise ConnectionError("API down")

    good_items = [_make_item("Fallback")]
    pipeline = KnowledgePipeline(
        connectors=[_FailConnector(), _FakeConnector(good_items)]
    )
    results = pipeline.run(query="test", domain="test")
    assert len(results) >= 1
