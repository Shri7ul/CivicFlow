"""Schema metadata and relationship tests (portable structural only)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Uuid, inspect
from sqlalchemy.orm import Session

from app.models import (
    AssetType,
    Base,
    Department,
    Incident,
    IncidentCategory,
    IncidentEvidence,
    IncidentSeverity,
    IncidentStatusEvent,
    InfrastructureAsset,
    Profile,
    Role,
    Scenario,
)

EXPECTED_TABLES = {
    "profiles",
    "departments",
    "incidents",
    "incident_evidence",
    "incident_status_events",
    "incident_relationships",
    "incident_clusters",
    "incident_cluster_members",
    "infrastructure_assets",
    "dependency_edges",
    "risk_cells",
    "risk_model_runs",
    "risk_cell_snapshots",
    "risk_assessments",
    "scenarios",
    "scenario_results",
    "decision_scenarios",
    "decision_actions",
    "action_resource_requirements",
    "response_resources",
    "decision_simulations",
    "role_change_audits",
    "model_versions",
    "model_version_events",
    "model_evaluations",
    "data_sources",
    "ingestion_runs",
    "ingested_records",
    "data_quality_snapshots",
    "alert_rules",
    "alerts",
    "notifications",
    "notification_preferences",
    "decision_reviews",
    "decision_review_events",
    "validation_datasets",
    "validation_experiments",
    "pilots",
    "pilot_reviewers",
    "pilot_transitions",
    "risk_review_cases",
    "risk_review_events",
    "correlation_candidates",
    "correlation_reviews",
    "infrastructure_sources",
    "infrastructure_source_events",
    "readiness_evidence",
    "readiness_evidence_events",
    "evidence_snapshots",
    "evidence_snapshot_events",
    "ground_truth_records",
    "ground_truth_events",
    "correlation_universes",
    "geographic_contexts",
    "pilot_boundaries",
    "pilot_boundary_events",
    "field_observations",
    "field_observation_events",
    "pilot_data_sources",
    "pilot_incidents",
    "pilot_incident_events",
    "baseline_comparisons",
    "pilot_shutdowns",
    "phase14_attestations",
    "phase14_attestation_events",
}


def test_registry_contains_all_goal_03_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_uuid_primary_keys_and_timezone_timestamps() -> None:
    for table_name in EXPECTED_TABLES:
        table = Base.metadata.tables[table_name]
        if "id" in table.c:
            assert isinstance(table.c.id.type, Uuid), table_name
        if "created_at" in table.c:
            assert isinstance(table.c.created_at.type, DateTime)
            assert table.c.created_at.type.timezone is True
        if "updated_at" in table.c:
            assert isinstance(table.c.updated_at.type, DateTime)
            assert table.c.updated_at.type.timezone is True


def test_postgis_spatial_indexes_are_explicit_gist() -> None:
    spatial = {
        "incidents": "ix_incidents_location_gist",
        "incident_clusters": "ix_incident_clusters_centroid_gist",
        "infrastructure_assets": "ix_infrastructure_assets_location_gist",
        "risk_cells": "ix_risk_cells_boundary_gist",
    }
    for table_name, index_name in spatial.items():
        table = Base.metadata.tables[table_name]
        index = next(idx for idx in table.indexes if idx.name == index_name)
        assert index.dialect_options["postgresql"]["using"] == "gist"


def test_relationship_round_trip(db_session: Session) -> None:
    profile = Profile(
        id=uuid.uuid4(),
        full_name="Test Reporter",
        role=Role.CITIZEN,
        is_active=True,
    )
    department = Department(name="Public Works", is_active=True)
    db_session.add_all([profile, department])
    db_session.flush()

    incident = Incident(
        title="Blocked drain",
        description="Water is pooling on Central Avenue.",
        category=IncidentCategory.DRAINAGE,
        severity=IncidentSeverity.HIGH,
        location="POINT(90.4125 23.8103)",
        reporter_id=profile.id,
        assigned_department_id=department.id,
        resolved_at=None,
    )
    db_session.add(incident)
    db_session.flush()

    evidence = IncidentEvidence(
        incident_id=incident.id,
        uploaded_by=profile.id,
        storage_path="incidents/photo.jpg",
        file_name="photo.jpg",
        mime_type="image/jpeg",
        file_size=1234,
    )
    db_session.add(evidence)
    db_session.commit()

    assert incident.reporter.id == profile.id
    assert incident.assigned_department.name == "Public Works"
    assert incident.evidence[0].uploader.id == profile.id
    assert profile.reported_incidents[0].id == incident.id
    assert incident.created_at.tzinfo is not None or isinstance(
        incident.created_at, datetime
    )


def test_jsonb_columns_store_structured_metadata(db_session: Session) -> None:
    from app.models import InfrastructureAsset

    asset = InfrastructureAsset(
        name="Central Avenue",
        asset_type=AssetType.ROAD,
        location="LINESTRING(90.41 23.81, 90.42 23.82)",
        criticality_score=8.5,
        metadata_json={"lanes": 4, "seed": True},
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    assert asset.metadata_json["lanes"] == 4


def test_uuid_defaults_are_generated_for_non_auth_entities(db_session: Session) -> None:
    department = Department(name="Drainage & Sanitation", is_active=True)
    db_session.add(department)
    db_session.commit()
    assert isinstance(department.id, uuid.UUID)


def test_profile_id_requires_explicit_supabase_identity() -> None:
    profile = Profile(full_name="No Identity", role=Role.CITIZEN, is_active=True)
    assert profile.id is None


def test_inspector_reports_foreign_keys(db_engine) -> None:
    inspector = inspect(db_engine)
    incidents_fks = {fk["referred_table"] for fk in inspector.get_foreign_keys("incidents")}
    assert {"profiles", "departments"}.issubset(incidents_fks)
    evidence_fks = {
        fk["referred_table"]
        for fk in inspector.get_foreign_keys("incident_evidence")
    }
    assert {"incidents", "profiles"}.issubset(evidence_fks)


def test_json_columns_have_database_server_defaults() -> None:
    assert InfrastructureAsset.__table__.c.metadata.server_default is not None
    assert Scenario.__table__.c.parameters.server_default is not None
