"""Threshold alert evaluation and in-app notification delivery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.governance.service import resolve_risk_config
from app.ingestion.service import quality_overview
from app.models import (
    Alert,
    AlertRule,
    AlertRuleType,
    AlertSeverity,
    AlertStatus,
    DataQualityStatus,
    Notification,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationPreference,
    Profile,
    Role,
)
from app.risk.engine import RiskEngine, RiskQuery
from app.operations.notifications import get_notification_adapter


SEVERITY_RANK = {
    AlertSeverity.INFO: 0,
    AlertSeverity.WARNING: 1,
    AlertSeverity.CRITICAL: 2,
}


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    if operator == "==":
        return value == threshold
    return value >= threshold


def _recent_duplicate(session: Session, dedupe_key: str, window_minutes: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    return session.scalar(
        select(Alert.id).where(
            Alert.dedupe_key == dedupe_key,
            Alert.triggered_at >= cutoff,
        )
    ) is not None


def _notify_staff(session: Session, alert: Alert) -> int:
    staff = session.scalars(
        select(Profile).where(
            Profile.role.in_([Role.WORKER, Role.ADMIN]),
            Profile.is_active.is_(True),
        )
    ).all()
    delivered = 0
    for profile in staff:
        preference = session.get(NotificationPreference, profile.id)
        if preference is not None:
            if not preference.in_app_enabled:
                continue
            if SEVERITY_RANK[alert.severity] < SEVERITY_RANK[preference.minimum_severity]:
                continue
        adapter = get_notification_adapter(NotificationChannel.IN_APP.value)
        result = adapter.deliver(
            recipient_id=str(profile.id),
            title=alert.title,
            message=alert.message,
        )
        session.add(
            Notification(
                alert_id=alert.id,
                recipient_id=profile.id,
                channel=NotificationChannel.IN_APP,
                delivery_status=(
                    NotificationDeliveryStatus.DELIVERED
                    if result.delivered
                    else NotificationDeliveryStatus.FAILED
                ),
                dedupe_key=alert.dedupe_key,
                delivered_at=(
                    datetime.now(timezone.utc) if result.delivered else None
                ),
                error=result.error,
            )
        )
        if result.delivered:
            delivered += 1
    return delivered


def create_alert(
    session: Session,
    *,
    rule: AlertRule,
    title: str,
    message: str,
    dedupe_key: str,
    context: dict,
) -> Alert | None:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"civicflow-alert:{dedupe_key}"},
        )
    if _recent_duplicate(
        session,
        dedupe_key,
        max(rule.dedupe_window_minutes, rule.cooldown_minutes),
    ):
        return None
    alert = Alert(
        rule_id=rule.id,
        severity=rule.severity,
        title=title,
        message=message,
        dedupe_key=dedupe_key,
        context=context,
    )
    session.add(alert)
    session.flush()
    _notify_staff(session, alert)
    return alert


def _risk_metric(session: Session, settings: Settings) -> float:
    config = resolve_risk_config(session, settings)
    computation = RiskEngine(session, config).compute(
        RiskQuery(
            resolution=config.default_resolution,
            window_hours=config.default_window_hours,
            bbox=None,
            limit=config.max_cells,
        )
    )
    return max((cell.risk_score for cell in computation.cells), default=0.0)


def evaluate_rules(
    session: Session, *, settings: Settings, actor_id: UUID | None = None
) -> list[Alert]:
    del actor_id
    rules = session.scalars(
        select(AlertRule).where(AlertRule.is_enabled.is_(True))
    ).all()
    created: list[Alert] = []
    max_risk: float | None = None
    for rule in rules:
        if rule.rule_type == AlertRuleType.RISK_THRESHOLD:
            if max_risk is None:
                max_risk = _risk_metric(session, settings)
            threshold = float(rule.threshold_value or 0)
            if _compare(max_risk, rule.operator, threshold):
                alert = create_alert(
                    session,
                    rule=rule,
                    title=f"{rule.name}: risk threshold reached",
                    message=(
                        f"Maximum current cell risk is {max_risk:.2f}, at or above "
                        f"the configured {threshold:.2f} threshold."
                    ),
                    dedupe_key=f"rule:{rule.id}:risk",
                    context={"metric": rule.metric, "value": max_risk, "threshold": threshold},
                )
                if alert:
                    created.append(alert)
        elif rule.rule_type == AlertRuleType.DATA_FRESHNESS:
            stale_items = [
                item
                for item in quality_overview(session)
                if item["status"]
                in {
                    DataQualityStatus.STALE,
                    DataQualityStatus.DEGRADED,
                    DataQualityStatus.UNKNOWN,
                }
            ]
            if not _compare(
                float(len(stale_items)),
                rule.operator,
                float(rule.threshold_value or 1),
            ):
                continue
            for item in stale_items:
                status = item["status"]
                source = item["source"]
                alert = create_alert(
                    session,
                    rule=rule,
                    title=f"{rule.name}: {source.name} is {status.value.lower()}",
                    message="; ".join(item["issues"]) or f"Data quality is {status.value}.",
                    dedupe_key=f"rule:{rule.id}:source:{source.id}",
                    context={
                        "metric": rule.metric,
                        "source_id": str(source.id),
                        "source_key": source.source_key,
                        "status": status.value,
                        "freshness_minutes": item["freshness_minutes"],
                    },
                )
                if alert:
                    created.append(alert)
        elif rule.rule_type == AlertRuleType.INGESTION_FAILURE:
            from app.models import IngestionRun, IngestionStatus

            failed_runs = session.scalars(
                select(IngestionRun)
                .where(IngestionRun.status == IngestionStatus.FAILED)
                .order_by(IngestionRun.completed_at.desc())
                .limit(20)
            ).all()
            if not _compare(
                float(len(failed_runs)),
                rule.operator,
                float(rule.threshold_value or 1),
            ):
                continue
            for run in failed_runs:
                if run.completed_at is None:
                    continue
                alert = create_alert(
                    session,
                    rule=rule,
                    title=f"{rule.name}: ingestion failed",
                    message=run.error_summary or "An ingestion run failed.",
                    dedupe_key=f"rule:{rule.id}:run:{run.id}",
                    context={
                        "metric": rule.metric,
                        "run_id": str(run.id),
                        "source_id": str(run.source_id),
                    },
                )
                if alert:
                    created.append(alert)
    session.commit()
    for alert in created:
        session.refresh(alert)
    return created


def acknowledge_alert(
    session: Session, alert: Alert, *, actor_id: UUID
) -> Alert:
    if alert.status == AlertStatus.RESOLVED:
        raise ValueError("Resolved alerts cannot be acknowledged.")
    if alert.status == AlertStatus.ACKNOWLEDGED:
        return alert
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by = actor_id
    alert.acknowledged_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(alert)
    return alert


def resolve_alert(session: Session, alert: Alert, *, actor_id: UUID) -> Alert:
    if alert.status == AlertStatus.RESOLVED:
        return alert
    alert.status = AlertStatus.RESOLVED
    alert.resolved_by = actor_id
    alert.resolved_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(alert)
    return alert
