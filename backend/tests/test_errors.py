"""Tests for consistent error handling."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.exceptions import AppError


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
        }
    }


def test_validation_errors_use_error_envelope(app: FastAPI) -> None:
    @app.get("/api/v1/test/validation/{item_id}")
    def validation_route(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    with TestClient(app) as client:
        response = client.get("/api/v1/test/validation/not-an-integer")

    assert response.status_code == 422
    payload = response.json()["error"]
    assert payload["code"] == "validation_error"
    assert payload["message"] == "Request validation failed."
    assert payload["details"][0]["field"] == "path.item_id"


def test_http_exceptions_use_error_envelope(app: FastAPI) -> None:
    @app.get("/api/v1/test/conflict")
    def conflict_route() -> None:
        raise HTTPException(status_code=409, detail="Resource is already closed")

    with TestClient(app) as client:
        response = client.get("/api/v1/test/conflict")

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "conflict",
        "message": "Resource is already closed",
    }


def test_application_errors_use_error_envelope(app: FastAPI) -> None:
    @app.get("/api/v1/test/application-error")
    def application_error_route() -> None:
        raise AppError(
            "Invalid operation",
            status_code=400,
            details=[{"field": "status", "message": "Not allowed"}],
        )

    with TestClient(app) as client:
        response = client.get("/api/v1/test/application-error")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"
    assert response.json()["error"]["details"] == [
        {"field": "status", "message": "Not allowed"}
    ]


def test_unexpected_errors_are_safe(app: FastAPI) -> None:
    @app.get("/api/v1/test/unexpected")
    def unexpected_route() -> None:
        raise RuntimeError("password=super-secret")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/test/unexpected")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred.",
        }
    }
    assert "super-secret" not in response.text
    assert "RuntimeError" not in response.text


def test_not_found_errors_are_safe(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/missing")

    assert "Traceback" not in response.text
    assert "starlette" not in response.text.lower()
