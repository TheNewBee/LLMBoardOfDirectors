from __future__ import annotations

from boardroom.knowledge.filtering import DomainFilter
from boardroom.knowledge.models import KnowledgeItem
from boardroom.knowledge.recency import RecencyScorer
from boardroom.knowledge.validation import SourceValidator


class DataQualityScorer:
    """Composite quality score: relevance + recency + authority."""

    def __init__(
        self,
        *,
        threshold: float = 0.3,
        relevance_weight: float = 0.4,
        recency_weight: float = 0.3,
        authority_weight: float = 0.3,
    ) -> None:
        self._threshold = threshold
        self._w_rel = relevance_weight
        self._w_rec = recency_weight
        self._w_auth = authority_weight
        self._domain_filter = DomainFilter()
        self._recency_scorer = RecencyScorer()
        self._source_validator = SourceValidator()

    def score(self, item: KnowledgeItem, domain: str) -> float:
        rel = self._domain_filter.score(item, domain)
        rec = self._recency_scorer.score(item)
        auth = self._source_validator.score(item)
        item.relevance_score = rel
        item.recency_score = rec
        item.authority_score = auth
        item.quality_score = self._w_rel * rel + self._w_rec * rec + self._w_auth * auth
        return item.quality_score

    def filter_items(
        self, items: list[KnowledgeItem], domain: str
    ) -> list[KnowledgeItem]:
        for item in items:
            self.score(item, domain)
        return [item for item in items if item.quality_score >= self._threshold]
