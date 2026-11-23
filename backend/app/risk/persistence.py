"""Explicit persistence for staff-triggered risk runs."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RiskCellSnapshot, RiskModelRun
from app.risk.engine import RiskComputation


def persist_run(
    session: Session,
    *,
    computation: RiskComputation,
    requested_by: UUID,
    summary: dict,
) -> RiskModelRun:
    run = RiskModelRun(
        model_version=computation.config.model_version,
        config_hash=computation.config.config_hash,
        resolution=computation.query.resolution,
        window_hours=computation.query.window_hours,
        window_start=computation.window_start,
        window_end=computation.window_end,
        query_parameters={
            "bbox": computation.query.bbox,
            "limit": computation.query.limit,
            "offset": computation.query.offset,
        },
        incident_count=len(computation.current_incidents),
        cell_count=len(computation.cells),
        duration_ms=computation.duration_ms,
        summary=summary,
        requested_by=requested_by,
        calculated_at=computation.generated_at,
    )
    session.add(run)
    session.flush()
    for cell in computation.cells:
        session.add(
            RiskCellSnapshot(
                run_id=run.id,
                h3_cell_id=cell.h3_cell_id,
                resolution=cell.resolution,
                boundary=cell.boundary_wkt,
                risk_score=cell.risk_score,
                incident_activity_score=cell.incident_activity_score,
                risk_category=cell.risk_category,
                confidence=cell.confidence,
                incident_count=cell.incident_count,
                active_count=cell.active_count,
                adjusted_incident_count=cell.adjusted_incident_count,
                severity_distribution=cell.severity_distribution,
                category_distribution=cell.category_distribution,
                factor_contributions=[asdict(factor) for factor in cell.factors],
                available_factors={
                    "keys": [
                        factor.key for factor in cell.factors if factor.available
                    ],
                    "availability": round(
                        sum(factor.weight for factor in cell.factors if factor.available),
                        4,
                    ),
                },
                infrastructure_exposure={
                    "normalized": cell.infrastructure.normalized,
                    "available": cell.infrastructure.available,
                    "nearby_asset_count": cell.infrastructure.nearby_asset_count,
                    "by_type": cell.infrastructure.by_type,
                    "dependency_count": cell.infrastructure.dependency_count,
                    "dataset": cell.infrastructure.dataset,
                },
                trend=asdict(cell.trend),
                model_version=cell.model_version,
                config_hash=cell.config_hash,
                calculated_at=computation.generated_at,
            )
        )
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(run)
    return run


def list_runs(session: Session, *, limit: int = 50) -> list[RiskModelRun]:
    return list(
        session.scalars(
            select(RiskModelRun)
            .order_by(RiskModelRun.calculated_at.desc())
            .limit(limit)
        ).all()
    )
