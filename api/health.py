"""Health endpoint returning service status."""
from __future__ import annotations

from http import HTTPStatus
from typing import Any, Dict

from src.api_utils import BaseJsonHandler, HttpError, datetime_now
from src.schemas import HealthResponse

VERSION = "1.0.0"
ORIGIN = "aws-webse"


def build_health_payload() -> Dict[str, Any]:
    response = HealthResponse(status="ok", time=datetime_now(), version=VERSION)
    return response.dict()


class handler(BaseJsonHandler):
    def handle_get(self, context) -> Dict[str, Any]:  # type: ignore[override]
        return build_health_payload()

    def handle_post(self, context, body: bytes) -> Dict[str, Any]:  # type: ignore[override]
        raise HttpError(HTTPStatus.METHOD_NOT_ALLOWED, "POST not supported")
