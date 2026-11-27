"""Regression tests for deployment-facing resilience defects."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.jwt import get_token_verifier
from app.db.session import get_db_session
from app.main import create_app
from app.models import Base, Profile, Role
from tests.auth_support import make_settings, make_token, make_verifier


def _engine_without_notifications():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE workforce_notifications"))
    return engine


def _client(session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    return TestClient(app)


def _profile(session: Session, role: Role = Role.CITIZEN) -> Profile:
    profile = Profile(
        id=uuid.uuid4(), full_name="Resilience Test User", role=role, is_active=True
    )
    session.add(profile)
    session.commit()
    return profile


def _auth(profile: Profile) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=profile.id)}"}


def test_notifications_degrade_to_empty_inbox_when_table_is_missing() -> None:
    engine = _engine_without_notifications()
    with Session(engine) as session:
        profile = _profile(session)
        response = _client(session).get(
            "/api/v1/workforce/notifications", headers=_auth(profile)
        )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "unread": 0}


def test_mark_notification_read_is_not_a_500_when_table_is_missing() -> None:
    engine = _engine_without_notifications()
    with Session(engine) as session:
        profile = _profile(session)
        response = _client(session).post(
            f"/api/v1/workforce/notifications/{uuid.uuid4()}/read",
            headers=_auth(profile),
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "notification_not_found"


def test_auth_me_uses_live_database_role_not_a_token_claim() -> None:
    """A DB role change is visible with the original, unchanged JWT."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        profile = _profile(session, Role.CITIZEN)
        headers = _auth(profile)  # token claims contain no privileged role
        client = _client(session)

        before = client.get("/api/v1/auth/me", headers=headers)
        assert before.status_code == 200
        assert before.json()["role"] == "CITIZEN"

        profile.role = Role.ADMIN
        session.commit()
        session.refresh(profile)

        after = client.get("/api/v1/auth/me", headers=headers)
        assert after.status_code == 200
        assert after.json()["role"] == "ADMIN"
