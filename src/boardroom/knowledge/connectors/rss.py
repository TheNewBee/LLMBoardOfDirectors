from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem, SourceType

_LOG = logging.getLogger(__name__)


class RSSConnector(KnowledgeConnector):
    """Fetch items from RSS/Atom feeds. Supply feed URLs via feed_urls parameter."""

    def __init__(self, feed_urls: list[str] | None = None) -> None:
        self._feed_urls = feed_urls or []

    @staticmethod
    def _is_safe_feed_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            return False
        if not parsed.hostname:
            return False
        host = parsed.hostname.lower()
        if host in {"localhost"} or host.endswith(".local"):
            return False
        try:
            addr_info = socket.getaddrinfo(host, None)
        except OSError:
            return False
        for entry in addr_info:
            ip = ipaddress.ip_address(entry[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False
        return True

    @property
    def source_type(self) -> SourceType:
        return SourceType.RSS

    def fetch(
        self, query: str, *, domain: str = "", max_items: int = 10
    ) -> list[KnowledgeItem]:
        try:
            import feedparser
        except ImportError:
            _LOG.warning("feedparser not installed; RSS connector disabled.")
            return []

        items: list[KnowledgeItem] = []
        query_lower = query.lower()
        for url in self._feed_urls:
            if not self._is_safe_feed_url(url):
                _LOG.warning("Skipping unsafe RSS feed URL: %r", url)
                continue
            try:
                resp = httpx.get(
                    url,
                    timeout=15,
                    follow_redirects=False,
                    headers={"User-Agent": "Boardroom/0.1 Knowledge Pipeline"},
                )
                if 300 <= resp.status_code < 400:
                    _LOG.warning(
                        "Skipping redirected RSS feed URL=%r status=%s",
                        url,
                        resp.status_code,
                    )
                    continue
                resp.raise_for_status()
                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:max_items]:
                    title = getattr(entry, "title", "")
                    content = getattr(entry, "summary", "") or getattr(entry, "description", "")
                    link = getattr(entry, "link", url)
                    ts = datetime.now(timezone.utc)
                    published = getattr(entry, "published", "")
                    if published:
                        try:
                            ts = parsedate_to_datetime(published)
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                        except Exception:
                            pass
                    if query_lower in title.lower() or query_lower in content.lower():
                        items.append(
                            KnowledgeItem(
                                source_type=SourceType.RSS,
                                url=link,
                                title=title,
                                content=content,
                                timestamp=ts,
                            )
                        )
            except httpx.HTTPStatusError:
                _LOG.warning("RSS feed HTTP error for feed=%r", url, exc_info=True)
            except httpx.RequestError:
                _LOG.warning("RSS feed request failed for feed=%r", url, exc_info=True)
            except Exception:
                _LOG.warning("RSS fetch failed for feed=%r", url, exc_info=True)
            if len(items) >= max_items:
                break
        return items[:max_items]
