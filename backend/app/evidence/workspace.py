"""Phase 11 evidence workspace aggregation.

Every number is derived from persisted rows or retained snapshot files. There are
no hardcoded operational metrics. Missing evidence is returned as null or an
explicit NOT_ASSESSED/BLOCKED state.
"""

from __future__ import annotations

import math
import re
import statistics
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.evidence.ground_truth import serialize_record, status_counts
from app.evidence.snapshots import serialize_snapshot
from app.evidence.universes import serialize_universe
from app.governance.correlation import metrics_for_universe
from app.governance.infrastructure import DOMAINS
from app.models.enums import (
    AssetType,
    EvidenceQualityStatus,
    EvidenceSnapshotStatus,
    GroundTruthSourceType,
    GroundTruthStatus,
    ProvenanceKind,
    SnapshotVerificationStatus,
    ValidationExperimentType,
    ValidationStatus,
)
from app.models.evidence import (
    CorrelationUniverse,
    EvidenceSnapshot,
    GroundTruthRecord,
)
from app.models.infrastructure import InfrastructureAsset
from app.models.pilot import (
    CorrelationCandidate,
    CorrelationReview,
    InfrastructureSource,
)
from app.models.validation import ValidationDataset, ValidationExperiment
from app.validation.service import dataset_records

MAX_CONTEXT_RECORDS = 10_000
MAX_CONTEXT_ASSETS = 5_000


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _age_days(value: datetime | None) -> int | None:
    aware = _aware(value)
    return (datetime.now(timezone.utc) - aware).days if aware else None


def _point(value: str | None) -> tuple[float, float] | None:
    match = re.match(r"^POINT\(([-0-9.eE]+) ([-0-9.eE]+)\)$", value or "")
    if not match:
        return None
    lon, lat = float(match.group(1)), float(match.group(2))
    if math.isfinite(lat) and math.isfinite(lon):
        return lat, lon
    return None


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(h))


def infrastructure_context(session: Session) -> dict:
    """Descriptive bridge/311 overlap; never an infrastructure-aware model run."""

    dataset = session.scalar(
        select(ValidationDataset)
        .where(ValidationDataset.dataset_key.like("nyc311-%-2026q3"))
        .order_by(ValidationDataset.period_end.desc())
        .limit(1)
    )
    assets = session.scalars(
        select(InfrastructureAsset).where(
            InfrastructureAsset.asset_type == AssetType.BRIDGE,
            InfrastructureAsset.is_active.is_(True),
        )
        .limit(MAX_CONTEXT_ASSETS + 1)
    ).all()
    points: list[tuple[float, float]] = []
    for asset in assets:
        point = _point(asset.location)
        if point is not None:
            points.append(point)
    base = {
        "dataset_key": dataset.dataset_key if dataset else None,
        "bridge_assets": len(assets),
        "bridge_assets_with_coordinates": len(points),
        "missing_coordinates": len(assets) - len(points),
        "radius_m": 750,
        "method": "descriptive 750 m proximity context using stored bridge geometry",
        "infra_aware_comparison": "NOT_ASSESSED",
        "reason": (
            "Only the bridge domain is integrated. No validated dependency graph, "
            "road/drainage assets, or human-verified infrastructure condition labels "
            "exist, so an infrastructure-aware risk comparison would require an "
            "unvalidated model change. No weights are invented."
        ),
    }
    unavailable = {
        **base,
        "status": "NOT_ASSESSED",
        "incidents": 0,
        "incidents_within_radius": 0,
        "coverage": None,
        "median_nearest_bridge_m": None,
        "caveat": (
            "No descriptive proximity context is computed. This is not evidence "
            "of zero exposure, zero coverage or an infrastructure-aware result."
        ),
    }
    if len(assets) > MAX_CONTEXT_ASSETS:
        return {
            **unavailable,
            "bridge_assets": len(assets),
            "caveat": "Active bridge assets exceed the bounded context limit.",
        }
    if dataset is None or not points:
        return unavailable
    try:
        records, _ = dataset_records(session, dataset)
    except Exception:  # noqa: BLE001 - evidence remains unavailable, not fabricated
        return unavailable
    if len(records) > MAX_CONTEXT_RECORDS:
        return {
            **unavailable,
            "incidents": len(records),
            "caveat": "Incident records exceed the bounded context limit.",
        }
    cell = 0.01
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for point in points:
        key = (int(math.floor(point[0] / cell)), int(math.floor(point[1] / cell)))
        grid.setdefault(key, []).append(point)
    covered = 0
    nearest: list[float] = []
    for record in records:
        point = (float(record["latitude"]), float(record["longitude"]))
        key = (int(math.floor(point[0] / cell)), int(math.floor(point[1] / cell)))
        candidates = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                candidates.extend(grid.get((key[0] + dx, key[1] + dy), []))
        distance = min((_haversine_m(point, bridge) for bridge in candidates), default=math.inf)
        if distance <= 750:
            covered += 1
            nearest.append(distance)
    total = len(records)
    return {
        **base,
        "status": "DESCRIPTIVE_ONLY",
        "incidents": total,
        "incidents_within_radius": covered,
        "coverage": round(covered / total, 6) if total else None,
        "median_nearest_bridge_m": round(statistics.median(nearest), 1) if nearest else None,
        "caveat": (
            "Proximity is not exposure, dependency, condition or causal impact. "
            "The bridge source does not include roads, drainage or emergency assets."
        ),
    }


def _dataset_snapshot(
    session: Session, dataset_id: Any
) -> EvidenceSnapshot | None:
    return session.scalar(
        select(EvidenceSnapshot)
        .where(EvidenceSnapshot.validation_dataset_id == dataset_id)
        .order_by(EvidenceSnapshot.retrieved_at.desc())
        .limit(1)
    )


def external_results(session: Session, limit: int = 6) -> list[dict]:
    rows = session.execute(
        select(ValidationExperiment, ValidationDataset)
        .join(ValidationDataset, ValidationExperiment.dataset_id == ValidationDataset.id)
        .where(
            ValidationExperiment.status == ValidationStatus.COMPLETED,
            ValidationExperiment.experiment_type.in_(
                (
                    ValidationExperimentType.RISK_BACKTEST,
                    ValidationExperimentType.RISK_TEMPORAL,
                    ValidationExperimentType.RISK_GEOGRAPHIC,
                )
            ),
        )
        .order_by(ValidationExperiment.created_at.desc())
        .limit(500)
    ).all()
    results = []
    seen_datasets: set[Any] = set()
    for experiment, dataset in rows:
        if dataset.id in seen_datasets:
            continue
        seen_datasets.add(dataset.id)
        if len(results) >= limit:
            break
        methods = (experiment.metrics or {}).get("methods", {})
        civic = methods.get("civicflow_risk", {})
        baselines = {
            key: value
            for key, value in (experiment.baselines or {}).items()
            if value.get("pr_auc") is not None
        }
        best_name, best = (
            max(baselines.items(), key=lambda item: item[1]["pr_auc"])
            if baselines
            else (None, {})
        )
        civic_pr = civic.get("pr_auc")
        best_pr = best.get("pr_auc")
        results.append(
            {
                "dataset_key": dataset.dataset_key,
                "name": dataset.name,
                "region": dataset.region,
                "period_start": _iso(dataset.period_start),
                "period_end": _iso(dataset.period_end),
                "freshness_days": _age_days(dataset.period_end),
                "record_count": experiment.record_count,
                "experiment_key": experiment.experiment_key,
                "experiment_type": experiment.experiment_type.value,
                "evidence_kind": experiment.evidence_kind.value,
                "status": experiment.status.value,
                "method": experiment.method,
                "config_hash": experiment.config_hash,
                "model_version": experiment.model_version,
                "civicflow": civic,
                "baselines": baselines,
                "strongest_baseline": best_name,
                "beats_strongest_baseline": (
                    civic_pr > best_pr
                    if civic_pr is not None and best_pr is not None
                    else None
                ),
                "delta_pr_auc": (
                    round(civic_pr - best_pr, 6)
                    if civic_pr is not None and best_pr is not None
                    else None
                ),
                "origin_count": (experiment.metrics or {}).get("origin_count"),
                "density": (experiment.metrics or {}).get("density"),
                "confidence_interval": None,
                "uncertainty_note": (
                    "Rolling-origin folds overlap temporally, so a conventional "
                    "independent-sample confidence interval is not reported here."
                ),
                "classification": (
                    "FRESH_EXTERNAL_HOLDOUT"
                    if (dataset.dataset_metadata or {}).get("phase11_evaluation_role")
                    else "HISTORICAL_OR_DIAGNOSTIC"
                ),
                "evaluation_role": (dataset.dataset_metadata or {}).get(
                    "phase11_evaluation_role"
                ),
                "limitations": experiment.limitations or [],
                "findings": experiment.findings or [],
            }
        )
    return results


def build_workspace(session: Session, *, include_context: bool = True) -> dict:
    datasets = session.scalars(
        select(ValidationDataset).order_by(ValidationDataset.created_at.desc()).limit(20)
    ).all()
    registry = []
    for dataset in datasets:
        snapshot = _dataset_snapshot(session, dataset.id)
        registry.append(
            {
                "dataset_key": dataset.dataset_key,
                "name": dataset.name,
                "region": dataset.region,
                "period_start": _iso(dataset.period_start),
                "period_end": _iso(dataset.period_end),
                "record_count": dataset.record_count,
                "status": dataset.status.value,
                "schema_version": dataset.schema_version,
                "snapshot_sha256": dataset.snapshot_sha256,
                "source_url": dataset.source_url,
                "license_note": dataset.license_note,
                "freshness_days": _age_days(dataset.period_end),
                "provenance": (
                    (
                        "REAL"
                        if snapshot.provenance_kind.value == "OPERATIONAL"
                        else snapshot.provenance_kind.value
                    )
                    if snapshot
                    else "UNKNOWN"
                ),
                "provenance_kind": (
                    snapshot.provenance_kind.value if snapshot else "UNKNOWN"
                ),
                "evidence_snapshot": serialize_snapshot(snapshot) if snapshot else None,
                "quality": snapshot.quality_status.value if snapshot else "UNKNOWN",
                "verification": (
                    snapshot.verification_status.value if snapshot else "PENDING"
                ),
                "external_role": (dataset.dataset_metadata or {}).get(
                    "phase11_evaluation_role"
                ),
            }
        )

    snapshots = session.scalars(
        select(EvidenceSnapshot)
        .order_by(EvidenceSnapshot.retrieved_at.desc())
        .limit(12)
    ).all()
    current = session.scalars(
        select(EvidenceSnapshot)
        .where(EvidenceSnapshot.is_current.is_(True))
        .limit(500)
    ).all()
    quality_counts = {value.value: 0 for value in EvidenceQualityStatus}
    provenance_counts = {value.value: 0 for value in ProvenanceKind}
    for snapshot in current:
        quality_counts[snapshot.quality_status.value] += 1
        provenance_counts[snapshot.provenance_kind.value] += 1
    quality_issues = []
    for snapshot in current:
        for check in snapshot.quality_checks or []:
            if check.get("status") in {"FAIL", "WARN"}:
                quality_issues.append(
                    {
                        "snapshot_key": snapshot.snapshot_key,
                        "check": check.get("check"),
                        "status": check.get("status"),
                        "detail": check.get("detail"),
                    }
                )

    gt_counts = status_counts(session)
    gt_total = sum(gt_counts.values())
    gt_provenance = {value.value: 0 for value in ProvenanceKind}
    for provenance, count in session.execute(
        select(
            GroundTruthRecord.provenance_kind,
            func.count(GroundTruthRecord.id),
        ).group_by(GroundTruthRecord.provenance_kind)
    ).all():
        gt_provenance[provenance.value] = int(count)
    operational_verified = int(
        session.scalar(
            select(func.count())
            .select_from(GroundTruthRecord)
            .where(
                GroundTruthRecord.provenance_kind == ProvenanceKind.OPERATIONAL,
                GroundTruthRecord.status == GroundTruthStatus.VERIFIED,
            )
        )
        or 0
    )
    gt_sources = {
        source.value: 0 for source in GroundTruthSourceType
    }
    for source_type, count in session.execute(
        select(GroundTruthRecord.source_type, func.count(GroundTruthRecord.id)).group_by(
            GroundTruthRecord.source_type
        )
    ).all():
        gt_sources[source_type.value] = int(count)
    recent_gt = session.scalars(
        select(GroundTruthRecord).order_by(GroundTruthRecord.created_at.desc()).limit(5)
    ).all()

    universes = session.scalars(
        select(CorrelationUniverse)
        .order_by(CorrelationUniverse.created_at.desc())
        .limit(6)
    ).all()
    universe_payload = []
    total_candidates = int(
        session.scalar(select(func.count()).select_from(CorrelationCandidate)) or 0
    )
    reviewed_candidates = int(
        session.scalar(
            select(func.count(func.distinct(CorrelationReview.candidate_id)))
        )
        or 0
    )
    for universe in universes[:6]:
        candidate_count = int(
            session.scalar(
                select(func.count())
                .select_from(CorrelationCandidate)
                .where(CorrelationCandidate.universe_key == universe.universe_key)
            )
            or 0
        )
        reviewed = int(
            session.scalar(
                select(func.count(func.distinct(CorrelationReview.candidate_id)))
                .select_from(CorrelationReview)
                .join(
                    CorrelationCandidate,
                    CorrelationReview.candidate_id == CorrelationCandidate.id,
                )
                .where(CorrelationCandidate.universe_key == universe.universe_key)
            )
            or 0
        )
        universe_payload.append(
            {
                **serialize_universe(universe),
                "candidate_count": candidate_count,
                "reviewed_candidates": reviewed,
                "metrics": (
                    metrics_for_universe(session, universe.universe_key)
                    if candidate_count
                    else None
                ),
            }
        )

    sources = session.scalars(
        select(InfrastructureSource)
        .order_by(InfrastructureSource.created_at.desc())
        .limit(50)
    ).all()
    source_payload = []
    integrated = 0
    for source in sources:
        latest = session.scalar(
            select(EvidenceSnapshot)
            .where(
                EvidenceSnapshot.infrastructure_source_id == source.id,
                EvidenceSnapshot.status == EvidenceSnapshotStatus.VALIDATED,
                EvidenceSnapshot.is_current.is_(True),
            )
            .order_by(EvidenceSnapshot.retrieved_at.desc())
            .limit(1)
        )
        has_active_assets = bool(
            session.scalar(
                select(func.count())
                .select_from(InfrastructureAsset)
                .where(
                    InfrastructureAsset.source_id == source.id,
                    InfrastructureAsset.is_active.is_(True),
                )
            )
        )
        integrated_flag = (
            latest is not None
            and source.validation_status.value == "VERIFIED"
            and has_active_assets
        )
        if integrated_flag:
            integrated += 1
        source_payload.append(
            {
                "source_key": source.source_key,
                "name": source.name,
                "category": source.category,
                "provider": source.provider,
                "source_url": source.source_url,
                "license_note": source.license_note,
                "validation_status": source.validation_status.value,
                "retrieved_at": _iso(source.retrieved_at),
                "dataset_version": source.dataset_version,
                "snapshot_sha256": source.snapshot_sha256,
                "latest_snapshot": serialize_snapshot(latest) if latest else None,
                "integrated": integrated_flag,
            }
        )
    assets_by_type = {
        row[0].value: int(row[1])
        for row in session.execute(
            select(InfrastructureAsset.asset_type, func.count(InfrastructureAsset.id))
            .where(InfrastructureAsset.is_active.is_(True))
            .group_by(InfrastructureAsset.asset_type)
        ).all()
    }
    verified_domains = sorted({source.category for source in sources if source.validation_status.value == "VERIFIED"})
    integrated_domains = sorted(
        {row["category"] for row in source_payload if row["integrated"]}
    )
    domain_items = []
    for key, label in DOMAINS:
        domain_items.append(
            {
                "domain": key,
                "label": label,
                "verified_source": key in verified_domains,
                "integrated_snapshot": key in integrated_domains,
            }
        )

    external = external_results(session)
    fresh_external = [
        item for item in external if item["classification"] == "FRESH_EXTERNAL_HOLDOUT"
    ]
    context = infrastructure_context(session) if include_context else None

    snapshot_total = int(
        session.scalar(select(func.count()).select_from(EvidenceSnapshot)) or 0
    )
    current_total = int(
        session.scalar(
            select(func.count())
            .select_from(EvidenceSnapshot)
            .where(EvidenceSnapshot.is_current.is_(True))
        )
        or 0
    )

    blockers = []
    if snapshot_total == 0 or int(
        session.scalar(
            select(func.count())
            .select_from(EvidenceSnapshot)
            .where(EvidenceSnapshot.status == EvidenceSnapshotStatus.VALIDATED)
        )
        or 0
    ) == 0:
        blockers.append("No validated evidence snapshot is available.")
    if operational_verified == 0:
        blockers.append(
            "No operational ground-truth assertion has been human-verified; "
            "synthetic test fixtures are not counted."
        )
    if not any(item.reference_complete for item in universes):
        blockers.append("No correlation reference universe is attested complete; recall remains null.")
    if reviewed_candidates == 0:
        blockers.append("No correlation candidate has an independent reviewer label.")
    if len(integrated_domains) < len(DOMAINS):
        blockers.append(
            f"Infrastructure integration covers {len(integrated_domains)} of "
            f"{len(DOMAINS)} domains; infrastructure-aware model evaluation is NOT_ASSESSED."
        )
    if not fresh_external:
        blockers.append("No fresh external validation result is registered.")
    elif not any(item["beats_strongest_baseline"] for item in fresh_external):
        blockers.append("No fresh external result exceeds its strongest baseline.")

    return {
        "protocol": "phase11-evidence-workspace-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_integrity": {
            "snapshots": snapshot_total,
            "current_snapshots": current_total,
            "quality_counts": quality_counts,
            "provenance_counts": provenance_counts,
            "automated_recomputations": int(
                session.scalar(
                    select(func.count())
                    .select_from(EvidenceSnapshot)
                    .where(
                        EvidenceSnapshot.verification_status
                        == SnapshotVerificationStatus.AUTOMATED_RECOMPUTATION
                    )
                )
                or 0
            ),
            "quality_issues": quality_issues[:20],
            "real_data_disclaimer": (
                "REAL_ACQUIRED means bytes were retrieved from the named public "
                "source and hashed; it does not mean CivicFlow field-verified the "
                "physical condition. SYNTHETIC fixtures are labelled separately."
            ),
        },
        "dataset_registry": registry,
        "snapshots": [serialize_snapshot(snapshot) for snapshot in snapshots],
        "ground_truth": {
            "total": gt_total,
            "status_counts": gt_counts,
            "source_counts": gt_sources,
            "provenance_counts": gt_provenance,
            "verified_count": gt_counts["VERIFIED"],
            "operational_verified_count": operational_verified,
            "human_verification": (
                "NONE" if operational_verified == 0 else "PRESENT"
            ),
            "recent": [serialize_record(record) for record in recent_gt],
            "workflow": [
                "CITIZEN_REPORT/AI_PREDICTION/HUMAN_OBSERVATION start UNVERIFIED",
                "A worker submits for review; status becomes IN_REVIEW",
                "A different staff reviewer records VERIFIED, REJECTED or INSUFFICIENT_EVIDENCE",
                "Creator self-verification is rejected",
                "History is append-only; original report and model scores are untouched",
            ],
        },
        "correlation": {
            "universes": universe_payload,
            "candidate_total": total_candidates,
            "reviewed_candidate_total": reviewed_candidates,
            "recall_available": any(
                ((universe.get("metrics") or {}).get("metrics") or {}).get("recall")
                is not None
                for universe in universe_payload
            ),
            "true_negatives_available": False,
            "note": (
                "Recall/F1 and true negatives remain null unless a complete "
                "reference universe exists and all required labels are present."
            ),
        },
        "infrastructure": {
            "domains": domain_items,
            "domains_integrated": len(integrated_domains),
            "domains_verified": len(verified_domains),
            "sources": source_payload,
            "assets_total": sum(assets_by_type.values()),
            "assets_by_type": assets_by_type,
            "independent_automated_checks": int(
                session.scalar(
                    select(func.count())
                    .select_from(EvidenceSnapshot)
                    .where(
                        EvidenceSnapshot.infrastructure_source_id.is_not(None),
                        EvidenceSnapshot.verification_status
                        == SnapshotVerificationStatus.AUTOMATED_RECOMPUTATION,
                    )
                )
                or 0
            ),
            "coverage_context": context,
        },
        "external_validation": {
            "results": external,
            "registered_fresh_datasets": sum(
                1 for item in registry if item.get("external_role")
            ),
            "methodology": (
                "Pinned q3-2026 NYC 311 slices acquired after Phase 9. The registered "
                "risk configuration is unchanged; no holdout tuning or model activation."
            ),
            "baseline_note": (
                "Strongest baseline is selected by observed holdout PR-AUC only for "
                "reporting; no model selection uses the holdout."
            ),
        },
        "blockers": blockers,
        "not_assessed": [
            "Infrastructure-aware model comparison (only bridge domain; no dependency graph).",
            "Correlation recall/F1/true negatives (no complete human-labelled universe).",
            "Human ground-truth verification (no verified records).",
            "Operational pilot readiness (no approved pilot or operational activation).",
        ],
        "synthetic_separation": (
            "Synthetic fixtures may exist only in automated tests and must be labelled "
            "SYNTHETIC. Operational evidence and synthetic fixtures are never pooled."
        ),
    }
