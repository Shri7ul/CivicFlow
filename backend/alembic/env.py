"""Alembic environment wired to CivicFlow Settings and model registry."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, engine_from_config, pool

from app.core.config import get_settings
from app.db.session import normalize_database_url
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

settings = get_settings()
_database_url = os.getenv("ALEMBIC_DATABASE_URL") or settings.database_url_value
if _database_url:
    # Alembic interpolation treats % specially in URLs/passwords.
    config.set_main_option(
        "sqlalchemy.url", normalize_database_url(_database_url).replace("%", "%%")
    )

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):  # noqa: ANN001
    """Keep PostGIS-owned tables out of CivicFlow autogenerate operations."""
    if type_ == "table" and name == "spatial_ref_sys":
        return False
    return True


def compare_type(  # noqa: ANN001
    _context, _inspected_column, _metadata_column, inspected_type, metadata_type
):
    """Treat non-native SQLAlchemy enums as their VARCHAR storage type.

    Phase 1 deliberately stores enums as VARCHAR plus a named CHECK constraint,
    so Alembic must not propose a type change from VARCHAR to Enum on every run.
    Length remains significant.
    """
    if (
        isinstance(metadata_type, SAEnum)
        and not metadata_type.native_enum
        and isinstance(inspected_type, String)
    ):
        # Flag only a database column that is too short for the enum values.
        # The migration intentionally declares VARCHAR storage, and some
        # historical columns were created one character wider.
        if inspected_type.length is None or metadata_type.length is None:
            return False
        return inspected_type.length < metadata_type.length
    return None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "No database URL configured. Set DATABASE_URL or ALEMBIC_DATABASE_URL."
        )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_type,
        compare_server_default=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    if not section.get("sqlalchemy.url"):
        raise RuntimeError(
            "No database URL configured. Set DATABASE_URL or ALEMBIC_DATABASE_URL."
        )
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=compare_type,
            compare_server_default=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
