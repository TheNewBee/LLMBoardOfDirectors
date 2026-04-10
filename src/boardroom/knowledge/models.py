from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class SourceType(str, Enum):
    WEB_SEARCH = "web_search"
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    REDDIT = "reddit"
    HACKERNEWS = "hackernews"
    STACKOVERFLOW = "stackoverflow"
    RSS = "rss"
    GITHUB_WIKI = "github_wiki"


@dataclass
class KnowledgeItem:
    source_type: SourceType
    url: str
    title: str
    content: str
    summary: str = ""
    quality_score: float = 0.0
    relevance_score: float = 0.0
    authority_score: float = 0.0
    recency_score: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        text = self.summary or self.content
        return max(1, len(text) // 4)
