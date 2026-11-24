"""Acquire Phase 11 real evidence and run fresh external validation.

This script is intentionally non-destructive:
- an already-registered external dataset is never overwritten;
- acquisition failures are persisted as FAILED snapshots;
- a failed fetch never replaces the current validated assets;
- no model is activated, no pilot is approved, no resources are dispatched.
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import select

from app.auth.dependencies import AuthenticatedUser
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.evidence.acquisition import (
    AcquisitionError,
    acquire_infrastructure_source,
)
from app.evidence.external import (
    ExternalAcquisitionError,
    acquire_external_dataset,
)
from app.evidence.snapshots import verify_snapshot
from app.models import Profile, Role
from app.models.validation import ValidationDataset, ValidationExperiment
from app.validation.phase11 import PHASE11_DATASETS
from app.validation.service import run_risk_experiment


def _actor(session):
    profile = session.scalar(
        select(Profile).where(Profile.role == Role.ADMIN).limit(1)
    )
    if profile is None:
        profile = session.scalar(
            select(Profile).where(Profile.role == Role.WORKER).limit(1)
        )
    if profile is None:
        return None
    return AuthenticatedUser(
        subject=profile.id,
        email=None,
        profile=profile,
    )


def _verify(session, snapshot, actor):
    if snapshot is None or snapshot.status.value != "VALIDATED":
        return None
    if snapshot.verification_status.value == "AUTOMATED_RECOMPUTATION":
        return "ALREADY_RECOMPUTED"
    if actor is None:
        return "PENDING_NO_STAFF_IDENTITY"
    verify_snapshot(session, snapshot, actor)
    return "AUTOMATED_RECOMPUTATION"


def acquire_infrastructure(session, actor):
    try:
        snapshot, created = acquire_infrastructure_source(
            session, "nyc-dot-bridge-ratings", actor
        )
    except AcquisitionError as error:
        return {
            "status": "FAILED",
            "error": error.message,
            "failure_snapshot_persisted": True,
        }
    verified = _verify(session, snapshot, actor)
    return {
        "status": snapshot.status.value,
        "created": created,
        "snapshot_key": snapshot.snapshot_key,
        "snapshot_id": str(snapshot.id),
        "records": snapshot.record_count,
        "raw_records": snapshot.raw_record_count,
        "duplicate_count": snapshot.duplicate_count,
        "invalid_count": snapshot.invalid_count,
        "snapshot_sha256": snapshot.snapshot_sha256,
        "raw_sha256": snapshot.raw_sha256,
        "quality": snapshot.quality_status.value,
        "quality_checks": snapshot.quality_checks,
        "verification": verified,
        "data_period_end": (
            snapshot.data_period_end.isoformat()
            if snapshot.data_period_end
            else None
        ),
    }


def acquire_external(session, actor, settings):
    results = []
    for key, spec in PHASE11_DATASETS.items():
        try:
            payload = acquire_external_dataset(
                session, spec, settings=settings, actor_id=actor.profile.id if actor else None
            )
        except ExternalAcquisitionError as error:
            results.append({"dataset_key": key, "status": "FAILED", "error": str(error)})
            continue
        snapshot = payload["snapshot"]
        verified = _verify(session, snapshot, actor)
        results.append(
            {
                "dataset_key": key,
                "status": snapshot.status.value if snapshot else "MISSING",
                "created": payload["created"],
                "reason": payload.get("reason"),
                "snapshot_key": snapshot.snapshot_key if snapshot else None,
                "snapshot_id": str(snapshot.id) if snapshot else None,
                "records": snapshot.record_count if snapshot else None,
                "snapshot_sha256": snapshot.snapshot_sha256 if snapshot else None,
                "quality": snapshot.quality_status.value if snapshot else None,
                "verification": verified,
                "period_end": (
                    snapshot.data_period_end.isoformat()
                    if snapshot and snapshot.data_period_end
                    else None
                ),
            }
        )
    return results


def evaluate(session, actor, settings, dataset_keys):
    outcomes = []
    for key in dataset_keys:
        dataset = session.scalar(
            select(ValidationDataset).where(ValidationDataset.dataset_key == key)
        )
        if dataset is None:
            outcomes.append({"dataset_key": key, "status": "DATASET_MISSING"})
            continue
        if dataset.status.value != "VALIDATED":
            outcomes.append(
                {
                    "dataset_key": key,
                    "status": "DATASET_NOT_VALIDATED",
                    "quality": (dataset.dataset_metadata or {}).get(
                        "source_quality_status"
                    ),
                }
            )
            continue
        existing = session.scalar(
            select(ValidationExperiment)
            .where(
                ValidationExperiment.dataset_id == dataset.id,
                ValidationExperiment.experiment_type == "RISK_BACKTEST",
                ValidationExperiment.status == "COMPLETED",
            )
            .order_by(ValidationExperiment.created_at.desc())
            .limit(1)
        )
        if existing is not None:
            outcomes.append(
                {
                    "dataset_key": key,
                    "status": "ALREADY_EVALUATED",
                    "experiment_key": existing.experiment_key,
                    "config_hash": existing.config_hash,
                    "methods": (existing.metrics or {}).get("methods"),
                    "baselines": existing.baselines,
                }
            )
            continue
        experiment = run_risk_experiment(
            session,
            dataset,
            settings=settings,
            actor_id=actor.profile.id if actor else None,
        )
        outcomes.append(
            {
                "dataset_key": key,
                "status": experiment.status.value,
                "experiment_key": experiment.experiment_key,
                "config_hash": experiment.config_hash,
                "methods": (experiment.metrics or {}).get("methods"),
                "baselines": experiment.baselines,
                "findings": experiment.findings,
                "limitations": experiment.limitations,
            }
        )
    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-infrastructure", action="store_true")
    parser.add_argument("--skip-external", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    session = get_session_factory()()
    try:
        actor = _actor(session)
        output = {
            "actor": (
                {"id": str(actor.profile.id), "role": actor.profile.role.value}
                if actor
                else None
            ),
            "identity_note": (
                "Acquisition is attributable. Automated recomputation is not human "
                "verification of physical condition."
            ),
        }
        if not args.skip_infrastructure:
            output["infrastructure"] = acquire_infrastructure(session, actor)
        if not args.skip_external:
            output["external"] = acquire_external(session, actor, settings)
            if args.evaluate:
                output["evaluation"] = evaluate(
                    session, actor, settings, list(PHASE11_DATASETS)
                )
        print(json.dumps(output, indent=2, default=str))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
