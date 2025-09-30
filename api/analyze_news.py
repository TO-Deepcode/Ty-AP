"""Analyze and cluster news items for multi-source confirmation."""
from __future__ import annotations

from http import HTTPStatus
from typing import Any, Dict

from src.api_utils import BaseJsonHandler, HttpError, parse_json
from src.confirm import cluster_news
from src.logging_setup import get_logger
from src.schemas import AnalyzeNewsRequest, AnalyzeNewsResponse
from src.storage import get_storage

logger = get_logger(__name__)

ORIGIN = "aws-webse"


def analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = AnalyzeNewsRequest(**payload)
    if not request.items:
        raise HttpError(HTTPStatus.BAD_REQUEST, "items cannot be empty")
    clusters = cluster_news(request.items, request.confirm_window_minutes, request.similarity_threshold, ORIGIN)
    storage = get_storage()
    for cluster in clusters:
        key = f"news/clustered/{cluster.first_seen.strftime('%Y%m%d')}/{cluster.cluster_id}.json"
        storage.put_json(
            key,
            {
                **cluster.dict(),
                "created_at": cluster.first_seen.isoformat(),
                "ttl_days": 30,
            },
        )
    response = AnalyzeNewsResponse(origin=ORIGIN, clusters=clusters)
    return response.dict()


class handler(BaseJsonHandler):
    def handle_post(self, context, body: bytes) -> Dict[str, Any]:  # type: ignore[override]
        payload = parse_json(body)
        result = analyze(payload)
        logger.info("analyze_news", request_id=context.request_id, clusters=len(result.get("clusters", [])))
        return result
