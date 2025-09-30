"""News confirmation and scoring utilities."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from rapidfuzz import fuzz

from .normalization import normalize_title
from .schemas import NewsCluster, NewsItem

SIMILARITY_WEIGHT = 0.6
SOURCE_WEIGHT = 0.3
FRESHNESS_WEIGHT = 0.1

SOURCE_SCORES: Dict[str, float] = {
    "coindesk": 1.0,
    "theblock": 1.0,
    "blockworks": 1.0,
    "cryptopanic": 2.0,
    "messari": 1.0,
}

ENTITY_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("BTC", re.compile(r"\bBTC\b", re.IGNORECASE)),
    ("ETH", re.compile(r"\bETH\b", re.IGNORECASE)),
    ("SOL", re.compile(r"\bSOL\b", re.IGNORECASE)),
    ("ETF", re.compile(r"\bETF\b", re.IGNORECASE)),
    ("SEC", re.compile(r"\bSEC\b", re.IGNORECASE)),
    ("HACK", re.compile(r"\bhack(ed|ing)?\b", re.IGNORECASE)),
    ("FUNDING", re.compile(r"\bfunding rate\b", re.IGNORECASE)),
)


@dataclass
class ClusterCandidate:
    canonical_title: str
    items: List[NewsItem] = field(default_factory=list)
    similarities: List[float] = field(default_factory=list)

    def add(self, item: NewsItem, similarity: float) -> None:
        self.items.append(item)
        self.similarities.append(similarity)
        if similarity > max(self.similarities[:-1], default=0):
            self.canonical_title = item.title

    @property
    def first_seen(self) -> datetime:
        return min(item.published_at for item in self.items)

    @property
    def last_seen(self) -> datetime:
        return max(item.published_at for item in self.items)

    @property
    def similarity_score(self) -> float:
        if not self.similarities:
            return 0.0
        return sum(self.similarities) / len(self.similarities)

    @property
    def source_score(self) -> float:
        return sum(SOURCE_SCORES.get(item.source, 0.5) for item in self.items)

    @property
    def freshness_score(self) -> float:
        now = datetime.now(timezone.utc)
        age_minutes = (now - self.first_seen).total_seconds() / 60.0
        freshness = max(0.0, 1.0 - (age_minutes / 1440.0))  # degrade across a day
        return freshness * 100

    def detect_entities(self) -> List[str]:
        entities: List[str] = []
        combined_text = " ".join(item.title for item in self.items)
        for label, pattern in ENTITY_PATTERNS:
            if pattern.search(combined_text) and label not in entities:
                entities.append(label)
        return entities

    def to_schema(self, origin: str) -> NewsCluster:
        similarity_component = (self.similarity_score / 100.0) * 100 * SIMILARITY_WEIGHT
        source_component = self.source_score * 10 * SOURCE_WEIGHT
        freshness_component = self.freshness_score * FRESHNESS_WEIGHT
        score = similarity_component + source_component + freshness_component
        sentiment = _sentiment_hint(self.items)

        return NewsCluster(
            origin=origin,
            cluster_id=f"cluster-{self.items[0].hash[:12]}",
            canonical_title=self.canonical_title,
            summary=self.items[0].summary,
            score=round(score, 2),
            source_count=len({item.source for item in self.items}),
            entities=self.detect_entities(),
            first_seen=self.first_seen,
            last_seen=self.last_seen,
            sentiment_hint=sentiment,
            links=[item.url for item in self.items],
        )


def cluster_news(items: Iterable[NewsItem], window_minutes: int, similarity_threshold: float, origin: str) -> List[NewsCluster]:
    sorted_items = sorted(items, key=lambda item: item.published_at)
    clusters: List[ClusterCandidate] = []
    for item in sorted_items:
        matched = False
        item_title = normalize_title(item.title)
        for cluster in clusters:
            if abs((item.published_at - cluster.first_seen).total_seconds()) > window_minutes * 60:
                continue
            similarity = fuzz.token_set_ratio(item_title, normalize_title(cluster.canonical_title))
            if similarity / 100.0 >= similarity_threshold:
                cluster.add(item, similarity)
                matched = True
                break
        if not matched:
            new_cluster = ClusterCandidate(canonical_title=item.title)
            new_cluster.add(item, 100.0)
            clusters.append(new_cluster)

    return [cluster.to_schema(origin) for cluster in clusters]


def _sentiment_hint(items: Iterable[NewsItem]) -> Optional[str]:
    negative_keywords = ("hack", "lawsuit", "layoff", "bankrupt")
    positive_keywords = ("launch", "growth", "profit", "surge")
    score = 0
    for item in items:
        title = item.title.lower()
        if any(word in title for word in positive_keywords):
            score += 1
        if any(word in title for word in negative_keywords):
            score -= 1
    if score > 1:
        return "positive"
    if score < -1:
        return "negative"
    return None
