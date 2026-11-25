"""Response serializers for Phase 14 control records."""

from __future__ import annotations

from datetime import datetime

from app.models.phase14 import (
    BaselineComparison,
    FieldObservation,
    FieldObservationEvent,
    Phase14Attestation,
    PilotBoundary,
    PilotBoundaryEvent,
    PilotDataSource,
    PilotIncident,
    PilotIncidentEvent,
    PilotShutdown,
)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _uid(value: object) -> str | None:
    return str(value) if value is not None else None


def serialize_boundary(boundary: PilotBoundary, *, events: list | None = None) -> dict:
    return {
        "id": str(boundary.id),
        "boundary_key": boundary.boundary_key,
        "name": boundary.name,
        "description": boundary.description,
        "pilot_id": _uid(boundary.pilot_id),
        "geographic_context_key": boundary.geographic_context_key,
        "source_type": boundary.source_type.value,
        "source_owner": boundary.source_owner,
        "source_name": boundary.source_name,
        "source_url": boundary.source_url,
        "source_date": iso(boundary.source_date),
        "boundary_version": boundary.boundary_version,
        "crs": boundary.crs,
        "geometry_geojson": boundary.geometry_geojson or {},
        "bbox_geojson": boundary.bbox_geojson or [],
        "coordinate_validation": boundary.coordinate_validation or {},
        "geometry_validation": boundary.geometry_validation or {},
        "provenance_note": boundary.provenance_note,
        "license_note": boundary.license_note,
        "integrity_sha256": boundary.integrity_sha256,
        "status": boundary.status.value,
        "submitted_by": _uid(boundary.submitted_by),
        "reviewed_by": _uid(boundary.reviewed_by),
        "reviewed_at": iso(boundary.reviewed_at),
        "decision_note": boundary.decision_note,
        "rejection_reason": boundary.rejection_reason,
        "created_by": _uid(boundary.created_by),
        "created_at": iso(boundary.created_at),
        "updated_at": iso(boundary.updated_at),
        "events": [serialize_boundary_event(event) for event in events or []],
        "activation_note": (
            "An APPROVED boundary is a geographic prerequisite only. It does "
            "not approve, activate or authorize a pilot."
        ),
    }


def serialize_boundary_event(event: PilotBoundaryEvent) -> dict:
    return {
        "id": str(event.id),
        "action": event.action,
        "from_status": event.from_status.value if event.from_status else None,
        "to_status": event.to_status.value,
        "actor_id": _uid(event.actor_id),
        "actor_email": event.actor_email,
        "note": event.note,
        "created_at": iso(event.created_at),
    }


def serialize_observation(
    observation: FieldObservation, *, events: list[FieldObservationEvent] | None = None
) -> dict:
    return {
        "id": str(observation.id),
        "observation_key": observation.observation_key,
        "pilot_id": _uid(observation.pilot_id),
        "geographic_context_key": observation.geographic_context_key,
        "observer_id": str(observation.observer_id),
        "observer_role_snapshot": observation.observer_role_snapshot,
        "source_reference": observation.source_reference,
        "observed_at": iso(observation.observed_at),
        "latitude": observation.latitude,
        "longitude": observation.longitude,
        "location": observation.location,
        "category": observation.category.value,
        "description": observation.description,
        "evidence_refs": observation.evidence_refs or [],
        "evidence_sha256": observation.evidence_sha256,
        "provenance_kind": observation.provenance_kind.value,
        "confidence": observation.confidence,
        "status": observation.status.value,
        "revision": observation.revision,
        "submitted_at": iso(observation.submitted_at),
        "reviewer_id": _uid(observation.reviewer_id),
        "reviewed_at": iso(observation.reviewed_at),
        "decision": observation.decision,
        "rejection_reason": observation.rejection_reason,
        "revision_notes": observation.revision_notes,
        "duplicate_of_id": _uid(observation.duplicate_of_id),
        "ground_truth_record_id": _uid(observation.ground_truth_record_id),
        "created_by": _uid(observation.created_by),
        "created_at": iso(observation.created_at),
        "updated_at": iso(observation.updated_at),
        "events": [serialize_observation_event(event) for event in events or []],
        "ground_truth_note": (
            "A VERIFIED observation is a reviewed assertion. Ground truth is "
            "created only by a separate, explicit human promotion decision."
        ),
    }


def serialize_observation_event(event: FieldObservationEvent) -> dict:
    return {
        "id": str(event.id),
        "action": event.action,
        "from_status": event.from_status.value if event.from_status else None,
        "to_status": event.to_status.value,
        "actor_id": _uid(event.actor_id),
        "actor_email": event.actor_email,
        "note": event.note,
        "rationale": event.rationale,
        "evidence_sha256": event.evidence_sha256,
        "created_at": iso(event.created_at),
    }


def serialize_data_source(source: PilotDataSource) -> dict:
    return {
        "id": str(source.id),
        "source_key": source.source_key,
        "geographic_context_key": source.geographic_context_key,
        "pilot_id": _uid(source.pilot_id),
        "source_identity": source.source_identity,
        "source_owner": source.source_owner,
        "dataset_name": source.dataset_name,
        "dataset_description": source.dataset_description,
        "geographic_scope": source.geographic_scope,
        "acquisition_method": source.acquisition_method,
        "endpoint": source.endpoint,
        "access_authorization": source.access_authorization.value,
        "license_note": source.license_note,
        "license_ref": source.license_ref,
        "timestamp_note": source.timestamp_note,
        "update_frequency": source.update_frequency,
        "data_quality_note": source.data_quality_note,
        "schema_version": source.schema_version,
        "provenance_note": source.provenance_note,
        "raw_sha256": source.raw_sha256,
        "normalized_sha256": source.normalized_sha256,
        "coverage_note": source.coverage_note,
        "missing_data_note": source.missing_data_note,
        "confidence_note": source.confidence_note,
        "limitations": source.limitations,
        "authorized_by": _uid(source.authorized_by),
        "authorized_at": iso(source.authorized_at),
        "created_by": _uid(source.created_by),
        "created_at": iso(source.created_at),
        "updated_at": iso(source.updated_at),
        "acquisition_note": (
            "Registration does not acquire data and does not grant access. "
            "No source is downloaded by this endpoint."
        ),
    }


def serialize_incident(
    incident: PilotIncident, *, events: list[PilotIncidentEvent] | None = None
) -> dict:
    return {
        "id": str(incident.id),
        "incident_key": incident.incident_key,
        "pilot_id": str(incident.pilot_id),
        "geographic_context_key": incident.geographic_context_key,
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity.value,
        "status": incident.status.value,
        "source": incident.source,
        "related_observation_id": _uid(incident.related_observation_id),
        "processing_stopped": incident.processing_stopped,
        "impact_summary": incident.impact_summary,
        "resolution_note": incident.resolution_note,
        "opened_at": iso(incident.opened_at),
        "investigating_at": iso(incident.investigating_at),
        "mitigated_at": iso(incident.mitigated_at),
        "resolved_at": iso(incident.resolved_at),
        "closed_at": iso(incident.closed_at),
        "created_by": _uid(incident.created_by),
        "created_at": iso(incident.created_at),
        "updated_at": iso(incident.updated_at),
        "events": [
            {
                "id": str(event.id),
                "action": event.action,
                "from_status": event.from_status.value if event.from_status else None,
                "to_status": event.to_status.value,
                "actor_id": _uid(event.actor_id),
                "actor_email": event.actor_email,
                "note": event.note,
                "created_at": iso(event.created_at),
            }
            for event in events or []
        ],
        "response_note": (
            "This record tracks pilot processing only. It never dispatches a "
            "crew, issues an alert, or makes a government decision."
        ),
    }


def serialize_baseline(comparison: BaselineComparison) -> dict:
    return {
        "id": str(comparison.id),
        "comparison_key": comparison.comparison_key,
        "pilot_id": _uid(comparison.pilot_id),
        "geographic_context_key": comparison.geographic_context_key,
        "comparison_type": comparison.comparison_type,
        "method": comparison.method,
        "baseline_name": comparison.baseline_name,
        "candidate_name": comparison.candidate_name,
        "label_source": comparison.label_source,
        "label_count": comparison.label_count,
        "sample_count": comparison.sample_count,
        "baseline_metrics": comparison.baseline_metrics or {},
        "candidate_metrics": comparison.candidate_metrics or {},
        "notes": comparison.notes,
        "limitations": comparison.limitations,
        "created_by": _uid(comparison.created_by),
        "created_at": iso(comparison.created_at),
        "updated_at": iso(comparison.updated_at),
        "null_note": "Metrics are null when the label set is invalid or unavailable.",
    }


def serialize_shutdown(shutdown: PilotShutdown) -> dict:
    return {
        "id": str(shutdown.id),
        "shutdown_key": shutdown.shutdown_key,
        "pilot_id": str(shutdown.pilot_id),
        "reason": shutdown.reason,
        "action": shutdown.action,
        "preserved_counts": shutdown.preserved_counts or {},
        "evidence_preserved": shutdown.evidence_preserved,
        "audit_preserved": shutdown.audit_preserved,
        "provenance_preserved": shutdown.provenance_preserved,
        "decisions_preserved": shutdown.decisions_preserved,
        "incidents_preserved": shutdown.incidents_preserved,
        "model_activation_disabled": shutdown.model_activation_disabled,
        "reauthorization_required": shutdown.reauthorization_required,
        "performed_by": _uid(shutdown.performed_by),
        "created_at": iso(shutdown.created_at),
        "preservation_note": "Shutdown never deletes evidence, audit or decision rows.",
    }


def serialize_attestation(attestation: Phase14Attestation) -> dict:
    return {
        "id": str(attestation.id),
        "category": attestation.category,
        "criterion_key": attestation.criterion_key,
        "status": attestation.status.value,
        "evidence": attestation.evidence,
        "evidence_refs": attestation.evidence_refs or [],
        "blocking": attestation.blocking,
        "assessed_by": _uid(attestation.assessed_by),
        "assessed_at": iso(attestation.assessed_at),
        "created_at": iso(attestation.created_at),
        "updated_at": iso(attestation.updated_at),
    }
