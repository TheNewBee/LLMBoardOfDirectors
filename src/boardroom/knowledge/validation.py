from __future__ import annotations

from urllib.parse import urlparse

from boardroom.knowledge.models import KnowledgeItem

_HIGH_AUTHORITY_DOMAINS = frozenset({
    "arxiv.org", "scholar.google.com", "semanticscholar.org",
    "nature.com", "science.org", "ieee.org", "acm.org",
    "github.com", "stackoverflow.com", "wikipedia.org",
    "nytimes.com", "reuters.com", "bbc.com", "bloomberg.com",
    "docs.python.org", "readthedocs.io",
})

_BLOCKLIST_DOMAINS = frozenset({
    "pinterest.com", "quora.com",
})


class SourceValidator:
    """Score source authority based on domain reputation."""

    def score(self, item: KnowledgeItem) -> float:
        try:
            host = urlparse(item.url).hostname or ""
        except Exception:
            return 0.3
        host_lower = host.lower()
        if any(d in host_lower for d in _BLOCKLIST_DOMAINS):
            return 0.0
        if any(d in host_lower for d in _HIGH_AUTHORITY_DOMAINS):
            return 0.9
        if host_lower.endswith(".edu") or host_lower.endswith(".gov"):
            return 0.85
        return 0.4
