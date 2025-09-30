"""Minimal compatibility shim for the deprecated stdlib cgi.parse_header."""
from __future__ import annotations

from typing import Dict, Tuple


def parse_header(line: str) -> Tuple[str, Dict[str, str]]:
    main_value = ""
    params: Dict[str, str] = {}
    if not line:
        return main_value, params
    parts = [part.strip() for part in line.split(";")]
    if parts:
        main_value = parts[0]
    for item in parts[1:]:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        value = value.strip().strip('"')
        params[key.lower().strip()] = value
    return main_value, params


__all__ = ["parse_header"]
