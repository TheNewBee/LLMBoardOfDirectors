from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem, SourceType

_LOG = logging.getLogger(__name__)


class RedditConnector(KnowledgeConnector):
    @property
    def source_type(self) -> SourceType:
        return SourceType.REDDIT

    def fetch(
        self, query: str, *, domain: str = "", max_items: int = 10
    ) -> list[KnowledgeItem]:
        search_query = f"{domain} {query}".strip() if domain else query
        url = "https://www.reddit.com/search.json"
        params = {"q": search_query, "limit": max_items, "sort": "relevance", "t": "year"}
        headers = {"User-Agent": "Boardroom/0.1 Knowledge Pipeline"}
        items: list[KnowledgeItem] = []
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])
            for post in posts:
                d = post.get("data", {})
                created = d.get("created_utc", 0)
                ts = datetime.fromtimestamp(created, tz=timezone.utc) if created else datetime.now(timezone.utc)
                content = d.get("selftext", "") or d.get("title", "")
                items.append(
                    KnowledgeItem(
                        source_type=SourceType.REDDIT,
                        url=f"https://reddit.com{d.get('permalink', '')}",
                        title=d.get("title", ""),
                        content=content,
                        timestamp=ts,
                        metadata={
                            "score": str(d.get("score", 0)),
                            "num_comments": str(d.get("num_comments", 0)),
                        },
                    )
                )
        except httpx.HTTPStatusError:
            _LOG.warning("Reddit HTTP error for query=%r", search_query, exc_info=True)
        except httpx.RequestError:
            _LOG.warning("Reddit request failed for query=%r", search_query, exc_info=True)
        except Exception:
            _LOG.warning("Reddit fetch failed for query=%r", search_query, exc_info=True)
        return items
