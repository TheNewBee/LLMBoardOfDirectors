from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem, SourceType

_LOG = logging.getLogger(__name__)


class GitHubWikiConnector(KnowledgeConnector):
    """Fetch content from GitHub repositories via the search API."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.GITHUB_WIKI

    def fetch(
        self, query: str, *, domain: str = "", max_items: int = 10
    ) -> list[KnowledgeItem]:
        search_query = f"{domain} {query}".strip() if domain else query
        url = "https://api.github.com/search/repositories"
        params = {"q": search_query, "per_page": max_items, "sort": "stars"}
        headers = {"Accept": "application/vnd.github.v3+json"}
        items: list[KnowledgeItem] = []
        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            repos = resp.json().get("items", [])
            for repo in repos:
                updated = repo.get("updated_at", "")
                ts = datetime.now(timezone.utc)
                if updated:
                    try:
                        ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                items.append(
                    KnowledgeItem(
                        source_type=SourceType.GITHUB_WIKI,
                        url=repo.get("html_url", ""),
                        title=repo.get("full_name", ""),
                        content=repo.get("description", "") or "",
                        timestamp=ts,
                        metadata={"stars": str(repo.get("stargazers_count", 0))},
                    )
                )
        except httpx.HTTPStatusError:
            _LOG.warning("GitHub HTTP error for query=%r", search_query, exc_info=True)
        except httpx.RequestError:
            _LOG.warning("GitHub request failed for query=%r", search_query, exc_info=True)
        except Exception:
            _LOG.warning("GitHub fetch failed for query=%r", search_query, exc_info=True)
        return items
