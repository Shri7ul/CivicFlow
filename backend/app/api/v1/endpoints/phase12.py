"""Phase 12 geographic-context and Dhaka readiness APIs.

Staff-only. Context keys are validated against the central registry; an
unknown key is rejected rather than silently broadening a query. These roles
only read persisted data or documented configuration. They never activate a
pilot, a model, a dispatch action or a public alert.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_worker
from app.core.exceptions import AppError
from app.db.session import get_db_session
from app.geo.contexts import (
    UNKNOWN_CONTEXT_KEY,
    all_contexts,
    assert_context_known,
    get_context,
    pilot_area_selection_status,
)
from app.governance.dhaka_readiness import assess_dhaka_readiness
from app.models.evidence import EvidenceSnapshot
from app.models.geo import GeographicContextRecord
from app.models.validation import ValidationDataset

router = APIRouter()


def _serialize_context(row: GeographicContextRecord) -> dict:
    return {
        "key": row.context_key,
        "display_name": row.display_name,
        "country_code": row.country_code,
        "country_name": row.country_name,
        "kind": row.context_kind,
        "bbox_geojson": row.bbox_geojson,
        "center_geojson": row.center_geojson,
        "crs": row.crs,
        "provenance_basis": row.provenance_basis,
        "boundary_basis": row.boundary_basis,
        "boundary_status": row.boundary_status,
        "operational_authority": row.operational_authority,
        "is_pilot_eligible": row.is_pilot_eligible,
        "source_urls": row.source_urls,
        "notes": row.notes,
    }


def _require_known(key: str) -> str:
    # UNKNOWN is a valid query bucket (records with unprovenanced geography),
    # but it is not a registered operational context and cannot be asserted as
    # one. Everything else must match the registry exactly.
    if key == UNKNOWN_CONTEXT_KEY:
        return key
    try:
        return assert_context_known(key)
    except ValueError as error:
        raise AppError(str(error), status_code=422, code="unknown_geographic_context") from error


@router.get("/geography/contexts")
def list_contexts(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    rows = session.scalars(
        select(GeographicContextRecord).order_by(GeographicContextRecord.context_key)
    ).all()
    registered = {row.context_key: _serialize_context(row) for row in rows}
    # If migrations have not yet been applied (for example in structural ORM
    # tests), expose the authoritative registry definitions instead of an
    # empty list. Never invent an unregistered context.
    for definition in all_contexts():
        registered.setdefault(
            definition.key,
            {
                "key": definition.key,
                "display_name": definition.display_name,
                "country_code": definition.country_code,
                "country_name": definition.country_name,
                "kind": definition.kind.value,
                "bbox_geojson": definition.bbox.as_geojson(),
                "center_geojson": {
                    "latitude": definition.center_latitude,
                    "longitude": definition.center_longitude,
                },
                "crs": definition.crs,
                "provenance_basis": definition.provenance_basis,
                "boundary_basis": definition.boundary_basis,
                "boundary_status": definition.boundary_status.value,
                "operational_authority": definition.operational_authority,
                "is_pilot_eligible": definition.is_pilot_eligible,
                "source_urls": list(definition.source_urls),
                "notes": definition.notes,
            },
        )
    items = [registered[key] for key in sorted(registered)]
    return {
        "items": items,
        "count": len(items),
        "disclaimer": (
            "A geographic context is an identity and screening envelope, not "
            "evidence of operational status, verified ground truth or approval."
        ),
    }


@router.get("/geography/contexts/{context_key}")
def get_context_detail(
    context_key: str,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    key = _require_known(context_key)
    row = session.scalar(
        select(GeographicContextRecord).where(
            GeographicContextRecord.context_key == key
        )
    )
    if row is None:
        # Migration not yet applied: fall back to the authoritative registry
        # definition rather than inventing a row.
        definition = get_context(key)
        return {
            "key": definition.key,
            "display_name": definition.display_name,
            "country_code": definition.country_code,
            "country_name": definition.country_name,
            "kind": definition.kind.value,
            "bbox_geojson": definition.bbox.as_geojson(),
            "center_geojson": {
                "latitude": definition.center_latitude,
                "longitude": definition.center_longitude,
            },
            "crs": definition.crs,
            "provenance_basis": definition.provenance_basis,
            "boundary_basis": definition.boundary_basis,
            "boundary_status": definition.boundary_status.value,
            "operational_authority": definition.operational_authority,
            "is_pilot_eligible": definition.is_pilot_eligible,
            "source_urls": list(definition.source_urls),
            "notes": definition.notes,
        }
    return _serialize_context(row)


@router.get("/geography/pilot-areas")
def pilot_areas(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
) -> dict:
    del user
    return pilot_area_selection_status()


@router.get("/geography/readiness/dhaka")
def dhaka_readiness(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    return assess_dhaka_readiness(session)


@router.get("/geography/datasets")
def datasets_for_context(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    geographic_context: str = UNKNOWN_CONTEXT_KEY,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict:
    del user
    key = _require_known(geographic_context)
    rows = session.scalars(
        select(ValidationDataset)
        .where(ValidationDataset.geographic_context_key == key)
        .order_by(ValidationDataset.dataset_key)
        .limit(limit)
    ).all()
    return {
        "geographic_context_key": key,
        "items": [
            {
                "dataset_key": row.dataset_key,
                "name": row.name,
                "region": row.region,
                "geographic_context_key": row.geographic_context_key,
                "status": row.status.value,
                "record_count": row.record_count,
                "snapshot_sha256": row.snapshot_sha256,
                "class": "RESEARCH_DATASET",
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.get("/geography/snapshots")
def snapshots_for_context(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    geographic_context: str = UNKNOWN_CONTEXT_KEY,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict:
    del user
    key = _require_known(geographic_context)
    rows = session.scalars(
        select(EvidenceSnapshot)
        .where(EvidenceSnapshot.geographic_context_key == key)
        .order_by(EvidenceSnapshot.retrieved_at.desc())
        .limit(limit)
    ).all()
    return {
        "geographic_context_key": key,
        "items": [
            {
                "snapshot_key": row.snapshot_key,
                "geographic_context_key": row.geographic_context_key,
                "source_key": row.source_key,
                "kind": row.kind.value,
                "status": row.status.value,
                "provenance_kind": row.provenance_kind.value,
                "record_count": row.record_count,
                "geographic_coverage": row.geographic_coverage,
                "retrieved_at": row.retrieved_at.isoformat() if row.retrieved_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
        "disclaimer": "Raw bytes and personal observations are never returned by this endpoint.",
    }


@router.get("/geography/isolation")
def isolation_report(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    rows = session.scalars(
        select(
            EvidenceSnapshot.geographic_context_key,
            func.count(EvidenceSnapshot.id),
        ).group_by(EvidenceSnapshot.geographic_context_key)
    ).all()
    counts = {str(key or UNKNOWN_CONTEXT_KEY): int(total) for key, total in rows}
    cross_region = session.scalars(
        select(EvidenceSnapshot.snapshot_key).where(
            EvidenceSnapshot.geographic_context_key == "BD-DHAKA",
            EvidenceSnapshot.source_key.like("nyc%"),
        )
    ).all()
    return {
        "snapshot_counts_by_context": counts,
        "cross_region_dhaka_snapshots": list(cross_region),
        "isolated": not cross_region,
        "registered_contexts": sorted(
            [*(context.key for context in all_contexts()), UNKNOWN_CONTEXT_KEY]
        ),
        "disclaimer": (
            "This reports persisted geographic labels and source-key checks. "
            "It does not validate provenance authenticity or human verification."
        ),
    }
