from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from boardroom.models import WebSearchConfig

_WHITESPACE_RE = re.compile(r"\s+")
_POTENTIAL_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9]|api[_-]?key|authorization:|bearer\s+)", re.IGNORECASE
)


def sanitize_search_query(query: str, *, max_len: int = 160) -> str:
    sanitized = _WHITESPACE_RE.sub(" ", query).strip()
    if not sanitized:
        raise ValueError("Search query cannot be empty.")
    if _POTENTIAL_SECRET_RE.search(sanitized):
        raise ValueError("Search query appears to contain credentials.")
    return sanitized[:max_len]


@dataclass(frozen=True)
class WebSearchResult:
    query: str
    provider: str
    results: list[dict[str, str]]


class WebSearchTool:
    def __init__(
        self,
        *,
        config: WebSearchConfig | None = None,
        env: Mapping[str, str] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config or WebSearchConfig()
        self._env: Mapping[str, str] = env if env is not None else os.environ
        timeout = float(self._config.timeout_seconds)
        self._client = client or httpx.Client(timeout=timeout)

    @property
    def max_results_cap(self) -> int:
        return int(self._config.max_results_cap)

    def search(self, query: str, *, max_results: int = 3) -> WebSearchResult:
        clean = sanitize_search_query(
            query, max_len=int(self._config.query_max_len))
        cap = max(1, min(10, int(max_results)))
        if self._config.provider == "google":
            return self._search_google(clean, cap)
        return self._search_duckduckgo(clean, cap)

    def _search_duckduckgo(self, clean: str, max_results: int) -> WebSearchResult:
        url = str(self._config.duckduckgo_url).rstrip("/") + "/"
        response = self._client.get(
            url,
            params={
                "q": clean,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            },
        )
        response.raise_for_status()
        payload = response.json()
        rows: list[dict[str, str]] = []

        abstract_text = str(payload.get("AbstractText") or "").strip()
        abstract_url = str(payload.get("AbstractURL") or "").strip()
        if abstract_text and abstract_url:
            rows.append(
                {
                    "title": str(payload.get("Heading") or "DuckDuckGo Abstract"),
                    "url": abstract_url,
                    "snippet": abstract_text,
                }
            )

        for topic in payload.get("RelatedTopics", []):
            if len(rows) >= max_results:
                break
            if not isinstance(topic, dict):
                continue
            text = str(topic.get("Text") or "").strip()
            link = str(topic.get("FirstURL") or "").strip()
            if not text or not link:
                continue
            rows.append({"title": text[:80], "url": link, "snippet": text})

        return WebSearchResult(
            query=clean, provider="duckduckgo", results=rows[:max_results])

    def _search_google(self, clean: str, max_results: int) -> WebSearchResult:
        api_key = str(
            self._env.get(self._config.google_api_key_env, "") or "").strip()
        if not api_key:
            raise ValueError(
                f"Missing environment variable {self._config.google_api_key_env!r} "
                "for Google web search.",
            )
        cx = self._config.google_cse_id.strip()
        num = min(10, max(1, max_results))
        base = str(self._config.google_api_url).rstrip("/")
        response = self._client.get(
            base,
            params={
                "key": api_key,
                "cx": cx,
                "q": clean,
                "num": str(num),
            },
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        rows: list[dict[str, str]] = []
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            link = str(item.get("link") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if link:
                rows.append(
                    {"title": title or link, "url": link, "snippet": snippet})
            if len(rows) >= max_results:
                break

        return WebSearchResult(
            query=clean, provider="google", results=rows[:max_results])
