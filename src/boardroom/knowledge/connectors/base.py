from __future__ import annotations

from abc import ABC, abstractmethod

from boardroom.knowledge.models import KnowledgeItem, SourceType


class KnowledgeConnector(ABC):
    """Abstract base for all knowledge source connectors."""

    @property
    @abstractmethod
    def source_type(self) -> SourceType: ...

    @abstractmethod
    def fetch(
        self, query: str, *, domain: str = "", max_items: int = 10
    ) -> list[KnowledgeItem]: ...
