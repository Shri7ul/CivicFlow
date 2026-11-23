"""Database connectivity health checks.

Phase 1 uses the shared engine/session configuration. No schema is created by
the application at runtime; Alembic owns schema evolution.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import clear_engine_cache, get_engine

logger = get_logger("database")


@dataclass(frozen=True)
class DatabaseCheck:
    configured: bool
    reachable: bool
    message: str


def check_database() -> DatabaseCheck:
    """Check real database connectivity without exposing connection details."""
    engine = None
    try:
        engine = get_engine()
    except Exception as exc:
        logger.warning(
            "Database engine configuration failed | %s", type(exc).__name__
        )
        return DatabaseCheck(
            configured=True,
            reachable=False,
            message="Database configuration is invalid.",
        )

    if engine is None:
        return DatabaseCheck(
            configured=False,
            reachable=False,
            message="Database is not configured for this environment.",
        )

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Database health check failed | %s", type(exc).__name__)
        return DatabaseCheck(
            configured=True,
            reachable=False,
            message="Database is configured but unreachable.",
        )

    logger.debug("Database health check succeeded")
    return DatabaseCheck(
        configured=True,
        reachable=True,
        message="Database connection is available.",
    )


__all__ = ["DatabaseCheck", "check_database", "clear_engine_cache"]
