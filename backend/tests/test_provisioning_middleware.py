"""Regression tests for authenticated provisioning with rate limiting enabled.

The default test environment disables rate limiting, which allowed a middleware
bug to reach production: an allowed mutating request left `response` unbound
and returned 500 instead of reaching the application. These tests force the
production-like code path without touching any live system.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.core.middleware as middleware
from app.auth.jwt import get_token_verifier
from app.db.session import get_db_session
from app.main import create_app
from app.models import Profile, Role
from tests.auth_support import make_settings, make_token, make_verifier


def _token(subject: uuid.UUID, **overrides: Any) -> str:
    return make_token(sub=subject, **overrides)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def limited_client(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    settings = make_settings(
        rate_limit_enabled=True,
        rate_limit_requests_per_minute=100,
        security_headers_enabled=True,
    )
    monkeypatch.setattr(middleware, "get_settings", lambda: settings)
    middleware.reset_limiter()
    app: FastAPI = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    middleware.reset_limiter()


def test_allowed_mutating_request_reaches_app_not_500(
    limited_client: TestClient,
) -> None:
    """An allowed POST must be handled by FastAPI, returning 401 without a token."""
    response = limited_client.post("/api/v1/auth/provision", json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"
    assert response.headers.get("x-request-id")


def test_invalid_token_provisioning_is_401_not_500(
    limited_client: TestClient,
) -> None:
    response = limited_client.post(
        "/api/v1/auth/provision",
        headers={"Authorization": "Bearer invalid.token.here"},
        json={},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


def test_new_user_provisioning_lifecycle_under_rate_limiting(
    limited_client: TestClient, db_session: Session
) -> None:
    subject = uuid.uuid4()
    token = _token(subject)

    missing = limited_client.get("/api/v1/auth/me", headers=_auth(token))
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "profile_required"

    provision = limited_client.post(
        "/api/v1/auth/provision", headers=_auth(token), json={}
    )
    assert provision.status_code == 200
    assert provision.json()["id"] == str(subject)
    assert provision.json()["role"] == Role.CITIZEN.value

    loaded = limited_client.get("/api/v1/auth/me", headers=_auth(token))
    assert loaded.status_code == 200
    assert loaded.json()["id"] == str(subject)

    assert (
        db_session.scalar(
            select(func.count()).select_from(Profile).where(Profile.id == subject)
        )
        == 1
    )


def test_existing_profile_is_reused_and_not_duplicated(
    limited_client: TestClient, db_session: Session
) -> None:
    subject = uuid.uuid4()
    headers = _auth(_token(subject))

    first = limited_client.post(
        "/api/v1/auth/provision", headers=headers, json={"full_name": "First Name"}
    )
    second = limited_client.post(
        "/api/v1/auth/provision", headers=headers, json={"full_name": "Second Name"}
    )
    assert first.status_code == second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["full_name"] == "First Name"
    assert (
        db_session.scalar(
            select(func.count()).select_from(Profile).where(Profile.id == subject)
        )
        == 1
    )


def test_low_limit_returns_429_without_crashing_middleware(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = make_settings(
        rate_limit_enabled=True,
        rate_limit_requests_per_minute=10,
        security_headers_enabled=True,
    )
    monkeypatch.setattr(middleware, "get_settings", lambda: settings)
    middleware.reset_limiter()
    app: FastAPI = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            results = [
                client.post("/api/v1/auth/provision", json={}) for _ in range(11)
            ]
        assert [item.status_code for item in results[:10]] == [401] * 10
        throttled = results[-1]
        assert throttled.status_code == 429
        assert throttled.headers.get("retry-after") == "60"
    finally:
        middleware.reset_limiter()


def test_database_failure_is_a_structured_500(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dependency failure must not surface as an UnboundLocalError."""
    settings = make_settings(
        rate_limit_enabled=True,
        rate_limit_requests_per_minute=100,
        security_headers_enabled=True,
    )
    monkeypatch.setattr(middleware, "get_settings", lambda: settings)
    middleware.reset_limiter()

    def _broken_session() -> Session:
        raise RuntimeError("simulated database failure")

    app: FastAPI = create_app()
    app.dependency_overrides[get_db_session] = _broken_session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/auth/provision",
                headers=_auth(_token(uuid.uuid4())),
                json={},
            )
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "internal_server_error"
    finally:
        middleware.reset_limiter()
