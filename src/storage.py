"""JSON storage abstraction over local disk or HTTP blob store."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import ujson

from .config import get_settings
from .http_clients import request_json, request_raw, request_text
from .logging_setup import get_logger
from .security import build_auth_header

logger = get_logger(__name__)


def _prepare_payload(data: Any) -> Any:
    if isinstance(data, datetime):
        return data.isoformat()
    if isinstance(data, dict):
        return {key: _prepare_payload(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_prepare_payload(item) for item in data]
    return data


class StorageBackend:
    def put_json(self, key: str, data: Dict[str, Any]) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError

    def list(self, prefix: str, limit: int = 100) -> List[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def delete(self, key: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class LocalStorage(StorageBackend):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        return self.root.joinpath(key)

    def put_json(self, key: str, data: Dict[str, Any]) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = _prepare_payload(data)
        path.write_text(ujson.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("local_storage_put", key=key, path=str(path))

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        path = self._path_for(key)
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        logger.debug("local_storage_get", key=key, path=str(path))
        return ujson.loads(content)

    def list(self, prefix: str, limit: int = 100) -> List[str]:
        results: List[str] = []
        base = self.root.joinpath(prefix)
        if not base.exists():
            return []
        for file_path in base.rglob("*.json"):
            results.append(str(file_path.relative_to(self.root)))
            if len(results) >= limit:
                break
        return sorted(results)

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        if path.exists():
            path.unlink()
            logger.debug("local_storage_delete", key=key, path=str(path))


class RemoteStorage(StorageBackend):
    def __init__(self, base_url: str, bucket: Optional[str], access_key: Optional[str], secret_key: Optional[str]) -> None:
        self.base_url = base_url.rstrip("/")
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key

    def _headers(self, payload: bytes) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.access_key and self.secret_key:
            payload_hash = hashlib.sha256(payload).hexdigest()
            headers["Authorization"] = build_auth_header(self.access_key, self.secret_key, payload_hash)
        return headers

    def _object_url(self, key: str) -> str:
        if self.bucket:
            return f"{self.base_url}/object/{self.bucket}/{key}"
        return f"{self.base_url}/object/{key}"

    def _list_url(self) -> str:
        if self.bucket:
            return f"{self.base_url}/list/{self.bucket}"
        return f"{self.base_url}/list"

    def put_json(self, key: str, data: Dict[str, Any]) -> None:
        prepared = _prepare_payload(data)
        payload = ujson.dumps(prepared).encode("utf-8")
        url = self._object_url(key)
        response = request_raw("PUT", url, content=payload, headers=self._headers(payload))
        logger.info("remote_storage_put", key=key, url=url, status=response.status_code)

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        url = self._object_url(key)
        try:
            text = request_text("GET", url, headers=self._headers(b""))
        except Exception as exc:  # pragma: no cover - network branch
            logger.warning("remote_storage_get_failed", key=key, url=url, error=str(exc))
            return None
        return ujson.loads(text)

    def list(self, prefix: str, limit: int = 100) -> List[str]:
        params = {"prefix": prefix, "limit": str(limit)}
        if self.bucket:
            params["bucket"] = self.bucket
        response = request_json("GET", self._list_url(), params=params, headers=self._headers(b""))
        return response.get("keys", [])

    def delete(self, key: str) -> None:
        url = self._object_url(key)
        response = request_raw("DELETE", url, headers=self._headers(b""))
        logger.info("remote_storage_delete", key=key, url=url, status=response.status_code)


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.is_production and settings.blob_base_url:
        return RemoteStorage(settings.blob_base_url, settings.blob_bucket, settings.blob_access_key, settings.blob_secret_key)
    local_root = Path(os.getenv("DATA_DIR", ".data"))
    return LocalStorage(local_root)
