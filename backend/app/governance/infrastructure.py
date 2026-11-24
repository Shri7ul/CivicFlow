"""Infrastructure source registry. Metadata only; no fetch or ingestion."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.governance.errors import GovernanceError
from app.models.enums import InfrastructureValidationStatus
from app.models.pilot import InfrastructureSource, InfrastructureSourceEvent

DOMAINS = (
    ("ROADS", "Roads"),
    ("BRIDGES", "Bridges"),
    ("PUBLIC_FACILITIES", "Public facilities"),
    ("WATER", "Water"),
    ("DRAINAGE", "Drainage"),
    ("EMERGENCY_FACILITIES", "Emergency facilities"),
    ("TRANSIT", "Transit"),
)


def get_source(session: Session, source_id: uuid.UUID) -> InfrastructureSource:
    source = session.get(InfrastructureSource, source_id)
    if source is None:
        raise GovernanceError(
            "Infrastructure source not found",
            status_code=404,
            code="infrastructure_source_not_found",
        )
    return source


def create_source(
    session: Session, payload: object, actor: AuthenticatedUser
) -> InfrastructureSource:
    data = payload
    existing = session.scalar(
        select(InfrastructureSource.id).where(
            InfrastructureSource.source_key == data.source_key
        )
    )
    if existing is not None:
        raise GovernanceError(
            "An infrastructure source with this key already exists",
            status_code=409,
            code="source_key_conflict",
        )
    source = InfrastructureSource(
        source_key=data.source_key,
        name=data.name,
        category=data.category,
        source_url=data.source_url,
        provider=data.provider,
        license_note=data.license_note,
        retrieved_at=data.retrieved_at,
        dataset_version=data.dataset_version,
        geographic_coverage=data.geographic_coverage,
        crs=data.crs,
        schema_version=data.schema_version,
        validation_status=InfrastructureValidationStatus.PENDING,
        snapshot_sha256=data.snapshot_sha256,
        update_frequency=data.update_frequency,
        known_limitations=data.known_limitations,
        details=data.metadata,
        created_by=actor.profile.id,
    )
    session.add(source)
    session.flush()
    session.add(
        InfrastructureSourceEvent(
            source_id=source.id,
            action="REGISTERED",
            from_status=None,
            to_status=InfrastructureValidationStatus.PENDING,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=(
                "Source registered for metadata review. Registration is not "
                "validation and no asset data was ingested."
            ),
        )
    )
    session.commit()
    return source


def decide_validation(
    session: Session,
    source: InfrastructureSource,
    target: InfrastructureValidationStatus,
    note: str,
    actor: AuthenticatedUser,
) -> InfrastructureSource:
    session.refresh(source, with_for_update=True)
    if target == InfrastructureValidationStatus.PENDING:
        raise GovernanceError(
            "A validation decision cannot return a source to PENDING",
            code="invalid_source_transition",
        )
    if target == source.validation_status:
        raise GovernanceError(
            "The source already has this validation status",
            status_code=409,
            code="source_status_unchanged",
        )
    clean = note.strip()
    if len(clean) < 10:
        raise GovernanceError(
            "A validation note of at least 10 characters is required",
            code="validation_note_required",
        )
    if target == InfrastructureValidationStatus.VERIFIED:
        missing = [
            field
            for field in (
                "snapshot_sha256",
                "license_note",
                "geographic_coverage",
                "crs",
                "schema_version",
            )
            if not getattr(source, field)
        ]
        if missing:
            raise GovernanceError(
                "Cannot verify source without: " + ", ".join(missing),
                status_code=409,
                code="source_metadata_incomplete",
            )
    previous = source.validation_status
    source.validation_status = target
    session.add(
        InfrastructureSourceEvent(
            source_id=source.id,
            action="VALIDATION_DECISION",
            from_status=previous,
            to_status=target,
            actor_id=actor.profile.id,
            actor_email=actor.email,
            note=clean,
        )
    )
    session.commit()
    return source


def events_for(
    session: Session, source_id: uuid.UUID
) -> list[InfrastructureSourceEvent]:
    return list(
        session.scalars(
            select(InfrastructureSourceEvent)
            .where(InfrastructureSourceEvent.source_id == source_id)
            .order_by(InfrastructureSourceEvent.created_at)
        ).all()
    )


def coverage(session: Session) -> dict:
    sources = session.scalars(select(InfrastructureSource)).all()
    rows = []
    for domain, label in DOMAINS:
        subset = [item for item in sources if item.category == domain]
        verified = [
            item
            for item in subset
            if item.validation_status == InfrastructureValidationStatus.VERIFIED
        ]
        if verified:
            state = "VERIFIED_METADATA"
        elif subset:
            state = "UNVERIFIED"
        else:
            state = "NO_SOURCE"
        rows.append(
            {
                "category": domain,
                "label": label,
                "state": state,
                "sources": len(subset),
                "verified": len(verified),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domains": rows,
        "verified_domains": sum(1 for row in rows if row["verified"]),
        "total_domains": len(rows),
        "asset_data_available": False,
        "disclaimer": (
            "Verified metadata means the registry fields were reviewed; it does "
            "not mean asset geometry, condition, or coverage was validated. No "
            "infrastructure assets were fetched or ingested in Phase 10."
        ),
    }
