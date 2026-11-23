"""Authentication, provisioning, RBAC, and audited role management API tests."""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    AuthenticatedUser,
    require_active_user,
    require_admin,
    require_worker,
)
from app.auth.jwt import get_token_verifier
from app.core.config import Settings
from app.db.session import get_db_session
from app.main import create_app
from app.models import Profile, Role, RoleChangeAudit
from app.services.profiles import change_profile_role
from tests.auth_support import make_settings, make_token, make_verifier


def _settings() -> Settings:
    return make_settings()


def _token(subject: uuid.UUID, **overrides: Any) -> str:
    return make_token(sub=subject, **overrides)


def _profile(
    session: Session,
    *,
    role: Role = Role.CITIZEN,
    is_active: bool = True,
    profile_id: uuid.UUID | None = None,
) -> Profile:
    profile = Profile(
        id=profile_id or uuid.uuid4(),
        full_name=f"{role.value.title()} User",
        role=role,
        is_active=is_active,
    )
    session.add(profile)
    session.commit()
    return profile


def _client(session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(_settings())
    return TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_missing_or_malformed_authorization_is_401(db_session: Session) -> None:
    with _client(db_session) as client:
        assert client.get("/api/v1/auth/me").status_code == 401
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Token abc"}
        )
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


def test_expired_and_invalid_tokens_are_401(db_session: Session) -> None:
    subject = uuid.uuid4()
    expired = _token(subject, exp=int(time.time()) - 10)
    with _client(db_session) as client:
        response = client.get("/api/v1/auth/me", headers=_auth(expired))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


def test_authenticated_profile_round_trip(db_session: Session) -> None:
    profile = _profile(db_session)
    with _client(db_session) as client:
        response = client.get("/api/v1/auth/me", headers=_auth(_token(profile.id)))
    assert response.status_code == 200
    assert response.json()["id"] == str(profile.id)
    assert response.json()["role"] == "CITIZEN"


def test_provisioning_is_idempotent_and_never_grants_claimed_privileges(
    db_session: Session,
) -> None:
    subject = uuid.uuid4()
    token = _token(subject)
    with _client(db_session) as client:
        missing = client.get("/api/v1/auth/me", headers=_auth(token))
        assert missing.status_code == 403
        assert missing.json()["error"]["code"] == "profile_required"

        first = client.post("/api/v1/auth/provision", headers=_auth(token), json={})
        assert first.status_code == 200
        assert first.json()["role"] == "CITIZEN"
        second = client.post(
            "/api/v1/auth/provision",
            headers=_auth(token),
            json={"full_name": "Claimed Admin"},
        )
        assert second.status_code == 200
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["role"] == "CITIZEN"
        assert second.json()["full_name"] != "Claimed Admin"

    assert (
        db_session.scalar(
            select(func.count()).select_from(Profile).where(Profile.id == subject)
        )
        == 1
    )


def test_provisioning_rejects_unknown_fields(db_session: Session) -> None:
    subject = uuid.uuid4()
    with _client(db_session) as client:
        response = client.post(
            "/api/v1/auth/provision",
            headers=_auth(_token(subject)),
            json={"role": "ADMIN"},
        )
    assert response.status_code == 422


def test_inactive_account_is_forbidden(db_session: Session) -> None:
    profile = _profile(db_session, is_active=False)
    with _client(db_session) as client:
        response = client.get("/api/v1/auth/me", headers=_auth(_token(profile.id)))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_inactive"


def test_own_profile_update_cannot_change_role(db_session: Session) -> None:
    profile = _profile(db_session)
    headers = _auth(_token(profile.id))
    with _client(db_session) as client:
        updated = client.patch(
            "/api/v1/auth/me",
            headers=headers,
            json={"full_name": "Updated Name", "phone": "+1 555 0100"},
        )
        assert updated.status_code == 200
        assert updated.json()["full_name"] == "Updated Name"
        assert updated.json()["phone"] == "+1 555 0100"
        assert updated.json()["role"] == "CITIZEN"

        role_attempt = client.patch(
            "/api/v1/auth/me", headers=headers, json={"role": "ADMIN"}
        )
        assert role_attempt.status_code == 422

        blank_name = client.patch(
            "/api/v1/auth/me", headers=headers, json={"full_name": "   "}
        )
        assert blank_name.status_code == 422


def test_admin_role_change_is_audited(db_session: Session) -> None:
    admin = _profile(db_session, role=Role.ADMIN)
    target = _profile(db_session)
    with _client(db_session) as client:
        response = client.patch(
            f"/api/v1/admin/profiles/{target.id}/role",
            headers=_auth(_token(admin.id)),
            json={"role": "WORKER", "reason": "Verified field staff"},
        )
    assert response.status_code == 200
    assert response.json()["role"] == "WORKER"

    audit = db_session.scalar(select(RoleChangeAudit))
    assert audit is not None
    assert audit.actor_id == admin.id
    assert audit.target_profile_id == target.id
    assert audit.old_role is Role.CITIZEN
    assert audit.new_role is Role.WORKER
    assert audit.reason == "Verified field staff"


def test_role_change_authorization_and_self_change_guards(db_session: Session) -> None:
    citizen = _profile(db_session)
    admin = _profile(db_session, role=Role.ADMIN)
    target = _profile(db_session)

    with _client(db_session) as client:
        forbidden = client.patch(
            f"/api/v1/admin/profiles/{target.id}/role",
            headers=_auth(_token(citizen.id)),
            json={"role": "ADMIN"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "insufficient_role"

        self_change = client.patch(
            f"/api/v1/admin/profiles/{admin.id}/role",
            headers=_auth(_token(admin.id)),
            json={"role": "CITIZEN"},
        )
        assert self_change.status_code == 400
        assert self_change.json()["error"]["code"] == "self_role_change_forbidden"

        unknown = client.patch(
            f"/api/v1/admin/profiles/{uuid.uuid4()}/role",
            headers=_auth(_token(admin.id)),
            json={"role": "WORKER"},
        )
        assert unknown.status_code == 404


def test_role_endpoint_rejects_invalid_role(db_session: Session) -> None:
    admin = _profile(db_session, role=Role.ADMIN)
    target = _profile(db_session)
    with _client(db_session) as client:
        response = client.patch(
            f"/api/v1/admin/profiles/{target.id}/role",
            headers=_auth(_token(admin.id)),
            json={"role": "SUPERADMIN"},
        )
    assert response.status_code == 422


def test_last_active_admin_guard_at_service_layer(db_session: Session) -> None:
    target_admin = _profile(db_session, role=Role.ADMIN)
    unpersisted_actor = Profile(
        id=uuid.uuid4(),
        full_name="Defensive Actor",
        role=Role.ADMIN,
        is_active=True,
    )
    with pytest.raises(Exception) as exc:
        change_profile_role(
            db_session,
            actor=unpersisted_actor,
            target_profile_id=target_admin.id,
            new_role=Role.CITIZEN,
        )
    assert getattr(exc.value, "code", None) == "last_admin_protected"


def _rbac_app(session: Session) -> TestClient:
    app = FastAPI()

    @app.get("/active")
    def active(user: AuthenticatedUser = Depends(require_active_user)) -> dict[str, str]:
        return {"role": user.profile.role.value}

    @app.get("/worker")
    def worker(user: AuthenticatedUser = Depends(require_worker)) -> dict[str, str]:
        return {"role": user.profile.role.value}

    @app.get("/admin")
    def admin(user: AuthenticatedUser = Depends(require_admin)) -> dict[str, str]:
        return {"role": user.profile.role.value}

    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(_settings())
    return TestClient(app)


@pytest.mark.parametrize(
    ("role", "worker_status", "admin_status"),
    [
        (Role.CITIZEN, 403, 403),
        (Role.WORKER, 200, 403),
        (Role.ADMIN, 200, 200),
    ],
)
def test_centralized_role_matrix(
    db_session: Session, role: Role, worker_status: int, admin_status: int
) -> None:
    profile = _profile(db_session, role=role)
    headers = _auth(_token(profile.id))
    with _rbac_app(db_session) as client:
        assert client.get("/active", headers=headers).status_code == 200
        assert client.get("/worker", headers=headers).status_code == worker_status
        assert client.get("/admin", headers=headers).status_code == admin_status


def test_rbac_rejects_inactive_profiles(db_session: Session) -> None:
    profile = _profile(db_session, role=Role.ADMIN, is_active=False)
    with _rbac_app(db_session) as client:
        assert client.get("/admin", headers=_auth(_token(profile.id))).status_code == 403
