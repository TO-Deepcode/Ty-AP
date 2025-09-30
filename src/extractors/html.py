"""Generic HTML article extraction utilities."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from bs4 import BeautifulSoup

from ..logging_setup import get_logger
from ..normalization import normalize_whitespace, parse_datetime

logger = get_logger(__name__)


class ExtractionResult(Dict[str, Optional[str]]):
    pass


ARTICLE_SELECTORS = [
    "article",
    "div.article-content",
    "div.post-body",
    "div.entry-content",
]


TIME_META_KEYS = [
    ("meta", {"property": "article:published_time"}),
    ("meta", {"name": "pubdate"}),
    ("meta", {"name": "date"}),
    ("time", {}),
]


def extract_article(html: str) -> Dict[str, Optional[str]]:
    soup = BeautifulSoup(html, "html.parser")

    title = _extract_title(soup)
    summary = _extract_summary(soup)
    body = _extract_body(soup)
    published_at = _extract_published_at(soup)

    return {
        "title": title,
        "summary": summary,
        "content": body,
        "published_at": published_at.isoformat() if published_at else None,
    }


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    if soup.find("meta", property="og:title"):
        return normalize_whitespace(soup.find("meta", property="og:title")["content"])
    if soup.title:
        return normalize_whitespace(soup.title.get_text())
    return None


def _extract_summary(soup: BeautifulSoup) -> Optional[str]:
    tag = soup.find("meta", attrs={"name": "description"})
    if tag and tag.get("content"):
        return normalize_whitespace(tag["content"])
    tag = soup.find("meta", property="og:description")
    if tag and tag.get("content"):
        return normalize_whitespace(tag["content"])
    return None


def _extract_body(soup: BeautifulSoup) -> Optional[str]:
    for selector in ARTICLE_SELECTORS:
        container = soup.select_one(selector)
        if container:
            paragraphs = [normalize_whitespace(p.get_text()) for p in container.find_all("p") if p.get_text(strip=True)]
            if paragraphs:
                return "\n".join(paragraphs)
    paragraphs = [normalize_whitespace(p.get_text()) for p in soup.find_all("p") if p.get_text(strip=True)]
    if paragraphs:
        return "\n".join(paragraphs)
    return None


def _extract_published_at(soup: BeautifulSoup) -> Optional[datetime]:
    for tag_name, attrs in TIME_META_KEYS:
        tag = soup.find(tag_name, attrs=attrs)
        if tag:
            content = tag.get("content") or tag.get_text()
            parsed = parse_datetime(content)
            if parsed:
                return parsed
    return None
