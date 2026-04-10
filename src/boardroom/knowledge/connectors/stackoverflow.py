from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem, SourceType

_LOG = logging.getLogger(__name__)
_SO_API = "https://api.stackexchange.com/2.3/search/advanced"


class StackOverflowConnector(KnowledgeConnector):
    @property
    def source_type(self) -> SourceType:
        return SourceType.STACKOVERFLOW

    def fetch(
        self, query: str, *, domain: str = "", max_items: int = 10
    ) -> list[KnowledgeItem]:
        search_query = f"{domain} {query}".strip() if domain else query
        params = {
            "q": search_query,
            "pagesize": max_items,
            "order": "desc",
            "sort": "relevance",
            "site": "stackoverflow",
            "filter": "default",
        }
        items: list[KnowledgeItem] = []
        try:
            resp = httpx.get(_SO_API, params=params, timeout=15)
            resp.raise_for_status()
            questions = resp.json().get("items", [])
            for q in questions:
                created = q.get("creation_date", 0)
                ts = datetime.fromtimestamp(created, tz=timezone.utc) if created else datetime.now(timezone.utc)
                tags = q.get("tags", [])
                items.append(
                    KnowledgeItem(
                        source_type=SourceType.STACKOVERFLOW,
                        url=q.get("link", ""),
                        title=q.get("title", ""),
                        content=q.get("title", ""),
                        timestamp=ts,
                        metadata={
                            "score": str(q.get("score", 0)),
                            "answer_count": str(q.get("answer_count", 0)),
                            "tags": ",".join(tags),
                        },
                    )
                )
        except httpx.HTTPStatusError:
            _LOG.warning("StackOverflow HTTP error for query=%r", search_query, exc_info=True)
        except httpx.RequestError:
            _LOG.warning("StackOverflow request failed for query=%r", search_query, exc_info=True)
        except Exception:
            _LOG.warning("StackOverflow fetch failed for query=%r", search_query, exc_info=True)
        return items
