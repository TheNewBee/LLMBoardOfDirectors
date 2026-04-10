from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem, SourceType

_LOG = logging.getLogger(__name__)
_HN_SEARCH_API = "https://hn.algolia.com/api/v1/search"


class HackerNewsConnector(KnowledgeConnector):
    @property
    def source_type(self) -> SourceType:
        return SourceType.HACKERNEWS

    def fetch(
        self, query: str, *, domain: str = "", max_items: int = 10
    ) -> list[KnowledgeItem]:
        search_query = f"{domain} {query}".strip() if domain else query
        params = {"query": search_query, "hitsPerPage": max_items, "tags": "story"}
        items: list[KnowledgeItem] = []
        try:
            resp = httpx.get(_HN_SEARCH_API, params=params, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            for hit in hits:
                ts_str = hit.get("created_at", "")
                ts = datetime.now(timezone.utc)
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                items.append(
                    KnowledgeItem(
                        source_type=SourceType.HACKERNEWS,
                        url=story_url,
                        title=hit.get("title", ""),
                        content=hit.get("story_text", "") or hit.get("title", ""),
                        timestamp=ts,
                        metadata={"points": str(hit.get("points", 0))},
                    )
                )
        except httpx.HTTPStatusError:
            _LOG.warning("HN HTTP error for query=%r", search_query, exc_info=True)
        except httpx.RequestError:
            _LOG.warning("HN request failed for query=%r", search_query, exc_info=True)
        except Exception:
            _LOG.warning("HN fetch failed for query=%r", search_query, exc_info=True)
        return items
