"""Database configuration and session behavior tests."""

from __future__ import annotations

import pytest

from app.core.config import Settings, get_settings
from app.db.session import (
    DatabaseUnavailableError,
    _connect_args,
    clear_engine_cache,
    get_db_session,
    get_engine,
    normalize_database_url,
)


def test_supabase_url_forms_normalize_to_psycopg() -> None:
    assert (
        normalize_database_url("postgres://u:p@host:5432/db")
        == "postgresql+psycopg://u:p@host:5432/db"
    )
    assert (
        normalize_database_url("postgresql://u:p@host:5432/db")
        == "postgresql+psycopg://u:p@host:5432/db"
    )
    assert (
        normalize_database_url("postgresql+psycopg://u:p@host:5432/db")
        == "postgresql+psycopg://u:p@host:5432/db"
    )


def test_postgres_connect_args_use_ssl_and_timeout() -> None:
    args = _connect_args(
        "postgresql://u:p@host:5432/db",
        connect_timeout_s=7,
        sslmode="require",
        is_production=False,
    )
    assert args == {"connect_timeout": 7, "sslmode": "require"}


def test_ssl_in_url_is_not_duplicated() -> None:
    args = _connect_args(
        "postgresql://u:p@host:5432/db?sslmode=verify-full",
        connect_timeout_s=5,
        sslmode="require",
        is_production=True,
    )
    assert args == {"connect_timeout": 5}


def test_production_defaults_postgres_to_require_ssl() -> None:
    args = _connect_args(
        "postgresql://u:p@host:5432/db",
        connect_timeout_s=5,
        sslmode=None,
        is_production=True,
    )
    assert args["sslmode"] == "require"


def test_no_database_configuration_returns_none_and_503() -> None:
    get_settings.cache_clear()
    assert get_engine() is None
    dependency = get_db_session()
    with pytest.raises(DatabaseUnavailableError) as exc:
        next(dependency)
    assert exc.value.status_code == 503


def test_sqlite_engine_is_created_for_isolated_tests(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    get_settings.cache_clear()
    clear_engine_cache()
    engine = get_engine()
    assert engine is not None
    assert engine.dialect.name == "sqlite"


def test_settings_expose_supabase_derived_urls() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        supabase_url="https://project.supabase.co/",
    )
    assert settings.supabase_issuer == "https://project.supabase.co/auth/v1"
    assert (
        settings.supabase_jwks_url_value
        == "https://project.supabase.co/auth/v1/.well-known/jwks.json"
    )
