"""Tests for health endpoints and database health behavior."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import health as health_endpoint
from app.core.config import get_settings
from app.db.health import DatabaseCheck, check_database, clear_engine_cache
from app.schemas.health import HealthResponse


def test_application_starts_and_responds(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_response_schema(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    payload = response.json()

    assert payload == {
        "status": "healthy",
        "service": "CivicFlow API",
        "environment": "testing",
        "version": "v1",
    }
    assert HealthResponse.model_validate(payload).status == "healthy"


def test_health_does_not_claim_database_status(client: TestClient) -> None:
    payload = client.get("/api/v1/health").json()
    assert "database" not in payload


def test_database_health_reports_not_configured(client: TestClient) -> None:
    response = client.get("/api/v1/health/database")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_configured",
        "database": "not_configured",
        "message": "Database is not configured for this environment.",
    }


def test_database_health_reports_reachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        health_endpoint,
        "check_database",
        lambda: DatabaseCheck(
            configured=True,
            reachable=True,
            message="Database connection is available.",
        ),
    )

    response = client.get("/api/v1/health/database")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["database"] == "reachable"


def test_database_health_reports_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        health_endpoint,
        "check_database",
        lambda: DatabaseCheck(
            configured=True,
            reachable=False,
            message="Database is configured but unreachable.",
        ),
    )

    response = client.get("/api/v1/health/database")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["database"] == "unreachable"


def test_invalid_database_url_is_handled_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "not-a-valid-database-url")
    get_settings.cache_clear()
    clear_engine_cache()

    check = check_database()

    assert check.configured is True
    assert check.reachable is False
    assert check.message == "Database configuration is invalid."
    assert "not-a-valid-database-url" not in check.message
