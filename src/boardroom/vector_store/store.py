from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from datetime import timezone
from pathlib import Path
from typing import Any, Protocol

import chromadb
from chromadb.config import Settings

from boardroom.models import MeetingState

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class EmbeddingFunction(Protocol):
    def __call__(self, input: Sequence[str]) -> list[list[float]]:
        ...


class HashEmbeddingFunction:
    """Small deterministic embedding function for local/offline usage."""

    def __init__(self, *, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def __call__(self, input: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(
                token.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest, "big") % self.dimensions
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            return vec
        return [v / norm for v in vec]


class MeetingVectorStore:
    def __init__(
        self,
        *,
        persist_dir: Path,
        collection_name: str = "boardroom_meetings",
        embedding_function: EmbeddingFunction | None = None,
        client: Any | None = None,
    ) -> None:
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = client or chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function or HashEmbeddingFunction(),
        )

    def upsert_meeting(self, *, meeting: MeetingState, transcript_markdown: str) -> None:
        if not transcript_markdown.strip():
            return
        started = meeting.start_time
        if started.tzinfo is not None:
            started = started.astimezone(timezone.utc).replace(tzinfo=None)
        metadata = {
            "meeting_id": meeting.meeting_id,
            "turn_count": meeting.turn_count,
            "termination_reason": meeting.termination_reason.value
            if meeting.termination_reason is not None
            else "n/a",
            "started_at": started.isoformat(),
        }
        self._collection.upsert(
            ids=[meeting.meeting_id],
            documents=[transcript_markdown],
            metadatas=[metadata],
        )

    def search(self, *, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not query.strip():
            return []
        collection_count = int(self._collection.count())
        if collection_count <= 0:
            return []
        n_results = min(max(1, limit), collection_count)
        out = self._collection.query(
            query_texts=[query],
            n_results=n_results,
        )
        ids = out.get("ids", [[]])[0]
        documents = out.get("documents", [[]])[0]
        metadatas = out.get("metadatas", [[]])[0]
        distances = out.get("distances", [[]])[0]
        rows: list[dict[str, Any]] = []
        for idx, doc_id in enumerate(ids):
            rows.append(
                {
                    "id": doc_id,
                    "document": documents[idx] if idx < len(documents) else "",
                    "metadata": metadatas[idx] if idx < len(metadatas) else {},
                    "distance": distances[idx] if idx < len(distances) else None,
                }
            )
        return rows
