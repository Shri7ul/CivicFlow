"""Fresh external NYC 311 acquisition with retained response bytes.

The request is generated only from a pinned Phase 11 specification. A registered
dataset is never overwritten by a later fetch: the pinned gzip snapshot is the
reproducible evaluation input.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.ingestion.base import SourceRecord
from app.ingestion.service import ingest_records
from app.models.enums import (
    EvidenceQualityStatus,
    EvidenceSnapshotKind,
    EvidenceSnapshotStatus,
    SnapshotVerificationStatus,
    SourceReliability,
    SourceStatus,
    ValidationDatasetStatus,
)
from app.models.evidence import EvidenceSnapshot, EvidenceSnapshotEvent
from app.models.operations import DataSource
from app.models.validation import ValidationDataset
from app.validation.dataset import (
    NYC311_SCHEMA_VERSION,
    NYC311DatasetSpec,
    canonical_hash,
    normalize_rows,
    snapshot_path,
    write_snapshot,
)
from app.validation.phase11 import PHASE11_DATASETS
from app.validation.service import register_dataset

MAX_HTTP_BYTES = 25_000_000


class ExternalAcquisitionError(Exception):
    pass


def _request_url(spec: NYC311DatasetSpec, limit: int) -> str:
    quoted = "','".join(spec.selected_types)
    where = (
        f"created_date between '{spec.period_start.strftime('%Y-%m-%dT%H:%M:%S')}' "
        f"and '{spec.period_end.strftime('%Y-%m-%dT%H:%M:%S')}' "
        f"AND latitude between {spec.bbox[0]} and {spec.bbox[2]} "
        f"AND longitude between {spec.bbox[1]} and {spec.bbox[3]} "
        f"AND complaint_type in ('{quoted}')"
    )
    params = {
        "$select": (
            "unique_key,created_date,complaint_type,descriptor,"
            "latitude,longitude,borough,status"
        ),
        "$where": where,
        "$order": "created_date,unique_key",
        "$limit": str(limit + 1),
    }
    return f"{spec.source_url}?{urlencode(params)}"


def _fetch(spec: NYC311DatasetSpec, limit: int) -> tuple[bytes, list[dict], str]:
    url = _request_url(spec, limit)
    try:
        with httpx.stream(
            "GET",
            url,
            timeout=httpx.Timeout(180.0, connect=10.0),
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": "CivicFlow-Evidence/1.0 (external validation)",
            },
        ) as response:
            status = response.status_code
            content_type = response.headers.get("content-type", "")
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_HTTP_BYTES:
                    raise ExternalAcquisitionError("Source response exceeded byte cap")
                chunks.append(chunk)
            raw = b"".join(chunks)
    except ExternalAcquisitionError:
        raise
    except (httpx.HTTPError, OSError) as error:
        raise ExternalAcquisitionError(
            f"Fresh external acquisition failed: {type(error).__name__}"
        ) from error
    if status != 200:
        raise ExternalAcquisitionError(f"Source returned HTTP {status}")
    if "json" not in content_type.lower():
        raise ExternalAcquisitionError("Source did not return JSON")
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ExternalAcquisitionError("Source returned invalid JSON") from error
    if not isinstance(rows, list):
        raise ExternalAcquisitionError("Source returned a non-array payload")
    if len(rows) > limit:
        raise ExternalAcquisitionError("Source exceeded the configured record cap")
    return raw, rows, url


def _quality(
    spec: NYC311DatasetSpec,
    rows: list[dict],
    records: list[dict],
    rejected: list[dict],
    limit: int,
) -> tuple[EvidenceQualityStatus, list[dict]]:
    duplicate_rejections = sum(
        1 for item in rejected if "duplicate" in str(item.get("reason", "")).lower()
    )
    invalid = len(rejected) - duplicate_rejections
    rejected_ratio = len(rejected) / len(rows) if rows else 1.0
    checks = [
        {
            "check": "record_cap",
            "status": "PASS" if len(rows) <= limit else "FAIL",
            "detail": f"{len(rows)} source rows; cap {limit}.",
        },
        {
            "check": "normalized_count",
            "status": "PASS" if len(records) >= 100 else "FAIL",
            "detail": f"{len(records)} normalized complaints; minimum 100.",
        },
        {
            "check": "rejection_ratio",
            "status": "PASS" if rejected_ratio <= 0.1 else "FAIL",
            "detail": f"{len(rejected)} rejected; {invalid} invalid and "
            f"{duplicate_rejections} duplicate.",
        },
        {
            "check": "unique_ids",
            "status": "PASS" if len({r['external_id'] for r in records}) == len(records) else "FAIL",
            "detail": "Normalized unique_key values must be unique.",
        },
        {
            "check": "spatial_bounds",
            "status": "PASS" if records else "FAIL",
            "detail": (
                f"All coordinates inside {spec.bbox}."
                if all(
                    spec.bbox[0] <= row["latitude"] <= spec.bbox[2]
                    and spec.bbox[1] <= row["longitude"] <= spec.bbox[3]
                    for row in records
                )
                else "Coordinate outside the pinned study bbox."
            ),
        },
        {
            "check": "temporal_bounds",
            "status": "PASS" if records else "FAIL",
            "detail": (
                f"All observations inside {spec.period_start.date()} to "
                f"{spec.period_end.date()}."
                if all(
                    spec.period_start
                    <= datetime.fromisoformat(row["observed_at"])
                    <= spec.period_end
                    for row in records
                )
                else "Observation outside the pinned period."
            ),
        },
    ]
    if any(item["status"] == "FAIL" for item in checks):
        return EvidenceQualityStatus.FAIL, checks
    return EvidenceQualityStatus.PASS, checks


def _source_key(spec: NYC311DatasetSpec) -> str:
    return f"{spec.dataset_key}-validation"


def acquire_external_dataset(
    session: Session,
    spec: NYC311DatasetSpec,
    *,
    settings: Settings,
    actor_id: uuid.UUID | None = None,
) -> dict:
    if spec.dataset_key not in PHASE11_DATASETS:
        raise ExternalAcquisitionError("Dataset is not a pinned Phase 11 slice")
    pinned = PHASE11_DATASETS[spec.dataset_key]
    if spec != pinned:
        raise ExternalAcquisitionError(
            "Dataset specification does not match the pinned Phase 11 slice"
        )
    # Use the registered specification, never caller-supplied mutable fields, for
    # the request URL, bbox, period and snapshot filename.
    spec = pinned
    existing = session.scalar(
        select(ValidationDataset).where(
            ValidationDataset.dataset_key == spec.dataset_key
        )
    )
    if existing is not None:
        snapshot = session.scalar(
            select(EvidenceSnapshot).where(
                EvidenceSnapshot.validation_dataset_id == existing.id
            )
        )
        return {
            "dataset": existing,
            "snapshot": snapshot,
            "created": False,
            "reason": "pinned dataset already registered; not overwritten",
        }

    limit = min(settings.validation_max_records, 25_000)
    raw, rows, request_url = _fetch(spec, limit)
    records, rejected = normalize_rows(rows, spec)
    digest = canonical_hash(records)
    path = snapshot_path(Path(__file__).resolve().parents[2], spec)
    write_snapshot(
        path,
        records=records,
        rejected=rejected,
        metadata={
            "request_url": request_url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "row_count_raw": len(rows),
            "query": {
                "dataset_key": spec.dataset_key,
                "period_start": spec.period_start.isoformat(),
                "period_end": spec.period_end.isoformat(),
                "bbox": list(spec.bbox),
                "complaint_types": list(spec.selected_types),
                "order": "created_date,unique_key",
            },
        },
        spec=spec,
    )
    quality, checks = _quality(spec, rows, records, rejected, limit)

    source = session.scalar(
        select(DataSource).where(DataSource.source_key == _source_key(spec))
    )
    if source is None:
        source = DataSource(
            source_key=_source_key(spec),
            name=f"NYC 311 Service Requests ({spec.name})",
            category="public service requests",
            access_method="pinned Socrata query + retained HTTP response",
            license_note=spec.license_note,
            reliability=SourceReliability.VERIFIED,
            status=SourceStatus.ACTIVE,
            adapter="manual",
            freshness_target_minutes=180 * 24 * 60,
            retry_limit=2,
            metadata_json={
                "dataset_key": spec.dataset_key,
                "schema_version": NYC311_SCHEMA_VERSION,
                "source_url": spec.source_url,
                "external_validation": True,
                "note": (
                    "Public complaint activity used for external validation; "
                    "not verified hazard impact or operational ground truth."
                ),
            },
        )
        session.add(source)
        session.commit()
        session.refresh(source)
    elif source.adapter != "manual":
        source.adapter = "manual"
        session.commit()

    source_records = [
        SourceRecord(
            external_id=record["external_id"],
            payload=record,
            observed_at=datetime.fromisoformat(record["observed_at"]),
            provenance={
                "dataset_key": spec.dataset_key,
                "schema_version": NYC311_SCHEMA_VERSION,
                "snapshot_sha256": digest,
                "source_url": spec.source_url,
            },
        )
        for record in records
    ]
    run, run_quality = ingest_records(
        session,
        source,
        idempotency_key=f"phase11-nyc311-{digest[:24]}",
        records=source_records,
        actor_id=actor_id,
    )
    dataset = register_dataset(
        session,
        dataset_key=spec.dataset_key,
        name=spec.name,
        description=spec.description,
        source_url=spec.source_url,
        license_note=spec.license_note,
        region=spec.region,
        geographic_context_key="US-NYC",
        period_start=spec.period_start,
        period_end=spec.period_end,
        source_id=source.id,
        ingestion_run_id=run.id,
        snapshot_sha256=digest,
        snapshot_path=path.name,
        record_count=len(records),
        schema_version=NYC311_SCHEMA_VERSION,
        dataset_metadata={
            "request_url": request_url,
            "query": {
                "period_start": spec.period_start.isoformat(),
                "period_end": spec.period_end.isoformat(),
                "bbox": list(spec.bbox),
                "complaint_types": list(spec.selected_types),
            },
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "bbox": list(spec.bbox),
            "rejected_count": len(rejected),
            "ingestion_status": run.status.value,
            "quality_status": run_quality.status.value,
            "phase11_evaluation_role": "FRESH_EXTERNAL_TEMPORAL_GEOGRAPHIC",
            "phase11_freshness_days": (
                datetime.now(timezone.utc) - spec.period_end
            ).days,
            "source_quality_status": quality.value,
            "license_note": spec.license_note,
            "note": (
                "Acquired after Phase 9; held out from configuration/model "
                "selection. Complaint activity only."
            ),
        },
        actor_id=actor_id,
    )
    if quality == EvidenceQualityStatus.FAIL:
        dataset.status = ValidationDatasetStatus.INSUFFICIENT
        session.commit()
        session.refresh(dataset)

    normalized_bytes = json.dumps(
        records, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    snapshot = EvidenceSnapshot(
        snapshot_key=f"{spec.dataset_key}-{digest[:12]}",
        kind=EvidenceSnapshotKind.RESEARCH_DATASET,
        geographic_context_key="US-NYC",
        status=(
            EvidenceSnapshotStatus.VALIDATED
            if quality != EvidenceQualityStatus.FAIL
            else EvidenceSnapshotStatus.QUARANTINED
        ),
        source_key=spec.dataset_key,
        source_url=spec.source_url,
        provider="NYC 311 / NYC Open Data (Socrata erm2-nwe9)",
        license_note=spec.license_note,
        dataset_version=f"erm2-nwe9@{spec.period_end.date().isoformat()}",
        retrieved_at=datetime.now(timezone.utc),
        snapshot_sha256=digest,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        schema_version=NYC311_SCHEMA_VERSION,
        schema_fingerprint=hashlib.sha256(
            json.dumps(sorted(rows[0].keys())).encode("utf-8")
        ).hexdigest()
        if rows
        else None,
        record_count=len(records),
        raw_record_count=len(rows),
        duplicate_count=sum(
            1 for item in rejected if "duplicate" in str(item.get("reason", "")).lower()
        ),
        invalid_count=sum(
            1 for item in rejected if "duplicate" not in str(item.get("reason", "")).lower()
        ),
        missing_fields=0,
        byte_size=len(normalized_bytes),
        media_type="application/json",
        crs="EPSG:4326",
        # Validation datasets store bbox as (south, west, north, east); evidence
        # snapshots use GeoJSON order (west, south, east, north).
        bbox=[spec.bbox[1], spec.bbox[0], spec.bbox[3], spec.bbox[2]],
        data_period_start=spec.period_start,
        data_period_end=spec.period_end,
        geographic_coverage=spec.region,
        quality_status=quality,
        quality_checks=checks,
        lineage={
            "source_key": spec.dataset_key,
            "source_url": spec.source_url,
            "request_url": request_url,
            "raw_http_sha256": hashlib.sha256(raw).hexdigest(),
            "normalization": "nyc311-normalized-v1, unique_key deduplicated",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "raw_record_count": len(rows),
            "rejected_count": len(rejected),
            "ingestion_run_id": str(run.id),
            "external_validation": True,
            "configuration_used_for_selection": False,
        },
        verification_status=SnapshotVerificationStatus.PENDING,
        is_current=True,
        validation_dataset_id=dataset.id,
        raw_content=raw,
        normalized_content=normalized_bytes,
        created_by=actor_id,
    )
    session.add(snapshot)
    session.flush()
    session.add(
        EvidenceSnapshotEvent(
            snapshot_id=snapshot.id,
            action="EXTERNAL_ACQUIRED",
            from_status=None,
            to_status=snapshot.status,
            actor_id=actor_id,
            note=(
                f"Fresh Q3 2026 external slice: {len(rows)} source rows, "
                f"{len(records)} normalized; {len(rejected)} rejected."
            ),
        )
    )
    session.commit()
    return {"dataset": dataset, "snapshot": snapshot, "created": True, "quality": checks}
