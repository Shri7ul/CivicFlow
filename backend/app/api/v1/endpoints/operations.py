"""Phase 7 operations dashboard, ingestion, alerting, and notification APIs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_admin, require_worker
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.db.session import get_db_session
from app.ingestion.base import SourceRecord
from app.ingestion.service import (
    IngestionError,
    ingest_records,
    latest_quality,
    quality_overview,
)
from app.models import (
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    DataSource,
    DecisionReview,
    DecisionReviewStatus,
    IngestionRun,
    Notification,
    NotificationPreference,
)
from app.operations.alerts import (
    acknowledge_alert,
    evaluate_rules,
    resolve_alert,
)
from app.operations.dashboard import dashboard
from app.schemas.operations import (
    AlertResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    IngestionRequest,
    IngestionRunResponse,
    NotificationResponse,
    PreferenceUpdate,
    QualityItemResponse,
    QualitySnapshotResponse,
    SourceCreate,
    SourceResponse,
)

router = APIRouter()


def _source_or_404(session: Session, source_id: uuid.UUID) -> DataSource:
    source = session.get(DataSource, source_id)
    if source is None:
        raise AppError("Data source not found.", status_code=404, code="source_not_found")
    return source


def _serialize_source(source: DataSource) -> dict:
    return {
        "id": source.id,
        "source_key": source.source_key,
        "name": source.name,
        "category": source.category,
        "access_method": source.access_method,
        "license_note": source.license_note,
        "reliability": source.reliability,
        "status": source.status,
        "adapter": source.adapter,
        "freshness_target_minutes": source.freshness_target_minutes,
        "retry_limit": source.retry_limit,
        "metadata": source.metadata_json or {},
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def _serialize_run(run: IngestionRun) -> dict:
    return {
        "id": run.id,
        "source_id": run.source_id,
        "idempotency_key": run.idempotency_key,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "records_received": run.records_received,
        "records_valid": run.records_valid,
        "records_invalid": run.records_invalid,
        "records_duplicate": run.records_duplicate,
        "records_upserted": run.records_upserted,
        "schema_fingerprint": run.schema_fingerprint,
        "error_summary": run.error_summary,
        "retry_count": run.retry_count,
    }


def _serialize_quality(snapshot) -> dict | None:
    if snapshot is None:
        return None
    return {
        "id": snapshot.id,
        "source_id": snapshot.source_id,
        "status": snapshot.status,
        "freshness_minutes": snapshot.freshness_minutes,
        "records_total": snapshot.records_total,
        "invalid_records": snapshot.invalid_records,
        "duplicate_records": snapshot.duplicate_records,
        "missing_fields": snapshot.missing_fields,
        "coverage": snapshot.coverage or {},
        "issues": snapshot.issues or [],
        "schema_fingerprint": snapshot.schema_fingerprint,
        "recorded_at": snapshot.recorded_at,
    }


def _serialize_rule(rule: AlertRule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "metric": rule.metric,
        "operator": rule.operator,
        "threshold_value": (
            float(rule.threshold_value) if rule.threshold_value is not None else None
        ),
        "severity": rule.severity,
        "scope": rule.scope or {},
        "cooldown_minutes": rule.cooldown_minutes,
        "dedupe_window_minutes": rule.dedupe_window_minutes,
        "is_enabled": rule.is_enabled,
        "in_app_enabled": rule.in_app_enabled,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _serialize_alert(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "rule_id": alert.rule_id,
        "severity": alert.severity,
        "status": alert.status,
        "title": alert.title,
        "message": alert.message,
        "dedupe_key": alert.dedupe_key,
        "context": alert.context or {},
        "triggered_at": alert.triggered_at,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
    }


@router.get("/dashboard")
def operations_dashboard(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    return dashboard(session, settings)


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    del user
    return [
        _serialize_source(source)
        for source in session.scalars(select(DataSource).order_by(DataSource.name)).all()
    ]


@router.post("/sources", response_model=SourceResponse, status_code=201)
def create_source(
    payload: SourceCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    existing = session.scalar(
        select(DataSource).where(DataSource.source_key == payload.source_key)
    )
    if existing is not None:
        raise AppError(
            "A source with this key already exists.",
            status_code=409,
            code="source_key_conflict",
        )
    metadata = dict(payload.metadata)
    metadata["required_fields"] = payload.required_fields
    source = DataSource(
        source_key=payload.source_key,
        name=payload.name,
        category=payload.category,
        access_method=payload.access_method,
        license_note=payload.license_note,
        reliability=payload.reliability,
        status=payload.status,
        adapter=payload.adapter,
        freshness_target_minutes=payload.freshness_target_minutes,
        retry_limit=payload.retry_limit,
        metadata_json=metadata,
        created_by=user.profile.id,
    )
    session.add(source)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise AppError(
            "A source with this key already exists.",
            status_code=409,
            code="source_key_conflict",
        ) from error
    session.refresh(source)
    return _serialize_source(source)


@router.get("/sources/{source_id}/runs", response_model=list[IngestionRunResponse])
def list_runs(
    source_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict]:
    del user
    _source_or_404(session, source_id)
    runs = session.scalars(
        select(IngestionRun)
        .where(IngestionRun.source_id == source_id)
        .order_by(IngestionRun.started_at.desc())
        .limit(limit)
    ).all()
    return [_serialize_run(run) for run in runs]


@router.post("/sources/{source_id}/runs")
def run_ingestion(
    source_id: uuid.UUID,
    payload: IngestionRequest,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    source = _source_or_404(session, source_id)
    records = [
        SourceRecord(
            external_id=item.external_id,
            payload=item.payload,
            observed_at=item.observed_at,
            provenance=item.provenance,
        )
        for item in payload.records
    ]
    try:
        run, snapshot = ingest_records(
            session,
            source,
            idempotency_key=payload.idempotency_key,
            records=records,
            actor_id=user.profile.id,
        )
    except IngestionError as error:
        raise AppError(str(error), status_code=422, code=error.code) from error
    return {
        "run": _serialize_run(run),
        "quality": _serialize_quality(snapshot),
    }


@router.get("/quality", response_model=list[QualityItemResponse])
def quality(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    del user
    return [
        {
            "source": _serialize_source(item["source"]),
            "status": item["status"],
            "freshness_minutes": item["freshness_minutes"],
            "issues": item["issues"],
            "snapshot": _serialize_quality(item["snapshot"]),
        }
        for item in quality_overview(session)
    ]


@router.get("/alerts/rules", response_model=list[AlertRuleResponse])
def list_rules(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    del user
    return [
        _serialize_rule(rule)
        for rule in session.scalars(select(AlertRule).order_by(AlertRule.created_at.desc())).all()
    ]


@router.post("/alerts/rules", response_model=AlertRuleResponse, status_code=201)
def create_rule(
    payload: AlertRuleCreate,
    user: Annotated[AuthenticatedUser, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    rule = AlertRule(
        name=payload.name.strip(),
        rule_type=payload.rule_type,
        metric=payload.metric.strip(),
        operator=payload.operator,
        threshold_value=payload.threshold_value,
        severity=payload.severity,
        scope=payload.scope,
        cooldown_minutes=payload.cooldown_minutes,
        dedupe_window_minutes=payload.dedupe_window_minutes,
        is_enabled=payload.is_enabled,
        in_app_enabled=payload.in_app_enabled,
        created_by=user.profile.id,
    )
    session.add(rule)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(rule)
    return _serialize_rule(rule)


@router.post("/alerts/evaluate", response_model=list[AlertResponse])
def evaluate_alert_rules(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[dict]:
    created = evaluate_rules(session, settings=settings, actor_id=user.profile.id)
    return [_serialize_alert(alert) for alert in created]


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    status: AlertStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict]:
    del user
    statement = select(Alert).order_by(Alert.triggered_at.desc()).limit(limit)
    if status is not None:
        statement = statement.where(Alert.status == status)
    return [_serialize_alert(alert) for alert in session.scalars(statement).all()]


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge(
    alert_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    alert = session.get(Alert, alert_id, with_for_update=True)
    if alert is None:
        raise AppError("Alert not found.", status_code=404, code="alert_not_found")
    try:
        alert = acknowledge_alert(session, alert, actor_id=user.profile.id)
    except ValueError as error:
        raise AppError(str(error), status_code=409, code="alert_not_actionable") from error
    return _serialize_alert(alert)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertResponse)
def resolve(
    alert_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    alert = session.get(Alert, alert_id, with_for_update=True)
    if alert is None:
        raise AppError("Alert not found.", status_code=404, code="alert_not_found")
    alert = resolve_alert(session, alert, actor_id=user.profile.id)
    return _serialize_alert(alert)


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict]:
    statement = (
        select(Notification)
        .where(Notification.recipient_id == user.profile.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    return [
        {
            "id": item.id,
            "alert_id": item.alert_id,
            "channel": item.channel.value,
            "delivery_status": item.delivery_status.value,
            "dedupe_key": item.dedupe_key,
            "created_at": item.created_at,
            "delivered_at": item.delivered_at,
            "read_at": item.read_at,
        }
        for item in session.scalars(statement).all()
    ]


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    item = session.get(Notification, notification_id)
    if item is None or item.recipient_id != user.profile.id:
        raise AppError("Notification not found.", status_code=404, code="notification_not_found")
    if item.read_at is None:
        item.read_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(item)
    return {
        "id": item.id,
        "alert_id": item.alert_id,
        "channel": item.channel.value,
        "delivery_status": item.delivery_status.value,
        "dedupe_key": item.dedupe_key,
        "created_at": item.created_at,
        "delivered_at": item.delivered_at,
        "read_at": item.read_at,
    }


@router.get("/notification-preferences")
def get_preferences(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    preference = session.get(NotificationPreference, user.profile.id)
    if preference is None:
        return {"in_app_enabled": True, "minimum_severity": AlertSeverity.INFO.value}
    return {
        "in_app_enabled": preference.in_app_enabled,
        "minimum_severity": preference.minimum_severity.value,
    }


@router.put("/notification-preferences")
def update_preferences(
    payload: PreferenceUpdate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    preference = session.get(NotificationPreference, user.profile.id)
    if preference is None:
        preference = NotificationPreference(profile_id=user.profile.id)
        session.add(preference)
    if payload.in_app_enabled is not None:
        preference.in_app_enabled = payload.in_app_enabled
    if payload.minimum_severity is not None:
        preference.minimum_severity = payload.minimum_severity
    preference.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(preference)
    return {
        "in_app_enabled": preference.in_app_enabled,
        "minimum_severity": preference.minimum_severity.value,
    }
