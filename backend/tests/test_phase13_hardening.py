"""Phase 13 production-hardening and adversarial isolation tests.

All records created in this module are deterministic SYNTHETIC fixtures. They
are never counted as operational evidence, human verification or pilot
approval. Tests prove that missing evidence blocks readiness and that one
geographic context cannot borrow another context's data.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints import health as health_endpoint
from app.core.config import Settings, get_settings
from app.core.middleware import _FixedWindowLimiter, reset_limiter
from app.core.request_context import (
    REQUEST_ID_HEADER,
    get_request_id,
    normalize_request_id,
)
from app.db.health import DatabaseCheck
from app.evidence.workspace import build_workspace
from app.geo.contexts import BD_DHAKA, US_NYC, UNKNOWN_CONTEXT_KEY
from app.governance.dhaka_readiness import assess_dhaka_readiness
from app.models import (
    EvidenceQualityStatus,
    EvidenceSnapshot,
    EvidenceSnapshotKind,
    EvidenceSnapshotStatus,
    Profile,
    ProvenanceKind,
    Role,
    SnapshotVerificationStatus,
)


def _settings(**overrides: object) -> Settings:
    database_url = overrides.pop("database_url", None)
    return Settings(
        database_url=database_url,
        supabase_url="https://project.supabase.co",
        supabase_jwks_url="https://project.supabase.co/auth/v1/keys",
        **overrides,  # type: ignore[arg-type]
    )


def _request_id_shape(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", value))


# --- correlation ids --------------------------------------------------------


def test_request_id_accepts_safe_value_and_rejects_injection() -> None:
    assert normalize_request_id("trace-abc_123.4:5") == "trace-abc_123.4:5"
    malicious = normalize_request_id("abc\nX-Evil: 1")
    assert _request_id_shape(malicious)
    assert "\n" not in malicious
    assert normalize_request_id(None) != normalize_request_id(None)


def test_request_id_is_echoed_and_scoped(client: TestClient) -> None:
    assert get_request_id() == "-"
    response = client.get(
        "/api/v1/health", headers={REQUEST_ID_HEADER: "p13-trace-001"}
    )
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "p13-trace-001"

    unsafe = client.get("/api/v1/health", headers={REQUEST_ID_HEADER: "bad\nvalue"})
    assert _request_id_shape(unsafe.headers[REQUEST_ID_HEADER])
    assert unsafe.headers[REQUEST_ID_HEADER] != "bad\nvalue"
    assert get_request_id() == "-"


# --- security headers -------------------------------------------------------


def test_security_headers_present_without_exposing_secrets(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert "geolocation=()" in headers["permissions-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]

    body = response.text.lower()
    for marker in ("postgres://", "service_role", "supabase_service_role_key", "traceback"):
        assert marker not in body


def test_error_responses_do_not_leak_stack_traces(client: TestClient) -> None:
    missing = client.get("/api/v1/governance/geography/contexts/DOES-NOT-EXIST")
    assert missing.status_code in {401, 403, 404, 422}
    assert "Traceback" not in missing.text
    assert "File \"" not in missing.text


# --- readiness / dependency health -----------------------------------------


def test_readiness_is_dependency_gated(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        health_endpoint,
        "check_database",
        lambda: DatabaseCheck(
            configured=True, reachable=False, message="Database unavailable."
        ),
    )
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["database"] == "unreachable"
    assert body["build_version"]


def test_readiness_passes_only_with_reachable_database(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        health_endpoint,
        "check_database",
        lambda: DatabaseCheck(
            configured=True, reachable=True, message="Database connection is available."
        ),
    )
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_dependency_endpoint_reports_booleans_only(client: TestClient) -> None:
    response = client.get("/api/v1/health/dependencies")
    assert response.status_code in {200, 503}
    body = response.json()
    assert set(body) == {
        "status",
        "build_version",
        "database",
        "auth_verification_configured",
        "evidence_storage_configured",
    }
    assert isinstance(body["auth_verification_configured"], bool)
    assert body["database"] in {"reachable", "unreachable", "not_configured"}


# --- production configuration ----------------------------------------------


def test_production_hardening_defaults() -> None:
    settings = _settings(
        app_env="production", database_url="postgresql://user@localhost/civicflow"
    )
    assert settings.is_production
    assert settings.rate_limiting_active is True
    assert settings.docs_effective_enabled is False
    assert settings.security_headers_enabled is True

    explicit = _settings(
        app_env="production",
        database_url="postgresql://user@localhost/civicflow",
        rate_limit_enabled=False,
        api_docs_enabled=True,
    )
    assert explicit.rate_limiting_active is False


def test_production_rejects_insecure_configuration() -> None:
    with pytest.raises(ValueError):
        _settings(
            app_env="production",
            database_url="postgresql://user@localhost/civicflow",
            cors_origins=["*"],
            cors_allow_credentials=True,
        )
    with pytest.raises(ValueError):
        _settings(app_env="production", database_url=None)
    with pytest.raises(ValueError):
        _settings(
            app_env="production",
            database_url="postgresql://user@localhost/civicflow",
            debug=True,
        )


# --- rate limiting ----------------------------------------------------------


def test_fixed_window_limiter_blocks_excess_requests() -> None:
    limiter = _FixedWindowLimiter(limit=2, window_seconds=60)
    now = time.monotonic()
    assert limiter.allow("peer-a", now)
    assert limiter.allow("peer-a", now + 0.1)
    assert not limiter.allow("peer-a", now + 0.2)
    assert limiter.allow("peer-b", now)
    assert limiter.allow("peer-a", now + 61)
    reset_limiter()


# --- geographic isolation matrix -------------------------------------------


def _snapshot(
    session: Session, *, context_key: str, key: str, source_key: str
) -> EvidenceSnapshot:
    raw = json.dumps({"fixture": True, "context": context_key}).encode("utf-8")
    normalized = json.dumps([{"fixture": True}]).encode("utf-8")
    snapshot = EvidenceSnapshot(
        snapshot_key=key,
        kind=EvidenceSnapshotKind.RESEARCH_DATASET,
        provenance_kind=ProvenanceKind.SYNTHETIC,
        status=EvidenceSnapshotStatus.VALIDATED,
        source_key=source_key,
        source_url="https://example.invalid/synthetic-fixture",
        provider="SYNTHETIC TEST FIXTURE",
        license_note="Synthetic fixture; not operational evidence.",
        dataset_version="fixture-v1",
        retrieved_at=datetime.now(timezone.utc),
        snapshot_sha256=hashlib.sha256(normalized).hexdigest(),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        schema_version="fixture-v1",
        record_count=1,
        raw_record_count=1,
        byte_size=len(normalized),
        crs="EPSG:4326",
        bbox=(
            [-74.0, 40.6, -73.9, 40.7]
            if context_key == US_NYC.key
            else [90.39, 23.78, 90.41, 23.80]
        ),
        geographic_coverage="Synthetic fixture",
        geographic_context_key=context_key,
        quality_status=EvidenceQualityStatus.PASS,
        quality_checks=[],
        lineage={"fixture": True},
        verification_status=SnapshotVerificationStatus.PENDING,
        is_current=True,
        raw_content=raw,
        normalized_content=normalized,
    )
    session.add(snapshot)
    session.commit()
    return snapshot


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(US_NYC.key, 1), (BD_DHAKA.key, 1), (UNKNOWN_CONTEXT_KEY, 0)],
)
def test_context_matrix_never_returns_foreign_or_unknown_rows(
    db_session: Session, requested: str, expected: int
) -> None:
    _snapshot(db_session, context_key=US_NYC.key, key="p13-nyc", source_key="nyc311-x")
    _snapshot(
        db_session,
        context_key=BD_DHAKA.key,
        key="p13-dhaka",
        source_key="dhaka-osm-x",
    )
    workspace = build_workspace(db_session, geographic_context_key=requested)
    keys = {row["geographic_context_key"] for row in workspace["snapshots"]}
    assert len(workspace["snapshots"]) == expected
    assert keys <= {requested}


def test_client_supplied_context_cannot_widen_scope(db_session: Session) -> None:
    """A caller cannot ask for one context and receive another context's rows."""
    from app.auth.dependencies import get_token_verifier
    from app.db.session import get_db_session
    from app.main import create_app
    from tests.auth_support import make_settings, make_token, make_verifier

    _snapshot(db_session, context_key=US_NYC.key, key="p13-nyc-api", source_key="nyc311-y")
    profile = Profile(id=uuid.uuid4(), full_name="Worker", role=Role.WORKER, is_active=True)
    db_session.add(profile)
    db_session.commit()

    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: make_verifier(make_settings())
    client = TestClient(app)
    headers = {
        "Authorization": "Bearer "
        + make_token(sub=profile.id, email=f"{profile.id}@example.com")
    }
    response = client.get(
        "/api/v1/governance/evidence/workspace",
        params={"geographic_context": BD_DHAKA.key},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["snapshots"] == []
    assert response.json()["geographic_context_key"] == BD_DHAKA.key


# --- readiness gate integrity ------------------------------------------------


def test_readiness_payload_never_contains_activation_authorization(
    db_session: Session,
) -> None:
    report = assess_dhaka_readiness(db_session)
    assert report["pilot_activation_authorized"] is False
    assert report["ready_for_activation"] is False
    assert report["overall"] == "NOT_READY"
    assert "model_activation" in str(report).lower() or "model" in str(report).lower()


def test_missing_mandatory_evidence_never_passes(db_session: Session) -> None:
    report = assess_dhaka_readiness(db_session)
    mandatory = {item["key"] for item in report["categories"] if item.get("mandatory")}
    assert len(mandatory) >= 10
    assert report["mandatory_unmet"]
    for key in report["mandatory_unmet"]:
        assert key in mandatory or key in {c["key"] for c in report["categories"]}
    assert all(item["status"] != "PASS" for item in report["categories"] if item.get("mandatory"))


# --- migration / RLS regression guards --------------------------------------


def test_migration_0023_preserves_rls_and_evidence_history() -> None:
    backend = Path(__file__).resolve().parents[1]
    migration = (
        backend / "alembic" / "versions" / "0023_phase12_geography.py"
    ).read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL" in migration and "GRANT SELECT" in migration
    assert "geographic_context_key" in migration
    assert "downgrade" in migration
    # The backfill only populates the new column; it must not rewrite hashes,
    # provenance, raw/normalized content or history.
    for forbidden in (
        "DROP TABLE evidence_snapshots",
        "DELETE FROM",
        "snapshot_sha256 =",
        "raw_sha256 =",
        "provenance_kind =",
    ):
        assert forbidden not in migration


def test_runtime_settings_never_expose_service_role_key() -> None:
    secret = "phase13-distinct-secret-value-9f3a"
    settings = _settings(supabase_service_role_key=secret)
    assert secret not in str(settings)
    assert secret not in repr(settings)
    assert settings.supabase_service_role_key is not None
    assert settings.supabase_service_role_key.get_secret_value() == secret
    assert get_settings() is not None
