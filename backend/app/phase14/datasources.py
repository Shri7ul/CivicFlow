"""Dhaka data-source registration with explicit access authorization.

Registration records provenance only. It does not contact, download or scrape
any source. Only a distinct administrator can authorize a source, and research
classifications can never be promoted to operational authorization here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.geo.contexts import require_context
from app.governance.errors import GovernanceError
from app.models.enums import (
    DataSourceAuthorization,
    ProvenanceKind,
    Role,
)
from app.models.phase14 import PilotDataSource


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail(message: str, *, code: str, status_code: int = 400) -> None:
    raise GovernanceError(message, code=code, status_code=status_code)


def register_source(session: Session, payload: Any, actor: AuthenticatedUser) -> PilotDataSource:
    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can register a data source", code="source_forbidden", status_code=403)
    context_key = require_context(payload.geographic_context_key).key
    existing = session.scalar(
        select(PilotDataSource.id).where(PilotDataSource.source_key == payload.source_key)
    )
    if existing is not None:
        _fail("A data source with this key already exists", code="source_key_conflict", status_code=409)

    classification = payload.classification
    initial = (
        DataSourceAuthorization.RESEARCH_ONLY
        if classification == "RESEARCH_ONLY"
        else DataSourceAuthorization.UNAUTHORIZED
    )
    if payload.provenance_kind == ProvenanceKind.SYNTHETIC and initial != DataSourceAuthorization.RESEARCH_ONLY:
        _fail(
            "Synthetic sources must be registered as RESEARCH_ONLY",
            code="synthetic_source_classification",
            status_code=422,
        )
    source = PilotDataSource(
        source_key=payload.source_key,
        geographic_context_key=context_key,
        pilot_id=payload.pilot_id,
        source_identity=payload.source_identity,
        source_owner=payload.source_owner,
        dataset_name=payload.dataset_name,
        dataset_description=payload.dataset_description,
        geographic_scope=payload.geographic_scope,
        acquisition_method=payload.acquisition_method,
        endpoint=payload.endpoint,
        access_authorization=initial,
        license_note=payload.license_note,
        license_ref=payload.license_ref,
        timestamp_note=payload.timestamp_note,
        update_frequency=payload.update_frequency,
        data_quality_note=payload.data_quality_note,
        schema_version=payload.schema_version,
        provenance_note=payload.provenance_note,
        raw_sha256=payload.raw_sha256,
        normalized_sha256=payload.normalized_sha256,
        coverage_note=payload.coverage_note,
        missing_data_note=payload.missing_data_note,
        confidence_note=payload.confidence_note,
        limitations=payload.limitations,
        created_by=actor.profile.id,
    )
    session.add(source)
    session.commit()
    return source


def authorize_source(
    session: Session, source: PilotDataSource, payload: Any, actor: AuthenticatedUser
) -> PilotDataSource:
    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can authorize a source", code="authorization_forbidden", status_code=403)
    session.refresh(source, with_for_update=True)
    if source.access_authorization == DataSourceAuthorization.RESEARCH_ONLY:
        _fail(
            "A research-only source cannot be promoted to operational authorization here",
            code="research_only_source",
            status_code=422,
        )
    if source.access_authorization not in {
        DataSourceAuthorization.UNAUTHORIZED,
        DataSourceAuthorization.PENDING_REVIEW,
        DataSourceAuthorization.REVOKED,
    }:
        _fail("Source is not in an authorizable state", code="invalid_source_state", status_code=409)
    if source.created_by is not None and actor.profile.id == source.created_by:
        _fail("The registering administrator cannot authorize their own source", code="separation_of_duties", status_code=403)
    required = (
        source.license_note,
        payload.license_ref,
        source.raw_sha256,
        source.normalized_sha256,
        source.data_quality_note,
        source.limitations,
        (payload.authorization_reference or "").strip(),
    )
    if not all(required):
        _fail(
            "Authorization requires license reference, both hashes, quality note, "
            "limitations and an authorization reference",
            code="authorization_evidence_incomplete",
            status_code=422,
        )
    source.license_ref = payload.license_ref.strip()
    source.access_authorization = DataSourceAuthorization.AUTHORIZED
    source.authorized_by = actor.profile.id
    source.authorized_at = _now()
    source.provenance_note = (
        f"{source.provenance_note or ''} | authorization_reference="
        f"{(payload.authorization_reference or '').strip()}"
    )
    session.commit()
    return source


def revoke_source(
    session: Session, source: PilotDataSource, reason: str, actor: AuthenticatedUser
) -> PilotDataSource:
    if actor.profile.role != Role.ADMIN:
        _fail("Only an administrator can revoke a source", code="revocation_forbidden", status_code=403)
    session.refresh(source, with_for_update=True)
    if source.access_authorization != DataSourceAuthorization.AUTHORIZED:
        _fail("Only an AUTHORIZED source can be revoked", code="invalid_source_state", status_code=409)
    if len((reason or "").strip()) < 10:
        _fail("A revocation reason of at least 10 characters is required", code="reason_required", status_code=422)
    source.access_authorization = DataSourceAuthorization.REVOKED
    source.provenance_note = f"{source.provenance_note or ''} | revocation_reason={reason.strip()}"
    session.commit()
    return source


def authorized_sources(session: Session, context_key: str) -> list[PilotDataSource]:
    return list(
        session.scalars(
            select(PilotDataSource).where(
                PilotDataSource.geographic_context_key == context_key,
                PilotDataSource.access_authorization == DataSourceAuthorization.AUTHORIZED,
            )
        ).all()
    )


def count(session: Session, *, context_key: str | None = None) -> int:
    statement = select(func.count()).select_from(PilotDataSource)
    if context_key:
        statement = statement.where(PilotDataSource.geographic_context_key == context_key)
    return int(session.scalar(statement) or 0)
