from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.dedup import ContentDeduplicator
from boardroom.knowledge.models import KnowledgeItem
from boardroom.knowledge.scoring import DataQualityScorer
from boardroom.knowledge.summarizer import ContentSummarizer

_LOG = logging.getLogger(__name__)


class KnowledgePipeline:
    """Orchestrates: fetch -> filter -> validate -> summarize -> dedup -> score."""

    def __init__(
        self,
        *,
        connectors: list[KnowledgeConnector],
        quality_threshold: float = 0.3,
        max_items_per_source: int = 20,
        max_workers: int = 4,
    ) -> None:
        self._connectors = connectors
        self._scorer = DataQualityScorer(threshold=quality_threshold)
        self._summarizer = ContentSummarizer()
        self._deduplicator = ContentDeduplicator()
        self._max_items_per_source = max_items_per_source
        self._max_workers = max_workers

    def run(
        self, query: str, domain: str, *, max_total: int = 100
    ) -> list[KnowledgeItem]:
        if not self._connectors:
            return []
        raw_items = self._fetch_all(query, domain)
        if not raw_items:
            return []
        summarized = self._summarizer.apply(raw_items)
        deduped = self._deduplicator.deduplicate(summarized)
        scored = self._scorer.filter_items(deduped, domain)
        scored.sort(key=lambda x: x.quality_score, reverse=True)
        return scored[:max_total]

    def _fetch_all(self, query: str, domain: str) -> list[KnowledgeItem]:
        all_items: list[KnowledgeItem] = []

        def _fetch_one(connector: KnowledgeConnector) -> list[KnowledgeItem]:
            try:
                return connector.fetch(
                    query, domain=domain, max_items=self._max_items_per_source
                )
            except httpx.HTTPStatusError as exc:
                _LOG.warning(
                    "Connector %s HTTP %s for query=%r",
                    connector.source_type.value,
                    exc.response.status_code,
                    query,
                    exc_info=True,
                )
                return []
            except httpx.RequestError:
                _LOG.warning(
                    "Connector %s request failed for query=%r",
                    connector.source_type.value,
                    query,
                    exc_info=True,
                )
                return []
            except Exception:
                _LOG.warning(
                    "Connector %s failed for query=%r",
                    connector.source_type.value,
                    query,
                    exc_info=True,
                )
                return []

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(_fetch_one, c): c for c in self._connectors}
            for future in as_completed(futures):
                all_items.extend(future.result())
        return all_items
