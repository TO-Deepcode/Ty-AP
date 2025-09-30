"""Logging configuration for the serverless functions.

Ensures structlog is configured once per cold start and reused across invocations.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import structlog


def configure_logging() -> None:
    """Set up structlog with JSON rendering suitable for serverless logs."""
    if getattr(configure_logging, "_configured", False):
        return

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    configure_logging._configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger with a given name."""
    configure_logging()
    logger = structlog.get_logger(name)
    return logger.bind(service="aws-webse")
