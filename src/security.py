"""Security utilities: HMAC verification and CORS handling."""
from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, Mapping, MutableMapping, Optional

from .config import get_settings


class UnauthorizedError(Exception):
    """Raised when a request fails signature validation."""


class ForbiddenOriginError(Exception):
    """Raised when a request originates from a blocked origin."""


@dataclass
class RequestContext:
    """Holds metadata extracted from an incoming request."""

    request_id: str
    received_at: datetime
    headers: Mapping[str, str]
    method: str
    path: str
    query_params: Mapping[str, str]


SIGNATURE_HEADER = "X-Signature"
REQUEST_ID_HEADER = "X-Request-ID"


def compute_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return digest


def verify_signature(body: bytes, headers: Mapping[str, str]) -> None:
    settings = get_settings()
    signature = headers.get(SIGNATURE_HEADER)
    if not signature:
        raise UnauthorizedError("missing signature header")

    expected = compute_signature(body, settings.hmac_shared_secret)
    if not hmac.compare_digest(expected, signature):
        raise UnauthorizedError("invalid signature")


def normalize_header_map(headers: Mapping[str, str]) -> Dict[str, str]:
    return {k.lower(): v for k, v in headers.items()}


def extract_origin(headers: Mapping[str, str]) -> Optional[str]:
    lowered = normalize_header_map(headers)
    return lowered.get("origin")


def ensure_cors(headers: MutableMapping[str, str], request_headers: Mapping[str, str]) -> None:
    settings = get_settings()
    origin = extract_origin(request_headers)
    if origin and _is_allowed_origin(origin, settings.allowed_origins):
        headers["Access-Control-Allow-Origin"] = origin
    elif origin:
        raise ForbiddenOriginError(f"origin {origin} not allowed")

    headers.update(
        {
            "Access-Control-Allow-Headers": "Content-Type, X-Signature, X-Request-ID",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Credentials": "false",
        }
    )


def _is_allowed_origin(origin: str, allowed: Iterable[str]) -> bool:
    if not allowed:
        return False
    return origin in allowed


def build_auth_header(key: str, secret: str, payload_hash: str) -> str:
    """Produce a simple HMAC authorization header for blob uploads."""
    string_to_sign = f"{key}:{payload_hash}"
    mac = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256)
    signature = base64.b64encode(mac.digest()).decode("ascii")
    return f"HMAC {key}:{signature}"
