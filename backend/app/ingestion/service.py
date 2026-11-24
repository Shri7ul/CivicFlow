"""Idempotent source ingestion and data-quality tracking."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ingestion.base import (
    AdapterUnavailable,
    SourceRecord,
    get_adapter,
)
from app.models import (
    DataQualitySnapshot,
    DataSource,
    DataQualityStatus,
    IngestedRecord,
    IngestionRun,
    IngestionStatus,
    SourceStatus,
)


class IngestionError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _schema_fingerprint(records: list[dict]) -> str | None:
    keys = sorted({key for record in records for key in record})
    if not keys:
        return None
    return hashlib.sha256(",".join(keys).encode("utf-8")).hexdigest()[:32]


def _missing_fields(payload: dict, required: list[str]) -> int:
    return sum(1 for field in required if field not in payload or payload[field] in (None, ""))


def _quality_status(
    source: DataSource,
    *,
    completed_at: datetime | None,
    invalid: int,
    missing: int,
    now: datetime,
) -> tuple[DataQualityStatus, int | None, list[str]]:
    if completed_at is not None and completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    if source.status == SourceStatus.UNAVAILABLE:
        return DataQualityStatus.UNKNOWN, None, ["Source is marked unavailable."]
    if completed_at is None:
        return DataQualityStatus.UNKNOWN, None, ["No successful ingestion run."]
    freshness = max(0, int((now - completed_at).total_seconds() // 60))
    issues: list[str] = []
    if freshness > source.freshness_target_minutes:
        issues.append(
            f"Data is {freshness} minutes old; target is {source.freshness_target_minutes}."
        )
        return DataQualityStatus.STALE, freshness, issues
    if invalid or missing:
        issues.append("Invalid or missing-field records were observed.")
        return DataQualityStatus.DEGRADED, freshness, issues
    return DataQualityStatus.HEALTHY, freshness, issues


def _snapshot(
    session: Session,
    source: DataSource,
    run: IngestionRun | None,
    *,
    now: datetime | None = None,
) -> DataQualitySnapshot:
    now = now or datetime.now(timezone.utc)
    latest = session.scalar(
        select(IngestionRun)
        .where(
            IngestionRun.source_id == source.id,
            IngestionRun.completed_at.is_not(None),
        )
        .order_by(IngestionRun.completed_at.desc())
        .limit(1)
    )
    run = latest or run
    completed_at = run.completed_at if run is not None else None
    invalid = run.records_invalid if run is not None else 0
    missing = 0
    if run is not None and run.provenance:
        missing = int(run.provenance.get("missing_fields", 0))
    status, freshness, issues = _quality_status(
        source,
        completed_at=completed_at,
        invalid=invalid,
        missing=missing,
        now=now,
    )
    latest_schema = run.schema_fingerprint if run is not None else None
    schema_changed = False
    if run is not None and run.provenance.get("previous_schema_fingerprint"):
        previous = run.provenance["previous_schema_fingerprint"]
        if previous != latest_schema:
            schema_changed = True
            issues.append("Schema fingerprint changed from the previous run.")
            if status == DataQualityStatus.HEALTHY:
                status = DataQualityStatus.DEGRADED
    if run is not None and run.status == IngestionStatus.FAILED:
        issues.append("The latest ingestion run failed.")
        if status == DataQualityStatus.HEALTHY:
            status = DataQualityStatus.DEGRADED
    snapshot = DataQualitySnapshot(
        source_id=source.id,
        status=status,
        freshness_minutes=freshness,
        records_total=run.records_received if run is not None else 0,
        invalid_records=invalid,
        duplicate_records=run.records_duplicate if run is not None else 0,
        missing_fields=missing,
        coverage={
            "adapter": source.adapter,
            "run_id": str(run.id) if run is not None else None,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "schema_changed": schema_changed,
        },
        issues=issues,
        schema_fingerprint=latest_schema,
        recorded_at=now,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def ingest_records(
    session: Session,
    source: DataSource,
    *,
    idempotency_key: str,
    records: list[SourceRecord],
    actor_id: UUID | None,
) -> tuple[IngestionRun, DataQualitySnapshot]:
    locked_source = session.scalar(
        select(DataSource)
        .where(DataSource.id == source.id)
        .with_for_update()
    )
    if locked_source is None:
        raise IngestionError("Data source not found.", code="source_not_found")
    source = locked_source
    if source.status != SourceStatus.ACTIVE:
        raise IngestionError("Source is not active.", code="source_not_active")
    try:
        get_adapter(source.adapter)
    except AdapterUnavailable as error:
        raise IngestionError(str(error), code="adapter_not_configured") from error
    if source.adapter != "manual":
        raise IngestionError(
            "This adapter requires an external fetch worker, which is not configured.",
            code="adapter_not_configured",
        )
    existing = session.scalar(
        select(IngestionRun).where(
            IngestionRun.source_id == source.id,
            IngestionRun.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        latest = session.scalar(
            select(DataQualitySnapshot)
            .where(DataQualitySnapshot.source_id == source.id)
            .order_by(DataQualitySnapshot.recorded_at.desc())
            .limit(1)
        )
        if latest is None:
            latest = _snapshot(session, source, existing)
            session.commit()
            session.refresh(latest)
        return existing, latest
    if not records:
        raise IngestionError("At least one record is required.", code="empty_batch")
    previous = session.scalar(
        select(IngestionRun)
        .where(IngestionRun.source_id == source.id)
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    now = datetime.now(timezone.utc)
    run = IngestionRun(
        source_id=source.id,
        idempotency_key=idempotency_key,
        status=IngestionStatus.RUNNING,
        triggered_by=actor_id,
    )
    session.add(run)
    session.flush()
    valid_payloads: list[dict] = []
    invalid = 0
    duplicates = 0
    upserted = 0
    required = list(source.metadata_json.get("required_fields", []))
    missing = 0
    seen: set[str] = set()
    for record in records:
        external_id = record.external_id.strip()
        if not external_id or len(external_id) > 200 or not isinstance(record.payload, dict):
            invalid += 1
            continue
        if external_id in seen:
            duplicates += 1
            continue
        seen.add(external_id)
        valid_payloads.append(record.payload)
        missing += _missing_fields(record.payload, required)
        payload_hash = _hash(record.payload)
        existing_record = session.scalar(
            select(IngestedRecord).where(
                IngestedRecord.source_id == source.id,
                IngestedRecord.external_id == external_id,
            )
        )
        if existing_record is None:
            session.add(
                IngestedRecord(
                    source_id=source.id,
                    external_id=external_id,
                    payload_hash=payload_hash,
                    payload=record.payload,
                    observed_at=record.observed_at,
                    provenance=record.provenance or {},
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )
            upserted += 1
        elif existing_record.payload_hash == payload_hash:
            duplicates += 1
            existing_record.observed_at = record.observed_at
            existing_record.provenance = record.provenance or {}
            existing_record.last_seen_at = now
        else:
            existing_record.payload_hash = payload_hash
            existing_record.payload = record.payload
            existing_record.observed_at = record.observed_at
            existing_record.provenance = record.provenance or {}
            existing_record.last_seen_at = now
            upserted += 1
    run.records_received = len(records)
    run.records_valid = len(valid_payloads)
    run.records_invalid = invalid
    run.records_duplicate = duplicates
    run.records_upserted = upserted
    run.completed_at = now
    run.schema_fingerprint = _schema_fingerprint(valid_payloads)
    run.provenance = {
        "missing_fields": missing,
        "previous_schema_fingerprint": (
            previous.schema_fingerprint if previous is not None else None
        ),
        "adapter": source.adapter,
        "source_reliability": source.reliability.value,
    }
    if valid_payloads and invalid:
        run.status = IngestionStatus.PARTIAL
    elif not valid_payloads:
        run.status = IngestionStatus.FAILED
        run.error_summary = "No valid records in batch."
    else:
        run.status = IngestionStatus.COMPLETED
    snapshot = _snapshot(session, source, run, now=now)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        concurrent = session.scalar(
            select(IngestionRun).where(
                IngestionRun.source_id == source.id,
                IngestionRun.idempotency_key == idempotency_key,
            )
        )
        if concurrent is not None:
            latest = latest_quality(session, source.id)
            if latest is not None:
                return concurrent, latest
        raise IngestionError(
            "Ingestion conflicted with a concurrent write; retry with a new idempotency key.",
            code="ingestion_conflict",
        ) from error
    session.refresh(run)
    session.refresh(snapshot)
    return run, snapshot


def latest_quality(session: Session, source_id: UUID) -> DataQualitySnapshot | None:
    return session.scalar(
        select(DataQualitySnapshot)
        .where(DataQualitySnapshot.source_id == source_id)
        .order_by(DataQualitySnapshot.recorded_at.desc())
        .limit(1)
    )


def quality_overview(session: Session) -> list[dict]:
    sources = session.scalars(select(DataSource).order_by(DataSource.name)).all()
    result = []
    for source in sources:
        latest = latest_quality(session, source.id)
        if latest is None:
            status, freshness, issues = _quality_status(
                source, completed_at=None, invalid=0, missing=0,
                now=datetime.now(timezone.utc),
            )
            result.append(
                {
                    "source": source,
                    "status": status,
                    "freshness_minutes": freshness,
                    "issues": issues,
                    "snapshot": None,
                }
            )
        else:
            completed_at = None
            completed_text = (latest.coverage or {}).get("completed_at")
            if completed_text:
                try:
                    completed_at = datetime.fromisoformat(completed_text)
                    if completed_at.tzinfo is None:
                        completed_at = completed_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    completed_at = None
            status, freshness, current_issues = _quality_status(
                source,
                completed_at=completed_at,
                invalid=latest.invalid_records,
                missing=latest.missing_fields,
                now=datetime.now(timezone.utc),
            )
            issues = list(current_issues)
            historical_schema_warning = next(
                (
                    issue
                    for issue in (latest.issues or [])
                    if issue.startswith("Schema fingerprint changed")
                ),
                None,
            )
            if historical_schema_warning and historical_schema_warning not in issues:
                issues.append(historical_schema_warning)
            latest_failed = session.scalar(
                select(IngestionRun)
                .where(
                    IngestionRun.source_id == source.id,
                    IngestionRun.status == IngestionStatus.FAILED,
                )
                .order_by(IngestionRun.completed_at.desc())
                .limit(1)
            )
            if latest_failed is not None and latest_failed.completed_at is not None:
                failed_at = latest_failed.completed_at
                if failed_at.tzinfo is None:
                    failed_at = failed_at.replace(tzinfo=timezone.utc)
                if completed_at is None or failed_at >= completed_at:
                    failure_issue = "The latest ingestion run failed."
                    if failure_issue not in issues:
                        issues.append(failure_issue)
                    if status == DataQualityStatus.HEALTHY:
                        status = DataQualityStatus.DEGRADED
            result.append(
                {
                    "source": source,
                    "status": status,
                    "freshness_minutes": freshness,
                    "issues": issues,
                    "snapshot": latest,
                }
            )
    return result


def stale_data_warnings(session: Session) -> list[str]:
    warnings = []
    for item in quality_overview(session):
        if item["status"] in {DataQualityStatus.STALE, DataQualityStatus.DEGRADED, DataQualityStatus.UNKNOWN}:
            name = item["source"].name
            details = "; ".join(item["issues"]) or "quality status is not healthy"
            warnings.append(f"Data source '{name}' is {item['status'].value}: {details}")
    return warnings


def record_failure(
    session: Session,
    source: DataSource,
    *,
    idempotency_key: str,
    message: str,
    actor_id: UUID | None,
) -> IngestionRun:
    run = IngestionRun(
        source_id=source.id,
        idempotency_key=idempotency_key,
        status=IngestionStatus.FAILED,
        completed_at=datetime.now(timezone.utc),
        error_summary=message[:2000],
        triggered_by=actor_id,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
