"""Unified operational dashboard built from real application records."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.governance.service import active_model, resolve_risk_config
from app.ingestion.service import quality_overview, stale_data_warnings
from app.models import (
    Alert,
    AlertStatus,
    AlertSeverity,
    DataQualityStatus,
    DecisionReview,
    DecisionReviewStatus,
    DecisionScenario,
    DecisionSimulation,
    Incident,
    IncidentStatus,
    ModelEvaluation,
    ModelVersion,
    RiskCategory,
)
from app.risk.engine import RiskEngine, RiskQuery, RiskQueryError


def _count(session: Session, statement) -> int:
    return int(session.scalar(statement) or 0)


def dashboard(session: Session, settings: Settings) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    incidents_by_status = {
        status.value: _count(
            session,
            select(func.count(Incident.id)).where(Incident.status == status),
        )
        for status in IncidentStatus
    }
    incidents_24h = _count(
        session,
        select(func.count(Incident.id)).where(Incident.created_at >= since),
    )
    risk_config = resolve_risk_config(session, settings)
    risk_payload: dict[str, Any]
    try:
        computation = RiskEngine(session, risk_config).compute(
            RiskQuery(
                resolution=risk_config.default_resolution,
                window_hours=risk_config.default_window_hours,
                bbox=None,
                limit=risk_config.max_cells,
            )
        )
        risk_payload = {
            "available": True,
            "resolution": risk_config.default_resolution,
            "window_hours": risk_config.default_window_hours,
            "cell_count": len(computation.cells),
            "max_score": round(
                max((cell.risk_score for cell in computation.cells), default=0.0), 2
            ),
            "bands": {
                category.value: sum(
                    1
                    for cell in computation.cells
                    if risk_config.category_for(cell.risk_score) == category
                )
                for category in RiskCategory
            },
            "incident_count": len(computation.current_incidents),
        }
    except (RiskQueryError, ValueError):
        risk_payload = {
            "available": False,
            "resolution": risk_config.default_resolution,
            "window_hours": risk_config.default_window_hours,
            "cell_count": 0,
            "max_score": None,
            "bands": {},
            "incident_count": 0,
        }
    quality = []
    for item in quality_overview(session):
        snapshot = item["snapshot"]
        quality.append(
            {
                "source_id": str(item["source"].id),
                "source_key": item["source"].source_key,
                "name": item["source"].name,
                "reliability": item["source"].reliability.value,
                "status": item["status"].value,
                "freshness_minutes": item["freshness_minutes"],
                "issues": item["issues"],
                "last_run": (
                    snapshot.coverage.get("completed_at") if snapshot is not None else None
                ),
            }
        )
    models = session.scalars(
        select(ModelVersion).order_by(ModelVersion.created_at.desc()).limit(20)
    ).all()
    active_risk = active_model(session, "risk")
    active_decision = active_model(session, "decision")
    latest_evaluation = None
    if active_risk is not None:
        latest_evaluation = session.scalar(
            select(ModelEvaluation)
            .where(ModelEvaluation.model_version_id == active_risk.id)
            .order_by(ModelEvaluation.created_at.desc())
            .limit(1)
        )
    if latest_evaluation is None:
        latest_evaluation = session.scalar(
            select(ModelEvaluation)
            .join(ModelVersion, ModelVersion.id == ModelEvaluation.model_version_id)
            .where(ModelVersion.model_name == "risk")
            .order_by(ModelEvaluation.created_at.desc())
            .limit(1)
        )
    alert_counts = {
        severity.value: _count(
            session,
            select(func.count(Alert.id)).where(
                Alert.status == AlertStatus.ACTIVE,
                Alert.severity == severity,
            ),
        )
        for severity in AlertSeverity
    }
    recent_alerts = session.scalars(
        select(Alert).order_by(Alert.triggered_at.desc()).limit(8)
    ).all()
    pending_reviews = session.scalars(
        select(DecisionReview)
        .where(
            DecisionReview.status.in_(
                [DecisionReviewStatus.SUBMITTED, DecisionReviewStatus.REVISION_REQUESTED]
            )
        )
        .order_by(DecisionReview.submitted_at.asc())
        .limit(20)
    ).all()
    scenario_count = _count(session, select(func.count(DecisionScenario.id)))
    simulation_count = _count(session, select(func.count(DecisionSimulation.id)))
    try:
        database_ok = session.execute(text("SELECT 1")).scalar() == 1
    except Exception:
        database_ok = False
    return {
        "generated_at": now.isoformat(),
        "incidents": {
            "by_status": incidents_by_status,
            "last_24h": incidents_24h,
        },
        "risk": risk_payload,
        "data_quality": {
            "sources": quality,
            "warnings": stale_data_warnings(session),
            "stale_or_unknown": sum(
                1
                for item in quality
                if item["status"] in {"STALE", "DEGRADED", "UNKNOWN"}
            ),
        },
        "models": {
            "items": [
                {
                    "id": str(model.id),
                    "model_name": model.model_name,
                    "version": model.version,
                    "config_hash": model.config_hash,
                    "is_active": model.is_active,
                    "created_at": model.created_at.isoformat(),
                    "activated_at": (
                        model.activated_at.isoformat() if model.activated_at else None
                    ),
                }
                for model in models
            ],
            "active_risk": (
                {
                    "id": str(active_risk.id),
                    "version": active_risk.version,
                    "config_hash": active_risk.config_hash,
                }
                if active_risk
                else None
            ),
            "active_decision": (
                {
                    "id": str(active_decision.id),
                    "version": active_decision.version,
                    "config_hash": active_decision.config_hash,
                }
                if active_decision
                else None
            ),
            "latest_evaluation": (
                {
                    "id": str(latest_evaluation.id),
                    "method": latest_evaluation.method.value,
                    "status": latest_evaluation.status.value,
                    "dataset_label": latest_evaluation.dataset_label,
                    "is_synthetic": latest_evaluation.is_synthetic,
                    "sample_count": latest_evaluation.sample_count,
                    "metrics": latest_evaluation.metrics,
                    "created_at": latest_evaluation.created_at.isoformat(),
                }
                if latest_evaluation
                else None
            ),
        },
        "alerts": {
            "active_by_severity": alert_counts,
            "recent": [
                {
                    "id": str(alert.id),
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "title": alert.title,
                    "message": alert.message,
                    "triggered_at": alert.triggered_at.isoformat(),
                }
                for alert in recent_alerts
            ],
        },
        "planning": {
            "scenario_count": scenario_count,
            "simulation_count": simulation_count,
            "pending_review_count": len(pending_reviews),
            "pending_reviews": [
                {
                    "id": str(review.id),
                    "scenario_id": str(review.scenario_id),
                    "title": review.title,
                    "status": review.status.value,
                    "submitted_at": (
                        review.submitted_at.isoformat() if review.submitted_at else None
                    ),
                }
                for review in pending_reviews
            ],
        },
        "health": {
            "database": database_ok,
            "app_env": settings.app_env,
        },
        "safety": {
            "dispatch_performed": False,
            "execution_authorized": False,
            "reservations_created": False,
            "note": "Operational dashboard is read-only; approvals do not execute plans.",
        },
    }
