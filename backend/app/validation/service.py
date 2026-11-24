"""Dataset registry, experiment persistence, and report assembly."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.governance.service import resolve_decision_config, resolve_risk_config
from app.models import (
    DataSource,
    IngestedRecord,
    IngestionRun,
    ValidationDataset,
    ValidationDatasetStatus,
    ValidationEvidenceKind,
    ValidationExperiment,
    ValidationExperimentType,
    ValidationStatus,
)
from app.validation.correlation import run_correlation_validation
from app.validation.dataset import NYC311_BBOX, load_snapshot, normalize_nyc311_record
from app.validation.decision import run_decision_validation
from app.validation.risk import run_risk_backtest

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "validation"
APP_VERSION = "0.9.0"


class ValidationError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _safe_snapshot_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = DATA_ROOT / path
    resolved = path.resolve()
    root = DATA_ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValidationError(
            "Dataset snapshot path must stay inside backend/data/validation.",
            code="unsafe_snapshot_path",
        )
    return resolved


def register_dataset(
    session: Session,
    *,
    dataset_key: str,
    name: str,
    description: str | None,
    source_url: str,
    license_note: str,
    region: str,
    period_start: datetime | None,
    period_end: datetime | None,
    source_id: uuid.UUID | None,
    ingestion_run_id: uuid.UUID | None,
    snapshot_sha256: str,
    snapshot_path: str | None,
    record_count: int,
    schema_version: str,
    dataset_metadata: dict,
    actor_id: uuid.UUID | None,
) -> ValidationDataset:
    existing = session.scalar(
        select(ValidationDataset).where(
            ValidationDataset.dataset_key == dataset_key
        )
    )
    if existing is not None:
        if existing.snapshot_sha256 != snapshot_sha256:
            raise ValidationError(
                "Dataset key already exists with a different snapshot hash.",
                code="dataset_snapshot_conflict",
            )
        return existing
    if source_id is not None and session.get(DataSource, source_id) is None:
        raise ValidationError("Data source not found.", code="source_not_found")
    if ingestion_run_id is not None:
        run = session.get(IngestionRun, ingestion_run_id)
        if run is None or (source_id is not None and run.source_id != source_id):
            raise ValidationError(
                "Ingestion run does not belong to the dataset source.",
                code="ingestion_run_mismatch",
            )
    dataset = ValidationDataset(
        dataset_key=dataset_key.strip(),
        name=name.strip(),
        description=description,
        source_url=source_url.strip(),
        license_note=license_note.strip(),
        region=region.strip(),
        period_start=period_start,
        period_end=period_end,
        source_id=source_id,
        ingestion_run_id=ingestion_run_id,
        snapshot_sha256=snapshot_sha256,
        snapshot_path=snapshot_path,
        record_count=record_count,
        schema_version=schema_version,
        status=(
            ValidationDatasetStatus.VALIDATED
            if record_count >= 100
            else ValidationDatasetStatus.INSUFFICIENT
        ),
        dataset_metadata=dataset_metadata,
        created_by=actor_id,
    )
    session.add(dataset)
    session.commit()
    session.refresh(dataset)
    return dataset


def dataset_records(session: Session, dataset: ValidationDataset) -> tuple[list[dict], dict]:
    path = _safe_snapshot_path(dataset.snapshot_path)
    if path is not None and path.exists():
        payload = load_snapshot(path)
        if payload["snapshot_sha256"] != dataset.snapshot_sha256:
            raise ValidationError(
                "Snapshot file does not match the registered dataset hash.",
                code="dataset_snapshot_mismatch",
            )
        records = payload["records"]
        if len(records) != dataset.record_count:
            raise ValidationError(
                "Snapshot file record count does not match the registry.",
                code="dataset_count_mismatch",
            )
        metadata = dict(payload.get("metadata", {}))
        if payload.get("bbox"):
            metadata["bbox"] = payload["bbox"]
        return records, metadata
    if dataset.source_id is None:
        raise ValidationError(
            "Dataset has neither a usable snapshot nor an ingestion source.",
            code="dataset_records_unavailable",
        )
    rows = session.scalars(
        select(IngestedRecord)
        .where(IngestedRecord.source_id == dataset.source_id)
        .order_by(IngestedRecord.external_id)
    ).all()
    records: list[dict] = []
    rejected = 0
    for row in rows:
        payload = dict(row.payload or {})
        payload["external_id"] = row.external_id
        payload["observed_at"] = (
            row.observed_at.isoformat()
            if row.observed_at is not None
            else payload.get("observed_at")
        )
        try:
            if {"category", "severity", "latitude", "longitude"}.issubset(payload):
                records.append(payload)
            else:
                records.append(normalize_nyc311_record(payload))
        except (KeyError, TypeError, ValueError):
            rejected += 1
    records.sort(key=lambda item: (item["observed_at"], item["external_id"]))
    metadata = {
        "loaded_from": "ingested_records",
        "rejected_count": rejected,
        "record_count": len(records),
    }
    return records, metadata


def _new_experiment(
    session: Session,
    *,
    experiment_type: ValidationExperimentType,
    evidence_kind: ValidationEvidenceKind,
    name: str,
    method: str,
    dataset: ValidationDataset | None,
    actor_id: uuid.UUID | None,
    model_name: str | None = None,
    model_version: str | None = None,
    config_hash: str | None = None,
    split_method: str | None = None,
    region: str | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    record_count: int = 0,
    protocol_key: str | None = None,
    variant_key: str | None = None,
) -> ValidationExperiment:
    experiment = ValidationExperiment(
        experiment_key=f"{experiment_type.value.lower()}-{uuid.uuid4()}",
        protocol_key=protocol_key,
        variant_key=variant_key,
        name=name,
        description=None,
        dataset_id=dataset.id if dataset else None,
        dataset_version=dataset.dataset_key if dataset else None,
        dataset_snapshot_sha256=dataset.snapshot_sha256 if dataset else None,
        experiment_type=experiment_type,
        evidence_kind=evidence_kind,
        status=ValidationStatus.RUNNING,
        method=method,
        split_method=split_method,
        region=region,
        period_start=period_start,
        period_end=period_end,
        record_count=record_count,
        model_name=model_name,
        model_version=model_version,
        config_hash=config_hash,
        created_by=actor_id,
    )
    session.add(experiment)
    session.commit()
    session.refresh(experiment)
    return experiment


def _complete_experiment(
    session: Session,
    experiment: ValidationExperiment,
    *,
    status: ValidationStatus,
    metrics: dict,
    baselines: dict,
    findings: list[str],
    limitations: list[str],
    reproducibility: dict,
) -> ValidationExperiment:
    experiment.status = status
    experiment.metrics = metrics
    experiment.baselines = baselines
    experiment.findings = findings
    experiment.limitations = limitations
    experiment.reproducibility = reproducibility
    experiment.completed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(experiment)
    return experiment


def _fail_experiment(
    session: Session, experiment: ValidationExperiment, error: Exception
) -> None:
    session.rollback()
    stored = session.get(ValidationExperiment, experiment.id)
    if stored is None:
        return
    stored.status = ValidationStatus.FAILED
    stored.error_summary = f"{type(error).__name__}: {error}"[:2000]
    stored.completed_at = datetime.now(timezone.utc)
    session.commit()


def run_risk_experiment(
    session: Session,
    dataset: ValidationDataset,
    *,
    settings: Settings,
    actor_id: uuid.UUID | None,
) -> ValidationExperiment:
    config = resolve_risk_config(session, settings)
    records, metadata = dataset_records(session, dataset)
    bbox_value = (
        metadata.get("bbox")
        or (metadata.get("query") or {}).get("bbox")
        or dataset.dataset_metadata.get("bbox")
        or list(NYC311_BBOX)
    )
    try:
        bbox = tuple(float(value) for value in bbox_value)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "Dataset bbox metadata is invalid.", code="dataset_bbox_invalid"
        ) from error
    if len(bbox) != 4:
        raise ValidationError(
            "Dataset bbox metadata must contain four coordinates.",
            code="dataset_bbox_invalid",
        )
    if len(records) > settings.validation_max_records:
        raise ValidationError(
            "Dataset exceeds the configured validation record cap.",
            code="validation_dataset_too_large",
        )
    experiment = _new_experiment(
        session,
        experiment_type=ValidationExperimentType.RISK_BACKTEST,
        evidence_kind=ValidationEvidenceKind.EMPIRICAL_OBSERVATIONAL,
        name=f"Temporal risk backtest · {dataset.dataset_key}",
        method="rolling-origin temporal holdout against next-period incident activity",
        dataset=dataset,
        actor_id=actor_id,
        model_name="risk",
        model_version=config.model_version,
        config_hash=config.config_hash,
        split_method="rolling_origin_temporal_holdout",
        region=dataset.region,
        period_start=dataset.period_start,
        period_end=dataset.period_end,
        record_count=len(records),
    )
    try:
        result = run_risk_backtest(
            records,
            settings=settings,
            config=config,
            dataset_key=dataset.dataset_key,
            bbox=bbox,
        )
        methods = result.get("methods", {})
        risk = methods.get("civicflow_risk", {})
        baseline = methods.get("baseline_recent", {})
        baseline_methods = {
            key: value
            for key, value in methods.items()
            if key.startswith("baseline_") and value.get("pr_auc") is not None
        }
        best_name, best = (
            max(baseline_methods.items(), key=lambda item: item[1]["pr_auc"])
            if baseline_methods
            else ("none", {})
        )
        risk_pr = risk.get("pr_auc")
        best_pr = best.get("pr_auc")
        if risk_pr is None or best_pr is None:
            comparison = "Baseline comparison was inconclusive."
        elif risk_pr > best_pr:
            comparison = (
                f"CivicFlow PR-AUC exceeded the strongest baseline "
                f"({best_name}) by {round(risk_pr - best_pr, 6)}."
            )
        elif risk_pr == best_pr:
            comparison = f"CivicFlow PR-AUC tied the strongest baseline ({best_name})."
        else:
            comparison = (
                f"CivicFlow PR-AUC did not exceed the strongest baseline "
                f"({best_name}); it was lower by {round(best_pr - risk_pr, 6)}. "
                "This is reported as an unfavorable empirical result, not hidden."
            )
        findings = [
            "Origins use only data available before each origin; the label is "
            "any incident in the following fixed window.",
            f"CivicFlow mean PR-AUC: {risk.get('pr_auc')}; mean ROC-AUC: "
            f"{risk.get('roc_auc')}; mean precision@k: "
            f"{risk.get('precision_at_k')}; mean recall@k: "
            f"{risk.get('recall_at_k')}.",
            f"Recent-count baseline mean PR-AUC: {baseline.get('pr_auc')}; "
            f"mean ROC-AUC: {baseline.get('roc_auc')}; mean precision@k: "
            f"{baseline.get('precision_at_k')}; mean recall@k: "
            f"{baseline.get('recall_at_k')}.",
            comparison,
            "This is observational next-period activity validation, not a "
            "causal or operational impact claim.",
        ]
        limitations = [
            "The target is service-request activity in the next window, not "
            "verified hazard impact or municipal ground truth.",
            "Category and severity mappings are explicit heuristic adaptations "
            "of public complaint types.",
            "No infrastructure assets or dependencies are present in the "
            "isolated validation database, so those risk factors are excluded.",
            "Results are specific to this region, period, complaint-type "
            "selection, and configuration.",
        ]
        reproducibility = {
            "dataset_key": dataset.dataset_key,
            "dataset_snapshot_sha256": dataset.snapshot_sha256,
            "dataset_metadata": metadata,
            "dataset_bbox": list(bbox),
            "risk_config": config.as_dict(),
            "risk_config_hash": config.config_hash,
            "settings": {
                "validation_history_hours": settings.validation_history_hours,
                "validation_target_hours": settings.validation_target_hours,
                "validation_max_folds": settings.validation_max_folds,
                "validation_top_k": settings.validation_top_k,
                "validation_resolution": settings.validation_resolution,
            },
            "app_version": APP_VERSION,
            "method": "RiskEngine on isolated snapshot with as_of clocks",
        }
        status = (
            ValidationStatus.COMPLETED
            if result.get("status") == "COMPLETED"
            else ValidationStatus.INSUFFICIENT_DATA
        )
        if status != ValidationStatus.COMPLETED:
            limitations.append(
                "Insufficient folds or class variation for metrics."
            )
        return _complete_experiment(
            session,
            experiment,
            status=status,
            metrics=result,
            baselines={
                key: value
                for key, value in methods.items()
                if key != "civicflow_risk"
            },
            findings=findings,
            limitations=limitations,
            reproducibility=reproducibility,
        )
    except Exception as error:
        _fail_experiment(session, experiment, error)
        raise


def run_correlation_experiment(
    session: Session,
    *,
    settings: Settings,
    actor_id: uuid.UUID | None,
) -> ValidationExperiment:
    experiment = _new_experiment(
        session,
        experiment_type=ValidationExperimentType.CORRELATION_SYNTHETIC,
        evidence_kind=ValidationEvidenceKind.SYNTHETIC_FIXTURE,
        name="Synthetic duplicate-scoring validation",
        method="hand-labelled synthetic pair fixtures against Phase 4 scorer",
        dataset=None,
        actor_id=actor_id,
        model_name="intelligence",
        model_version="phase4-correlation",
        split_method="fixed_synthetic_cases",
        record_count=8,
    )
    try:
        result = run_correlation_validation(settings)
        limitations = [
            "These are hand-constructed fixtures, not municipal duplicate labels.",
            "No auto-merge or incident mutation occurs.",
            "Precision/recall are synthetic validation only and must not be "
            "presented as real-world field performance.",
        ]
        findings = [
            f"Synthetic precision: {result['precision']}; recall: "
            f"{result['recall']}; F1: {result['f1']}.",
            "The scorer still returns suggestions for human review only.",
        ]
        return _complete_experiment(
            session,
            experiment,
            status=(
                ValidationStatus.COMPLETED
                if result["status"] == "COMPLETED"
                else ValidationStatus.INSUFFICIENT_DATA
            ),
            metrics=result,
            baselines={},
            findings=findings,
            limitations=limitations,
            reproducibility={
                "fixture": "app/validation/correlation.py",
                "case_count": result["case_count"],
                "app_version": APP_VERSION,
            },
        )
    except Exception as error:
        _fail_experiment(session, experiment, error)
        raise


def run_decision_experiment(
    session: Session,
    *,
    settings: Settings,
    actor_id: uuid.UUID | None,
) -> ValidationExperiment:
    config = resolve_decision_config(session, settings)
    experiment = _new_experiment(
        session,
        experiment_type=ValidationExperimentType.DECISION_SIMULATION,
        evidence_kind=ValidationEvidenceKind.SIMULATED_PLANNING,
        name="Synthetic bounded planning comparison",
        method="four strategies over identical synthetic actions/resources",
        dataset=None,
        actor_id=actor_id,
        model_name="decision",
        model_version=config.model_version,
        config_hash=config.config_hash,
        split_method="identical_inputs_deterministic_repeat",
        record_count=7,
    )
    try:
        result = run_decision_validation(settings, config=config)
        limitations = [
            "Expected risk reduction and resource availability are synthetic "
            "planning assumptions, not observed outcomes.",
            "No dispatch, reservation, or incident mutation occurs.",
            "Results only compare scheduler behavior under this bounded fixture.",
        ]
        findings = [
            f"Winner under the configured objective: {result['winner']}.",
            f"Deterministic schedule repeat: {result['deterministic_schedule']}.",
            "Planned reduction is a simulated objective value, not realized impact.",
        ]
        return _complete_experiment(
            session,
            experiment,
            status=ValidationStatus.COMPLETED,
            metrics=result,
            baselines={},
            findings=findings,
            limitations=limitations,
            reproducibility={
                "fixture": "app/validation/decision.py",
                "decision_config": config.as_dict(),
                "decision_config_hash": config.config_hash,
                "app_version": APP_VERSION,
            },
        )
    except Exception as error:
        _fail_experiment(session, experiment, error)
        raise


def build_report(
    experiment: ValidationExperiment,
    dataset: ValidationDataset | None,
) -> dict:
    return {
        "experiment_id": str(experiment.id),
        "experiment_key": experiment.experiment_key,
        "name": experiment.name,
        "status": experiment.status.value,
        "experiment_type": experiment.experiment_type.value,
        "evidence_kind": experiment.evidence_kind.value,
        "executive_summary": (
            (
                f"{experiment.findings[1]} {experiment.findings[3]}"
                if experiment.experiment_type.value == "RISK_BACKTEST"
                and len(experiment.findings) >= 4
                else experiment.findings[0]
            )
            if experiment.findings
            else "No findings were recorded."
        ),
        "dataset": (
            {
                "key": dataset.dataset_key,
                "name": dataset.name,
                "source_url": dataset.source_url,
                "license_note": dataset.license_note,
                "region": dataset.region,
                "period_start": dataset.period_start.isoformat()
                if dataset.period_start
                else None,
                "period_end": dataset.period_end.isoformat()
                if dataset.period_end
                else None,
                "snapshot_sha256": dataset.snapshot_sha256,
                "record_count": dataset.record_count,
                "schema_version": dataset.schema_version,
                "metadata": dataset.dataset_metadata,
            }
            if dataset
            else None
        ),
        "methodology": {
            "method": experiment.method,
            "split_method": experiment.split_method,
            "model_name": experiment.model_name,
            "model_version": experiment.model_version,
            "config_hash": experiment.config_hash,
        },
        "dataset_snapshot_sha256": experiment.dataset_snapshot_sha256,
        "metrics": experiment.metrics,
        "baselines": experiment.baselines,
        "findings": experiment.findings,
        "limitations": experiment.limitations,
        "reproducibility": experiment.reproducibility,
        "started_at": experiment.started_at.isoformat(),
        "completed_at": experiment.completed_at.isoformat()
        if experiment.completed_at
        else None,
    }
