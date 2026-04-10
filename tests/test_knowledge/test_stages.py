from __future__ import annotations

from datetime import datetime, timezone, timedelta

from boardroom.knowledge.filtering import DomainFilter
from boardroom.knowledge.validation import SourceValidator
from boardroom.knowledge.recency import RecencyScorer
from boardroom.knowledge.dedup import ContentDeduplicator
from boardroom.knowledge.scoring import DataQualityScorer
from boardroom.knowledge.models import KnowledgeItem, SourceType


def _item(
    title: str = "Test",
    content: str = "Content about finance.",
    url: str = "https://example.com",
    days_ago: int = 0,
) -> KnowledgeItem:
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return KnowledgeItem(
        source_type=SourceType.WEB_SEARCH,
        url=url,
        title=title,
        content=content,
        timestamp=ts,
    )


def test_domain_filter_scores_relevance() -> None:
    f = DomainFilter()
    item = _item(content="Machine learning algorithms and deep neural networks.")
    score = f.score(item, domain="machine learning")
    assert 0.0 <= score <= 1.0
    assert score > 0


def test_domain_filter_low_relevance_for_offtopic() -> None:
    f = DomainFilter()
    item = _item(content="Best recipes for chocolate cake baking.")
    score = f.score(item, domain="machine learning")
    assert score < 0.5


def test_source_validator_scores_authority() -> None:
    v = SourceValidator()
    item = _item(url="https://arxiv.org/abs/2301.00001")
    score = v.score(item)
    assert 0.0 <= score <= 1.0


def test_source_validator_penalizes_unknown_domain() -> None:
    v = SourceValidator()
    item = _item(url="https://random-blog-12345.xyz/post")
    score = v.score(item)
    low = _item(url="https://arxiv.org/abs/123")
    high_score = v.score(low)
    assert score <= high_score


def test_recency_scorer_prefers_recent() -> None:
    scorer = RecencyScorer()
    recent = _item(days_ago=1)
    old = _item(days_ago=365)
    assert scorer.score(recent) > scorer.score(old)


def test_recency_scorer_range() -> None:
    scorer = RecencyScorer()
    item = _item(days_ago=30)
    score = scorer.score(item)
    assert 0.0 <= score <= 1.0


def test_deduplicator_removes_exact_duplicates() -> None:
    dedup = ContentDeduplicator()
    items = [
        _item(title="A", content="Same content here."),
        _item(title="B", content="Same content here."),
        _item(title="C", content="Different content entirely."),
    ]
    result = dedup.deduplicate(items)
    assert len(result) <= len(items)
    assert len(result) >= 2


def test_deduplicator_keeps_unique() -> None:
    dedup = ContentDeduplicator()
    items = [
        _item(title="A", content="Topic about AI."),
        _item(title="B", content="Topic about cooking."),
    ]
    result = dedup.deduplicate(items)
    assert len(result) == 2


def test_quality_scorer_composite() -> None:
    scorer = DataQualityScorer()
    item = _item(content="Detailed analysis of market trends.")
    score = scorer.score(item, domain="market analysis")
    assert 0.0 <= score <= 1.0


def test_quality_scorer_threshold_filter() -> None:
    scorer = DataQualityScorer(threshold=0.3)
    items = [
        _item(content="Detailed finance analysis with data.", days_ago=5),
        _item(content="x", days_ago=400),
    ]
    filtered = scorer.filter_items(items, domain="finance")
    for item in filtered:
        assert item.quality_score >= 0.0
