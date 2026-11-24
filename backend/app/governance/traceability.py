"""Read-only traceability for persisted risk assessments."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.governance.errors import GovernanceError
from app.governance.serialization import iso, number, serialize_review_event
from app.models.enums import RiskReviewStatus
from app.models.operations import ModelVersion
from app.models.pilot import Pilot, RiskReviewCase, RiskReviewEvent
from app.models.risk import RiskCellSnapshot, RiskModelRun


def get_run(session: Session, run_id: uuid.UUID) -> RiskModelRun:
    run = session.get(RiskModelRun, run_id)
    if run is None:
        raise GovernanceError(
            "Risk run not found", status_code=404, code="risk_run_not_found"
        )
    return run


def list_runs(session: Session, limit: int) -> list[dict]:
    runs = session.scalars(
        select(RiskModelRun).order_by(RiskModelRun.calculated_at.desc()).limit(limit)
    ).all()
    counts = dict(
        session.execute(
            select(RiskReviewCase.run_id, func.count(RiskReviewCase.id))
            .where(RiskReviewCase.run_id.in_([item.id for item in runs]))
            .group_by(RiskReviewCase.run_id)
        ).all()
    ) if runs else {}
    final_statuses = (
        RiskReviewStatus.ACCEPTED,
        RiskReviewStatus.REJECTED,
        RiskReviewStatus.NEEDS_INVESTIGATION,
        RiskReviewStatus.NEEDS_MORE_DATA,
    )
    reviewed_counts = dict(
        session.execute(
            select(RiskReviewCase.run_id, func.count(RiskReviewCase.id))
            .where(
                RiskReviewCase.run_id.in_([item.id for item in runs]),
                RiskReviewCase.status.in_(final_statuses),
            )
            .group_by(RiskReviewCase.run_id)
        ).all()
    ) if runs else {}
    return [
        {
            "id": str(run.id),
            "model_version": run.model_version,
            "config_hash": run.config_hash,
            "resolution": run.resolution,
            "window_hours": run.window_hours,
            "window_start": iso(run.window_start),
            "window_end": iso(run.window_end),
            "calculated_at": iso(run.calculated_at),
            "incident_count": run.incident_count,
            "cell_count": run.cell_count,
            "duration_ms": run.duration_ms,
            "review_cases": int(counts.get(run.id, 0)),
            "reviewed_cases": int(reviewed_counts.get(run.id, 0)),
        }
        for run in runs
    ]


def _model_version(session: Session, version: str) -> ModelVersion | None:
    return session.scalar(
        select(ModelVersion)
        .where(ModelVersion.model_name == "risk", ModelVersion.version == version)
        .order_by(ModelVersion.created_at.desc())
        .limit(1)
    )


def _active_model_version(session: Session) -> ModelVersion | None:
    return session.scalar(
        select(ModelVersion).where(
            ModelVersion.model_name == "risk", ModelVersion.is_active.is_(True)
        )
    )


def _factor_summary(cells: list[RiskCellSnapshot]) -> list[dict]:
    rows: dict[str, dict] = {}
    for cell in cells:
        for factor in cell.factor_contributions or []:
            key = str(factor.get("key") or "unknown")
            row = rows.setdefault(
                key,
                {
                    "key": key,
                    "label": factor.get("label") or key,
                    "cells_present": 0,
                    "cells_available": 0,
                    "contribution_sum": 0.0,
                    "contribution_min": None,
                    "contribution_max": None,
                    "last_explanation": None,
                },
            )
            row["cells_present"] += 1
            if factor.get("available"):
                row["cells_available"] += 1
            contribution = factor.get("contribution")
            if contribution is not None:
                value = float(contribution)
                row["contribution_sum"] += value
                row["contribution_min"] = (
                    value
                    if row["contribution_min"] is None
                    else min(row["contribution_min"], value)
                )
                row["contribution_max"] = (
                    value
                    if row["contribution_max"] is None
                    else max(row["contribution_max"], value)
                )
            if factor.get("explanation"):
                row["last_explanation"] = factor["explanation"]
    payload = []
    for row in rows.values():
        present = row.pop("cells_present")
        available = row.pop("cells_available")
        total = row.pop("contribution_sum")
        payload.append(
            {
                **row,
                "cells_present": present,
                "available_share": round(available / present, 4) if present else None,
                "mean_contribution": round(total / present, 6) if present else None,
            }
        )
    payload.sort(key=lambda item: item["key"])
    return payload


def build_trace(
    session: Session,
    run_id: uuid.UUID,
    *,
    cell_id: uuid.UUID | None = None,
    cell_limit: int = 50,
    include_cells: bool = True,
) -> dict:
    run = get_run(session, run_id)
    total_cells = int(
        session.scalar(
            select(func.count())
            .select_from(RiskCellSnapshot)
            .where(RiskCellSnapshot.run_id == run.id)
        )
        or 0
    )
    selected_cell: RiskCellSnapshot | None = None
    if cell_id is not None:
        selected_cell = session.get(RiskCellSnapshot, cell_id)
        if selected_cell is None or selected_cell.run_id != run.id:
            raise GovernanceError(
                "Risk cell not found in this run",
                status_code=404,
                code="risk_cell_not_found",
            )
    cell_query = select(RiskCellSnapshot).where(RiskCellSnapshot.run_id == run.id)
    if selected_cell is not None:
        cell_query = cell_query.where(RiskCellSnapshot.id == selected_cell.id)
    else:
        cell_query = cell_query.order_by(
            RiskCellSnapshot.risk_score.desc(), RiskCellSnapshot.h3_cell_id
        ).limit(cell_limit if include_cells else 0)
    cells = list(session.scalars(cell_query).all())
    version = _model_version(session, run.model_version)
    active = _active_model_version(session)
    config_found = version is not None
    active_matches = bool(
        active and active.version == run.model_version and active.config_hash == run.config_hash
    )
    case_query = select(RiskReviewCase).where(RiskReviewCase.run_id == run.id)
    if selected_cell is not None:
        case_query = case_query.where(RiskReviewCase.cell_id == selected_cell.id)
    cases = list(session.scalars(case_query.order_by(RiskReviewCase.created_at)).all())
    events: dict[uuid.UUID, list[RiskReviewEvent]] = defaultdict(list)
    if cases:
        for event in session.scalars(
            select(RiskReviewEvent)
            .where(RiskReviewEvent.case_id.in_([item.id for item in cases]))
            .order_by(RiskReviewEvent.created_at)
        ).all():
            events[event.case_id].append(event)
    pilots: dict[uuid.UUID, Pilot] = {}
    for pilot_id in {case.pilot_id for case in cases if case.pilot_id}:
        pilot = session.get(Pilot, pilot_id)
        if pilot is not None:
            pilots[pilot_id] = pilot
    review_counts = Counter(case.status.value for case in cases)
    reviewer_emails = sorted(
        {
            event.actor_email
            for rows in events.values()
            for event in rows
            if event.actor_email
        }
    )
    source_datasets = []
    query_parameters = run.query_parameters or {}
    dataset_key = query_parameters.get("dataset_key") if isinstance(query_parameters, dict) else None
    if dataset_key:
        source_datasets.append(str(dataset_key))
    missing = []
    if not config_found:
        missing.append("Registered model_versions row for this model version was not found.")
    if not source_datasets:
        missing.append(
            "The risk run does not persist the source dataset or ingestion snapshot identifiers."
        )
    if not cases:
        missing.append("No human review cases exist for this assessment.")
    return {
        "protocol": "phase10-risk-trace-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "exportable": True,
        "read_only": True,
        "assessment": {
            "id": str(run.id),
            "model_version": run.model_version,
            "config_hash": run.config_hash,
            "resolution": run.resolution,
            "window_hours": run.window_hours,
            "window_start": iso(run.window_start),
            "window_end": iso(run.window_end),
            "calculated_at": iso(run.calculated_at),
            "duration_ms": run.duration_ms,
            "incident_count": run.incident_count,
            "cell_count": run.cell_count,
            "requested_by": str(run.requested_by) if run.requested_by else None,
            "query_parameters": query_parameters,
            "summary": run.summary or {},
            "reproducible": config_found and bool(run.config_hash),
        },
        "model_configuration": {
            "found": config_found,
            "model_name": "risk",
            "version": run.model_version,
            "config_hash_matches": (
                version.config_hash == run.config_hash if version else None
            ),
            "config": version.config if version else None,
            "description": version.description if version else None,
            "registered_at": iso(version.created_at) if version else None,
            "active_version": active.version if active else None,
            "active_config_hash": active.config_hash if active else None,
            "active_matches_run": active_matches,
            "activation_changed": False,
            "note": (
                "This endpoint reads the registry only. It never activates, "
                "deactivates, or rewrites a model configuration."
            ),
        },
        "inputs": {
            "window_start": iso(run.window_start),
            "window_end": iso(run.window_end),
            "resolution": run.resolution,
            "query_parameters": query_parameters,
            "incident_count": run.incident_count,
            "cell_count": run.cell_count,
            "source_datasets": source_datasets,
            "source_lineage_complete": bool(source_datasets),
        },
        "spatial_units": {
            "resolution": run.resolution,
            "total_cells": total_cells,
            "returned_cells": len(cells),
            "truncated": selected_cell is None and total_cells > len(cells),
            "cells": [
                {
                    "id": str(cell.id),
                    "h3_cell_id": cell.h3_cell_id,
                    "risk_score": number(cell.risk_score),
                    "risk_category": cell.risk_category,
                    "confidence": number(cell.confidence),
                    "calculated_at": iso(cell.calculated_at),
                }
                for cell in cells
            ],
        },
        "factor_contributions": _factor_summary(cells),
        "reviews": {
            "case_count": len(cases),
            "status_counts": dict(review_counts),
            "reviewers": reviewer_emails,
            "cases": [
                {
                    "id": str(case.id),
                    "cell_id": str(case.cell_id),
                    "pilot_id": str(case.pilot_id) if case.pilot_id else None,
                    "pilot": (
                        {
                            "id": str(pilots[case.pilot_id].id),
                            "name": pilots[case.pilot_id].name,
                            "status": pilots[case.pilot_id].status.value,
                            "mode": pilots[case.pilot_id].mode.value,
                        }
                        if case.pilot_id in pilots
                        else None
                    ),
                    "status": case.status.value,
                    "assigned_reviewer_id": (
                        str(case.assigned_reviewer_id)
                        if case.assigned_reviewer_id
                        else None
                    ),
                    "events": [
                        serialize_review_event(event)
                        for event in events.get(case.id, [])
                    ],
                }
                for case in cases
            ],
            "review_decision_distinct_from_prediction": True,
            "note": (
                "Review statuses are human judgments. They never modify the "
                "persisted model score, factors, or configuration."
            ),
        },
        "provenance": {
            "complete": not missing,
            "missing": missing,
            "model_configuration_linked": config_found,
            "dataset_lineage_linked": bool(source_datasets),
            "human_review_linked": bool(cases),
        },
        "limitations": [
            "Risk scores are model outputs and are not verified hazards.",
            "Incident-level lineage is limited to the persisted run parameters.",
            "A missing review is not evidence that the score is correct.",
        ],
    }
