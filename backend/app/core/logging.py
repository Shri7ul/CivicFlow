"""Centralized logging configuration.

Log lines carry a request correlation identifier when the record is emitted
inside an HTTP request. Query strings, bodies, tokens and user-provided values
are never added to the record by this module.
"""

from __future__ import annotations

import logging

from app.core.request_context import get_request_id

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "request_id=%(request_id)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


class RequestContextFilter(logging.Filter):
    """Attach the active request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure application and Uvicorn loggers with one consistent format."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        force=True,
    )
    for handler in logging.getLogger().handlers:
        if not any(isinstance(item, RequestContextFilter) for item in handler.filters):
            handler.addFilter(RequestContextFilter())

    # Let Uvicorn log records flow through the root handler instead of
    # installing a second, differently formatted handler.
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

    # Request logging is handled by our middleware.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced CivicFlow logger."""
    return logging.getLogger(f"civicflow.{name}")
