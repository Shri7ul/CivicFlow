"""Tests for API routing, CORS, and request logging."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


def test_openapi_contains_versioned_health_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/health" in paths
    assert "/api/v1/health/database" in paths


def test_cors_allows_configured_frontend_origin(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"] == "http://localhost:3000"
    )


def test_cors_preflight_succeeds(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"] == "http://localhost:3000"
    )


def test_cors_does_not_allow_unknown_origin(client: TestClient) -> None:
    response = client.get(
        "/api/v1/health",
        headers={"Origin": "https://untrusted.example"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_request_logging_records_method_path_status_and_duration(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="civicflow.request")

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert "Request | GET /api/v1/health | 200 |" in caplog.text
    assert "ms" in caplog.text
