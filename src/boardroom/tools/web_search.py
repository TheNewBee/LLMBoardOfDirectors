from __future__ import annotations

import importlib
import os
import re
from collections.abc import Callable, Iterable, Mapping
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


def _default_ddgs_factory() -> Any:
    try:
        module = importlib.import_module("ddgs")
        ddgs_cls = getattr(module, "DDGS")
    except ImportError as exc:
        raise ValueError(
            "DDGS backend is selected but package 'ddgs' is not installed."
        ) from exc
    return ddgs_cls()


class WebSearchTool:
    def __init__(
        self,
        *,
        config: WebSearchConfig | None = None,
        env: Mapping[str, str] | None = None,
        client: httpx.Client | None = None,
        ddgs_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._config = config or WebSearchConfig()
        self._env: Mapping[str, str] = env if env is not None else os.environ
        timeout = float(self._config.timeout_seconds)
        self._client = client or httpx.Client(timeout=timeout)
        self._ddgs_factory = ddgs_factory or _default_ddgs_factory

    @property
    def max_results_cap(self) -> int:
        return int(self._config.max_results_cap)

    def search(self, query: str, *, max_results: int = 3) -> WebSearchResult:
        clean = sanitize_search_query(
            query, max_len=int(self._config.query_max_len))
        requested = max(1, int(max_results))
        cap = min(int(self._config.max_results_cap), requested)
        if self._config.provider == "tavily":
            return self._search_tavily(clean, cap)
        return self._search_ddgs(clean, cap)

    def _search_ddgs(self, clean: str, max_results: int) -> WebSearchResult:
        rows: list[dict[str, str]] = []
        ddgs = self._ddgs_factory()
        try:
            raw_rows: Iterable[dict[str, Any]] = ddgs.text(
                clean, max_results=max_results)
            for row in raw_rows:
                if len(rows) >= max_results:
                    break
                if not isinstance(row, dict):
                    continue
                title = str(row.get("title") or row.get(
                    "source") or "").strip()
                url = str(row.get("href") or row.get("url") or "").strip()
                snippet = str(
                    row.get("body") or row.get(
                        "snippet") or row.get("description") or ""
                ).strip()
                if not url:
                    continue
                rows.append(
                    {"title": title or url, "url": url, "snippet": snippet})
        finally:
            closer = getattr(ddgs, "close", None)
            if callable(closer):
                closer()
        return WebSearchResult(query=clean, provider="ddgs", results=rows[:max_results])

    def _search_tavily(self, clean: str, max_results: int) -> WebSearchResult:
        api_key = str(self._env.get(
            self._config.tavily_api_key_env, "") or "").strip()
        if not api_key:
            raise ValueError(
                f"Missing environment variable {self._config.tavily_api_key_env!r} "
                "for Tavily web search.",
            )
        response = self._client.post(
            str(self._config.tavily_api_url),
            json={
                "api_key": api_key,
                "query": clean,
                "search_depth": self._config.tavily_search_depth,
                "max_results": max_results,
            },
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        rows: list[dict[str, str]] = []
        for row in payload.get("results", []):
            if len(rows) >= max_results:
                break
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            url = str(row.get("url") or "").strip()
            snippet = str(row.get("content") or row.get(
                "snippet") or "").strip()
            if not url:
                continue
            rows.append(
                {"title": title or url, "url": url, "snippet": snippet})
        return WebSearchResult(query=clean, provider="tavily", results=rows[:max_results])
