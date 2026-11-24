"""Immutable correlation reference-universe attestations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.geo.contexts import UNKNOWN_CONTEXT_KEY
from app.governance.errors import GovernanceError
from app.models.enums import EvidenceSnapshotStatus, ProvenanceKind
from app.models.evidence import CorrelationUniverse, EvidenceSnapshot


def get_universe(session: Session, universe_id: uuid.UUID) -> CorrelationUniverse:
    universe = session.get(CorrelationUniverse, universe_id)
    if universe is None:
        raise GovernanceError(
            "Correlation universe not found",
            status_code=404,
            code="correlation_universe_not_found",
        )
    return universe


def get_by_key(session: Session, universe_key: str) -> CorrelationUniverse | None:
    return session.scalar(
        select(CorrelationUniverse).where(
            CorrelationUniverse.universe_key == universe_key
        )
    )


def create_universe(
    session: Session, payload: Any, actor: AuthenticatedUser
) -> CorrelationUniverse:
    if get_by_key(session, payload.universe_key) is not None:
        raise GovernanceError(
            "A correlation universe with this key already exists; universes are immutable",
            status_code=409,
            code="correlation_universe_exists",
        )
    if payload.provenance_kind == ProvenanceKind.MIXED:
        raise GovernanceError(
            "A single candidate universe cannot be labelled MIXED without a "
            "per-candidate provenance ledger",
            status_code=422,
            code="mixed_provenance_unsupported",
        )
    snapshot = None
    if payload.reference_dataset_snapshot_id is not None:
        snapshot = session.get(EvidenceSnapshot, payload.reference_dataset_snapshot_id)
        if snapshot is None:
            raise GovernanceError(
                "Reference dataset snapshot not found",
                status_code=404,
                code="evidence_snapshot_not_found",
            )
        if snapshot.status != EvidenceSnapshotStatus.VALIDATED:
            raise GovernanceError(
                "The reference snapshot is not validated",
                status_code=409,
                code="reference_snapshot_not_validated",
            )
    universe = CorrelationUniverse(
        universe_key=payload.universe_key,
        name=payload.name,
        description=payload.description,
        version=payload.version,
        provenance_kind=payload.provenance_kind,
        geographic_context_key=(
            snapshot.geographic_context_key if snapshot is not None else UNKNOWN_CONTEXT_KEY
        ),
        reference_complete=payload.reference_complete,
        reference_size=payload.reference_size,
        reference_note=payload.reference_note,
        candidate_method=payload.candidate_method,
        candidate_method_version=payload.candidate_method_version,
        reference_dataset_snapshot_id=payload.reference_dataset_snapshot_id,
        created_by=actor.profile.id,
    )
    session.add(universe)
    session.commit()
    return universe


def serialize_universe(universe: CorrelationUniverse) -> dict:
    return {
        "id": str(universe.id),
        "universe_key": universe.universe_key,
        "name": universe.name,
        "description": universe.description,
        "version": universe.version,
        "provenance_kind": universe.provenance_kind.value,
        "reference_complete": universe.reference_complete,
        "reference_size": universe.reference_size,
        "reference_note": universe.reference_note,
        "candidate_method": universe.candidate_method,
        "candidate_method_version": universe.candidate_method_version,
        "reference_dataset_snapshot_id": (
            str(universe.reference_dataset_snapshot_id)
            if universe.reference_dataset_snapshot_id
            else None
        ),
        "attested_by": str(universe.created_by) if universe.created_by else None,
        "attested_at": universe.created_at.isoformat(),
        "immutable": True,
        "disclaimer": (
            "A complete universe attests that all reference duplicate pairs were "
            "enumerated. It does not make reviewer labels physical ground truth, "
            "and it does not establish true-negative counts."
        ),
    }
