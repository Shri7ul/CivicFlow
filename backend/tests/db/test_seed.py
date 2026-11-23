"""Seed determinism and idempotency tests."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Department,
    DependencyEdge,
    InfrastructureAsset,
    Profile,
    RiskCell,
)
from app.seed import seed_development_data


def test_seed_is_deterministic_and_idempotent(db_session: Session) -> None:
    first = seed_development_data(db_session)
    assert first.departments_created == 3
    assert first.assets_created == 5
    assert first.dependencies_created == 3

    counts_before = {
        "departments": db_session.scalar(select(func.count()).select_from(Department)),
        "assets": db_session.scalar(
            select(func.count()).select_from(InfrastructureAsset)
        ),
        "dependencies": db_session.scalar(
            select(func.count()).select_from(DependencyEdge)
        ),
    }
    assert counts_before == {"departments": 3, "assets": 5, "dependencies": 3}

    second = seed_development_data(db_session)
    assert second.departments_created == 0
    assert second.assets_created == 0
    assert second.dependencies_created == 0

    counts_after = {
        "departments": db_session.scalar(select(func.count()).select_from(Department)),
        "assets": db_session.scalar(
            select(func.count()).select_from(InfrastructureAsset)
        ),
        "dependencies": db_session.scalar(
            select(func.count()).select_from(DependencyEdge)
        ),
    }
    assert counts_after == counts_before


def test_seed_does_not_create_users_or_risk_cells(db_session: Session) -> None:
    seed_development_data(db_session)
    assert db_session.scalar(select(func.count()).select_from(Profile)) == 0
    assert db_session.scalar(select(func.count()).select_from(RiskCell)) == 0


def test_seed_does_not_overwrite_user_modified_seed_rows(db_session: Session) -> None:
    seed_development_data(db_session)
    asset = db_session.scalar(
        select(InfrastructureAsset).where(InfrastructureAsset.name == "Central Avenue")
    )
    assert asset is not None
    asset.description = "User-edited description"
    db_session.commit()

    seed_development_data(db_session)
    db_session.refresh(asset)
    assert asset.description == "User-edited description"
