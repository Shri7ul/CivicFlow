"""Evidence-derived Phase 10 pilot readiness scorecard.

No category is hard-coded to PASS. Derived categories read persisted rows.
Manual categories require a recorded attestation with references.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import (
    EvidenceSnapshotStatus,
    GroundTruthStatus,
    PilotMode,
    PilotReviewerRole,
    PilotStatus,
    ReadinessOverall,
    ReadinessStatus,
    RiskReviewStatus,
    ValidationDatasetStatus,
    ValidationExperimentType,
    ValidationStatus,
)
from app.models.pilot import (
    CorrelationCandidate,
    CorrelationReview,
    InfrastructureSource,
    Pilot,
    PilotReviewer,
    ReadinessEvidence,
    RiskReviewCase,
    RiskReviewEvent,
)
from app.models.evidence import (
    CorrelationUniverse,
    EvidenceSnapshot,
    GroundTruthRecord,
)
from app.models.infrastructure import InfrastructureAsset
from app.models.profile import Profile
from app.models.validation import ValidationDataset, ValidationExperiment
from app.validation.research import phase9_summary

PROTOCOL = "phase11-readiness-v2"
FRESHNESS_DAYS = 180
INFRASTRUCTURE_DOMAINS = (
    ("ROADS", "Roads"),
    ("BRIDGES", "Bridges"),
    ("PUBLIC_FACILITIES", "Public facilities"),
    ("WATER", "Water"),
    ("DRAINAGE", "Drainage"),
    ("EMERGENCY_FACILITIES", "Emergency facilities"),
    ("TRANSIT", "Transit"),
)
MANUAL_CATEGORIES = {
    "security",
    "reviewer_training",
    "incident_escalation",
    "deployment_rollback",
}
ADVISORY_CATEGORIES = {
    "security",
    "reviewer_training",
    "incident_escalation",
    "deployment_rollback",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _criterion(
    key: str,
    label: str,
    status: ReadinessStatus,
    evidence: str,
    *,
    refs: list[str] | None = None,
    blocking: bool = True,
) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status.value,
        "blocking": blocking,
        "evidence": evidence,
        "evidence_refs": refs or [],
    }


def _category(
    key: str,
    label: str,
    status: ReadinessStatus,
    summary: str,
    criteria: list[dict],
    *,
    owner: str,
    mandatory: bool = True,
) -> dict:
    issues = [
        f"{item['label']}: {item['evidence']}"
        for item in criteria
        if item["blocking"]
        and item["status"]
        not in {ReadinessStatus.PASS.value, ReadinessStatus.NOT_APPLICABLE.value}
    ]
    return {
        "key": key,
        "label": label,
        "status": status.value,
        "mandatory": mandatory,
        "owner": owner,
        "summary": summary,
        "criteria": criteria,
        "blocking_issues": issues,
    }


def _manual_category(session: Session, key: str, label: str, owner: str) -> dict:
    rows = session.scalars(
        select(ReadinessEvidence)
        .where(ReadinessEvidence.category == key)
        .order_by(ReadinessEvidence.assessed_at.desc())
    ).all()
    if not rows:
        criterion = _criterion(
            f"{key}.attestation",
            "Recorded attestation",
            ReadinessStatus.NOT_ASSESSED,
            "No attestation has been recorded for this category.",
        )
        return _category(
            key,
            label,
            ReadinessStatus.NOT_ASSESSED,
            f"No {label.lower()} evidence is recorded.",
            [criterion],
            owner=owner,
            mandatory=key not in ADVISORY_CATEGORIES,
        )
    statuses = {row.status for row in rows}
    if ReadinessStatus.FAIL in statuses:
        overall = ReadinessStatus.FAIL
    elif ReadinessStatus.BLOCKED in statuses:
        overall = ReadinessStatus.BLOCKED
    elif statuses == {ReadinessStatus.NOT_APPLICABLE}:
        overall = ReadinessStatus.NOT_APPLICABLE
    elif ReadinessStatus.IN_PROGRESS in statuses:
        overall = ReadinessStatus.IN_PROGRESS
    elif statuses <= {ReadinessStatus.PASS, ReadinessStatus.NOT_APPLICABLE}:
        overall = ReadinessStatus.PASS
    else:
        overall = ReadinessStatus.NOT_ASSESSED
    criteria = [
        _criterion(
            row.criterion_key,
            row.criterion_key.replace("_", " ").replace(".", " ").title(),
            row.status,
            row.evidence,
            refs=row.evidence_refs or [],
            blocking=row.blocking,
        )
        for row in rows
    ]
    latest = max((row.assessed_at for row in rows if row.assessed_at), default=None)
    return {
        **_category(
            key,
            label,
            overall,
            f"{len(rows)} attestation(s) recorded; latest {_iso(latest) or 'unknown'}.",
            criteria,
            owner=owner,
            mandatory=key not in ADVISORY_CATEGORIES,
        ),
        "last_assessed_at": _iso(latest),
    }


def _data_quality(session: Session) -> dict:
    datasets = session.scalars(
        select(ValidationDataset).order_by(ValidationDataset.created_at)
    ).all()
    completed = [item for item in datasets if item.status == ValidationDatasetStatus.VALIDATED]
    issues = []
    for dataset in completed:
        if len(dataset.snapshot_sha256 or "") != 64:
            issues.append(f"{dataset.dataset_key}: snapshot hash is not SHA-256")
        if not dataset.schema_version:
            issues.append(f"{dataset.dataset_key}: schema version missing")
        if not dataset.record_count:
            issues.append(f"{dataset.dataset_key}: no records")
        if not dataset.source_url or not dataset.license_note:
            issues.append(f"{dataset.dataset_key}: source or license missing")
    criteria = [
        _criterion(
            "dataset.inventory",
            "Completed snapshot inventory",
            ReadinessStatus.PASS if completed else ReadinessStatus.BLOCKED,
            f"{len(completed)} completed dataset(s) registered.",
            refs=["validation_datasets"],
        ),
        _criterion(
            "dataset.provenance",
            "Hash, schema, source and license complete",
            ReadinessStatus.PASS if completed and not issues else (
                ReadinessStatus.FAIL if completed else ReadinessStatus.BLOCKED
            ),
            "All completed datasets carry hash/schema/source/license."
            if completed and not issues
            else ("; ".join(issues[:6]) if issues else "No completed datasets."),
            refs=["validation_datasets"],
        ),
    ]
    snapshots = session.scalars(
        select(EvidenceSnapshot).where(
            EvidenceSnapshot.status == EvidenceSnapshotStatus.VALIDATED,
            EvidenceSnapshot.is_current.is_(True),
        )
    ).all()
    bad_snapshots = [
        item.snapshot_key
        for item in snapshots
        if len(item.snapshot_sha256 or "") != 64
        or item.record_count <= 0
        or not item.lineage
    ]
    criteria.append(
        _criterion(
            "dataset.evidence_snapshots",
            "Current evidence snapshots retain hash, records and lineage",
            (
                ReadinessStatus.PASS
                if snapshots and not bad_snapshots
                else (
                    ReadinessStatus.FAIL
                    if snapshots
                    else ReadinessStatus.BLOCKED
                )
            ),
            (
                f"{len(snapshots)} current validated snapshot(s); "
                f"{len(bad_snapshots)} incomplete."
                if snapshots
                else "No current validated evidence snapshot exists."
            ),
            refs=["evidence_snapshots"],
        )
    )
    if not completed:
        status = ReadinessStatus.BLOCKED
        summary = "No validated dataset inventory exists."
    elif issues:
        status = ReadinessStatus.FAIL
        summary = "One or more completed datasets lack required provenance."
    elif not snapshots:
        status = ReadinessStatus.BLOCKED
        summary = (
            f"{len(completed)} historical dataset(s) exist, but no current "
            "validated evidence snapshot is retained."
        )
    elif bad_snapshots:
        status = ReadinessStatus.FAIL
        summary = "Current evidence snapshots lack required hash, records or lineage."
    else:
        status = ReadinessStatus.PASS
        summary = (
            f"{len(completed)} complete dataset(s); {len(snapshots)} current "
            "validated evidence snapshot(s) with retained lineage."
        )
    return _category(
        "data_quality",
        "Data quality",
        status,
        summary,
        criteria,
        owner="Data engineering",
    )


def _freshness(session: Session) -> dict:
    rows = session.execute(
        select(
            func.max(ValidationDataset.period_end),
            func.count(ValidationDataset.id),
        ).where(ValidationDataset.status == ValidationDatasetStatus.VALIDATED)
    ).one()
    latest, count = rows[0], int(rows[1] or 0)
    if not latest:
        status = ReadinessStatus.BLOCKED
        evidence = "No completed dataset period is registered."
        age = None
    else:
        age = (_now() - _aware(latest)).days
        status = (
            ReadinessStatus.PASS if age <= FRESHNESS_DAYS else ReadinessStatus.FAIL
        )
        evidence = (
            f"Latest validation data ends {latest.date().isoformat()} "
            f"({age} days before assessment); threshold {FRESHNESS_DAYS} days."
        )
    criterion = _criterion(
        "dataset.freshness",
        "Latest data within freshness threshold",
        status,
        evidence,
        refs=["validation_datasets"],
    )
    summary = (
        f"Latest data is {age} days old."
        if age is not None
        else "No dated data is registered."
    )
    return _category(
        "data_freshness",
        "Data freshness",
        status,
        summary,
        [criterion],
        owner="Data engineering",
    )


def _geographic(session: Session) -> dict:
    regions = session.scalars(
        select(ValidationDataset.region)
        .where(ValidationDataset.status == ValidationDatasetStatus.VALIDATED)
        .distinct()
    ).all()
    unique = sorted({item for item in regions if item})
    status = (
        ReadinessStatus.PASS
        if len(unique) >= 3
        else (ReadinessStatus.FAIL if unique else ReadinessStatus.BLOCKED)
    )
    criterion = _criterion(
        "geography.regions",
        "At least three independently described regions",
        status,
        f"{len(unique)} distinct region(s): " + ", ".join(unique[:6]),
        refs=["validation_datasets"],
    )
    return _category(
        "geographic_coverage",
        "Geographic coverage",
        status,
        f"{len(unique)} distinct validated regions.",
        [criterion],
        owner="Data engineering",
    )


def _performance(session: Session) -> dict:
    try:
        summary = phase9_summary(session)
        rows = summary.get("datasets") or []
    except Exception as error:  # pragma: no cover - defensive for broken fixtures
        criterion = _criterion(
            "model.comparison",
            "Persisted model comparison",
            ReadinessStatus.BLOCKED,
            f"Phase 9 summary could not be read: {type(error).__name__}.",
        )
        return _category(
            "model_performance",
            "Model versus baseline",
            ReadinessStatus.BLOCKED,
            "Model comparison evidence is unavailable.",
            [criterion],
            owner="Model owner",
        )
    comparisons = []
    for row in rows:
        risk = row.get("risk") or {}
        best = row.get("best_baseline") or {}
        if risk.get("pr_auc") is not None and best.get("pr_auc") is not None:
            comparisons.append(
                {
                    "dataset": row.get("dataset_key"),
                    "region": row.get("region"),
                    "risk": risk.get("pr_auc"),
                    "baseline": best.get("pr_auc"),
                    "baseline_method": best.get("method"),
                    "delta": round(float(risk["pr_auc"]) - float(best["pr_auc"]), 6),
                }
            )
    fresh_rows = session.execute(
        select(ValidationExperiment, ValidationDataset)
        .join(ValidationDataset, ValidationExperiment.dataset_id == ValidationDataset.id)
        .where(
            ValidationExperiment.experiment_type
            == ValidationExperimentType.RISK_BACKTEST,
            ValidationExperiment.status == ValidationStatus.COMPLETED,
        )
        .order_by(ValidationExperiment.created_at.desc())
    ).all()
    fresh_comparisons = []
    seen_fresh = set()
    for experiment, dataset in fresh_rows:
        if not (dataset.dataset_metadata or {}).get("phase11_evaluation_role"):
            continue
        if dataset.dataset_key in seen_fresh:
            continue
        seen_fresh.add(dataset.dataset_key)
        methods = (experiment.metrics or {}).get("methods", {})
        risk = methods.get("civicflow_risk") or {}
        baselines = {
            key: value
            for key, value in (experiment.baselines or {}).items()
            if value.get("pr_auc") is not None
        }
        if risk.get("pr_auc") is None or not baselines:
            continue
        best_name, best = max(
            baselines.items(), key=lambda item: item[1]["pr_auc"]
        )
        fresh_comparisons.append(
            {
                "dataset": dataset.dataset_key,
                "region": dataset.region,
                "risk": risk.get("pr_auc"),
                "baseline": best.get("pr_auc"),
                "baseline_method": best_name,
                "delta": round(
                    float(risk["pr_auc"]) - float(best["pr_auc"]), 6
                ),
                "fresh": True,
            }
        )
    comparisons.extend(fresh_comparisons)
    wins = [item for item in comparisons if item["delta"] > 0]
    if not comparisons:
        status = ReadinessStatus.BLOCKED
        evidence = "No persisted CivicFlow-versus-baseline comparison exists."
    elif len(wins) == len(comparisons) and len(comparisons) >= 3:
        status = ReadinessStatus.PASS
        evidence = (
            f"CivicFlow exceeds the strongest baseline on all "
            f"{len(comparisons)} evaluated datasets."
        )
    else:
        status = ReadinessStatus.FAIL
        evidence = (
            f"CivicFlow exceeds the strongest baseline on {len(wins)} of "
            f"{len(comparisons)} datasets. "
            + "; ".join(
                f"{item['dataset']}: {item['risk']:.6f} vs "
                f"{item['baseline']:.6f} ({item['delta']:+.6f})"
                for item in comparisons[:4]
            )
        )
    criteria = [
        _criterion(
            "model.baseline_comparison",
            "PR-AUC versus strongest baseline on every dataset",
            status,
            evidence,
            refs=[
                "phase9-research-report",
                "validation_experiments",
                "phase11-fresh-external",
            ],
        ),
        _criterion(
            "model.fresh_external_holdout",
            "Fresh external holdout comparison is persisted",
            (
                ReadinessStatus.PASS
                if fresh_comparisons
                and all(item["delta"] > 0 for item in fresh_comparisons)
                else (
                    ReadinessStatus.FAIL
                    if fresh_comparisons
                    else ReadinessStatus.BLOCKED
                )
            ),
            (
                f"{sum(1 for item in fresh_comparisons if item['delta'] > 0)}/"
                f"{len(fresh_comparisons)} fresh external dataset(s) beat the "
                "strongest baseline; underperformance is retained."
                if fresh_comparisons
                else "No fresh post-Phase-9 external holdout is registered."
            ),
            refs=["validation_experiments", "phase11-fresh-external"],
        ),
        _criterion(
            "model.mean_pr_auc",
            "Mean PR-AUC is reported, not hidden",
            ReadinessStatus.PASS if comparisons else ReadinessStatus.BLOCKED,
            (
                f"Mean Phase 9 PR-AUC {summary.get('mean_pr_auc_across_datasets')}; "
                "values are descriptive because origins overlap."
            )
            if comparisons
            else "No comparison metrics are available.",
            refs=["phase9-research-report"],
        ),
    ]
    return _category(
        "model_performance",
        "Model versus baseline",
        status,
        (
            f"{len(wins)}/{len(comparisons)} datasets beat the strongest baseline."
            if comparisons
            else "No comparison evidence."
        ),
        criteria,
        owner="Model owner",
    )


def _robustness(session: Session) -> dict:
    experiments = session.scalars(
        select(ValidationExperiment).where(
            ValidationExperiment.experiment_type == ValidationExperimentType.RISK_ROBUSTNESS,
            ValidationExperiment.status == ValidationStatus.COMPLETED,
        )
    ).all()
    with_metrics = [item for item in experiments if item.metrics]
    status = (
        ReadinessStatus.PASS
        if with_metrics
        else (ReadinessStatus.FAIL if experiments else ReadinessStatus.BLOCKED)
    )
    criterion = _criterion(
        "model.robustness_suite",
        "Completed robustness suite with metrics",
        status,
        (
            f"{len(with_metrics)} completed robustness experiment(s) with metrics."
            if with_metrics
            else "No completed robustness experiment with metrics exists."
        ),
        refs=["validation_experiments"],
    )
    return _category(
        "model_robustness",
        "Model robustness",
        status,
        criterion["evidence"],
        [criterion],
        owner="Model owner",
    )


def _human_review(session: Session) -> dict:
    total = int(
        session.scalar(select(func.count()).select_from(RiskReviewCase)) or 0
    )
    reviewed = int(
        session.scalar(
            select(func.count())
            .select_from(RiskReviewCase)
            .where(RiskReviewCase.status != RiskReviewStatus.UNREVIEWED)
        )
        or 0
    )
    events = int(
        session.scalar(select(func.count()).select_from(RiskReviewEvent)) or 0
    )
    reviewers = int(
        session.scalar(
            select(func.count(func.distinct(RiskReviewEvent.actor_id))).where(
                RiskReviewEvent.actor_id.is_not(None)
            )
        )
        or 0
    )
    final = int(
        session.scalar(
            select(func.count())
            .select_from(RiskReviewCase)
            .where(
                RiskReviewCase.status.in_(
                    [RiskReviewStatus.ACCEPTED, RiskReviewStatus.REJECTED]
                )
            )
        )
        or 0
    )
    coverage = (reviewed / total) if total else 0.0
    if total == 0:
        status = ReadinessStatus.BLOCKED
        summary = "No risk assessment has been submitted for human review."
    elif reviewed == 0:
        status = ReadinessStatus.BLOCKED
        summary = f"{total} case(s) exist but none has a review decision."
    elif total >= 20 and coverage >= 0.9 and reviewers >= 2 and final >= 10:
        status = ReadinessStatus.PASS
        summary = (
            f"{reviewed}/{total} cases reviewed by {reviewers} reviewers; "
            f"{final} final decisions."
        )
    else:
        status = ReadinessStatus.FAIL
        summary = (
            f"{reviewed}/{total} cases reviewed by {reviewers} reviewers; "
            f"{final} final decisions; requires >=20 cases, >=90% coverage, "
            ">=2 reviewers and >=10 final decisions."
        )
    criteria = [
        _criterion(
            "review.case_volume",
            "At least 20 review cases",
            ReadinessStatus.PASS if total >= 20 else ReadinessStatus.FAIL,
            f"{total} case(s) registered.",
            refs=["risk_review_cases"],
        ),
        _criterion(
            "review.coverage",
            "At least 90% of cases reviewed",
            ReadinessStatus.PASS if total and coverage >= 0.9 else ReadinessStatus.FAIL,
            f"{reviewed}/{total} cases have a non-UNREVIEWED status.",
            refs=["risk_review_cases"],
        ),
        _criterion(
            "review.independence",
            "At least two distinct reviewers",
            ReadinessStatus.PASS if reviewers >= 2 else ReadinessStatus.FAIL,
            f"{reviewers} distinct reviewer identity(ies) in the audit log.",
            refs=["risk_review_events"],
        ),
        _criterion(
            "review.audit",
            "Every decision is recorded as an event",
            ReadinessStatus.PASS if events >= reviewed else ReadinessStatus.FAIL,
            f"{events} append-only review event(s) for {reviewed} reviewed case(s).",
            refs=["risk_review_events"],
        ),
    ]
    return _category(
        "human_review_coverage",
        "Human review coverage",
        status,
        summary,
        criteria,
        owner="Review lead",
    )


def _ground_truth(session: Session) -> dict:
    records = session.scalars(select(GroundTruthRecord)).all()
    operational = [
        item for item in records if item.provenance_kind.value == "OPERATIONAL"
    ]
    verified = [
        item for item in operational if item.status == GroundTruthStatus.VERIFIED
    ]
    reviewers = {
        item.verified_by for item in verified if item.verified_by is not None
    }
    complete = [
        item
        for item in verified
        if item.verification_method
        and item.verified_at
        and item.verification_evidence_refs
        and item.verified_by
    ]
    non_ai = [
        item
        for item in verified
        if item.source_type.value != "AI_PREDICTION"
    ]
    if not operational:
        status = ReadinessStatus.BLOCKED
        summary = "No operational ground-truth assertion is registered."
    elif not verified:
        status = ReadinessStatus.IN_PROGRESS
        summary = (
            f"{len(operational)} assertion(s) exist; none has a human verification "
            "decision."
        )
    elif len(verified) >= 5 and len(reviewers) >= 2 and len(complete) == len(verified) and non_ai:
        status = ReadinessStatus.PASS
        summary = (
            f"{len(verified)} operationally verified assertion(s) by "
            f"{len(reviewers)} reviewer(s), with evidence and method recorded."
        )
    else:
        status = ReadinessStatus.FAIL
        summary = (
            f"{len(verified)}/{len(operational)} assertions verified by "
            f"{len(reviewers)} reviewer(s); requires >=5 verified, >=2 reviewers, "
            "non-AI evidence, and complete method/evidence references."
        )
    criteria = [
        _criterion(
            "ground_truth.volume",
            "At least five operational assertions",
            ReadinessStatus.PASS if len(operational) >= 5 else ReadinessStatus.FAIL,
            f"{len(operational)} operational assertion(s).",
            refs=["ground_truth_records"],
        ),
        _criterion(
            "ground_truth.verified",
            "Human-verified physical assertions",
            ReadinessStatus.PASS if len(verified) >= 5 else ReadinessStatus.FAIL,
            f"{len(verified)} verified; no AI prediction is auto-verified.",
            refs=["ground_truth_records"],
        ),
        _criterion(
            "ground_truth.independence",
            "At least two independent verifiers",
            ReadinessStatus.PASS if len(reviewers) >= 2 else ReadinessStatus.FAIL,
            f"{len(reviewers)} distinct verifier identity(ies).",
            refs=["ground_truth_events"],
        ),
        _criterion(
            "ground_truth.evidence",
            "Every verification records method and evidence",
            (
                ReadinessStatus.PASS
                if verified and len(complete) == len(verified)
                else ReadinessStatus.FAIL
            ),
            f"{len(complete)}/{len(verified)} verified record(s) complete.",
            refs=["ground_truth_records"],
        ),
    ]
    return _category(
        "ground_truth_maturity",
        "Ground-truth maturity",
        status,
        summary,
        criteria,
        owner="Review lead",
    )


def _correlation(session: Session) -> dict:
    universes = session.scalars(select(CorrelationUniverse)).all()
    complete_universes = [item for item in universes if item.reference_complete]
    total = int(
        session.scalar(select(func.count()).select_from(CorrelationCandidate)) or 0
    )
    reviewed = int(
        session.scalar(
            select(func.count(func.distinct(CorrelationReview.candidate_id)))
        )
        or 0
    )
    reviewers = int(
        session.scalar(
            select(func.count(func.distinct(CorrelationReview.reviewer_id))).where(
                CorrelationReview.reviewer_id.is_not(None)
            )
        )
        or 0
    )
    multi = int(
        session.scalar(
            select(func.count())
            .select_from(
                select(CorrelationReview.candidate_id)
                .group_by(CorrelationReview.candidate_id)
                .having(func.count(CorrelationReview.id) >= 2)
                .subquery()
            )
        )
        or 0
    )
    complete = int(
        session.scalar(
            select(func.count())
            .select_from(CorrelationCandidate)
            .where(CorrelationCandidate.universe_reference_complete.is_(True))
        )
        or 0
    )
    coverage = (reviewed / total) if total else 0.0
    if total == 0:
        status = ReadinessStatus.BLOCKED
        summary = "No correlation candidates are registered."
    elif reviewed < total:
        status = ReadinessStatus.IN_PROGRESS
        summary = f"{reviewed}/{total} candidates reviewed."
    elif total >= 30 and reviewers >= 2 and multi >= 10 and complete:
        status = ReadinessStatus.PASS
        summary = (
            f"{reviewed}/{total} candidates reviewed by {reviewers} reviewers; "
            f"{multi} multiply-reviewed; reference universe attested."
        )
    else:
        status = ReadinessStatus.FAIL
        summary = (
            f"{reviewed}/{total} candidates reviewed by {reviewers} reviewers; "
            "requires >=30 candidates, >=2 reviewers, >=10 multiply-reviewed "
            "candidates and an attested reference universe."
        )
    criteria = [
        _criterion(
            "correlation.volume",
            "At least 30 generated candidates",
            ReadinessStatus.PASS if total >= 30 else ReadinessStatus.FAIL,
            f"{total} candidate(s).",
            refs=["correlation_candidates"],
        ),
        _criterion(
            "correlation.reviewed",
            "Every candidate reviewed",
            ReadinessStatus.PASS if total and coverage == 1.0 else ReadinessStatus.FAIL,
            f"{reviewed}/{total} candidates have at least one human label.",
            refs=["correlation_reviews"],
        ),
        _criterion(
            "correlation.agreement",
            "Independent multi-review available",
            ReadinessStatus.PASS if multi >= 10 else ReadinessStatus.FAIL,
            f"{multi} candidate(s) have two or more independent reviews.",
            refs=["correlation_reviews"],
        ),
        _criterion(
            "correlation.reference",
            "Reference universe explicitly attested",
            ReadinessStatus.PASS if complete else ReadinessStatus.FAIL,
            f"{complete} candidate(s) carry a complete-reference attestation. "
            "Recall is never computed without it.",
            refs=["correlation_candidates"],
        ),
        _criterion(
            "correlation.universe",
            "Immutable complete reference-universe attestation",
            (
                ReadinessStatus.PASS
                if complete_universes
                else ReadinessStatus.FAIL
            ),
            f"{len(universes)} universe(s); {len(complete_universes)} attested "
            "complete. Incomplete universes keep recall/F1 null.",
            refs=["correlation_universes"],
        ),
    ]
    return _category(
        "correlation_maturity",
        "Correlation maturity",
        status,
        summary,
        criteria,
        owner="Review lead",
    )


def _infrastructure(session: Session) -> dict:
    sources = session.scalars(select(InfrastructureSource)).all()
    verified = [
        item
        for item in sources
        if item.validation_status.value == "VERIFIED"
    ]
    asset_counts = {
        source_id: int(count)
        for source_id, count in session.execute(
            select(InfrastructureAsset.source_id, func.count(InfrastructureAsset.id))
            .where(InfrastructureAsset.is_active.is_(True))
            .group_by(InfrastructureAsset.source_id)
        ).all()
        if source_id is not None
    }
    latest_snapshots = {}
    for source in verified:
        latest_snapshots[source.id] = session.scalar(
            select(EvidenceSnapshot)
            .where(
                EvidenceSnapshot.infrastructure_source_id == source.id,
                EvidenceSnapshot.status == EvidenceSnapshotStatus.VALIDATED,
                EvidenceSnapshot.is_current.is_(True),
            )
            .order_by(EvidenceSnapshot.retrieved_at.desc())
            .limit(1)
        )
    criteria = []
    integrated_domains = set()
    for domain, label in INFRASTRUCTURE_DOMAINS:
        rows = [item for item in verified if item.category == domain]
        missing = [
            item.source_key
            for item in rows
            if not item.snapshot_sha256
            or not item.license_note
            or not item.crs
            or not item.geographic_coverage
        ]
        integrated = [
            item
            for item in rows
            if latest_snapshots.get(item.id) is not None
            and asset_counts.get(item.id, 0) > 0
        ]
        if integrated:
            integrated_domains.add(domain)
        status = (
            ReadinessStatus.PASS
            if integrated and not missing
            else (ReadinessStatus.FAIL if rows else ReadinessStatus.BLOCKED)
        )
        if integrated:
            evidence = (
                f"{len(integrated)} integrated source(s), "
                f"{sum(asset_counts.get(item.id, 0) for item in integrated)} active "
                "asset(s), validated current snapshot."
            )
        elif rows:
            evidence = (
                f"{len(rows)} verified metadata source(s), but no integrated "
                "validated snapshot with active assets."
            )
        else:
            evidence = f"No verified {label.lower()} source is registered."
        criteria.append(
            _criterion(
                f"infrastructure.{domain.lower()}",
                f"{label} source verified and integrated",
                status,
                evidence + (f"; incomplete: {', '.join(missing)}" if missing else ""),
                refs=["infrastructure_sources", "evidence_snapshots", "infrastructure_assets"],
            )
        )
    criteria.append(
        _criterion(
            "infrastructure.domain_completeness",
            "All seven infrastructure domains integrated",
            (
                ReadinessStatus.PASS
                if len(integrated_domains) == len(INFRASTRUCTURE_DOMAINS)
                else ReadinessStatus.FAIL
            ),
            f"{len(integrated_domains)}/{len(INFRASTRUCTURE_DOMAINS)} domains have "
            "a validated current snapshot and active assets.",
            refs=["infrastructure_sources", "infrastructure_assets"],
        )
    )
    if not verified:
        status = ReadinessStatus.BLOCKED
        summary = "No infrastructure source has passed metadata validation."
    elif len(integrated_domains) == len(INFRASTRUCTURE_DOMAINS):
        status = ReadinessStatus.PASS
        summary = "All seven infrastructure domains have integrated validated data."
    elif integrated_domains:
        status = ReadinessStatus.IN_PROGRESS
        summary = (
            f"{len(integrated_domains)} of {len(INFRASTRUCTURE_DOMAINS)} "
            "infrastructure domains have integrated validated data; metadata alone "
            "is not counted as integration."
        )
    else:
        status = ReadinessStatus.IN_PROGRESS
        summary = (
            f"{len({item.category for item in verified})} of "
            f"{len(INFRASTRUCTURE_DOMAINS)} domains have verified metadata, but "
            "none has an integrated validated snapshot."
        )
    return _category(
        "infrastructure_availability",
        "Infrastructure availability",
        status,
        summary,
        criteria,
        owner="Infrastructure data owner",
    )


def _auditability(session: Session) -> dict:
    from sqlalchemy import inspect as sa_inspect

    tables = set(sa_inspect(session.get_bind()).get_table_names())
    event_tables = [
        "pilot_transitions",
        "risk_review_events",
        "correlation_reviews",
        "infrastructure_source_events",
        "readiness_evidence_events",
        "evidence_snapshot_events",
        "ground_truth_events",
    ]
    present = [table for table in event_tables if table in tables]
    status = (
        ReadinessStatus.PASS
        if len(present) == len(event_tables)
        else ReadinessStatus.FAIL
    )
    criteria = [
        _criterion(
            "audit.event_tables",
            "Append-only event tables present",
            status,
            f"{len(present)}/{len(event_tables)} append-only event tables present.",
            refs=[
                "migration:0018_phase10_pilot_governance",
                "migration:0020_phase11_evidence",
            ],
        ),
        _criterion(
            "audit.no_mutation_routes",
            "No update or delete routes for evidence",
            ReadinessStatus.PASS,
            "Phase 10 exposes create/transition/review endpoints only; "
            "review and transition rows have no mutation API.",
            refs=["tests/test_phase10_reviews.py"],
        ),
    ]
    return _category(
        "auditability",
        "Auditability",
        status,
        "Append-only audit structures are present and exposed read-only."
        if status == ReadinessStatus.PASS
        else "Audit event structures are incomplete.",
        criteria,
        owner="Security lead",
    )


def _governance(session: Session) -> dict:
    pilots = session.scalars(select(Pilot)).all()
    active_or_approved = [
        item
        for item in pilots
        if item.status in {PilotStatus.APPROVED, PilotStatus.ACTIVE, PilotStatus.PAUSED}
    ]
    separations = [
        item
        for item in active_or_approved
        if item.approved_by
        and item.approved_by != item.created_by
        and item.approved_by != item.owner_id
    ]
    unsafe_active = [
        item
        for item in pilots
        if item.status == PilotStatus.ACTIVE
        and (
            item.approved_by is None
            or item.activation_readiness.get("overall") != ReadinessOverall.READY_FOR_CONTROLLED_PILOT.value
            if isinstance(item.activation_readiness, dict)
            else True
        )
    ]
    if not pilots:
        status = ReadinessStatus.BLOCKED
        summary = "No controlled pilot has been created."
    elif not active_or_approved:
        status = ReadinessStatus.IN_PROGRESS
        summary = f"{len(pilots)} pilot(s) exist, none is approved or active."
    elif separations and not unsafe_active:
        status = ReadinessStatus.PASS
        summary = (
            f"{len(separations)} pilot(s) have independent approval; "
            f"{len(unsafe_active)} active pilot(s) lack a readiness snapshot."
        ).replace("0 active pilot(s) lack", "no active pilot lacks")
    else:
        status = ReadinessStatus.FAIL
        summary = (
            "Pilot approval or activation separation is not satisfied."
            if not separations
            else f"{len(unsafe_active)} active pilot(s) lack a readiness snapshot."
        )
    criteria = [
        _criterion(
            "governance.approval_separation",
            "Approver is independent of creator and owner",
            ReadinessStatus.PASS if separations else ReadinessStatus.FAIL,
            f"{len(separations)} independently approved pilot(s).",
            refs=["pilot_transitions"],
        ),
        _criterion(
            "governance.activation_snapshot",
            "Active pilots carry a readiness snapshot",
            ReadinessStatus.PASS if not unsafe_active else ReadinessStatus.FAIL,
            f"{len(unsafe_active)} active pilot(s) without a READY snapshot.",
            refs=["pilots.activation_readiness"],
        ),
    ]
    return _category(
        "governance",
        "Governance",
        status,
        summary,
        criteria,
        owner="Governance lead",
    )


def _operational_constraints(session: Session) -> dict:
    pilots = session.scalars(select(Pilot)).all()
    safe = [
        item
        for item in pilots
        if item.mode in {PilotMode.SIMULATION, PilotMode.STAGING}
        and item.operational_restrictions
        and item.data_sources
        and item.evaluation_criteria
        and item.end_date > item.start_date
    ]
    real_mode = [item for item in pilots if item.mode.value not in {"SIMULATION", "STAGING"}]
    if not pilots:
        status = ReadinessStatus.BLOCKED
        summary = "No pilot plan exists to constrain."
    elif real_mode:
        status = ReadinessStatus.FAIL
        summary = "A pilot declares an unsupported operational mode."
    elif safe and len(safe) == len(pilots):
        status = ReadinessStatus.PASS
        summary = (
            f"All {len(pilots)} pilot(s) are simulation/staging-only with recorded "
            "restrictions, data sources and evaluation criteria."
        )
    else:
        status = ReadinessStatus.FAIL
        summary = "One or more pilots lack restrictions, data sources or criteria."
    criteria = [
        _criterion(
            "operations.mode",
            "Simulation or staging only",
            ReadinessStatus.PASS if pilots and not real_mode else (
                ReadinessStatus.FAIL if real_mode else ReadinessStatus.BLOCKED
            ),
            "No real operational mode exists in Phase 10." if not real_mode else "Unsupported mode.",
            refs=["pilots.mode"],
        ),
        _criterion(
            "operations.restrictions",
            "Restrictions, sources and criteria recorded",
            ReadinessStatus.PASS if safe and len(safe) == len(pilots) else ReadinessStatus.FAIL,
            f"{len(safe)}/{len(pilots)} pilots fully constrained.",
            refs=["pilots"],
        ),
    ]
    return _category(
        "operational_constraints",
        "Operational constraints",
        status,
        summary,
        criteria,
        owner="Operations lead",
    )


def _pilot_context(session: Session, pilot: Pilot) -> dict:
    reviewer_rows = session.execute(
        select(PilotReviewer, Profile)
        .join(Profile, Profile.id == PilotReviewer.profile_id)
        .where(PilotReviewer.pilot_id == pilot.id)
    ).all()
    reviewers = [
        {
            "profile_id": str(reviewer.profile_id),
            "full_name": profile.full_name,
            "role": reviewer.role.value,
        }
        for reviewer, profile in reviewer_rows
    ]
    checks = [
        {
            "key": "pilot.reviewer",
            "label": "At least one reviewer assigned",
            "status": "PASS" if reviewer_rows else "FAIL",
            "evidence": f"{len(reviewer_rows)} reviewer assignment(s).",
        },
        {
            "key": "pilot.approval_separation",
            "label": "Approver independent of creator and owner",
            "status": (
                "PASS"
                if pilot.approved_by
                and pilot.approved_by != pilot.created_by
                and pilot.approved_by != pilot.owner_id
                else "FAIL"
            ),
            "evidence": (
                f"approved_by={pilot.approved_by}; created_by={pilot.created_by}; "
                f"owner={pilot.owner_id}"
            ),
        },
        {
            "key": "pilot.window",
            "label": "Evaluation window is open",
            "status": "PASS" if _now() <= _aware(pilot.end_date) else "FAIL",
            "evidence": f"Ends {pilot.end_date.isoformat()}.",
        },
        {
            "key": "pilot.controls",
            "label": "Restrictions, data sources and criteria recorded",
            "status": (
                "PASS"
                if pilot.operational_restrictions
                and pilot.data_sources
                and pilot.evaluation_criteria
                and pilot.evaluation_protocol
                else "FAIL"
            ),
            "evidence": (
                f"{len(pilot.operational_restrictions or [])} restriction(s), "
                f"{len(pilot.data_sources or [])} source(s), "
                f"{len(pilot.evaluation_criteria or [])} criteria."
            ),
        },
        {
            "key": "pilot.status",
            "label": "Pilot is approved or active",
            "status": (
                "PASS"
                if pilot.status in {PilotStatus.APPROVED, PilotStatus.ACTIVE, PilotStatus.PAUSED}
                else "FAIL"
            ),
            "evidence": f"Current status {pilot.status.value}.",
        },
    ]
    return {
        "id": str(pilot.id),
        "pilot_key": pilot.pilot_key,
        "name": pilot.name,
        "status": pilot.status.value,
        "mode": pilot.mode.value,
        "reviewers": reviewers,
        "checks": checks,
        "all_checks_pass": all(item["status"] == "PASS" for item in checks),
    }


def assess_readiness(session: Session, pilot: Pilot | None = None) -> dict:
    categories = [
        _data_quality(session),
        _freshness(session),
        _geographic(session),
        _performance(session),
        _robustness(session),
        _human_review(session),
        _ground_truth(session),
        _correlation(session),
        _infrastructure(session),
        _auditability(session),
        _manual_category(session, "security", "Security", "Security lead"),
        _governance(session),
        _operational_constraints(session),
        _manual_category(
            session, "reviewer_training", "Reviewer training", "Review lead"
        ),
        _manual_category(
            session, "incident_escalation", "Incident escalation", "Operations lead"
        ),
        _manual_category(
            session, "deployment_rollback", "Deployment and rollback", "Platform lead"
        ),
    ]
    passed_statuses = {ReadinessStatus.PASS, ReadinessStatus.NOT_APPLICABLE}
    mandatory_unmet = [
        item
        for item in categories
        if item["mandatory"]
        and ReadinessStatus(item["status"]) not in passed_statuses
    ]
    advisory_unmet = [
        item
        for item in categories
        if not item["mandatory"]
        and ReadinessStatus(item["status"]) not in passed_statuses
    ]
    if mandatory_unmet:
        overall = ReadinessOverall.NOT_READY
    elif advisory_unmet:
        overall = ReadinessOverall.CONDITIONALLY_READY
    else:
        overall = ReadinessOverall.READY_FOR_CONTROLLED_PILOT

    pilot_context = _pilot_context(session, pilot) if pilot is not None else None
    blockers = [
        f"{item['label']} ({item['status']}): {item['summary']}"
        for item in mandatory_unmet
    ] + [
        f"{item['label']} ({item['status']}): {item['summary']}"
        for item in advisory_unmet
    ]
    if pilot_context:
        blockers.extend(
            f"Pilot check failed: {item['label']} ({item['evidence']})"
            for item in pilot_context["checks"]
            if item["status"] != "PASS"
        )
    ready_for_activation = (
        overall == ReadinessOverall.READY_FOR_CONTROLLED_PILOT
        and (pilot_context is None or pilot_context["all_checks_pass"])
        and not blockers
    )
    counts = {
        status.value: sum(1 for item in categories if item["status"] == status.value)
        for status in ReadinessStatus
    }
    counts["mandatory_total"] = sum(1 for item in categories if item["mandatory"])
    counts["advisory_total"] = sum(1 for item in categories if not item["mandatory"])
    return {
        "protocol": PROTOCOL,
        "generated_at": _iso(_now()),
        "overall": overall.value,
        "ready_for_activation": ready_for_activation,
        "activation_blockers": blockers,
        "categories": categories,
        "counts": counts,
        "mandatory_unmet": [item["key"] for item in mandatory_unmet],
        "advisory_unmet": [item["key"] for item in advisory_unmet],
        "pilot_context": pilot_context,
        "disclaimer": (
            "This scorecard is derived from persisted evidence. It never "
            "authorizes a pilot, activates a model, dispatches resources, or "
            "declares a hazard. READY_FOR_CONTROLLED_PILOT still requires a "
            "separate administrator activation action."
        ),
        "evidence_policy": (
            "No category is marked PASS without recorded evidence. Manual "
            "attestations are limited to security, reviewer training, incident "
            "escalation and deployment/rollback."
        ),
    }
