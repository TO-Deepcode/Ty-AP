"""Deduplication helpers for crawling."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

from rapidfuzz import fuzz

from .normalization import canonicalize_url, deterministic_hash, normalize_title


@dataclass
class DedupeIndex:
    url_hashes: Dict[str, str] = field(default_factory=dict)
    content_hashes: Dict[str, str] = field(default_factory=dict)

    def add(self, url: str, content: str, title: str) -> Tuple[bool, str]:
        canonical_url = canonicalize_url(url)
        title_key = normalize_title(title)
        url_key = deterministic_hash(canonical_url)
        content_key = deterministic_hash(content[:5000], title_key)

        if url_key in self.url_hashes:
            return False, self.url_hashes[url_key]
        if content_key in self.content_hashes:
            return False, self.content_hashes[content_key]

        self.url_hashes[url_key] = url_key
        self.content_hashes[content_key] = content_key
        return True, url_key


def near_duplicate(title: str, existing_titles: Iterable[str], threshold: float = 90.0) -> bool:
    for other in existing_titles:
        score = fuzz.token_set_ratio(normalize_title(title), normalize_title(other))
        if score >= threshold:
            return True
    return False
