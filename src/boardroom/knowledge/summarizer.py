from __future__ import annotations

from boardroom.knowledge.models import KnowledgeItem


class ContentSummarizer:
    """Summarize content to fit token budgets. Uses truncation by default;
    can be upgraded to LLM-based summarization later."""

    def __init__(self, max_chars: int = 1000) -> None:
        self._max_chars = max_chars

    def summarize(self, item: KnowledgeItem) -> str:
        content = item.content.strip()
        if len(content) <= self._max_chars:
            return content
        return content[: self._max_chars].rsplit(" ", 1)[0] + "..."

    def apply(self, items: list[KnowledgeItem]) -> list[KnowledgeItem]:
        for item in items:
            item.summary = self.summarize(item)
        return items
