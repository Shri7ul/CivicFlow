"""Deterministic, explicit development seed data.

No authentication users are created. Risk cells are intentionally omitted
because valid H3 identifiers/boundaries cannot be generated without the H3
engine introduced in a later phase.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import (
    AssetType,
    Department,
    DependencyEdge,
    DependencyType,
    InfrastructureAsset,
)

SEED_NAMESPACE = uuid.UUID("8b43a3b6-8f4e-4e8f-9f6f-2b7c4b6d5a10")


def _seed_id(kind: str, name: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"{kind}:{name}")


DEPARTMENTS = (
    ("Public Works", "Roads, civic facilities, and public infrastructure."),
    ("Drainage & Sanitation", "Drainage, waste, and sanitation response."),
    ("Emergency Services", "Emergency coordination and critical facilities."),
)

ASSETS = (
    {
        "key": "central-avenue",
        "name": "Central Avenue",
        "asset_type": AssetType.ROAD,
        "location": "LINESTRING(90.4125 23.8103, 90.4160 23.8120)",
        "criticality": 8.5,
        "metadata": {"seed": True, "lanes": 4},
    },
    {
        "key": "north-drain-main",
        "name": "North Drain Main",
        "asset_type": AssetType.DRAIN,
        "location": "LINESTRING(90.4080 23.8150, 90.4140 23.8175)",
        "criticality": 7.0,
        "metadata": {"seed": True, "capacity_class": "primary"},
    },
    {
        "key": "city-general-hospital",
        "name": "City General Hospital",
        "asset_type": AssetType.HOSPITAL,
        "location": "POINT(90.4070 23.8060)",
        "criticality": 10.0,
        "metadata": {"seed": True, "beds": 450},
    },
    {
        "key": "riverbank-shelter",
        "name": "Riverbank Shelter",
        "asset_type": AssetType.SHELTER,
        "location": "POINT(90.4210 23.8180)",
        "criticality": 9.0,
        "metadata": {"seed": True, "capacity": 300},
    },
    {
        "key": "central-fire-station",
        "name": "Central Fire Station",
        "asset_type": AssetType.FIRE_STATION,
        "location": "POINT(90.4135 23.8090)",
        "criticality": 9.5,
        "metadata": {"seed": True},
    },
)

DEPENDENCIES = (
    ("central-avenue", "city-general-hospital", DependencyType.SERVES, 0.9),
    ("north-drain-main", "central-avenue", DependencyType.PROTECTS, 0.8),
    ("riverbank-shelter", "city-general-hospital", DependencyType.DEPENDS_ON, 0.7),
)


@dataclass(frozen=True)
class SeedResult:
    departments_created: int
    assets_created: int
    dependencies_created: int


def seed_development_data(session: Session) -> SeedResult:
    """Insert deterministic seed rows without overwriting existing data."""
    departments_created = 0
    assets_created = 0
    dependencies_created = 0

    department_ids: dict[str, uuid.UUID] = {}
    for name, description in DEPARTMENTS:
        existing = session.scalar(
            select(Department).where(func.lower(Department.name) == name.lower())
        )
        if existing is not None:
            department_ids[name] = existing.id
            continue
        department = Department(
            id=_seed_id("department", name),
            name=name,
            description=description,
            is_active=True,
        )
        session.add(department)
        department_ids[name] = department.id
        departments_created += 1

    asset_ids: dict[str, uuid.UUID] = {}
    for asset in ASSETS:
        asset_id = _seed_id("asset", asset["key"])
        asset_ids[asset["key"]] = asset_id
        if session.get(InfrastructureAsset, asset_id) is not None:
            continue
        session.add(
            InfrastructureAsset(
                id=asset_id,
                name=asset["name"],
                asset_type=asset["asset_type"],
                location=asset["location"],
                criticality_score=asset["criticality"],
                is_active=True,
                metadata_json=dict(asset["metadata"]),
            )
        )
        assets_created += 1

    for source_key, target_key, dependency_type, strength in DEPENDENCIES:
        edge_id = _seed_id("dependency", f"{source_key}:{target_key}:{dependency_type.value}")
        if session.get(DependencyEdge, edge_id) is not None:
            continue
        session.add(
            DependencyEdge(
                id=edge_id,
                source_asset_id=asset_ids[source_key],
                target_asset_id=asset_ids[target_key],
                dependency_type=dependency_type,
                strength=strength,
                description="Deterministic development seed dependency.",
            )
        )
        dependencies_created += 1

    session.commit()
    return SeedResult(
        departments_created=departments_created,
        assets_created=assets_created,
        dependencies_created=dependencies_created,
    )


def main() -> None:
    settings = get_settings()
    if settings.is_production:
        raise SystemExit("Refusing to seed a production environment.")
    session = get_session_factory()()
    try:
        result = seed_development_data(session)
    finally:
        session.close()
    print(
        "Seed complete: "
        f"{result.departments_created} departments, "
        f"{result.assets_created} assets, "
        f"{result.dependencies_created} dependencies created."
    )


if __name__ == "__main__":
    main()
