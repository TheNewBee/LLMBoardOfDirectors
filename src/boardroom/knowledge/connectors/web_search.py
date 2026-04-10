from __future__ import annotations

import logging
from datetime import datetime, timezone

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem, SourceType

_LOG = logging.getLogger(__name__)


class WebSearchConnector(KnowledgeConnector):
    @property
    def source_type(self) -> SourceType:
        return SourceType.WEB_SEARCH

    def fetch(
        self, query: str, *, domain: str = "", max_items: int = 10
    ) -> list[KnowledgeItem]:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            _LOG.warning("duckduckgo_search not installed; web search connector disabled.")
            return []
        search_query = f"{domain} {query}".strip() if domain else query
        items: list[KnowledgeItem] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(search_query, max_results=max_items):
                    items.append(
                        KnowledgeItem(
                            source_type=SourceType.WEB_SEARCH,
                            url=r.get("href", r.get("link", "")),
                            title=r.get("title", ""),
                            content=r.get("body", r.get("snippet", "")),
                            timestamp=datetime.now(timezone.utc),
                        )
                    )
        except Exception:
            _LOG.warning("Web search failed for query=%r", search_query, exc_info=True)
        return items
