"""RSS extraction helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import feedparser

from ..http_clients import request_text
from ..logging_setup import get_logger
from ..normalization import normalize_whitespace, parse_datetime

logger = get_logger(__name__)


def fetch_rss_feed(url: str, max_items: int = 50) -> List[Dict[str, Any]]:
    logger.info("fetch_rss", url=url)
    xml = request_text("GET", url)
    feed = feedparser.parse(xml)

    entries: List[Dict[str, Any]] = []
    for entry in feed.entries[:max_items]:
        published = None
        for key in ("published", "updated", "created"):
            value = entry.get(key)
            if value:
                published = parse_datetime(value)
                if published:
                    break
        summary = entry.get("summary") or entry.get("description")
        entries.append(
            {
                "title": normalize_whitespace(entry.get("title", "")),
                "link": entry.get("link"),
                "summary": normalize_whitespace(summary) if summary else None,
                "published_at": published,
            }
        )
    return entries
