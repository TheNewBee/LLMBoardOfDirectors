from __future__ import annotations

from boardroom.knowledge.models import KnowledgeItem


class DomainFilter:
    """Score relevance of a knowledge item to a given domain using keyword overlap."""

    def score(self, item: KnowledgeItem, domain: str) -> float:
        if not domain:
            return 0.5
        domain_tokens = set(domain.lower().split())
        text = f"{item.title} {item.content}".lower()
        text_tokens = set(text.split())
        if not domain_tokens:
            return 0.5
        overlap = domain_tokens & text_tokens
        return min(1.0, len(overlap) / len(domain_tokens))
