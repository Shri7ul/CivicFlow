"""Staff validation workspace APIs backed by persisted experiments."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_admin, require_worker
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.db.session import get_db_session
from app.models import ValidationDataset, ValidationExperiment
from app.schemas.validation import (
    DatasetCreate,
    DatasetResponse,
    ExperimentDetail,
    ExperimentSummary,
    ValidationOverview,
)
from app.validation.service import (
    ValidationError,
    build_report,
    register_dataset,
    run_correlation_experiment,
    run_decision_experiment,
    run_risk_experiment,
)

router = APIRouter()


def _dataset_or_404(session: Session, dataset_id: uuid.UUID) -> ValidationDataset:
    dataset = session.get(ValidationDataset, dataset_id)
    if dataset is None:
        raise AppError(
            "Validation dataset not found.",
            status_code=404,
            code="validation_dataset_not_found",
        )
    return dataset


def _experiment_or_404(
    session: Session, experiment_id: uuid.UUID
) -> ValidationExperiment:
    experiment = session.get(ValidationExperiment, experiment_id)
    if experiment is None:
        raise AppError(
            "Validation experiment not found.",
            status_code=404,
            code="validation_experiment_not_found",
        )
    return experiment


def _serialize_dataset(dataset: ValidationDataset) -> dict:
    return {
        "id": dataset.id,
        "dataset_key": dataset.dataset_key,
        "name": dataset.name,
        "description": dataset.description,
        "source_url": dataset.source_url,
        "license_note": dataset.license_note,
        "region": dataset.region,
        "period_start": dataset.period_start,
        "period_end": dataset.period_end,
        "source_id": dataset.source_id,
        "ingestion_run_id": dataset.ingestion_run_id,
        "snapshot_sha256": dataset.snapshot_sha256,
        "snapshot_path": dataset.snapshot_path,
        "record_count": dataset.record_count,
        "schema_version": dataset.schema_version,
        "status": dataset.status.value,
        "metadata": dataset.dataset_metadata or {},
        "created_at": dataset.created_at,
    }


def _serialize_experiment(experiment: ValidationExperiment, *, detail: bool = False) -> dict:
    payload = {
        "id": experiment.id,
        "experiment_key": experiment.experiment_key,
        "name": experiment.name,
        "experiment_type": experiment.experiment_type.value,
        "evidence_kind": experiment.evidence_kind.value,
        "status": experiment.status.value,
        "dataset_id": experiment.dataset_id,
        "method": experiment.method,
        "split_method": experiment.split_method,
        "record_count": experiment.record_count,
        "model_name": experiment.model_name,
        "model_version": experiment.model_version,
        "config_hash": experiment.config_hash,
        "findings": experiment.findings or [],
        "limitations": experiment.limitations or [],
        "started_at": experiment.started_at,
        "completed_at": experiment.completed_at,
    }
    if detail:
        payload.update(
            {
                "dataset_version": experiment.dataset_version,
                "dataset_snapshot_sha256": experiment.dataset_snapshot_sha256,
                "region": experiment.region,
                "period_start": experiment.period_start,
                "period_end": experiment.period_end,
                "metrics": experiment.metrics or {},
                "baselines": experiment.baselines or {},
                "reproducibility": experiment.reproducibility or {},
                "error_summary": experiment.error_summary,
            }
        )
    return payload


@router.get("/overview", response_model=ValidationOverview)
def overview(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    datasets = session.scalars(
        select(ValidationDataset)
        .order_by(ValidationDataset.created_at.desc())
        .limit(100)
    ).all()
    experiments = session.scalars(
        select(ValidationExperiment)
        .order_by(ValidationExperiment.created_at.desc())
        .limit(100)
    ).all()
    return {
        "datasets": [_serialize_dataset(item) for item in datasets],
        "experiments": [
            _serialize_experiment(item) for item in experiments
        ],
        "evidence_kinds": [
            "EMPIRICAL_OBSERVATIONAL",
            "SYNTHETIC_FIXTURE",
            "SIMULATED_PLANNING",
        ],
        "limitations": [
            "Observational activity is not verified hazard impact.",
            "Synthetic and planning experiments are explicitly labelled.",
            "No validation experiment dispatches or reserves resources.",
        ],
    }


@router.get("/datasets", response_model=list[DatasetResponse])
def list_datasets(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    del user
    return [
        _serialize_dataset(item)
        for item in session.scalars(
            select(ValidationDataset).order_by(ValidationDataset.created_at.desc())
        ).all()
    ]


@router.post("/datasets", response_model=DatasetResponse, status_code=201)
def create_dataset(
    payload: DatasetCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        dataset = register_dataset(
            session,
            dataset_key=payload.dataset_key,
            name=payload.name,
            description=payload.description,
            source_url=payload.source_url,
            license_note=payload.license_note,
            region=payload.region,
            period_start=payload.period_start,
            period_end=payload.period_end,
            source_id=payload.source_id,
            ingestion_run_id=payload.ingestion_run_id,
            snapshot_sha256=payload.snapshot_sha256,
            snapshot_path=payload.snapshot_path,
            record_count=payload.record_count,
            schema_version=payload.schema_version,
            dataset_metadata=payload.metadata,
            actor_id=user.profile.id,
        )
    except ValidationError as error:
        raise AppError(str(error), status_code=409, code=error.code) from error
    return _serialize_dataset(dataset)


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    return _serialize_dataset(_dataset_or_404(session, dataset_id))


@router.get("/experiments", response_model=list[ExperimentSummary])
def list_experiments(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict]:
    del user
    return [
        _serialize_experiment(item)
        for item in session.scalars(
            select(ValidationExperiment)
            .order_by(ValidationExperiment.created_at.desc())
            .limit(limit)
        ).all()
    ]


@router.get("/experiments/{experiment_id}", response_model=ExperimentDetail)
def get_experiment(
    experiment_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    return _serialize_experiment(
        _experiment_or_404(session, experiment_id), detail=True
    )


@router.get("/experiments/{experiment_id}/report")
def get_report(
    experiment_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    experiment = _experiment_or_404(session, experiment_id)
    dataset = (
        session.get(ValidationDataset, experiment.dataset_id)
        if experiment.dataset_id
        else None
    )
    return build_report(experiment, dataset)


@router.post("/experiments/risk/{dataset_id}", response_model=ExperimentDetail)
def run_risk(
    dataset_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    dataset = _dataset_or_404(session, dataset_id)
    try:
        experiment = run_risk_experiment(
            session,
            dataset,
            settings=settings,
            actor_id=user.profile.id,
        )
    except ValidationError as error:
        raise AppError(str(error), status_code=422, code=error.code) from error
    return _serialize_experiment(experiment, detail=True)


@router.post("/experiments/correlation", response_model=ExperimentDetail)
def run_correlation(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    experiment = run_correlation_experiment(
        session, settings=settings, actor_id=user.profile.id
    )
    return _serialize_experiment(experiment, detail=True)


@router.post("/experiments/decision", response_model=ExperimentDetail)
def run_decision(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    experiment = run_decision_experiment(
        session, settings=settings, actor_id=user.profile.id
    )
    return _serialize_experiment(experiment, detail=True)
