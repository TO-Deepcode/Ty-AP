"""Utility base classes/helpers for Vercel-style serverless JSON handlers."""
from __future__ import annotations

import json
import traceback
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlparse

import ujson

from datetime import datetime, date

from .logging_setup import get_logger
from .security import ForbiddenOriginError, RequestContext, UnauthorizedError, ensure_cors, verify_signature

logger = get_logger(__name__)


class HttpError(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(message)


class BaseJsonHandler(BaseHTTPRequestHandler):
    server_version = "AWS-WEBse/1.0"

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler signature
        context = self._build_context()
        headers: Dict[str, str] = {}
        try:
            ensure_cors(headers, context.headers)
        except ForbiddenOriginError as exc:
            self._write_json(HTTPStatus.FORBIDDEN, {"message": str(exc)}, headers)
            return
        headers.setdefault("Content-Length", "0")
        self._write_json(HTTPStatus.NO_CONTENT, None, headers)

    def do_GET(self) -> None:  # noqa: N802
        context = self._build_context()
        try:
            ensure_cors_headers = {}
            ensure_cors(ensure_cors_headers, context.headers)
            payload = self.handle_get(context)
            self._write_json(HTTPStatus.OK, payload, ensure_cors_headers)
        except HttpError as exc:
            self._write_json(exc.status, {"message": exc.message}, {})
        except ForbiddenOriginError as exc:
            self._write_json(HTTPStatus.FORBIDDEN, {"message": str(exc)}, {})
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("handler_error", request_id=context.request_id, error=str(exc), traceback=traceback.format_exc())
            self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "internal error"}, {})

    def do_POST(self) -> None:  # noqa: N802
        context = self._build_context()
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        try:
            verify_signature(body, context.headers)
            ensure_cors_headers: Dict[str, str] = {}
            ensure_cors(ensure_cors_headers, context.headers)
            payload = self.handle_post(context, body)
            self._write_json(HTTPStatus.OK, payload, ensure_cors_headers)
        except UnauthorizedError as exc:
            self._write_json(HTTPStatus.UNAUTHORIZED, {"message": str(exc)}, {})
        except ForbiddenOriginError as exc:
            self._write_json(HTTPStatus.FORBIDDEN, {"message": str(exc)}, {})
        except HttpError as exc:
            self._write_json(exc.status, {"message": exc.message}, {})
        except json.JSONDecodeError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"message": "invalid json body"}, {})
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("handler_error", request_id=context.request_id, error=str(exc), traceback=traceback.format_exc())
            self._write_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "internal error"}, {})

    # Methods to be implemented by subclasses
    def handle_get(self, context: RequestContext) -> Dict[str, Any]:  # pragma: no cover - interface
        raise HttpError(HTTPStatus.METHOD_NOT_ALLOWED, "GET not supported")

    def handle_post(self, context: RequestContext, body: bytes) -> Dict[str, Any]:  # pragma: no cover - interface
        raise HttpError(HTTPStatus.METHOD_NOT_ALLOWED, "POST not supported")

    # Internal helpers
    def _build_context(self) -> RequestContext:
        request_id = self.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex}"
        parsed = urlparse(self.path)
        query = dict(parse_qsl(parsed.query))
        headers = {key: value for key, value in self.headers.items()}
        context = RequestContext(
            request_id=request_id,
            received_at=datetime_now(),
            headers=headers,
            method=self.command,
            path=parsed.path,
            query_params=query,
        )
        logger.bind(request_id=request_id)
        return context

    def _write_json(self, status: HTTPStatus, payload: Optional[Dict[str, Any]], extra_headers: Dict[str, str]) -> None:
        self.send_response(status.value)
        response_headers = {"Content-Type": "application/json"}
        response_headers.update(extra_headers)
        body = b""
        if payload is not None:
            serializable = _make_json_serializable(payload)
            body = ujson.dumps(serializable).encode("utf-8")
            response_headers["Content-Length"] = str(len(body))
        for key, value in response_headers.items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)


def parse_json(body: bytes) -> Dict[str, Any]:
    return ujson.loads(body.decode("utf-8") or "{}")


def datetime_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _make_json_serializable(data: Any) -> Any:
    if isinstance(data, (datetime, date)):
        return data.isoformat()
    if isinstance(data, dict):
        return {key: _make_json_serializable(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_make_json_serializable(item) for item in data]
    if isinstance(data, tuple):
        return [_make_json_serializable(item) for item in data]
    return data
