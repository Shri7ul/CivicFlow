"""Database engine, pooling, and request-scoped sessions."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger("database")
_ENGINES: list[Engine] = []


class DatabaseUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "Database is not configured for this environment.",
            status_code=503,
            code="database_unavailable",
        )


def normalize_database_url(database_url: str) -> str:
    """Normalize Supabase/PostgreSQL URL forms to the psycopg SQLAlchemy driver.

    Supabase dashboard URLs may use ``postgres://`` or ``postgresql://``.
    SQLAlchemy would otherwise select psycopg2, which this project does not
    install. Non-PostgreSQL URLs (used by isolated tests) pass through.
    """
    value = database_url.strip()
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://") :]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://") :]
    return value


def _connect_args(
    database_url: str,
    *,
    connect_timeout_s: int,
    sslmode: str | None,
    is_production: bool,
) -> dict[str, object]:
    url = make_url(normalize_database_url(database_url))
    if url.get_backend_name() != "postgresql":
        return {}

    args: dict[str, object] = {"connect_timeout": connect_timeout_s}
    # A URL query (e.g. ?sslmode=require) takes precedence and is left intact.
    if "sslmode" not in url.query:
        effective_sslmode = sslmode
        if effective_sslmode is None and is_production:
            effective_sslmode = "require"
        if effective_sslmode:
            args["sslmode"] = effective_sslmode
    return args


@lru_cache(maxsize=4)
def _create_engine(
    database_url: str,
    pool_size: int,
    max_overflow: int,
    pool_timeout_s: int,
    pool_recycle_s: int,
    connect_timeout_s: int,
    sslmode: str | None,
    is_production: bool,
) -> Engine:
    normalized = normalize_database_url(database_url)
    url = make_url(normalized)
    options: dict[str, object] = {
        "pool_pre_ping": True,
        "connect_args": _connect_args(
            normalized,
            connect_timeout_s=connect_timeout_s,
            sslmode=sslmode,
            is_production=is_production,
        ),
    }
    if url.get_backend_name() != "sqlite":
        options.update(
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout_s,
            pool_recycle=pool_recycle_s,
        )
    engine = create_engine(normalized, **options)
    _ENGINES.append(engine)
    return engine


def get_engine() -> Engine | None:
    """Return the configured engine, or None when no database is configured."""
    settings = get_settings()
    database_url = settings.database_url_value
    if not database_url:
        return None
    return _create_engine(
        database_url,
        settings.database_pool_size,
        settings.database_max_overflow,
        settings.database_pool_timeout_s,
        settings.database_pool_recycle_s,
        settings.database_connect_timeout_s,
        settings.database_sslmode,
        settings.is_production,
    )


@lru_cache(maxsize=4)
def _session_factory(_database_url: str) -> sessionmaker[Session]:
    engine = get_engine()
    if engine is None:  # pragma: no cover - guarded by get_db_session
        raise DatabaseUnavailableError()
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session_factory() -> sessionmaker[Session]:
    settings = get_settings()
    database_url = settings.database_url_value
    if not database_url:
        raise DatabaseUnavailableError()
    return _session_factory(database_url)


def get_db_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that always closes on error."""
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def clear_engine_cache() -> None:
    """Dispose cached engines and session factories (tests/reloads)."""
    for engine in _ENGINES:
        engine.dispose()
    _ENGINES.clear()
    _session_factory.cache_clear()
    _create_engine.cache_clear()
