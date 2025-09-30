"""Fetch and normalize news articles across multiple crypto publishers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from src.api_utils import BaseJsonHandler, parse_json
from src.config import get_settings
from src.confirm import SOURCE_SCORES
from src.dedupe import DedupeIndex, near_duplicate
from src.extractors.html import extract_article
from src.extractors.rss import fetch_rss_feed
from src.extractors.sites import get_extractor
from src.http_clients import request_text
from src.logging_setup import get_logger
from src.normalization import canonicalize_url, deterministic_hash, domain_from_url, parse_datetime
from src.rate_limit import allow_request
from src.schemas import NewsFetchRequest, NewsFetchResponse, NewsItem
from src.storage import get_storage

logger = get_logger(__name__)

ORIGIN = "aws-webse"
ROBOTS_CACHE: Dict[str, RobotFileParser] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_robots(url: str) -> RobotFileParser:
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base in ROBOTS_CACHE:
        return ROBOTS_CACHE[base]
    robots = RobotFileParser()
    robots_url = urljoin(base, "/robots.txt")
    try:
        content = request_text("GET", robots_url)
    except Exception as exc:  # pragma: no cover - fallback path
        logger.warning("robots_fetch_failed", url=robots_url, error=str(exc))
        robots.set_url(robots_url)
        robots.read()
        ROBOTS_CACHE[base] = robots
        return robots
    robots.parse(content.splitlines())
    ROBOTS_CACHE[base] = robots
    return robots


def _allowed(url: str) -> bool:
    settings = get_settings()
    robots = _get_robots(url)
    user_agent = settings.user_agent
    allowed = robots.can_fetch(user_agent, url)
    if not allowed:
        logger.info("robots_block", url=url)
    return allowed


def _fetch_article(source: str, url: str) -> Dict[str, Optional[str]]:
    extractor = get_extractor(source)
    html = request_text("GET", url)
    if extractor:
        return extractor(html)
    return extract_article(html)


def _build_news_item(source: str, entry: Dict[str, Any], since: Optional[datetime]) -> Optional[NewsItem]:
    link = entry.get("link")
    if not link:
        return None
    if since and entry.get("published_at") and entry["published_at"] < since:
        return None
    canonical_url = canonicalize_url(link)
    if not _allowed(link):
        return None
    domain = domain_from_url(link)
    if not allow_request(domain):
        logger.info("rate_limit_skip", source=source, url=link)
        return None
    article = _fetch_article(source, link)
    published = entry.get("published_at") or parse_datetime(article.get("published_at")) or _now()
    content = article.get("content")
    title = article.get("title") or entry.get("title") or canonical_url
    if since and published < since:
        return None
    news_id = deterministic_hash(source, canonical_url, title)
    item = NewsItem(
        origin=ORIGIN,
        id=news_id,
        source=source,
        url=canonical_url,
        title=title,
        summary=article.get("summary") or entry.get("summary"),
        published_at=published,
        fetched_at=_now(),
        content_text=content,
        language="en",
        hash=news_id,
        score_hint=SOURCE_SCORES.get(source, 0.5),
    )
    return item


def fetch_news(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = NewsFetchRequest(**payload)
    storage = get_storage()
    dedupe = DedupeIndex()
    collected: List[NewsItem] = []

    settings = get_settings()
    for source in request.sources:
        feed_url = settings.news_source_urls.get(source)
        if not feed_url:
            logger.warning("unknown_source", source=source)
            continue
        logger.info("news_fetch_source", source=source, feed=feed_url)
        entries = fetch_rss_feed(feed_url, max_items=request.max_per_source)
        kept = 0
        for entry in entries:
            item = _build_news_item(source, entry, request.since)
            if not item:
                continue
            if not dedupe.add(item.url, item.content_text or "", item.title)[0]:
                logger.debug("dedupe_skip", source=source, url=item.url)
                continue
            if near_duplicate(item.title, [existing.title for existing in collected]):
                logger.debug("near_duplicate_skip", source=source, title=item.title)
                continue
            collected.append(item)
            kept += 1
            key = f"news/raw/{source}/{item.fetched_at.strftime('%Y%m%d')}/{item.id}.json"
            storage.put_json(
                key,
                {
                    **item.dict(),
                    "created_at": item.fetched_at.isoformat(),
                    "ttl_days": 14,
                },
            )
        logger.info("news_fetch_stats", source=source, entries=len(entries), kept=kept)

    response = NewsFetchResponse(origin=ORIGIN, items=collected)
    return response.dict()


class handler(BaseJsonHandler):
    def handle_post(self, context, body: bytes) -> Dict[str, Any]:  # type: ignore[override]
        payload = parse_json(body)
        return fetch_news(payload)
