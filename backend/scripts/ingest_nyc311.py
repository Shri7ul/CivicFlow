"""Fetch, snapshot, ingest, and register bounded NYC 311 datasets.

Examples:
  .venv/Scripts/python.exe scripts/ingest_nyc311.py --refresh
  .venv/Scripts/python.exe scripts/ingest_nyc311.py --dataset nyc311-brooklyn-2025q2
  .venv/Scripts/python.exe scripts/ingest_nyc311.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
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
    NYC311_DATASETS,
    NYC311_SCHEMA_VERSION,
    NYC311_SPEC,
    fetch_nyc311_rows,
    load_snapshot,
    normalize_rows,
    snapshot_path,
    write_snapshot,
)
from app.validation.service import register_dataset  # noqa: E402


def _source_key(dataset_key: str) -> str:
    return (
        "nyc311-brooklyn-validation"
        if dataset_key == NYC311_SPEC.dataset_key
        else f"{dataset_key}-validation"
    )


def ingest_spec(spec, *, refresh: bool, no_db: bool, settings) -> dict:
    path = snapshot_path(BACKEND_ROOT, spec)
    if refresh or not path.exists():
        rows, fetch_metadata = fetch_nyc311_rows(
            limit=settings.validation_max_records, spec=spec
        )
        records, rejected = normalize_rows(rows, spec)
        digest = write_snapshot(
            path,
            records=records,
            rejected=rejected,
            metadata=fetch_metadata,
            spec=spec,
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
        raise SystemExit(f"{spec.dataset_key} snapshot exceeds the validation cap.")
    result = {
        "dataset_key": spec.dataset_key,
        "records": len(records),
        "sha256": digest,
        "snapshot_file": path.name,
    }
    if no_db:
        return result
    session = get_session_factory()()
    try:
        source_key = _source_key(spec.dataset_key)
        source = session.scalar(
            select(DataSource).where(DataSource.source_key == source_key)
        )
        if source is None:
            source = DataSource(
                source_key=source_key,
                name=f"NYC 311 Service Requests ({spec.name})",
                category="public service requests",
                access_method="Socrata public API + pinned gzip snapshot",
                license_note=spec.license_note,
                reliability=SourceReliability.VERIFIED,
                status=SourceStatus.ACTIVE,
                adapter="manual",
                freshness_target_minutes=525600,
                retry_limit=3,
                metadata_json={
                    "dataset_key": spec.dataset_key,
                    "schema_version": NYC311_SCHEMA_VERSION,
                    "source_url": spec.source_url,
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
                    "dataset_key": spec.dataset_key,
                    "schema_version": NYC311_SCHEMA_VERSION,
                    "snapshot_sha256": digest,
                    "source_url": spec.source_url,
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
            dataset_key=spec.dataset_key,
            name=spec.name,
            description=spec.description,
            source_url=spec.source_url,
            license_note=spec.license_note,
            region=spec.region,
            period_start=spec.period_start,
            period_end=spec.period_end,
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
                "bbox": list(spec.bbox),
                "rejected_count": rejected_count,
                "ingestion_status": run.status.value,
                "quality_status": quality.status.value,
                "reliability": "VERIFIED public source; complaint activity only",
                "download_command": (
                    ".venv/Scripts/python.exe scripts/ingest_nyc311.py "
                    f"--dataset {spec.dataset_key} --refresh"
                ),
                "snapshot_file": path.name,
                "license_note": spec.license_note,
            },
            actor_id=None,
        )
        result.update(
            {
                "dataset_id": str(dataset.id),
                "source_id": str(source.id),
                "run_id": str(run.id),
                "ingestion_status": run.status.value,
                "quality_status": quality.status.value,
            }
        )
        return result
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        choices=sorted(NYC311_DATASETS),
        default=NYC311_SPEC.dataset_key,
    )
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-db", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    specs = (
        list(NYC311_DATASETS.values())
        if args.all
        else [NYC311_DATASETS[args.dataset]]
    )
    results = []
    for spec in specs:
        print(f"INGEST {spec.dataset_key}", file=sys.stderr)
        results.append(
            ingest_spec(
                spec, refresh=args.refresh, no_db=args.no_db, settings=settings
            )
        )
    print(json.dumps(results if args.all else results[0], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
