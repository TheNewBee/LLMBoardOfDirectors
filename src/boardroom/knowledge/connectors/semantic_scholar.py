from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem, SourceType

_LOG = logging.getLogger(__name__)
_S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"


class SemanticScholarConnector(KnowledgeConnector):
    @property
    def source_type(self) -> SourceType:
        return SourceType.SEMANTIC_SCHOLAR

    def fetch(
        self, query: str, *, domain: str = "", max_items: int = 10
    ) -> list[KnowledgeItem]:
        search_query = f"{domain} {query}".strip() if domain else query
        params = {
            "query": search_query,
            "limit": max_items,
            "fields": "title,abstract,url,year,citationCount",
        }
        items: list[KnowledgeItem] = []
        try:
            resp = httpx.get(_S2_API, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            for paper in data:
                year = paper.get("year") or 2020
                ts = datetime(year, 1, 1, tzinfo=timezone.utc)
                items.append(
                    KnowledgeItem(
                        source_type=SourceType.SEMANTIC_SCHOLAR,
                        url=paper.get("url", ""),
                        title=paper.get("title", ""),
                        content=paper.get("abstract", "") or "",
                        timestamp=ts,
                        metadata={"citations": str(paper.get("citationCount", 0))},
                    )
                )
        except httpx.HTTPStatusError:
            _LOG.warning("Semantic Scholar HTTP error for query=%r", search_query, exc_info=True)
        except httpx.RequestError:
            _LOG.warning("Semantic Scholar request failed for query=%r", search_query, exc_info=True)
        except Exception:
            _LOG.warning("Semantic Scholar fetch failed for query=%r", search_query, exc_info=True)
        return items
