"""Helpers for text normalization, timezone handling, and hashing."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dateutil import parser as date_parser
import tldextract

WHITESPACE_RE = re.compile(r"\s+")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def normalize_whitespace(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def strip_html(value: str) -> str:
    return HTML_TAG_RE.sub("", value)


def normalize_title(value: str) -> str:
    cleaned = strip_html(value)
    cleaned = normalize_whitespace(cleaned)
    return cleaned


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = date_parser.parse(value)
    except (ValueError, TypeError):
        return None
    return to_utc(parsed)


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    query_pairs = sorted(parse_qsl(parsed.query, keep_blank_values=False))
    query = urlencode(query_pairs)
    normalized = urlunparse((scheme, netloc, path, "", query, ""))
    return normalized


def deterministic_hash(*parts: str) -> str:
    joined = "|".join(part.strip() for part in parts if part)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def domain_from_url(url: str) -> str:
    parsed = tldextract.extract(url)
    return ".".join(part for part in [parsed.domain, parsed.suffix] if part)
