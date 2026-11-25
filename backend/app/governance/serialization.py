"""Response serializers shared by Phase 10 endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.models.pilot import (
    CorrelationCandidate,
    CorrelationReview,
    InfrastructureSource,
    InfrastructureSourceEvent,
    Pilot,
    PilotTransition,
    ReadinessEvidence,
    ReadinessEvidenceEvent,
    RiskReviewCase,
    RiskReviewEvent,
)
from app.models.risk import RiskCellSnapshot, RiskModelRun


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def number(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def serialize_transition(event: PilotTransition) -> dict:
    return {
        "id": str(event.id),
        "action": event.action.value,
        "from_status": event.from_status.value if event.from_status else None,
        "to_status": event.to_status.value,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "actor_email": event.actor_email,
        "note": event.note,
        "created_at": iso(event.created_at),
    }


def serialize_pilot(pilot: Pilot, reviewers: list[dict] | None = None) -> dict:
    return {
        "id": str(pilot.id),
        "pilot_key": pilot.pilot_key,
        "name": pilot.name,
        "description": pilot.description,
        "status": pilot.status.value,
        "mode": pilot.mode.value,
        "region": pilot.region,
        "bbox": pilot.bbox or [],
        "start_date": iso(pilot.start_date),
        "end_date": iso(pilot.end_date),
        "eligible_categories": pilot.eligible_categories or [],
        "evaluation_protocol": pilot.evaluation_protocol,
        "operational_restrictions": pilot.operational_restrictions or [],
        "data_sources": pilot.data_sources or [],
        "evaluation_criteria": pilot.evaluation_criteria or [],
        "owner_id": str(pilot.owner_id) if pilot.owner_id else None,
        "created_by": str(pilot.created_by) if pilot.created_by else None,
        "approved_by": str(pilot.approved_by) if pilot.approved_by else None,
        "approved_at": iso(pilot.approved_at),
        "activated_by": str(pilot.activated_by) if pilot.activated_by else None,
        "activated_at": iso(pilot.activated_at),
        "paused_at": iso(pilot.paused_at),
        "paused_by": str(pilot.paused_by) if pilot.paused_by else None,
        "pause_reason": pilot.pause_reason,
        "completed_at": iso(pilot.completed_at),
        "terminated_at": iso(pilot.terminated_at),
        "terminated_by": str(pilot.terminated_by) if pilot.terminated_by else None,
        "termination_reason": pilot.termination_reason,
        "archived_at": iso(pilot.archived_at),
        "rejection_reason": pilot.rejection_reason,
        "activation_readiness": pilot.activation_readiness or {},
        "reviewers": reviewers or [],
        "created_at": iso(pilot.created_at),
        "updated_at": iso(pilot.updated_at),
        "disclaimer": (
            "A pilot is an evaluation plan. It does not authorize dispatch, "
            "public alerts, or an authoritative hazard declaration."
        ),
    }


def serialize_review_case(
    case: RiskReviewCase,
    *,
    run: RiskModelRun | None = None,
    cell: RiskCellSnapshot | None = None,
    pilot: Pilot | None = None,
    events: list[RiskReviewEvent] | None = None,
) -> dict:
    cell_payload = None
    if cell is not None:
        cell_payload = {
            "id": str(cell.id),
            "h3_cell_id": cell.h3_cell_id,
            "risk_score": number(cell.risk_score),
            "risk_category": cell.risk_category,
            "confidence": number(cell.confidence),
            "factor_contributions": cell.factor_contributions or [],
            "available_factors": cell.available_factors or [],
            "infrastructure_exposure": cell.infrastructure_exposure or {},
            "trend": cell.trend,
            "calculated_at": iso(cell.calculated_at),
            "model_version": cell.model_version,
            "config_hash": cell.config_hash,
        }
    run_payload = None
    if run is not None:
        run_payload = {
            "id": str(run.id),
            "model_version": run.model_version,
            "config_hash": run.config_hash,
            "resolution": run.resolution,
            "window_hours": run.window_hours,
            "window_start": iso(run.window_start),
            "window_end": iso(run.window_end),
            "calculated_at": iso(run.calculated_at),
            "incident_count": run.incident_count,
            "cell_count": run.cell_count,
        }
    return {
        "id": str(case.id),
        "run_id": str(case.run_id),
        "cell_id": str(case.cell_id),
        "pilot_id": str(case.pilot_id) if case.pilot_id else None,
        "pilot": (
            {
                "id": str(pilot.id),
                "pilot_key": pilot.pilot_key,
                "name": pilot.name,
                "status": pilot.status.value,
                "mode": pilot.mode.value,
            }
            if pilot is not None
            else None
        ),
        "status": case.status.value,
        "assigned_reviewer_id": (
            str(case.assigned_reviewer_id) if case.assigned_reviewer_id else None
        ),
        "created_by": str(case.created_by) if case.created_by else None,
        "created_at": iso(case.created_at),
        "updated_at": iso(case.updated_at),
        "last_decision_at": iso(case.last_decision_at),
        "run": run_payload,
        "risk": cell_payload,
        "events": [serialize_review_event(event) for event in events or []],
        "review_disclaimer": (
            "A review is a human judgment about a model output, not a verified "
            "hazard. It never changes the risk score."
        ),
        "prediction_vs_review": (
            "The risk score above is a model prediction. The review status is a "
            "separate human judgment and never changes the score."
        ),
    }


def serialize_review_event(event: RiskReviewEvent) -> dict:
    return {
        "id": str(event.id),
        "from_status": event.from_status.value if event.from_status else None,
        "to_status": event.to_status.value,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "actor_email": event.actor_email,
        "note": event.note,
        "requested_evidence": event.requested_evidence,
        "created_at": iso(event.created_at),
    }


def _incident_brief(incident: Any) -> dict | None:
    if incident is None:
        return None
    return {
        "id": str(incident.id),
        "title": getattr(incident, "title", None) or getattr(incident, "description", None),
        "category": (
            incident.category.value
            if hasattr(incident.category, "value")
            else incident.category
        ),
        "status": (
            incident.status.value
            if hasattr(incident.status, "value")
            else incident.status
        ),
        "created_at": iso(incident.created_at),
    }


def serialize_correlation_candidate(
    candidate: CorrelationCandidate,
    *,
    source: Any = None,
    target: Any = None,
    reviews: list[CorrelationReview] | None = None,
) -> dict:
    review_rows = reviews or []
    return {
        "id": str(candidate.id),
        "candidate_key": candidate.candidate_key,
        "source_incident": _incident_brief(source),
        "target_incident": _incident_brief(target),
        "similarity_score": number(candidate.similarity_score),
        "method": candidate.method,
        "method_version": candidate.method_version,
        "universe_key": candidate.universe_key,
        "universe_reference_complete": candidate.universe_reference_complete,
        "reference_universe_size": candidate.reference_universe_size,
        "reference_note": candidate.reference_note,
        "synthetic_fixture": candidate.synthetic_fixture,
        "generated_at": iso(candidate.generated_at),
        "created_by": str(candidate.created_by) if candidate.created_by else None,
        "review_state": "REVIEWED" if review_rows else "UNREVIEWED",
        "reviews": [
            {
                "id": str(review.id),
                "decision": review.decision.value,
                "reviewer_id": str(review.reviewer_id) if review.reviewer_id else None,
                "reviewer_email": review.reviewer_email,
                "note": review.note,
                "explanation": review.explanation,
                "created_at": iso(review.created_at),
            }
            for review in review_rows
        ],
        "disclaimer": (
            "Candidate pairs are generated suggestions; the review labels are "
            "human judgments and are not confirmed ground truth beyond this sample."
        ),
    }


def serialize_source(
    source: InfrastructureSource, events: list[InfrastructureSourceEvent] | None = None
) -> dict:
    return {
        "id": str(source.id),
        "source_key": source.source_key,
        "name": source.name,
        "category": source.category,
        "source_url": source.source_url,
        "provider": source.provider,
        "license_note": source.license_note,
        "retrieved_at": iso(source.retrieved_at),
        "dataset_version": source.dataset_version,
        "geographic_coverage": source.geographic_coverage,
        "crs": source.crs,
        "schema_version": source.schema_version,
        "validation_status": source.validation_status.value,
        "snapshot_sha256": source.snapshot_sha256,
        "update_frequency": source.update_frequency,
        "known_limitations": source.known_limitations,
        "metadata": source.details or {},
        "created_by": str(source.created_by) if source.created_by else None,
        "created_at": iso(source.created_at),
        "updated_at": iso(source.updated_at),
        "events": [
            {
                "id": str(event.id),
                "action": event.action,
                "from_status": (
                    event.from_status.value if event.from_status else None
                ),
                "to_status": event.to_status.value,
                "actor_email": event.actor_email,
                "note": event.note,
                "created_at": iso(event.created_at),
            }
            for event in events or []
        ],
        "asset_data": None,
        "asset_disclaimer": (
            "This registry row describes a source only. No roads, bridges, "
            "facilities, or network assets were ingested or validated here."
        ),
    }


def serialize_evidence(evidence: ReadinessEvidence) -> dict:
    return {
        "id": str(evidence.id),
        "category": evidence.category,
        "criterion_key": evidence.criterion_key,
        "status": evidence.status.value,
        "evidence": evidence.evidence,
        "evidence_refs": evidence.evidence_refs or [],
        "blocking": evidence.blocking,
        "owner_id": str(evidence.owner_id) if evidence.owner_id else None,
        "assessed_by": str(evidence.assessed_by) if evidence.assessed_by else None,
        "assessed_at": iso(evidence.assessed_at),
        "created_at": iso(evidence.created_at),
        "updated_at": iso(evidence.updated_at),
    }
