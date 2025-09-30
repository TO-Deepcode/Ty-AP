"""Cleanup endpoint to rotate expired JSON objects from storage."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.api_utils import BaseJsonHandler, parse_json
from src.logging_setup import get_logger
from src.schemas import CleanupRequest, CleanupResponse
from src.storage import get_storage

logger = get_logger(__name__)

PREFIXES = ["news/raw", "news/clustered", "market", "logs"]


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def cleanup(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = CleanupRequest(**payload)
    storage = get_storage()
    now = datetime.now(timezone.utc)
    deleted: List[str] = []
    kept = 0

    for prefix in PREFIXES:
        keys = storage.list(prefix, limit=1000)
        for key in keys:
            record = storage.get_json(key)
            if not record:
                continue
            created_at = record.get("created_at")
            ttl_days = record.get("ttl_days", 14)
            if not created_at:
                kept += 1
                continue
            created = _parse_timestamp(created_at)
            age_days = (now - created).days
            if age_days >= ttl_days:
                deleted.append(key)
                if not request.dry_run:
                    storage.delete(key)
            else:
                kept += 1
    response = CleanupResponse(deleted=deleted, kept=kept)
    logger.info("cleanup_done", deleted=len(deleted), kept=kept, dry_run=request.dry_run)
    return response.dict()


class handler(BaseJsonHandler):
    def handle_post(self, context, body: bytes) -> Dict[str, Any]:  # type: ignore[override]
        payload = parse_json(body)
        return cleanup(payload)
