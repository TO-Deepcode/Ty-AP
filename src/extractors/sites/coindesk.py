"""CoinDesk specific HTML extraction tweaks."""
from __future__ import annotations

from typing import Dict, Optional

from bs4 import BeautifulSoup

from ..html import extract_article
from ...normalization import normalize_whitespace, parse_datetime


def extract(html: str) -> Dict[str, Optional[str]]:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("div.article-page div.article-text")
    if body:
        paragraphs = [normalize_whitespace(p.get_text()) for p in body.find_all("p") if p.get_text(strip=True)]
        content = "\n".join(paragraphs) if paragraphs else None
    else:
        content = None

    headline = soup.find("h1")
    title = normalize_whitespace(headline.get_text()) if headline else None
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
