"""Shared HTTP client helpers with timeouts, retries, and proxy support."""
from __future__ import annotations

import json
from typing import Any, Dict

import httpx
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import get_settings
from .logging_setup import get_logger

_TIMEOUT = httpx.Timeout(15.0, connect=10.0, read=15.0)
_RETRYABLE = (httpx.HTTPError,)

logger = get_logger(__name__)


def _client_headers() -> Dict[str, str]:
    settings = get_settings()
    return {
        "User-Agent": settings.user_agent,
        "Accept": "application/json, text/*;q=0.9",
    }


def _client_kwargs() -> Dict[str, Any]:
    settings = get_settings()
    kwargs: Dict[str, Any] = {
        "timeout": _TIMEOUT,
        "headers": _client_headers(),
    }
    if settings.http_proxy:
        kwargs["proxies"] = settings.http_proxy
    return kwargs


@retry(
    retry=retry_if_exception_type(_RETRYABLE),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=1, max=8),
    reraise=True,
)
def _request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    settings = get_settings()
    with httpx.Client(**_client_kwargs()) as client:
        logger.debug("http_request", method=method, url=url, kwargs={k: str(v)[:200] for k, v in kwargs.items()})
        if settings.http_proxy:
            kwargs.setdefault("proxies", settings.http_proxy)
        response = client.request(method, url, **kwargs)
        response.raise_for_status()
        return response


def request_json(method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
    try:
        response = _request(method, url, **kwargs)
        return response.json()
    except RetryError as exc:  # pragma: no cover - defensive branch
        raise exc.last_attempt.exception()  # type: ignore[union-attr]


def request_text(method: str, url: str, **kwargs: Any) -> str:
    try:
        response = _request(method, url, **kwargs)
        return response.text
    except RetryError as exc:  # pragma: no cover
        raise exc.last_attempt.exception()  # type: ignore[union-attr]


def request_raw(method: str, url: str, **kwargs: Any) -> httpx.Response:
    try:
        return _request(method, url, **kwargs)
    except RetryError as exc:  # pragma: no cover
        raise exc.last_attempt.exception()  # type: ignore[union-attr]


def get_binary(url: str) -> bytes:
    try:
        response = _request("GET", url)
        return response.content
    except RetryError as exc:  # pragma: no cover
        raise exc.last_attempt.exception()  # type: ignore[union-attr]


async def aget_json(method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
    # Placeholder for potential async use. Kept simple for serverless compatibility.
    raise NotImplementedError("Async HTTP client not implemented in this deployment")
