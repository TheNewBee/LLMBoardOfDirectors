from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from boardroom.knowledge.models import KnowledgeItem, SourceType
from boardroom.vector_store.store import HashEmbeddingFunction

_LOG = logging.getLogger(__name__)


class KnowledgeVectorStore:
    """ChromaDB-backed knowledge storage with per-agent namespaces."""

    def __init__(
        self,
        *,
        persist_dir: Path,
        client: Any | None = None,
    ) -> None:
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._persist_dir = persist_dir
        self._client = client or chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._ef = HashEmbeddingFunction()
        self._meta_path = persist_dir / "_refresh_meta.json"
        self._meta = self._load_meta()

    def _collection_for(self, agent_id: str) -> Any:
        name = self._collection_name(agent_id)
        return self._client.get_or_create_collection(
            name=name,
            embedding_function=self._ef,
        )

    @staticmethod
    def _collection_name(agent_id: str) -> str:
        digest = hashlib.sha256(agent_id.encode("utf-8")).hexdigest()[:16]
        return f"knowledge_{digest}"

    @staticmethod
    def _legacy_collection_name(agent_id: str) -> str:
        return f"knowledge_{agent_id}"[:63]

    def _legacy_collection_for(self, agent_id: str) -> Any | None:
        legacy = self._legacy_collection_name(agent_id)
        if legacy == self._collection_name(agent_id):
            return None
        try:
            return self._client.get_collection(name=legacy, embedding_function=self._ef)
        except Exception:
            return None

    def _replace_collection(self, agent_id: str) -> Any:
        name = self._collection_name(agent_id)
        try:
            self._client.delete_collection(name)
        except Exception:
            # Collection may not exist yet.
            pass
        return self._collection_for(agent_id)

    def store(self, agent_id: str, items: list[KnowledgeItem]) -> None:
        if not items:
            return
        col = self._replace_collection(agent_id)
        ids = [f"{agent_id}_{i}" for i in range(len(items))]
        docs = [item.summary or item.content for item in items]
        metadatas = [
            {
                "source_type": item.source_type.value,
                "url": item.url,
                "title": item.title,
                "quality_score": str(item.quality_score),
                "timestamp": item.timestamp.isoformat(),
            }
            for item in items
        ]
        col.upsert(ids=ids, documents=docs, metadatas=metadatas)
        self.set_refresh_timestamp(agent_id, datetime.now(timezone.utc))

    def retrieve(
        self, agent_id: str, *, query: str, limit: int = 10, max_tokens: int | None = None
    ) -> list[KnowledgeItem]:
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

        items: list[KnowledgeItem] = []
        char_budget = (max_tokens * 4) if max_tokens else None
        chars_used = 0
        for i, doc in enumerate(docs):
            if char_budget and chars_used + len(doc) > char_budget:
                break
            meta = metas[i] if i < len(metas) else {}
            try:
                src = SourceType(meta.get("source_type", "web_search"))
            except ValueError:
                src = SourceType.WEB_SEARCH
            ts_str = meta.get("timestamp", "")
            ts = datetime.now(timezone.utc)
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                except ValueError:
                    pass
            items.append(
                KnowledgeItem(
                    source_type=src,
                    url=meta.get("url", ""),
                    title=meta.get("title", ""),
                    content=doc,
                    quality_score=float(meta.get("quality_score", "0")),
                    timestamp=ts,
                )
            )
            chars_used += len(doc)
        return items

    def last_refresh(self, agent_id: str) -> datetime | None:
        ts_str = self._meta.get(agent_id)
        if not ts_str:
            return None
        try:
            return datetime.fromisoformat(ts_str)
        except ValueError:
            return None

    def set_refresh_timestamp(self, agent_id: str, ts: datetime) -> None:
        self._meta[agent_id] = ts.isoformat()
        self._save_meta()

    def _load_meta(self) -> dict[str, str]:
        if self._meta_path.exists():
            try:
                return json.loads(self._meta_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_meta(self) -> None:
        self._meta_path.write_text(
            json.dumps(self._meta, indent=2), encoding="utf-8"
        )
