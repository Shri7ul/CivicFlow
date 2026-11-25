"""Phase 14 final readiness gate.

This is the server-enforced gate invoked by pilot ACTIVATE/RESUME. Every
category is derived from persisted rows or a recorded human attestation. There
is no hardcoded PASS, no client-submitted status and no activation authority:
even a fully satisfied gate only permits a separate explicit admin action.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo.contexts import BD_DHAKA, BoundingBox
from app.governance.readiness import FRESHNESS_DAYS, _category, _criterion
from app.models.enums import (
    AttestationStatus,
    BoundarySourceType,
    EvidenceSnapshotStatus,
    FieldObservationStatus,
    GroundTruthStatus,
    PilotMode,
    PilotStatus,
    ProvenanceKind,
    ReadinessOverall,
    ReadinessStatus,
    ValidationExperimentType,
)
from app.models.evidence import EvidenceSnapshot, GroundTruthRecord
from app.models.phase14 import (
    BaselineComparison,
    FieldObservation,
    Phase14Attestation,
    PilotBoundary,
    PilotDataSource,
    PilotIncident,
)
from app.models.pilot import Pilot, PilotReviewer, RiskReviewCase
from app.models.validation import ValidationExperiment
from app.phase14 import attestations, baselines, boundaries, datasources, incidents, observations

PROTOCOL = "phase14-final-gate-v1"
CONTEXT_KEY = BD_DHAKA.key
MANUAL_CATEGORIES = (
    "production_infrastructure",
    "migration",
    "backup_restore",
    "security_review",
    "legal_review",
    "stakeholder_approval",
    "reviewer_training",
    "monitoring",
    "rollback_drill",
)
ADVISORY_CATEGORIES = {"isolation"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _count(session: Session, statement: Any) -> int:
    return int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)


def _status_from_attestation(status: AttestationStatus) -> ReadinessStatus:
    return {
        AttestationStatus.PASS: ReadinessStatus.PASS,
        AttestationStatus.FAIL: ReadinessStatus.FAIL,
        AttestationStatus.BLOCKED: ReadinessStatus.BLOCKED,
        AttestationStatus.IN_PROGRESS: ReadinessStatus.IN_PROGRESS,
        AttestationStatus.NOT_ASSESSED: ReadinessStatus.NOT_ASSESSED,
    }[status]


def _attestation_category(
    session: Session,
    key: str,
    label: str,
    category: str,
    owner: str,
    *,
    mandatory: bool = True,
) -> dict:
    rows = attestations.find(session, category)
    status = _status_from_attestation(attestations.best_status(session, category))
    evidence = (
        "; ".join(f"{row.criterion_key}: {row.evidence}" for row in rows[:3])
        if rows
        else f"No recorded attestation for {category}. Missing evidence never passes."
    )
    refs = sorted({ref for row in rows for ref in (row.evidence_refs or [])})
    return _category(
        key,
        label,
        status,
        f"{sum(1 for row in rows if row.status == AttestationStatus.PASS)} of {len(rows)} attestation(s) at PASS.",
        [
            _criterion(
                f"{key}.attested",
                f"Recorded {label.lower()} attestation",
                status,
                evidence,
                refs=refs[:10],
            )
        ],
        owner=owner,
        mandatory=mandatory,
    )


def _boundary_category(session: Session, context_key: str, pilot_id: Any) -> dict:
    approved = boundaries.approved_for(session, context_key, pilot_id)
    eligible = [
        row
        for row in approved
        if row.source_type in boundaries.AUTHORITATIVE_SOURCES
        and len(row.integrity_sha256) == 64
        and row.geometry_validation.get("valid")
        and row.coordinate_validation.get("valid")
        and bool(row.license_note)
    ]
    return _category(
        "phase14_pilot_boundary",
        "Approved authoritative pilot boundary",
        ReadinessStatus.PASS if eligible else ReadinessStatus.BLOCKED,
        f"{len(eligible)} approved authoritative boundary/boundaries for the pilot context.",
        [
            _criterion(
                "phase14.boundary.approved",
                "Human-approved authoritative boundary with integrity hash",
                ReadinessStatus.PASS if eligible else ReadinessStatus.BLOCKED,
                (
                    f"{len(approved)} APPROVED boundary row(s), {len(eligible)} eligible. "
                    "The screening bbox alone is never a pilot boundary."
                ),
                refs=[f"pilot_boundaries:{context_key}"],
            )
        ],
        owner="Geographic review lead",
    )


def _source_category(session: Session, context_key: str) -> dict:
    authorized = datasources.authorized_sources(session, context_key)
    complete = [
        row
        for row in authorized
        if row.raw_sha256
        and row.normalized_sha256
        and row.license_ref
        and row.endpoint
        and row.limitations
        and row.data_quality_note
    ]
    return _category(
        "phase14_data_sources",
        "Authorized Dhaka data sources",
        ReadinessStatus.PASS if complete else ReadinessStatus.BLOCKED,
        f"{len(complete)} fully documented AUTHORIZED source(s) of {len(authorized)}.",
        [
            _criterion(
                "phase14.sources.authorized",
                "At least one authorized source with both hashes, license and access proof",
                ReadinessStatus.PASS if complete else ReadinessStatus.BLOCKED,
                "OSM research data remains RESEARCH_ONLY and is not authoritative incident evidence.",
                refs=[f"pilot_data_sources:{context_key}"],
            )
        ],
        owner="Data engineering lead",
    )


def _snapshots(session: Session, context_key: str) -> list[EvidenceSnapshot]:
    return list(
        session.scalars(
            select(EvidenceSnapshot).where(
                EvidenceSnapshot.geographic_context_key == context_key
            )
        ).all()
    )


def _data_category(session: Session, context_key: str) -> tuple[dict, dict, dict]:
    snapshots = _snapshots(session, context_key)
    validated = [
        row
        for row in snapshots
        if row.status == EvidenceSnapshotStatus.VALIDATED
        and row.provenance_kind != ProvenanceKind.SYNTHETIC
    ]
    data_quality = _category(
        "phase14_data_quality",
        "Dhaka data quality",
        ReadinessStatus.PASS if validated else ReadinessStatus.BLOCKED,
        f"{len(validated)} validated non-synthetic snapshot(s) of {len(snapshots)}.",
        [
            _criterion(
                "phase14.data.validated",
                "At least one validated non-synthetic snapshot",
                ReadinessStatus.PASS if validated else ReadinessStatus.BLOCKED,
                "Synthetic fixtures are never operational Dhaka evidence.",
                refs=[f"evidence_snapshots:{context_key}"],
            )
        ],
        owner="Data engineering lead",
    )

    newest = max((row.retrieved_at for row in snapshots if row.retrieved_at), default=None)
    if newest is None:
        freshness_status, freshness_evidence = ReadinessStatus.BLOCKED, "No retrieval timestamp recorded."
    else:
        age_days = (_now() - _aware(newest)).days
        freshness_status = (
            ReadinessStatus.PASS if age_days <= FRESHNESS_DAYS else ReadinessStatus.FAIL
        )
        freshness_evidence = f"Newest snapshot is {age_days} day(s) old."
    freshness = _category(
        "phase14_data_freshness",
        "Dhaka data freshness",
        freshness_status,
        freshness_evidence,
        [
            _criterion(
                "phase14.data.freshness",
                "Freshness within the configured window",
                freshness_status,
                freshness_evidence,
                refs=[f"evidence_snapshots:{context_key}"],
            )
        ],
        owner="Data engineering lead",
    )

    context = BD_DHAKA
    contained = [
        row
        for row in snapshots
        if row.bbox
        and len(row.bbox) == 4
        and context.bbox.contains_bbox(BoundingBox.from_geojson(row.bbox))
    ]
    complete_provenance = [
        row for row in snapshots if row.raw_sha256 and row.license_note and row.lineage
    ]
    verified_observations = list(
        session.scalars(
            select(FieldObservation).where(
                FieldObservation.geographic_context_key == context_key,
                FieldObservation.status == FieldObservationStatus.VERIFIED,
            )
        ).all()
    )
    observations_with_evidence = [
        row
        for row in verified_observations
        if row.evidence_sha256 or row.evidence_refs
    ]
    provenance_ok = (
        bool(snapshots)
        and len(complete_provenance) == len(snapshots)
        and bool(verified_observations)
        and len(observations_with_evidence) == len(verified_observations)
    )
    provenance = _category(
        "phase14_provenance",
        "Provenance completeness",
        ReadinessStatus.PASS if provenance_ok else ReadinessStatus.BLOCKED,
        (
            f"{len(complete_provenance)} of {len(snapshots)} snapshot(s) complete; "
            f"{len(observations_with_evidence)} of {len(verified_observations)} "
            "verified observations have evidence."
        ),
        [
            _criterion(
                "phase14.provenance.snapshots",
                "Hash, license and lineage on every context snapshot",
                ReadinessStatus.PASS
                if snapshots and len(complete_provenance) == len(snapshots)
                else ReadinessStatus.BLOCKED,
                f"{len(complete_provenance)} of {len(snapshots)} complete.",
                refs=[f"evidence_snapshots:{context_key}"],
            ),
            _criterion(
                "phase14.provenance.observations",
                "Evidence hash or reference on every verified field observation",
                ReadinessStatus.PASS
                if verified_observations
                and len(observations_with_evidence) == len(verified_observations)
                else ReadinessStatus.BLOCKED,
                f"{len(observations_with_evidence)} of {len(verified_observations)} complete.",
                refs=[f"field_observations:{context_key}"],
            ),
            _criterion(
                "phase14.coverage.snapshots",
                "Snapshots contained in the registered context envelope",
                ReadinessStatus.PASS if contained else ReadinessStatus.BLOCKED,
                f"{len(contained)} of {len(snapshots)} contained.",
                refs=[f"evidence_snapshots:{context_key}"],
            ),
        ],
        owner="Data engineering lead",
    )
    return data_quality, freshness, provenance


def _ground_truth_category(session: Session, context_key: str) -> dict:
    promoted = observations.verified_promoted_count(session, context_key=context_key)
    observers = observations.distinct_verified_observers(session, context_key=context_key)
    gt_rows = _count(
        session,
        select(GroundTruthRecord.id).where(
            GroundTruthRecord.geographic_context_key == context_key,
            GroundTruthRecord.status == GroundTruthStatus.VERIFIED,
        ),
    )
    passed = promoted >= 5 and observers >= 2 and gt_rows >= 5
    return _category(
        "phase14_ground_truth",
        "Human-verified field ground truth",
        ReadinessStatus.PASS if passed else ReadinessStatus.BLOCKED,
        f"{promoted} promoted observation(s), {observers} observer(s), {gt_rows} verified GT record(s).",
        [
            _criterion(
                "phase14.ground_truth.promoted",
                "At least five explicitly promoted, human-verified observations",
                ReadinessStatus.PASS if promoted >= 5 else ReadinessStatus.BLOCKED,
                f"{promoted} promoted observation(s).",
                refs=[f"field_observations:{context_key}"],
            ),
            _criterion(
                "phase14.ground_truth.independent",
                "At least two independent observers",
                ReadinessStatus.PASS if observers >= 2 else ReadinessStatus.BLOCKED,
                f"{observers} distinct verified observer(s).",
                refs=[f"field_observations:{context_key}"],
            ),
            _criterion(
                "phase14.ground_truth.not_ai",
                "Ground truth is not an AI prediction",
                ReadinessStatus.PASS
                if _count(
                    session,
                    select(GroundTruthRecord.id).where(
                        GroundTruthRecord.geographic_context_key == context_key,
                        GroundTruthRecord.status == GroundTruthStatus.VERIFIED,
                        GroundTruthRecord.source_type == "AI_PREDICTION",
                    ),
                )
                == 0
                else ReadinessStatus.FAIL,
                "AI predictions are excluded from ground truth.",
                refs=[f"ground_truth_records:{context_key}"],
            ),
        ],
        owner="Field operations lead",
    )


def _baseline_category(session: Session, context_key: str, pilot_id: Any) -> dict:
    comparisons = baselines.usable_comparisons(
        session, context_key=context_key, pilot_id=pilot_id
    )
    return _category(
        "phase14_baseline_comparison",
        "Baseline comparison",
        ReadinessStatus.PASS if comparisons else ReadinessStatus.BLOCKED,
        f"{len(comparisons)} comparison(s) with valid labels and non-null metrics.",
        [
            _criterion(
                "phase14.baseline.recorded",
                "Documented comparison with a valid label source",
                ReadinessStatus.PASS if comparisons else ReadinessStatus.BLOCKED,
                "Metrics remain null when labels are unavailable; NYC results are never Dhaka evidence.",
                refs=[f"baseline_comparisons:{context_key}"],
            )
        ],
        owner="ML validation lead",
    )


def _model_category(session: Session) -> dict:
    experiments = session.scalars(
        select(ValidationExperiment).where(
            ValidationExperiment.region.ilike("%dhaka%"),
            ValidationExperiment.experiment_type.in_(
                [
                    ValidationExperimentType.RISK_GEOGRAPHIC,
                    ValidationExperimentType.RISK_TEMPORAL,
                ]
            ),
        )
    ).all()
    with_metrics = [row for row in experiments if row.metrics and "pr_auc" in row.metrics]
    return _category(
        "phase14_model_validation",
        "Dhaka model validation",
        ReadinessStatus.PASS if with_metrics else ReadinessStatus.BLOCKED,
        f"{len(with_metrics)} persisted Dhaka experiment(s) with PR-AUC metrics.",
        [
            _criterion(
                "phase14.model.validated",
                "Validated Dhaka geographic/temporal experiment",
                ReadinessStatus.PASS if with_metrics else ReadinessStatus.BLOCKED,
                "No NYC metric is imported as Dhaka performance evidence. Model outputs remain RESEARCH_ONLY otherwise.",
                refs=["validation_experiments:BD-DHAKA"],
            )
        ],
        owner="ML validation lead",
    )


def _review_category(session: Session, pilot: Pilot | None) -> dict:
    if pilot is None:
        return _category(
            "phase14_human_review",
            "Human review coverage",
            ReadinessStatus.BLOCKED,
            "No pilot is associated with this assessment.",
            [
                _criterion(
                    "phase14.review.pilot",
                    "Review cases linked to a governed pilot",
                    ReadinessStatus.BLOCKED,
                    "Pilot is required.",
                )
            ],
            owner="Review lead",
        )
    cases = session.scalars(
        select(RiskReviewCase).where(RiskReviewCase.pilot_id == pilot.id)
    ).all()
    reviewers = session.scalars(
        select(PilotReviewer).where(PilotReviewer.pilot_id == pilot.id)
    ).all()
    final_statuses = {"ACCEPTED", "REJECTED", "NEEDS_INVESTIGATION", "NEEDS_MORE_DATA"}
    decided = [row for row in cases if row.status.value in final_statuses]
    distinct = {row.assigned_reviewer_id for row in cases if row.assigned_reviewer_id}
    passed = len(cases) >= 20 and len(decided) >= 10 and len(distinct) >= 2
    return _category(
        "phase14_human_review",
        "Human review coverage",
        ReadinessStatus.PASS if passed else ReadinessStatus.BLOCKED,
        f"{len(cases)} case(s), {len(decided)} decision(s), {len(distinct)} reviewer(s).",
        [
            _criterion(
                "phase14.review.coverage",
                "Twenty cases, ten decisions and two reviewers",
                ReadinessStatus.PASS if passed else ReadinessStatus.BLOCKED,
                "Human approval is explicit and auditable; model output is never human approval.",
                refs=[f"risk_review_cases:{pilot.pilot_key}"],
            )
        ],
        owner="Review lead",
    )


def _operations_category(session: Session, pilot: Pilot | None) -> tuple[dict, dict]:
    blocking_incident = 0
    if pilot is not None:
        blocking_incident = _count(
            session,
            select(PilotIncident.id).where(
                PilotIncident.pilot_id == pilot.id,
                PilotIncident.processing_stopped.is_(True),
            ),
        )
    monitoring_status = _status_from_attestation(attestations.best_status(session, "monitoring"))
    if blocking_incident:
        monitoring_status = ReadinessStatus.BLOCKED
    monitoring = _category(
        "phase14_monitoring",
        "Pilot monitoring and incident handling",
        monitoring_status,
        f"{blocking_incident} active processing stop(s).",
        [
            _criterion(
                "phase14.monitoring.ready",
                "Monitoring attestation and no active processing stop",
                monitoring_status,
                "Critical incidents stop platform processing only; no real-world response is automated.",
                refs=["pilot_incidents", "phase14_attestations:monitoring"],
            )
        ],
        owner="Operations lead",
    )

    if pilot is None:
        constraints = _category(
            "phase14_operational_constraints",
            "Operational constraints",
            ReadinessStatus.BLOCKED,
            "No pilot is associated with this assessment.",
            [
                _criterion(
                    "phase14.operations.pilot",
                    "Governed pilot exists",
                    ReadinessStatus.BLOCKED,
                    "Pilot is required.",
                )
            ],
            owner="Operations lead",
        )
        return monitoring, constraints

    forbidden = {
        "AUTO_DISPATCH",
        "AUTO_ALERT",
        "AUTO_ENFORCEMENT",
        "AUTO_BUDGET",
        "AUTO_ELIGIBILITY",
    }
    restrictions = set(pilot.operational_restrictions or [])
    constraints_ok = (
        pilot.mode in {PilotMode.SIMULATION, PilotMode.STAGING}
        and bool(pilot.operational_restrictions)
        and not (restrictions & forbidden)
    )
    constraints = _category(
        "phase14_operational_constraints",
        "Operational constraints",
        ReadinessStatus.PASS if constraints_ok else ReadinessStatus.BLOCKED,
        f"mode={pilot.mode.value}; {len(restrictions)} restriction(s) recorded.",
        [
            _criterion(
                "phase14.operations.non_autonomous",
                "Supervised, non-autonomous pilot constraints",
                ReadinessStatus.PASS if constraints_ok else ReadinessStatus.BLOCKED,
                "No dispatch, alerting, enforcement, budget or eligibility action is automated.",
                refs=[f"pilots:{pilot.pilot_key}"],
            )
        ],
        owner="Operations lead",
    )
    return monitoring, constraints


def _authorization_category(session: Session, pilot: Pilot | None) -> dict:
    status = _status_from_attestation(attestations.best_status(session, "explicit_authorization"))
    separation = False
    if pilot is not None and pilot.status in {PilotStatus.APPROVED, PilotStatus.ACTIVE}:
        separation = pilot.approved_by is not None and pilot.approved_by not in {
            pilot.created_by,
            pilot.owner_id,
        }
    passed = status == ReadinessStatus.PASS and separation
    return _category(
        "phase14_explicit_authorization",
        "Explicit pilot authorization",
        ReadinessStatus.PASS if passed else ReadinessStatus.BLOCKED,
        "Attestation present: "
        + str(status.value)
        + "; independent approval: "
        + str(separation)
        + ".",
        [
            _criterion(
                "phase14.authorization.explicit",
                "Recorded human authorization with separation of duties",
                ReadinessStatus.PASS if passed else ReadinessStatus.BLOCKED,
                "Activation itself remains a separate admin action recorded in pilot transitions.",
                refs=["phase14_attestations:explicit_authorization", "pilot_transitions"],
            )
        ],
        owner="Governance lead",
    )


def _isolation_category(session: Session, context_key: str) -> dict:
    snapshots = _snapshots(session, context_key)
    nyc_keys = [
        row for row in snapshots if row.source_key.lower().startswith(("nyc", "nyc311"))
    ]
    synthetic = [row for row in snapshots if row.provenance_kind == ProvenanceKind.SYNTHETIC]
    status = (
        ReadinessStatus.BLOCKED
        if not snapshots
        else ReadinessStatus.FAIL
        if nyc_keys or synthetic
        else ReadinessStatus.PASS
    )
    return _category(
        "phase14_isolation",
        "Geographic isolation (advisory)",
        status,
        f"{len(snapshots)} snapshot(s) inspected; {len(nyc_keys)} NYC-keyed, {len(synthetic)} synthetic.",
        [
            _criterion(
                "phase14.isolation.no_cross_geography",
                "No NYC research data labelled as Dhaka evidence",
                status,
                "NYC research evidence remains tagged US-NYC.",
                refs=[f"evidence_snapshots:{context_key}"],
                blocking=False,
            )
        ],
        owner="Security lead",
        mandatory=False,
    )


def assess_phase14_readiness(session: Session, pilot: Pilot | None = None) -> dict:
    """Compute the final gate from persisted Phase 14 evidence."""

    context_key = pilot.geographic_context_key if pilot is not None else CONTEXT_KEY
    pilot_id = pilot.id if pilot is not None else None
    categories = [
        _attestation_category(session, "phase14_production_infrastructure", "Production infrastructure", "production_infrastructure", "Platform lead"),
        _attestation_category(session, "phase14_migration", "Migration status", "migration", "Platform lead"),
        _attestation_category(session, "phase14_backup_restore", "Backup and restore verification", "backup_restore", "Platform lead"),
        _boundary_category(session, context_key, pilot_id),
        _source_category(session, context_key),
        *_data_category(session, context_key),
        _ground_truth_category(session, context_key),
        _baseline_category(session, context_key, pilot_id),
        _model_category(session),
        _review_category(session, pilot),
        _attestation_category(session, "phase14_security", "Security review", "security_review", "Security lead"),
        _attestation_category(session, "phase14_legal", "Legal review", "legal_review", "Legal lead"),
        _attestation_category(session, "phase14_stakeholder", "Stakeholder approval", "stakeholder_approval", "Governance lead"),
        _attestation_category(session, "phase14_reviewer_training", "Reviewer training", "reviewer_training", "Review lead"),
        _attestation_category(session, "phase14_rollback", "Rollback verification", "rollback_drill", "Platform lead"),
    ]
    monitoring, constraints = _operations_category(session, pilot)
    categories.extend([monitoring, constraints, _authorization_category(session, pilot)])
    categories.append(_isolation_category(session, context_key))

    passing = {ReadinessStatus.PASS.value, ReadinessStatus.NOT_APPLICABLE.value}
    mandatory_unmet = [
        item["key"] for item in categories if item["mandatory"] and item["status"] not in passing
    ]
    advisory_unmet = [
        item["key"] for item in categories if not item["mandatory"] and item["status"] not in passing
    ]
    overall = (
        ReadinessOverall.NOT_READY
        if mandatory_unmet
        else ReadinessOverall.CONDITIONALLY_READY
        if advisory_unmet
        else ReadinessOverall.READY_FOR_CONTROLLED_PILOT
    )

    window_valid = True
    if pilot is not None:
        window_valid = _now() <= _aware(pilot.end_date) and pilot.status == PilotStatus.APPROVED
    ready = overall == ReadinessOverall.READY_FOR_CONTROLLED_PILOT and not mandatory_unmet and window_valid
    blockers = [
        f"{item['label']} ({item['status']}): {item['summary']}"
        for item in categories
        if item["key"] in set(mandatory_unmet) | set(advisory_unmet)
    ]
    return {
        "protocol": PROTOCOL,
        "generated_at": _now().isoformat(),
        "geographic_context_key": context_key,
        "pilot_id": str(pilot_id) if pilot_id else None,
        "overall": overall.value,
        "categories": categories,
        "mandatory_unmet": mandatory_unmet,
        "advisory_unmet": advisory_unmet,
        "blockers": blockers,
        "ready_for_activation": ready,
        # A satisfied gate is a prerequisite, not an authorization. Activation
        # is a separate explicit admin transition recorded in pilot_transitions.
        "pilot_activation_authorized": False,
        "disclaimer": (
            "Computed from persisted evidence and human attestations. Missing "
            "evidence is never a PASS. This gate never activates a pilot or "
            "model, dispatches resources, or authorizes operational civic action."
        ),
    }
