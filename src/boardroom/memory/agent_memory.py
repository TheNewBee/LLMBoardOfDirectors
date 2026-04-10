from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from boardroom.models import Message
from boardroom.vector_store.store import HashEmbeddingFunction


@dataclass
class MemoryItem:
    agent_id: str
    meeting_id: str
    content: str
    memory_type: str = "argument"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentMemoryStore:
    """Per-agent memory backed by ChromaDB with isolated collections."""

    def __init__(
        self,
        *,
        persist_dir: Path,
        client: Any | None = None,
    ) -> None:
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = client or chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._ef = HashEmbeddingFunction()

    @staticmethod
    def _collection_name(agent_id: str) -> str:
        digest = hashlib.sha256(agent_id.encode("utf-8")).hexdigest()[:16]
        return f"agent_memory_{digest}"

    @staticmethod
    def _legacy_collection_name(agent_id: str) -> str:
        return f"agent_memory_{agent_id}"[:63]

    def _collection_for(self, agent_id: str) -> Any:
        name = self._collection_name(agent_id)
        return self._client.get_or_create_collection(
            name=name,
            embedding_function=self._ef,
        )

    def _legacy_collection_for(self, agent_id: str) -> Any | None:
        legacy = self._legacy_collection_name(agent_id)
        if legacy == self._collection_name(agent_id):
            return None
        try:
            return self._client.get_collection(name=legacy, embedding_function=self._ef)
        except Exception:
            return None

    def store_memories(self, agent_id: str, items: list[MemoryItem]) -> None:
        if not items:
            return
        col = self._collection_for(agent_id)
        ids = []
        for i, item in enumerate(items):
            payload = (
                f"{item.meeting_id}|{item.agent_id}|{item.memory_type}|"
                f"{item.timestamp}|{item.content}|{i}"
            )
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
            ids.append(f"{item.meeting_id}_{agent_id}_{digest}")
        documents = [item.content for item in items]
        metadatas = [
            {
                "agent_id": item.agent_id,
                "meeting_id": item.meeting_id,
                "memory_type": item.memory_type,
                "timestamp": item.timestamp,
            }
            for item in items
        ]
        col.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def retrieve(
        self,
        agent_id: str,
        *,
        query: str,
        limit: int = 10,
        max_tokens: int | None = None,
    ) -> list[MemoryItem]:
        col = self._collection_for(agent_id)
        count = int(col.count())
        if count == 0:
            legacy = self._legacy_collection_for(agent_id)
            if legacy is not None:
                col = legacy
                count = int(col.count())
        if count == 0:
            return []
        n = min(limit, count)
        results = col.query(query_texts=[query], n_results=n)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        items: list[MemoryItem] = []
        char_budget = (max_tokens * 4) if max_tokens else None
        chars_used = 0
        for i, doc in enumerate(docs):
            if char_budget is not None and chars_used + len(doc) > char_budget:
                break
            meta = metas[i] if i < len(metas) else {}
            items.append(
                MemoryItem(
                    agent_id=meta.get("agent_id", agent_id),
                    meeting_id=meta.get("meeting_id", ""),
                    content=doc,
                    memory_type=meta.get("memory_type", "argument"),
                    timestamp=meta.get("timestamp", ""),
                )
            )
            chars_used += len(doc)
        return items

    @staticmethod
    def extract_from_messages(
        *, messages: list[Message], meeting_id: str
    ) -> list[MemoryItem]:
        items: list[MemoryItem] = []
        for msg in messages:
            items.append(
                MemoryItem(
                    agent_id=msg.agent_id,
                    meeting_id=meeting_id,
                    content=msg.content,
                    memory_type="argument",
                )
            )
        return items
