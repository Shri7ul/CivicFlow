"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.health import clear_engine_cache
from app.main import create_app
from app.models import Base
from app.weather.cache import grid_cache


@pytest.fixture(autouse=True)
def test_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate tests from any local .env values and cache state."""
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("API_V1_PREFIX", "/api/v1")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "true")
    monkeypatch.setenv("DATABASE_URL", "")
    # Weather tests opt in explicitly with a mock provider; no existing test
    # should make a real external API call.
    monkeypatch.setenv("WEATHER_ENABLED", "false")
    get_settings.cache_clear()
    clear_engine_cache()
    grid_cache.clear()
    yield
    get_settings.cache_clear()
    clear_engine_cache()
    grid_cache.clear()


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    """Isolated in-memory SQLite engine with foreign keys enabled.

    These are structural ORM tests only, not PostgreSQL/PostGIS integration.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine, expire_on_commit=False) as session:
        yield session
