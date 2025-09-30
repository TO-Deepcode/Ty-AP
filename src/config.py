"""Application configuration modeled with Pydantic for type safety."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, List, Optional

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    env: str = Field("development", alias="ENV")
    bybit_api_key: Optional[str] = Field(None, alias="BYBIT_API_KEY")
    bybit_api_secret: Optional[str] = Field(None, alias="BYBIT_API_SECRET")
    binance_api_key: Optional[str] = Field(None, alias="BINANCE_API_KEY")
    binance_api_secret: Optional[str] = Field(None, alias="BINANCE_API_SECRET")
    cmc_api_key: Optional[str] = Field(None, alias="CMC_API_KEY")

    blob_base_url: Optional[str] = Field(None, alias="BLOB_BASE_URL")
    blob_access_key: Optional[str] = Field(None, alias="BLOB_ACCESS_KEY")
    blob_secret_key: Optional[str] = Field(None, alias="BLOB_SECRET_KEY")
    blob_bucket: Optional[str] = Field(None, alias="BLOB_BUCKET")

    hmac_shared_secret: str = Field(..., alias="HMAC_SHARED_SECRET")
    allowed_origins: List[str] = Field(default_factory=list, alias="ALLOWED_ORIGINS")
    http_proxy: Optional[str] = Field(None, alias="HTTP_PROXY")

    user_agent: str = Field(
        default="AWS-WEBse/1.0 (+https://your-domain; contact=ops@your-domain)",
        alias="USER_AGENT",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("allowed_origins", pre=True)
    def _split_origins(cls, value: Optional[str]) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return value
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def news_source_urls(self) -> Dict[str, str]:
        return {
            "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "theblock": "https://www.theblock.co/rss.xml",
            "blockworks": "https://blockworks.co/feed",
            "cointelegraph": "https://cointelegraph.com/rss",
            "defiant": "https://thedefiant.io/feed",
            "dlnews": "https://dlnews.com/feed",
            "protos": "https://protos.com/feed",
            "decrypt": "https://decrypt.co/feed",
            "cryptopanic": "https://cryptopanic.com/news/rss/",
            "messari": "https://messari.io/rss",
            "glassnode": "https://insights.glassnode.com/feed/",
        }


def _settings_from_env() -> Settings:
    # Required secret guard for development convenience
    if "HMAC_SHARED_SECRET" not in os.environ:
        os.environ.setdefault("HMAC_SHARED_SECRET", "dev-secret")
    return Settings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return singleton settings instance."""
    return _settings_from_env()
