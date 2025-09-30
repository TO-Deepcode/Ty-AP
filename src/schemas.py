"""Pydantic models for request and response payloads."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, conint, constr, validator


class ErrorResponse(BaseModel):
    message: str
    details: Optional[Dict[str, str]] = None


class HealthResponse(BaseModel):
    status: str
    time: datetime
    version: str


class Candle(BaseModel):
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketSnapshot(BaseModel):
    schema_version: str = Field("1.0", const=True)
    origin: str
    source: str
    symbol: str
    timeframe: str
    fetched_at: datetime
    from_time: datetime
    to_time: datetime
    candles: List[Candle]
    last_price: Optional[float]
    change_24h: Optional[float]


class MarketFetchRequest(BaseModel):
    exchanges: List[constr(min_length=3)]
    symbols: List[constr(min_length=3)]
    granularity: constr(min_length=2)
    limit: conint(gt=0, le=1000) = 200

    @validator("exchanges", each_item=True)
    def validate_exchange(cls, value: str) -> str:
        allowed = {"bybit", "binance", "cmc"}
        if value not in allowed:
            raise ValueError(f"unsupported exchange: {value}")
        return value

    @validator("granularity")
    def validate_granularity(cls, value: str) -> str:
        allowed = {"1m", "5m", "15m", "1h", "4h", "1d"}
        if value not in allowed:
            raise ValueError("granularity must be one of 1m,5m,15m,1h,4h,1d")
        return value


class MarketFetchResponse(BaseModel):
    schema_version: str = Field("1.0", const=True)
    origin: str
    snapshots: List[MarketSnapshot]


class NewsFetchRequest(BaseModel):
    sources: List[constr(min_length=3)]
    since: Optional[datetime]
    max_per_source: conint(gt=0, le=200) = 50


class NewsItem(BaseModel):
    schema_version: str = Field("1.0", const=True)
    origin: str
    id: str
    source: str
    url: HttpUrl
    title: str
    summary: Optional[str]
    published_at: datetime
    fetched_at: datetime
    content_text: Optional[str]
    language: Optional[str]
    hash: str
    score_hint: Optional[float]


class NewsFetchResponse(BaseModel):
    schema_version: str = Field("1.0", const=True)
    origin: str
    items: List[NewsItem]


class AnalyzeNewsRequest(BaseModel):
    items: List[NewsItem]
    confirm_window_minutes: conint(gt=0, le=720) = 180
    similarity_threshold: float = Field(0.82, ge=0.0, le=1.0)


class NewsCluster(BaseModel):
    schema_version: str = Field("1.0", const=True)
    origin: str
    cluster_id: str
    canonical_title: str
    summary: Optional[str]
    score: float
    source_count: int
    entities: List[str]
    first_seen: datetime
    last_seen: datetime
    sentiment_hint: Optional[str]
    links: List[str]


class AnalyzeNewsResponse(BaseModel):
    schema_version: str = Field("1.0", const=True)
    origin: str
    clusters: List[NewsCluster]


class StorageListResponse(BaseModel):
    prefix: str
    keys: List[str]


class CleanupRequest(BaseModel):
    dry_run: bool = False


class CleanupResponse(BaseModel):
    deleted: List[str]
    kept: int
