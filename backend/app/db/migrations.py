"""Apply Alembic revisions from the application startup lifecycle.

Render deploys this service manually from GitHub, so a blueprint-level command
is not sufficient. Every real process start upgrades the database before the
API accepts traffic. Tests and SQLite-backed local harnesses create their own
schema and are deliberately skipped.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger("db.migrations")

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _database_url(settings: Settings) -> str | None:
    return os.getenv("ALEMBIC_DATABASE_URL") or settings.database_url_value or None


def should_run_migrations(settings: Settings) -> bool:
    """True only for a real, configured, non-test SQL database."""
    if settings.app_env == "testing":
        return False
    url = _database_url(settings)
    if not url:
        return False
    try:
        dialect = make_url(url).get_backend_name()
    except Exception:
        # An unparseable URL must fail loudly in the upgrade step, not be
        # mistaken for a reason to skip it.
        return True
    return dialect != "sqlite"


def _upgrade_sync() -> None:
    ini_path = BACKEND_ROOT / "alembic.ini"
    if not ini_path.is_file():
        raise RuntimeError("alembic.ini is missing from the backend root.")
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("prepend_sys_path", str(BACKEND_ROOT))
    # alembic/env.py resolves the URL from ALEMBIC_DATABASE_URL or Settings.
    command.upgrade(config, "head")


async def apply_startup_migrations(settings: Settings) -> None:
    """Upgrade to head, or skip for test/SQLite/unconfigured environments."""
    if not should_run_migrations(settings):
        logger.info("Startup migrations skipped | reason=test_sqlite_or_unconfigured")
        return
    try:
        await asyncio.to_thread(_upgrade_sync)
        logger.info("Database schema is at Alembic head")
    except Exception:
        logger.exception(
            "Startup migration failed; refusing to serve an unmigrated schema"
        )
        raise
