from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

import pytest

from api.health import build_health_payload
from api.market_fetch import FETCHERS, process_request
from api.news_fetch import fetch_news
from api.analyze_news import analyze
from src.schemas import NewsItem
from src.storage import get_storage


@pytest.fixture(autouse=True)
def reset_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_storage.cache_clear()  # type: ignore[attr-defined]
    yield
    get_storage.cache_clear()  # type: ignore[attr-defined]


def test_health_payload():
    health = build_health_payload()
    assert health["status"] == "ok"
    assert "version" in health


def test_market_fetch_process_request(monkeypatch):
    now = datetime.now(timezone.utc)

    def fake_fetch(symbol: str, granularity: str, limit: int):
        from src.schemas import Candle, MarketSnapshot

        candle = Candle(open_time=now, open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0)
        return MarketSnapshot(
            origin="test",
            source="binance",
            symbol=symbol,
            timeframe=granularity,
            fetched_at=now,
            from_time=now,
            to_time=now,
            candles=[candle],
            last_price=1.5,
            change_24h=5.0,
        )

    monkeypatch.setitem(FETCHERS, "binance", fake_fetch)
    payload = {
        "exchanges": ["binance"],
        "symbols": ["BTCUSDT"],
        "granularity": "1h",
        "limit": 2,
    }
    result = process_request(payload)
    assert result["snapshots"][0]["symbol"] == "BTCUSDT"


def test_news_fetch(monkeypatch):
    published = datetime(2025, 1, 1, tzinfo=timezone.utc)

    monkeypatch.setattr("api.news_fetch.fetch_rss_feed", lambda url, max_items: [{"title": "Sample", "link": "https://example.com/a", "summary": "s", "published_at": published}])
    monkeypatch.setattr("api.news_fetch._allowed", lambda url: True)
    monkeypatch.setattr("api.news_fetch.allow_request", lambda domain: True)
    monkeypatch.setattr("api.news_fetch._fetch_article", lambda source, url: {"title": "Sample", "summary": "s", "content": "Body", "published_at": published.isoformat()})

    payload = {
        "sources": ["coindesk"],
        "since": published.isoformat(),
        "max_per_source": 5,
    }
    result = fetch_news(payload)
    assert len(result["items"]) == 1
    assert result["items"][0]["source"] == "coindesk"


def test_analyze_clusters(monkeypatch):
    now = datetime.now(timezone.utc)
    item = NewsItem(
        origin="test",
        id="1",
        source="coindesk",
        url="https://example.com/a",
        title="Example Title",
        summary="summary",
        published_at=now,
        fetched_at=now,
        content_text="body",
        language="en",
        hash="abc",
        score_hint=1.0,
    )
    payload = {
        "items": [item.dict()],
        "confirm_window_minutes": 60,
        "similarity_threshold": 0.5,
    }
    result = analyze(payload)
    assert result["clusters"]
    assert result["clusters"][0]["source_count"] == 1
