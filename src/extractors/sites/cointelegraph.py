"""Cointelegraph specific extraction tweaks."""
from __future__ import annotations

from typing import Dict, Optional

from bs4 import BeautifulSoup

from ..html import extract_article
from ...normalization import normalize_whitespace, parse_datetime


def extract(html: str) -> Dict[str, Optional[str]]:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    content = None
    if article:
        paragraphs = [normalize_whitespace(p.get_text()) for p in article.find_all("p") if p.get_text(strip=True)]
        if paragraphs:
            content = "\n".join(paragraphs)
    title_tag = soup.find("h1")
    title = normalize_whitespace(title_tag.get_text()) if title_tag else None
    summary_tag = soup.find("h2")
    summary = normalize_whitespace(summary_tag.get_text()) if summary_tag else None
    time_tag = soup.find("time")
    published = parse_datetime(time_tag.get("datetime")) if time_tag else None

    base = extract_article(html)
    base.update(
        {
            "title": title or base.get("title"),
            "summary": summary or base.get("summary"),
            "content": content or base.get("content"),
            "published_at": (published.isoformat() if published else base.get("published_at")),
        }
    )
    return base
