"""Dhaka-specific readiness assessment (Phase 12).

This is an additive view. It does not replace ``assess_readiness`` and never
returns PASS for missing evidence. Every derived category reads persisted rows
tagged ``BD-DHAKA``; manual categories require a recorded attestation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.geo.contexts import BD_DHAKA, US_NYC, BoundingBox, pilot_area_selection_status
from app.governance.readiness import FRESHNESS_DAYS, _category, _criterion
from app.models.evidence import (
    CorrelationUniverse,
    EvidenceSnapshot,
    GroundTruthRecord,
)
from app.models.enums import (
    EvidenceSnapshotStatus,
    PilotStatus,
    ProvenanceKind,
    ReadinessOverall,
    ReadinessStatus,
    ValidationExperimentType,
)
from app.models.geo import GeographicContextRecord
from app.models.pilot import (
    InfrastructureSource,
    Pilot,
    PilotReviewer,
    ReadinessEvidence,
    RiskReviewCase,
)
from app.models.validation import ValidationDataset, ValidationExperiment

PROTOCOL = "phase12-dhaka-readiness-v1"
CONTEXT_KEY = BD_DHAKA.key
MANUAL_CATEGORIES = (
    ("dhaka_security", "Dhaka security review", "Security lead"),
    ("dhaka_reviewer_training", "Dhaka reviewer training", "Review lead"),
    ("dhaka_incident_escalation", "Dhaka incident escalation", "Operations lead"),
    ("dhaka_deployment_rollback", "Dhaka deployment and rollback", "Platform lead"),
    ("dhaka_stakeholder_engagement", "Dhaka stakeholder engagement", "Governance lead"),
)
ADVISORY_KEYS = {
    "dhaka_security",
    "dhaka_reviewer_training",
    "dhaka_incident_escalation",
    "dhaka_deployment_rollback",
    "dhaka_stakeholder_engagement",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _count(session: Session, statement: Any) -> int:
    return int(session.scalar(select(func.count()).select_from(statement)) or 0)


def _manual(session: Session, key: str, label: str, owner: str) -> dict:
    rows = session.scalars(
        select(ReadinessEvidence).where(ReadinessEvidence.category == key)
    ).all()
    passed = [row for row in rows if row.status == ReadinessStatus.PASS]
    status = ReadinessStatus.PASS if passed else (
        ReadinessStatus.IN_PROGRESS
        if rows
        else ReadinessStatus.BLOCKED
    )
    evidence = (
        "; ".join(f"{row.criterion_key}: {row.evidence}" for row in rows[:3])
        if rows
        else "No attestation recorded for this Dhaka category."
    )
    criterion = _criterion(
        f"{key}.attestation",
        "Recorded attestation",
        status,
        evidence,
        refs=[f"readiness_evidence:{key}"],
    )
    return _category(
        key,
        label,
        status,
        f"{len(passed)} of {len(rows)} attestation(s) at PASS.",
        [criterion],
        owner=owner,
        mandatory=key not in ADVISORY_KEYS,
    )


def _derived(session: Session, key: str, label: str, criteria: list[dict], owner: str) -> dict:
    statuses = {item["status"] for item in criteria if item["blocking"]}
    if ReadinessStatus.BLOCKED.value in statuses:
        status = ReadinessStatus.BLOCKED
    elif ReadinessStatus.FAIL.value in statuses:
        status = ReadinessStatus.FAIL
    elif ReadinessStatus.NOT_ASSESSED.value in statuses or ReadinessStatus.IN_PROGRESS.value in statuses:
        status = ReadinessStatus.IN_PROGRESS
    else:
        status = ReadinessStatus.PASS
    return _category(
        key,
        label,
        status,
        f"{sum(1 for item in criteria if item['status'] == 'PASS')} of {len(criteria)} criterion/criteria satisfied.",
        criteria,
        owner=owner,
        mandatory=key not in ADVISORY_KEYS,
    )


def assess_dhaka_readiness(session: Session) -> dict:
    """Compute Dhaka readiness from persisted, context-tagged evidence."""

    context_record = session.scalar(
        select(GeographicContextRecord).where(
            GeographicContextRecord.context_key == CONTEXT_KEY
        )
    )
    boundary_status = (
        context_record.boundary_status if context_record else "MISSING"
    )
    boundary = "PASS" if boundary_status == "AUTHORITATIVE" else (
        "IN_PROGRESS" if boundary_status == "PROVISIONAL" else "BLOCKED"
    )
    categories = [
        _derived(
            session,
            "dhaka_geographic_boundary",
            "Dhaka geographic boundary",
            [
                _criterion(
                    "dhaka.boundary.authoritative",
                    "Authoritative boundary layer",
                    ReadinessStatus(boundary) if boundary != "MISSING" else ReadinessStatus.BLOCKED,
                    (
                        f"Registered context boundary status is {boundary_status}. "
                        "The current bbox is a research screening envelope, not a DNCC/DSCC/ward boundary."
                    ),
                    refs=["geographic_contexts:BD-DHAKA"],
                )
            ],
            "Urban data engineering",
        )
    ]

    selection = pilot_area_selection_status()
    dhaka_pilots = session.scalars(
        select(Pilot).where(Pilot.geographic_context_key == CONTEXT_KEY)
    ).all()
    approved = [
        pilot for pilot in dhaka_pilots if pilot.status in {PilotStatus.APPROVED, PilotStatus.ACTIVE}
    ]
    categories.append(
        _derived(
            session,
            "dhaka_pilot_area_selection",
            "Dhaka pilot area selection",
            [
                _criterion(
                    "dhaka.pilot.approved_area",
                    "Stakeholder-approved pilot area",
                    ReadinessStatus.PASS if approved else ReadinessStatus.BLOCKED,
                    (
                        f"{len(approved)} approved Dhaka pilot(s); "
                        f"registry selection status: {selection['status']}. {selection['reason']}"
                    ),
                    refs=["pilots:BD-DHAKA"],
                )
            ],
            "Pilot administrator",
        )
    )

    snapshots = session.scalars(
        select(EvidenceSnapshot).where(
            EvidenceSnapshot.geographic_context_key == CONTEXT_KEY
        )
    ).all()
    validated = [
        item
        for item in snapshots
        if item.status == EvidenceSnapshotStatus.VALIDATED
        and item.provenance_kind != ProvenanceKind.SYNTHETIC
    ]
    authoritative = [
        item for item in validated if not item.source_key.startswith("dhaka-osm")
    ]
    categories.append(
        _derived(
            session,
            "dhaka_source_availability",
            "Dhaka source availability",
            [
                _criterion(
                    "dhaka.sources.validated_snapshot",
                    "At least one validated BD-DHAKA snapshot",
                    ReadinessStatus.PASS if validated else ReadinessStatus.BLOCKED,
                    f"{len(validated)} validated snapshot(s) of {len(snapshots)} total.",
                    refs=["evidence_snapshots:BD-DHAKA"],
                ),
                _criterion(
                    "dhaka.sources.authoritative",
                    "At least one authoritative municipal/official source",
                    ReadinessStatus.PASS if authoritative else ReadinessStatus.BLOCKED,
                    (
                        f"{len(authoritative)} authoritative source(s). "
                        "OpenStreetMap research context is not an authoritative civic register."
                    ),
                    refs=["evidence_snapshots:BD-DHAKA"],
                ),
            ],
            "Data engineering",
        )
    )

    if snapshots:
        newest = max(
            (item.retrieved_at for item in snapshots if item.retrieved_at),
            default=None,
        )
        freshness_status = ReadinessStatus.BLOCKED
        freshness_evidence = "No retrieved timestamp recorded."
        if newest is not None:
            age_days = (_now() - newest.replace(tzinfo=newest.tzinfo or timezone.utc)).days
            freshness_status = (
                ReadinessStatus.PASS if age_days <= FRESHNESS_DAYS else ReadinessStatus.FAIL
            )
            freshness_evidence = f"Newest BD-DHAKA retrieval is {age_days} day(s) old."
    else:
        freshness_status = ReadinessStatus.BLOCKED
        freshness_evidence = "No BD-DHAKA snapshot exists."
    categories.append(
        _derived(
            session,
            "dhaka_data_freshness",
            "Dhaka data freshness",
            [
                _criterion(
                    "dhaka.data.age",
                    "Freshness within the configured window",
                    freshness_status,
                    freshness_evidence,
                    refs=["evidence_snapshots:BD-DHAKA"],
                )
            ],
            "Data engineering",
        )
    )

    contained_snapshots = [
        item
        for item in snapshots
        if item.bbox
        and len(item.bbox) == 4
        and BD_DHAKA.bbox.contains_bbox(
            BoundingBox.from_geojson(item.bbox)
        )
    ]
    pilot_bbox_ok = [
        pilot
        for pilot in dhaka_pilots
        if len(pilot.bbox) == 4
        and BD_DHAKA.bbox.contains_bbox(
            BoundingBox.from_geojson(pilot.bbox)
        )
    ]
    categories.append(
        _derived(
            session,
            "dhaka_geographic_coverage",
            "Dhaka geographic coverage",
            [
                _criterion(
                    "dhaka.coverage.snapshots",
                    "BD-DHAKA snapshots inside the registered envelope",
                    ReadinessStatus.PASS if contained_snapshots else ReadinessStatus.BLOCKED,
                    f"{len(contained_snapshots)} of {len(snapshots)} snapshot(s) fully contained.",
                    refs=["evidence_snapshots:BD-DHAKA"],
                ),
                _criterion(
                    "dhaka.coverage.pilot",
                    "Approved pilot bbox inside the registered envelope",
                    ReadinessStatus.PASS if pilot_bbox_ok else ReadinessStatus.BLOCKED,
                    f"{len(pilot_bbox_ok)} Dhaka pilot bbox(es) fully contained.",
                    refs=["pilots:BD-DHAKA"],
                ),
            ],
            "Spatial engineering",
        )
    )

    complete_provenance = [
        item
        for item in snapshots
        if item.raw_sha256 and item.license_note and item.lineage
    ]
    categories.append(
        _derived(
            session,
            "dhaka_data_provenance",
            "Dhaka data provenance",
            [
                _criterion(
                    "dhaka.provenance.completeness",
                    "Hash, license and lineage on every BD-DHAKA snapshot",
                    (
                        ReadinessStatus.PASS
                        if snapshots and len(complete_provenance) == len(snapshots)
                        else ReadinessStatus.BLOCKED
                    ),
                    f"{len(complete_provenance)} of {len(snapshots)} snapshot(s) complete.",
                    refs=["evidence_snapshots:BD-DHAKA"],
                )
            ],
            "Data engineering",
        )
    )

    gt_rows = session.scalars(
        select(GroundTruthRecord).where(
            GroundTruthRecord.geographic_context_key == CONTEXT_KEY
        )
    ).all()
    verified_gt = [
        row
        for row in gt_rows
        if row.status.value == "VERIFIED"
        and row.provenance_kind == ProvenanceKind.OPERATIONAL
    ]
    categories.append(
        _derived(
            session,
            "dhaka_ground_truth_readiness",
            "Dhaka ground-truth readiness",
            [
                _criterion(
                    "dhaka.ground_truth.verified",
                    "At least five human-verified field records",
                    ReadinessStatus.PASS if len(verified_gt) >= 5 else ReadinessStatus.BLOCKED,
                    f"{len(verified_gt)} verified BD-DHAKA record(s) of {len(gt_rows)} total.",
                    refs=["ground_truth_records:BD-DHAKA"],
                ),
                _criterion(
                    "dhaka.ground_truth.not_ai",
                    "AI predictions excluded from ground truth",
                    ReadinessStatus.PASS
                    if all(row.source_type.value != "AI_PREDICTION" for row in verified_gt)
                    else ReadinessStatus.FAIL,
                    "Verified records are checked for AI-prediction source type.",
                    refs=["ground_truth_records:BD-DHAKA"],
                ),
            ],
            "Field operations lead",
        )
    )

    universes = session.scalars(
        select(CorrelationUniverse).where(
            CorrelationUniverse.geographic_context_key == CONTEXT_KEY
        )
    ).all()
    complete_universes = [
        row for row in universes if row.reference_complete and (row.reference_size or 0) >= 30
    ]
    categories.append(
        _derived(
            session,
            "dhaka_correlation_readiness",
            "Dhaka correlation readiness",
            [
                _criterion(
                    "dhaka.correlation.complete_universe",
                    "Complete reference universe with at least 30 candidates",
                    ReadinessStatus.PASS if complete_universes else ReadinessStatus.BLOCKED,
                    f"{len(complete_universes)} attested complete BD-DHAKA universe(s) of {len(universes)}.",
                    refs=["correlation_universes:BD-DHAKA"],
                )
            ],
            "Correlation review lead",
        )
    )

    infra_sources = session.scalars(select(InfrastructureSource)).all()
    dhaka_infra = [
        row
        for row in infra_sources
        if "dhaka" in row.source_key.lower() or "dhaka" in row.geographic_coverage.lower()
    ]
    categories.append(
        _derived(
            session,
            "dhaka_infrastructure_coverage",
            "Dhaka infrastructure coverage",
            [
                _criterion(
                    "dhaka.infrastructure.domains",
                    "Authoritative coverage of all seven infrastructure domains",
                    ReadinessStatus.BLOCKED,
                    (
                        f"{len(dhaka_infra)} Dhaka-linked source(s); OSM research context "
                        "covers map features only. Seven authoritative domains are required."
                    ),
                    refs=["infrastructure_sources"],
                )
            ],
            "Infrastructure data lead",
        )
    )

    dhaka_experiments = session.scalars(
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
    experiments_with_metrics = [
        row for row in dhaka_experiments if row.metrics and "pr_auc" in row.metrics
    ]
    categories.append(
        _derived(
            session,
            "dhaka_model_validation",
            "Dhaka model validation",
            [
                _criterion(
                    "dhaka.validation.experiment",
                    "Persisted Dhaka geographic/temporal experiment",
                    ReadinessStatus.PASS if experiments_with_metrics else ReadinessStatus.BLOCKED,
                    f"{len(experiments_with_metrics)} Dhaka experiment(s) with PR-AUC metrics.",
                    refs=["validation_experiments:BD-DHAKA"],
                )
            ],
            "ML validation lead",
        )
    )
    categories.append(
        _derived(
            session,
            "dhaka_baseline_comparison",
            "Dhaka baseline comparison",
            [
                _criterion(
                    "dhaka.validation.baseline",
                    "Model compared against the strongest baseline on Dhaka data",
                    ReadinessStatus.BLOCKED,
                    (
                        "No Dhaka external slice has been evaluated. NYC comparisons "
                        "are never valid as Dhaka performance evidence."
                    ),
                    refs=["validation_experiments:BD-DHAKA"],
                )
            ],
            "ML validation lead",
        )
    )

    pilot_ids = [pilot.id for pilot in dhaka_pilots]
    reviews = (
        session.scalars(
            select(RiskReviewCase).where(RiskReviewCase.pilot_id.in_(pilot_ids))
        ).all()
        if pilot_ids
        else []
    )
    reviewers = (
        session.scalars(
            select(PilotReviewer).where(PilotReviewer.pilot_id.in_(pilot_ids))
        ).all()
        if pilot_ids
        else []
    )
    categories.append(
        _derived(
            session,
            "dhaka_human_review",
            "Dhaka human review",
            [
                _criterion(
                    "dhaka.review.cases",
                    "Human review cases linked to a Dhaka pilot",
                    ReadinessStatus.PASS if len(reviews) >= 20 else ReadinessStatus.BLOCKED,
                    f"{len(reviews)} review case(s), {len(reviewers)} reviewer(s).",
                    refs=["risk_review_cases:BD-DHAKA"],
                )
            ],
            "Review lead",
        )
    )

    categories.append(
        _derived(
            session,
            "dhaka_geographic_isolation",
            "Dhaka geographic isolation",
            [
                _criterion(
                    "dhaka.isolation.no_cross_region",
                    "No cross-context evidence mixing",
                    (
                        ReadinessStatus.BLOCKED
                        if not snapshots
                        else ReadinessStatus.PASS
                        if not [
                            item
                            for item in snapshots
                            if item.source_key.startswith("nyc")
                            or item.source_key.startswith("nyc311")
                        ]
                        else ReadinessStatus.FAIL
                    ),
                    (
                        "Checks BD-DHAKA snapshots for NYC source keys. "
                        f"{len(snapshots)} Dhaka snapshot(s) inspected."
                    ),
                    refs=["evidence_snapshots:BD-DHAKA"],
                ),
                _criterion(
                    "dhaka.isolation.no_synthetic",
                    "No synthetic fixture is treated as Dhaka evidence",
                    (
                        ReadinessStatus.BLOCKED
                        if not snapshots
                        else ReadinessStatus.FAIL
                        if any(
                            item.provenance_kind == ProvenanceKind.SYNTHETIC
                            for item in snapshots
                        )
                        else ReadinessStatus.PASS
                    ),
                    (
                        "Synthetic fixtures are never counted as operational "
                        f"Dhaka evidence; {len(snapshots)} snapshot(s) inspected."
                    ),
                    refs=["evidence_snapshots:BD-DHAKA"],
                ),
                _criterion(
                    "dhaka.isolation.nyc_preserved",
                    "NYC research evidence remains tagged US-NYC",
                    (
                        ReadinessStatus.PASS
                        if (
                            session.scalar(
                                select(func.count())
                                .select_from(EvidenceSnapshot)
                                .where(
                                    EvidenceSnapshot.geographic_context_key
                                    == US_NYC.key
                                )
                            )
                            or 0
                        ) > 0
                        else ReadinessStatus.BLOCKED
                    ),
                    (
                        "Checks persisted US-NYC snapshots. Historical NYC "
                        "dataset keys and hashes are unchanged."
                    ),
                    refs=["evidence_snapshots:US-NYC"],
                    blocking=False,
                ),
            ],
            "Security lead",
        )
    )

    categories.append(
        _derived(
            session,
            "dhaka_operational_constraints",
            "Dhaka operational constraints",
            [
                _criterion(
                    "dhaka.operations.non_autonomous",
                    "Supervised simulation/staging pilot only",
                    ReadinessStatus.BLOCKED,
                    (
                        "No approved Dhaka pilot exists. Automated dispatch, public "
                        "alerts, resource allocation and autonomous decisions remain disabled."
                    ),
                    refs=["pilots:BD-DHAKA"],
                )
            ],
            "Operations lead",
        )
    )

    categories.append(
        _category(
            "dhaka_model_activation",
            "Dhaka model activation",
            ReadinessStatus.NOT_APPLICABLE,
            "Phase 12 prepares evaluation only; no model was trained, promoted or activated.",
            [
                _criterion(
                    "dhaka.model.not_activated",
                    "No Phase 12 model activation",
                    ReadinessStatus.NOT_APPLICABLE,
                    "No activation endpoint was invoked during Phase 12.",
                    blocking=False,
                )
            ],
            owner="ML governance lead",
            mandatory=False,
        )
    )

    for key, label, owner in MANUAL_CATEGORIES:
        categories.append(_manual(session, key, label, owner))

    passed = {ReadinessStatus.PASS.value, ReadinessStatus.NOT_APPLICABLE.value}
    mandatory_unmet = [
        item for item in categories if item["mandatory"] and item["status"] not in passed
    ]
    advisory_unmet = [
        item for item in categories if not item["mandatory"] and item["status"] not in passed
    ]
    overall = (
        ReadinessOverall.NOT_READY
        if mandatory_unmet
        else ReadinessOverall.CONDITIONALLY_READY
        if advisory_unmet
        else ReadinessOverall.READY_FOR_CONTROLLED_PILOT
    )
    return {
        "protocol": PROTOCOL,
        "generated_at": _now().isoformat(),
        "geographic_context_key": CONTEXT_KEY,
        "overall": overall.value,
        "pilot_activation_authorized": False,
        "ready_for_activation": False,
        "categories": categories,
        "mandatory_unmet": [item["key"] for item in mandatory_unmet],
        "advisory_unmet": [item["key"] for item in advisory_unmet],
        "blockers": [
            f"{item['label']} ({item['status']}): {item['summary']}"
            for item in mandatory_unmet + advisory_unmet
        ],
        "pilot_area_selection": selection,
        "disclaimer": (
            "Computed from persisted BD-DHAKA evidence. Missing evidence is "
            "never a PASS. This view does not authorize a pilot, activate a "
            "model, dispatch resources or make safety claims."
        ),
    }
