"""Debug endpoint to list stored JSON objects."""
from __future__ import annotations

from http import HTTPStatus
from typing import Any, Dict

from src.api_utils import BaseJsonHandler, HttpError
from src.schemas import StorageListResponse
from src.storage import get_storage


class handler(BaseJsonHandler):
    def handle_get(self, context) -> Dict[str, Any]:  # type: ignore[override]
        prefix = context.query_params.get("prefix")
        if not prefix:
            raise HttpError(HTTPStatus.BAD_REQUEST, "prefix query parameter is required")
        limit_raw = context.query_params.get("limit", "100")
        try:
            limit = int(limit_raw)
        except ValueError:
            raise HttpError(HTTPStatus.BAD_REQUEST, "limit must be an integer")
        storage = get_storage()
        keys = storage.list(prefix, limit=limit)
        response = StorageListResponse(prefix=prefix, keys=keys)
        return response.dict()
