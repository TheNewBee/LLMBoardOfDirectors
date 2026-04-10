from __future__ import annotations

from boardroom.knowledge.models import KnowledgeItem


class ContentDeduplicator:
    """Remove near-duplicate items based on content similarity (token overlap)."""

    def __init__(self, similarity_threshold: float = 0.85) -> None:
        self._threshold = similarity_threshold

    def deduplicate(self, items: list[KnowledgeItem]) -> list[KnowledgeItem]:
        if not items:
            return []
        kept: list[KnowledgeItem] = []
        seen_signatures: list[set[str]] = []
        for item in items:
            tokens = set(item.content.lower().split())
            is_dup = False
            for sig in seen_signatures:
                if not tokens or not sig:
                    continue
                overlap = len(tokens & sig) / max(len(tokens), len(sig))
                if overlap >= self._threshold:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(item)
                seen_signatures.append(tokens)
        return kept
