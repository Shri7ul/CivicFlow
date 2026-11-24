"""Model governance and evaluation API tests."""

from __future__ import annotations

import uuid

import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import get_token_verifier
from app.core.config import Settings
from app.decisions.config import DecisionConfig
from app.governance.service import resolve_risk_config
from app.models import ModelVersion
from app.risk.config import RiskConfigError
from app.db.session import get_db_session
from app.main import create_app
from app.models import Profile, Role
from tests.auth_support import make_settings, make_token, make_verifier


def _profile(session: Session, role: Role, name: str) -> Profile:
    profile = Profile(id=uuid.uuid4(), full_name=name, role=role, is_active=True)
    session.add(profile)
    session.commit()
    return profile


def _client(session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    return TestClient(app)


def _auth(profile: Profile) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=profile.id)}"}


def test_model_registration_activation_and_events(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    with _client(db_session) as client:
        assert client.get("/api/v1/governance/models", headers=_auth(worker)).status_code == 200
        forbidden = client.post(
            "/api/v1/governance/models",
            headers=_auth(worker),
            json={"model_name": "risk", "version": "risk-test"},
        )
        assert forbidden.status_code == 403
        created = client.post(
            "/api/v1/governance/models",
            headers=_auth(admin),
            json={"model_name": "risk", "version": "risk-test", "description": "test"},
        )
        assert created.status_code == 201, created.text
        model = created.json()
        assert model["is_active"] is False
        activated = client.post(
            f"/api/v1/governance/models/{model['id']}/activate",
            headers=_auth(admin),
            json={"reason": "test activation"},
        )
        assert activated.status_code == 200, activated.text
        assert activated.json()["is_active"] is True
        runtime = client.get("/api/v1/governance/models/runtime", headers=_auth(worker))
        assert runtime.status_code == 200
        assert runtime.json()["risk"]["active"]["id"] == model["id"]
        events = client.get(
            f"/api/v1/governance/models/{model['id']}/events", headers=_auth(worker)
        )
        assert events.status_code == 200
        assert {item["action"] for item in events.json()} == {"REGISTERED", "ACTIVATED"}

        # Registering the same version/configuration is idempotent, while the
        # active pointer remains singular when a second version is activated.
        duplicate = client.post(
            "/api/v1/governance/models",
            headers=_auth(admin),
            json={"model_name": "risk", "version": "risk-test"},
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["id"] == model["id"]
        second = client.post(
            "/api/v1/governance/models",
            headers=_auth(admin),
            json={"model_name": "risk", "version": "risk-test-2"},
        )
        assert second.status_code == 201, second.text
        replacement = client.post(
            f"/api/v1/governance/models/{second.json()['id']}/activate",
            headers=_auth(admin),
            json={"reason": "replacement"},
        )
        assert replacement.status_code == 200, replacement.text
        runtime = client.get("/api/v1/governance/models/runtime", headers=_auth(worker))
        assert runtime.json()["risk"]["active"]["id"] == second.json()["id"]
        assert runtime.json()["risk"]["active"]["is_active"] is True
        first_detail = client.get(
            f"/api/v1/governance/models/{model['id']}/events", headers=_auth(worker)
        )
        assert {item["action"] for item in first_detail.json()} >= {
            "REGISTERED",
            "ACTIVATED",
            "DEACTIVATED",
        }


def test_synthetic_evaluation_is_persisted_and_labelled(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        model = client.post(
            "/api/v1/governance/models",
            headers=_auth(admin),
            json={"model_name": "risk", "version": "eval-model"},
        ).json()
        response = client.post(
            "/api/v1/governance/evaluations",
            headers=_auth(admin),
            json={
                "model_version_id": model["id"],
                "method": "SYNTHETIC_FIXTURE",
                "dataset_label": "synthetic unit fixture",
                "is_synthetic": True,
                "threshold": 50,
                "include_spatial": True,
                "time_split": True,
                "samples": [
                    {"predicted_score": 90, "observed": 1, "cell_id": "a"},
                    {"predicted_score": 70, "observed": 1, "cell_id": "a"},
                    {"predicted_score": 20, "observed": 0, "cell_id": "b"},
                    {"predicted_score": 10, "observed": 0, "cell_id": "b"},
                ],
            },
        )
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["is_synthetic"] is True
        assert payload["metrics"]["roc_auc"] == 1.0
        assert any("SYNTHETIC_FIXTURE" in warning for warning in payload["warnings"])
        assert payload["slices"]["spatial"]["group_count"] == 2
        listed = client.get(
            "/api/v1/governance/evaluations", headers=_auth(admin)
        )
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == payload["id"]


def test_synthetic_must_use_synthetic_method(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    with _client(db_session) as client:
        model = client.post(
            "/api/v1/governance/models",
            headers=_auth(admin),
            json={"model_name": "risk", "version": "validation-model"},
        ).json()
        response = client.post(
            "/api/v1/governance/evaluations",
            headers=_auth(admin),
            json={
                "model_version_id": model["id"],
                "method": "TIME_SPLIT",
                "dataset_label": "bad fixture",
                "is_synthetic": True,
                "samples": [{"predicted_score": 50, "observed": 1}],
            },
        )
        assert response.status_code == 422


def test_invalid_active_model_is_not_silently_replaced(db_session: Session) -> None:
    model = ModelVersion(
        model_name="risk",
        version="corrupt-active",
        config={"not": "a risk config"},
        config_hash="0" * 64,
        is_active=True,
    )
    db_session.add(model)
    db_session.commit()
    with pytest.raises(RiskConfigError):
        resolve_risk_config(
            db_session,
            Settings(_env_file=None, app_env="testing"),
        )


def test_active_decision_model_drives_simulation_config(db_session: Session) -> None:
    admin = _profile(db_session, Role.ADMIN, "Admin")
    worker = _profile(db_session, Role.WORKER, "Worker")
    settings = Settings(_env_file=None, app_env="testing")
    config = DecisionConfig.from_settings(settings).as_dict()
    config["max_actions"] = 9
    model = ModelVersion(
        model_name="decision",
        version="active-decision",
        config=config,
        config_hash="d" * 32,
        is_active=True,
    )
    db_session.add(model)
    db_session.commit()
    with _client(db_session) as client:
        response = client.get("/api/v1/decisions/config", headers=_auth(worker))
        assert response.status_code == 200, response.text
        assert response.json()["max_actions"] == 9
        assert response.json()["config_hash"] == DecisionConfig.from_dict(config).config_hash
