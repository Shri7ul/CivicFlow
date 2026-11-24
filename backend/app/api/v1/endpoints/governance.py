"""Model registry, activation, and evaluation APIs."""

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
from app.evaluation.engine import EvaluationError, EvaluationSample, evaluate_samples
from app.governance.service import (
    GovernanceError,
    activate_model,
    active_model,
    register_model,
    runtime_config,
)
from app.models import (
    EvaluationMethod,
    EvaluationStatus,
    ModelEvaluation,
    ModelVersion,
    ModelVersionEvent,
)
from app.schemas.operations import (
    EvaluationCreate,
    EvaluationResponse,
    ModelActivateRequest,
    ModelRegisterRequest,
    ModelVersionResponse,
)

router = APIRouter()


def _model_or_404(session: Session, model_id: uuid.UUID) -> ModelVersion:
    model = session.get(ModelVersion, model_id)
    if model is None:
        raise AppError("Model version not found.", status_code=404, code="model_not_found")
    return model


def _serialize_model(model: ModelVersion) -> dict:
    return {
        "id": model.id,
        "model_name": model.model_name,
        "version": model.version,
        "config_hash": model.config_hash,
        "description": model.description,
        "is_active": model.is_active,
        "activated_at": model.activated_at,
        "created_by": model.created_by,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _serialize_evaluation(item: ModelEvaluation) -> dict:
    return {
        "id": item.id,
        "model_version_id": item.model_version_id,
        "method": item.method,
        "status": item.status,
        "dataset_label": item.dataset_label,
        "is_synthetic": item.is_synthetic,
        "ground_truth_available": item.ground_truth_available,
        "split_strategy": item.split_strategy,
        "sample_count": item.sample_count,
        "metrics": item.metrics or {},
        "slices": item.slices or {},
        "warnings": item.warnings or [],
        "created_by": item.created_by,
        "created_at": item.created_at,
    }


@router.get("/models", response_model=list[ModelVersionResponse])
def list_models(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    model_name: str | None = Query(default=None, pattern="^(risk|decision)$"),
) -> list[dict]:
    del user
    statement = select(ModelVersion).order_by(ModelVersion.created_at.desc()).limit(200)
    if model_name is not None:
        statement = statement.where(ModelVersion.model_name == model_name)
    return [_serialize_model(model) for model in session.scalars(statement).all()]


@router.get("/models/runtime")
def runtime_models(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    payload = {}
    for model_name in ("risk", "decision"):
        config, config_hash = runtime_config(model_name, settings)
        active = active_model(session, model_name)
        payload[model_name] = {
            "runtime_config_hash": config_hash,
            "active": _serialize_model(active) if active else None,
            "matches_runtime": active is not None and active.config_hash == config_hash,
        }
    return payload


@router.get("/models/active/{model_name}", response_model=ModelVersionResponse | None)
def get_active_model(
    model_name: str,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict | None:
    del user
    if model_name not in {"risk", "decision"}:
        raise AppError("Unsupported model name.", status_code=422, code="invalid_model_name")
    model = active_model(session, model_name)
    return _serialize_model(model) if model else None


@router.post("/models", response_model=ModelVersionResponse, status_code=201)
def register(
    payload: ModelRegisterRequest,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        model = register_model(
            session,
            model_name=payload.model_name,
            version=payload.version,
            description=payload.description,
            settings=settings,
            actor_id=user.profile.id,
        )
    except GovernanceError as error:
        raise AppError(str(error), status_code=409, code=error.code) from error
    return _serialize_model(model)


@router.post("/models/{model_id}/activate", response_model=ModelVersionResponse)
def activate(
    model_id: uuid.UUID,
    payload: ModelActivateRequest,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    model = _model_or_404(session, model_id)
    try:
        model = activate_model(
            session,
            model,
            actor_id=user.profile.id,
            reason=payload.reason,
        )
    except GovernanceError as error:
        status = 404 if error.code == "model_not_found" else 409
        raise AppError(str(error), status_code=status, code=error.code) from error
    return _serialize_model(model)


def _config_diff(left, right, prefix: str = "") -> list[str]:
    changes: list[str] = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                changes.append(path)
            else:
                changes.extend(_config_diff(left[key], right[key], path))
    elif left != right:
        changes.append(prefix)
    return changes


@router.get("/models/{left_id}/compare/{right_id}")
def compare_models(
    left_id: uuid.UUID,
    right_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    left = _model_or_404(session, left_id)
    right = _model_or_404(session, right_id)
    if left.model_name != right.model_name:
        raise AppError(
            "Only models of the same type can be compared.",
            status_code=422,
            code="model_type_mismatch",
        )
    return {
        "model_name": left.model_name,
        "left": _serialize_model(left),
        "right": _serialize_model(right),
        "same_config": left.config_hash == right.config_hash,
        "changed_config_paths": _config_diff(left.config, right.config),
        "left_latest_evaluation": _serialize_evaluation(
            session.scalars(
                select(ModelEvaluation)
                .where(ModelEvaluation.model_version_id == left.id)
                .order_by(ModelEvaluation.created_at.desc())
                .limit(1)
            ).first()
        )
        if session.scalar(
            select(ModelEvaluation.id)
            .where(ModelEvaluation.model_version_id == left.id)
            .limit(1)
        )
        else None,
        "right_latest_evaluation": _serialize_evaluation(
            session.scalars(
                select(ModelEvaluation)
                .where(ModelEvaluation.model_version_id == right.id)
                .order_by(ModelEvaluation.created_at.desc())
                .limit(1)
            ).first()
        )
        if session.scalar(
            select(ModelEvaluation.id)
            .where(ModelEvaluation.model_version_id == right.id)
            .limit(1)
        )
        else None,
    }


@router.get("/models/{model_id}/events")
def model_events(
    model_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    del user
    _model_or_404(session, model_id)
    events = session.scalars(
        select(ModelVersionEvent)
        .where(ModelVersionEvent.model_version_id == model_id)
        .order_by(ModelVersionEvent.created_at)
    ).all()
    return [
        {
            "id": event.id,
            "action": event.action,
            "previous_model_version_id": event.previous_model_version_id,
            "actor_id": event.actor_id,
            "reason": event.reason,
            "created_at": event.created_at,
        }
        for event in events
    ]


@router.post("/evaluations", response_model=EvaluationResponse, status_code=201)
def create_evaluation(
    payload: EvaluationCreate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    model = _model_or_404(session, payload.model_version_id)
    if payload.is_synthetic and payload.method != EvaluationMethod.SYNTHETIC_FIXTURE:
        raise AppError(
            "Synthetic samples must use the SYNTHETIC_FIXTURE method.",
            status_code=422,
            code="synthetic_method_required",
        )
    if payload.method == EvaluationMethod.SYNTHETIC_FIXTURE and not payload.is_synthetic:
        raise AppError(
            "SYNTHETIC_FIXTURE evaluations must be marked is_synthetic.",
            status_code=422,
            code="synthetic_flag_required",
        )
    try:
        result = evaluate_samples(
            (
                EvaluationSample(
                    predicted_score=sample.predicted_score,
                    observed=sample.observed,
                    cell_id=sample.cell_id,
                    observed_at=sample.observed_at,
                )
                for sample in payload.samples
            ),
            threshold=payload.threshold,
            include_spatial=payload.include_spatial,
            time_split=payload.time_split,
        )
    except EvaluationError as error:
        raise AppError(str(error), status_code=422, code=error.code) from error
    split_strategy = "TIME_SPATIAL" if payload.time_split and payload.include_spatial else (
        "TIME" if payload.time_split else ("SPATIAL" if payload.include_spatial else "NONE")
    )
    warnings = list(result["warnings"])
    if payload.is_synthetic:
        warnings.insert(
            0,
            "SYNTHETIC_FIXTURE: these metrics test the evaluation code, not field performance.",
        )
    if not payload.is_synthetic:
        warnings.append(
            "Ground truth is caller-supplied; verify provenance before operational use."
        )
    record = ModelEvaluation(
        model_version_id=model.id,
        method=payload.method,
        status=EvaluationStatus(result["status"]),
        dataset_label=payload.dataset_label,
        is_synthetic=payload.is_synthetic,
        ground_truth_available=not payload.is_synthetic and result["status"] != "INSUFFICIENT_DATA",
        split_strategy=split_strategy,
        sample_count=result["sample_count"],
        metrics=result["metrics"],
        slices=result["slices"],
        config={
            "threshold": payload.threshold,
            "include_spatial": payload.include_spatial,
            "time_split": payload.time_split,
        },
        warnings=warnings,
        created_by=user.profile.id,
    )
    session.add(record)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(record)
    return _serialize_evaluation(record)


@router.get("/evaluations", response_model=list[EvaluationResponse])
def list_evaluations(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    model_version_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict]:
    del user
    statement = select(ModelEvaluation).order_by(ModelEvaluation.created_at.desc()).limit(limit)
    if model_version_id is not None:
        statement = statement.where(ModelEvaluation.model_version_id == model_version_id)
    return [_serialize_evaluation(item) for item in session.scalars(statement).all()]


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationResponse)
def get_evaluation(
    evaluation_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    item = session.get(ModelEvaluation, evaluation_id)
    if item is None:
        raise AppError("Evaluation not found.", status_code=404, code="evaluation_not_found")
    return _serialize_evaluation(item)
