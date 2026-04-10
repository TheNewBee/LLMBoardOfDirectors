from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from boardroom.knowledge.connectors.base import KnowledgeConnector
from boardroom.knowledge.models import KnowledgeItem, SourceType

_LOG = logging.getLogger(__name__)
_ARXIV_API = "https://export.arxiv.org/api/query"


class ArxivConnector(KnowledgeConnector):
    @property
    def source_type(self) -> SourceType:
        return SourceType.ARXIV

    def fetch(
        self, query: str, *, domain: str = "", max_items: int = 10
    ) -> list[KnowledgeItem]:
        search_query = f"{domain} {query}".strip() if domain else query
        params = {
            "search_query": f"all:{search_query}",
            "start": 0,
            "max_results": max_items,
            "sortBy": "relevance",
        }
        items: list[KnowledgeItem] = []
        try:
            resp = httpx.get(_ARXIV_API, params=params, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                summary_el = entry.find("atom:summary", ns)
                link_el = entry.find("atom:id", ns)
                published_el = entry.find("atom:published", ns)
                title = (title_el.text or "").strip() if title_el is not None else ""
                content = (summary_el.text or "").strip() if summary_el is not None else ""
                url = (link_el.text or "").strip() if link_el is not None else ""
                ts = datetime.now(timezone.utc)
                if published_el is not None and published_el.text:
                    try:
                        ts = datetime.fromisoformat(published_el.text.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                items.append(
                    KnowledgeItem(
                        source_type=SourceType.ARXIV,
                        url=url,
                        title=title,
                        content=content,
                        timestamp=ts,
                    )
                )
        except httpx.HTTPStatusError:
            _LOG.warning("ArXiv HTTP error for query=%r", search_query, exc_info=True)
        except httpx.RequestError:
            _LOG.warning("ArXiv request failed for query=%r", search_query, exc_info=True)
        except ET.ParseError:
            _LOG.warning("ArXiv parse failed for query=%r", search_query, exc_info=True)
        except Exception:
            _LOG.warning("ArXiv fetch failed for query=%r", search_query, exc_info=True)
        return items
