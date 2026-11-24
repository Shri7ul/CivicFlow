"""Fetch, snapshot, ingest, and register the bounded NYC 311 validation dataset.

Run from backend/:  .venv/Scripts/python.exe scripts/ingest_nyc311.py --refresh
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.ingestion.base import SourceRecord  # noqa: E402
from app.ingestion.service import ingest_records  # noqa: E402
from app.models import (  # noqa: E402
    DataSource,
    SourceReliability,
    SourceStatus,
)
from app.validation.dataset import (  # noqa: E402
    NYC311_DATASET_KEY,
    NYC311_LICENSE_NOTE,
    NYC311_PERIOD_END,
    NYC311_PERIOD_START,
    NYC311_REGION,
    NYC311_SCHEMA_VERSION,
    NYC311_SOURCE_URL,
    fetch_nyc311_rows,
    load_snapshot,
    normalize_rows,
    snapshot_path,
    write_snapshot,
)
from app.validation.service import register_dataset  # noqa: E402

SOURCE_KEY = "nyc311-brooklyn-validation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-db", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    path = snapshot_path(BACKEND_ROOT)
    if args.refresh or not path.exists():
        rows, fetch_metadata = fetch_nyc311_rows(
            limit=settings.validation_max_records
        )
        records, rejected = normalize_rows(rows)
        digest = write_snapshot(
            path, records=records, rejected=rejected, metadata=fetch_metadata
        )
        metadata = fetch_metadata
        rejected_count = len(rejected)
    else:
        payload = load_snapshot(path)
        records = payload["records"]
        metadata = payload.get("metadata", {})
        rejected_count = int(payload.get("rejected_count", 0))
        digest = payload["snapshot_sha256"]
    if len(records) > settings.validation_max_records:
        raise SystemExit("Snapshot exceeds the configured validation cap.")
    if args.no_db:
        print(json.dumps({"records": len(records), "sha256": digest}, indent=2))
        return 0
    session = get_session_factory()()
    try:
        source = session.scalar(
            select(DataSource).where(DataSource.source_key == SOURCE_KEY)
        )
        if source is None:
            source = DataSource(
                source_key=SOURCE_KEY,
                name="NYC 311 Service Requests (bounded Brooklyn validation slice)",
                category="public service requests",
                access_method="Socrata public API + pinned gzip snapshot",
                license_note=NYC311_LICENSE_NOTE,
                reliability=SourceReliability.VERIFIED,
                status=SourceStatus.ACTIVE,
                adapter="manual",
                freshness_target_minutes=525600,
                retry_limit=3,
                metadata_json={
                    "dataset_key": NYC311_DATASET_KEY,
                    "schema_version": NYC311_SCHEMA_VERSION,
                    "source_url": NYC311_SOURCE_URL,
                    "required_fields": [
                        "external_id",
                        "observed_at",
                        "category",
                        "severity",
                        "latitude",
                        "longitude",
                    ],
                    "note": (
                        "Validation-only public complaint activity; not verified "
                        "hazard ground truth and not an authoritative operational feed."
                    ),
                },
            )
            session.add(source)
            session.commit()
            session.refresh(source)
        source_records = [
            SourceRecord(
                external_id=record["external_id"],
                payload=record,
                observed_at=datetime.fromisoformat(record["observed_at"]),
                provenance={
                    "dataset_key": NYC311_DATASET_KEY,
                    "schema_version": NYC311_SCHEMA_VERSION,
                    "snapshot_sha256": digest,
                    "source_url": NYC311_SOURCE_URL,
                },
            )
            for record in records
        ]
        run, quality = ingest_records(
            session,
            source,
            idempotency_key=f"nyc311-{digest[:24]}",
            records=source_records,
            actor_id=None,
        )
        dataset = register_dataset(
            session,
            dataset_key=NYC311_DATASET_KEY,
            name="NYC 311 Brooklyn Q1 2025 validation slice",
            description=(
                "Bounded public 311 service-request activity used to validate "
                "spatial-temporal risk ranking and sensitivity. Not verified "
                "hazard impact and not municipal ground truth."
            ),
            source_url=NYC311_SOURCE_URL,
            license_note=NYC311_LICENSE_NOTE,
            region=NYC311_REGION,
            period_start=NYC311_PERIOD_START,
            period_end=NYC311_PERIOD_END,
            source_id=source.id,
            ingestion_run_id=run.id,
            snapshot_sha256=digest,
            snapshot_path=path.name,
            record_count=len(records),
            schema_version=NYC311_SCHEMA_VERSION,
            dataset_metadata={
                "query": metadata.get("query"),
                "retrieved_at": metadata.get("retrieved_at"),
                "request_url": metadata.get("request_url"),
                "rejected_count": rejected_count,
                "ingestion_status": run.status.value,
                "quality_status": quality.status.value,
                "reliability": "VERIFIED public source; complaint activity only",
                "download_command": (
                    ".venv/Scripts/python.exe scripts/ingest_nyc311.py --refresh"
                ),
                "snapshot_file": path.name,
                "license_note": NYC311_LICENSE_NOTE,
            },
            actor_id=None,
        )
        print(
            json.dumps(
                {
                    "dataset_id": str(dataset.id),
                    "dataset_key": dataset.dataset_key,
                    "records": dataset.record_count,
                    "sha256": digest,
                    "source_id": str(source.id),
                    "run_id": str(run.id),
                    "ingestion_status": run.status.value,
                    "quality_status": quality.status.value,
                },
                indent=2,
            )
        )
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
