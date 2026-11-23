"""Centralized logging configuration."""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(level: str = "INFO") -> None:
    """Configure application and Uvicorn loggers with one consistent format."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        force=True,
    )

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
