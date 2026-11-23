"""Database constraint tests on isolated SQLite.

These verify portable CHECK/UNIQUE/FK behavior. PostGIS index/type compilation
is verified separately by rendering the PostgreSQL migration offline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AssetType,
    Department,
    DependencyEdge,
    DependencyType,
    Incident,
    IncidentCategory,
    IncidentCluster,
    IncidentClusterMember,
    IncidentEvidence,
    IncidentRelationship,
    IncidentSeverity,
    IncidentStatus,
    InfrastructureAsset,
    Profile,
    RelationshipStatus,
    RelationshipType,
    RiskCell,
    Role,
)


def _profile(session: Session, *, role: Role = Role.CITIZEN) -> Profile:
    profile = Profile(
        id=uuid.uuid4(), full_name="Constraint User", role=role, is_active=True
    )
    session.add(profile)
    session.flush()
    return profile


def _incident(session: Session, reporter: Profile) -> Incident:
    incident = Incident(
        title="Test incident",
        description="Test description",
        category=IncidentCategory.ROADS,
        severity=IncidentSeverity.MEDIUM,
        location="POINT(90.4 23.8)",
        reporter_id=reporter.id,
    )
    session.add(incident)
    session.flush()
    return incident


def test_foreign_key_rejects_missing_reporter(db_session: Session) -> None:
    incident = Incident(
        title="Orphan incident",
        description="No profile",
        category=IncidentCategory.ROADS,
        severity=IncidentSeverity.LOW,
        location="POINT(90.4 23.8)",
        reporter_id=uuid.uuid4(),
    )
    db_session.add(incident)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_department_names_are_case_insensitively_unique(db_session: Session) -> None:
    db_session.add(Department(name="Public Works", is_active=True))
    db_session.flush()
    db_session.add(Department(name="public works", is_active=True))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_profile_role_check_constraint(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO profiles (id, full_name, role, is_active) "
                "VALUES (:id, 'Bad Role', 'SUPERADMIN', 1)"
            ),
            {"id": str(uuid.uuid4())},
        )
        db_session.commit()
    db_session.rollback()


def test_incident_enum_checks_and_resolved_timestamp(db_session: Session) -> None:
    reporter = _profile(db_session)
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO incidents "
                "(id, title, description, category, severity, status, location, reporter_id) "
                "VALUES (:id, 'Bad', 'Bad', 'NOT_A_CATEGORY', 'LOW', 'OPEN', 'POINT(0 0)', :rid)"
            ),
            {"id": str(uuid.uuid4()), "rid": str(reporter.id)},
        )
        db_session.commit()
    db_session.rollback()

    incident = _incident(db_session, reporter)
    incident.resolved_at = incident.created_at - timedelta(minutes=1)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_evidence_file_size_must_be_positive(db_session: Session) -> None:
    reporter = _profile(db_session)
    incident = _incident(db_session, reporter)
    db_session.add(
        IncidentEvidence(
            incident_id=incident.id,
            uploaded_by=reporter.id,
            storage_path="x/empty.jpg",
            file_name="empty.jpg",
            mime_type="image/jpeg",
            file_size=0,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_evidence_mime_type_is_allowlisted(db_session: Session) -> None:
    reporter = _profile(db_session)
    incident = _incident(db_session, reporter)
    db_session.add(
        IncidentEvidence(
            incident_id=incident.id,
            uploaded_by=reporter.id,
            storage_path="x/script.svg",
            file_name="script.svg",
            mime_type="image/svg+xml",
            file_size=10,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_evidence_file_size_has_ten_megabyte_cap(db_session: Session) -> None:
    reporter = _profile(db_session)
    incident = _incident(db_session, reporter)
    db_session.add(
        IncidentEvidence(
            incident_id=incident.id,
            uploaded_by=reporter.id,
            storage_path="x/huge.jpg",
            file_name="huge.jpg",
            mime_type="image/jpeg",
            file_size=10 * 1024 * 1024 + 1,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_evidence_storage_path_is_unique(db_session: Session) -> None:
    reporter = _profile(db_session)
    incident = _incident(db_session, reporter)
    for _ in range(2):
        db_session.add(
            IncidentEvidence(
                incident_id=incident.id,
                uploaded_by=reporter.id,
                storage_path="same/path.jpg",
                file_name="a.jpg",
                mime_type="image/jpeg",
                file_size=10,
            )
        )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cluster_membership_duplicate_and_single_cluster_constraints(
    db_session: Session,
) -> None:
    reporter = _profile(db_session)
    incident = _incident(db_session, reporter)
    cluster = IncidentCluster(
        category=IncidentCategory.ROADS,
        centroid="POINT(90.4 23.8)",
    )
    other = IncidentCluster(
        category=IncidentCategory.ROADS,
        centroid="POINT(90.5 23.9)",
    )
    db_session.add_all([cluster, other])
    db_session.flush()

    db_session.add(
        IncidentClusterMember(cluster_id=cluster.id, incident_id=incident.id)
    )
    db_session.commit()

    db_session.add(
        IncidentClusterMember(cluster_id=cluster.id, incident_id=incident.id)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(
        IncidentClusterMember(cluster_id=other.id, incident_id=incident.id)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_asset_criticality_and_dependency_checks(db_session: Session) -> None:
    asset = InfrastructureAsset(
        name="Road",
        asset_type=AssetType.ROAD,
        location="LINESTRING(0 0, 1 1)",
        criticality_score=Decimal("8.5"),
        metadata_json={},
    )
    db_session.add(asset)
    db_session.flush()

    bad_criticality = InfrastructureAsset(
        name="Bad asset",
        asset_type=AssetType.OTHER,
        location="POINT(0 0)",
        criticality_score=Decimal("11"),
    )
    db_session.add(bad_criticality)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_dependency_edges_prevent_self_and_duplicates(db_session: Session) -> None:
    a = InfrastructureAsset(
        name="A",
        asset_type=AssetType.ROAD,
        location="POINT(0 0)",
        criticality_score=1,
    )
    b = InfrastructureAsset(
        name="B",
        asset_type=AssetType.HOSPITAL,
        location="POINT(1 1)",
        criticality_score=2,
    )
    db_session.add_all([a, b])
    db_session.commit()

    db_session.add(
        DependencyEdge(
            source_asset_id=a.id,
            target_asset_id=a.id,
            dependency_type=DependencyType.SERVES,
            strength=Decimal("1"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    edge = DependencyEdge(
        source_asset_id=a.id,
        target_asset_id=b.id,
        dependency_type=DependencyType.SERVES,
        strength=Decimal("1"),
    )
    db_session.add(edge)
    db_session.commit()
    db_session.add(
        DependencyEdge(
            source_asset_id=a.id,
            target_asset_id=b.id,
            dependency_type=DependencyType.SERVES,
            strength=Decimal("0.5"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_risk_cell_ranges_and_unique_h3(db_session: Session) -> None:
    cell = RiskCell(
        h3_cell_id="8928308280fffff",
        resolution=9,
        boundary="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
        current_risk_score=Decimal("50"),
        incident_count=2,
    )
    db_session.add(cell)
    db_session.commit()

    db_session.add(
        RiskCell(
            h3_cell_id="8928308280fffff",
            resolution=9,
            boundary="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(
        RiskCell(
            h3_cell_id="8928308280ffffe",
            resolution=99,
            boundary="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
            current_risk_score=Decimal("101"),
            incident_count=-1,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_incident_relationship_constraints_and_unique_pair(
    db_session: Session,
) -> None:
    reporter = _profile(db_session)
    db_session.commit()
    first = _incident(db_session, reporter)
    second = _incident(db_session, reporter)
    db_session.commit()

    relationship = IncidentRelationship(
        incident_a_id=min(first.id, second.id, key=str),
        incident_b_id=max(first.id, second.id, key=str),
        relationship_type=RelationshipType.DUPLICATE,
        status=RelationshipStatus.CONFIRMED,
        confidence=Decimal("0.900"),
        signals={"distance_m": 10},
    )
    db_session.add(relationship)
    db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(
            IncidentRelationship(
                incident_a_id=relationship.incident_a_id,
                incident_b_id=relationship.incident_b_id,
                relationship_type=RelationshipType.DUPLICATE,
                status=RelationshipStatus.DISMISSED,
                confidence=Decimal("0.400"),
            )
        )
        db_session.commit()
    db_session.rollback()

    with pytest.raises(IntegrityError):
        db_session.add(
            IncidentRelationship(
                incident_a_id=first.id,
                incident_b_id=first.id,
                relationship_type=RelationshipType.RELATED,
                status=RelationshipStatus.CONFIRMED,
                confidence=Decimal("0.500"),
            )
        )
        db_session.commit()
    db_session.rollback()
