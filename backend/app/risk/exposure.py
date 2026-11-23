"""Infrastructure proximity and inferred exposure for risk cells."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from app.models import AssetType
from app.risk.geo import geometry_distance_m

TYPE_EXPOSURE_WEIGHTS: dict[AssetType, float] = {
    AssetType.HOSPITAL: 1.0,
    AssetType.FIRE_STATION: 0.95,
    AssetType.SHELTER: 0.85,
    AssetType.WATER_FACILITY: 0.90,
    AssetType.POWER_FACILITY: 0.90,
    AssetType.DRAIN: 0.80,
    AssetType.ROAD: 0.70,
    AssetType.SCHOOL: 0.60,
    AssetType.OTHER: 0.40,
}


@dataclass(frozen=True)
class RiskAsset:
    id: UUID
    name: str
    asset_type: AssetType
    criticality_score: float
    geometry_wkt: str
    source: str | None
    metadata: dict


@dataclass(frozen=True)
class AssetExposureItem:
    id: UUID
    name: str
    asset_type: str
    criticality_score: float
    distance_m: float
    dependency_count: int
    source: str | None


@dataclass(frozen=True)
class InfrastructureExposure:
    normalized: float | None
    available: bool
    explanation: str
    items: tuple[AssetExposureItem, ...]
    nearby_asset_count: int
    by_type: dict[str, int]
    dependency_count: int
    dataset: dict


def compute_exposure(
    *,
    latitude: float,
    longitude: float,
    assets: Iterable[RiskAsset],
    dependency_counts: dict[UUID, int],
    radius_m: int,
) -> InfrastructureExposure:
    asset_list = list(assets)
    authoritative = sum(
        1 for asset in asset_list if asset.metadata.get("authoritative") is True
    )
    development = len(asset_list) - authoritative
    dataset = {
        "active_asset_count": len(asset_list),
        "authoritative_asset_count": authoritative,
        "development_or_unknown_asset_count": development,
        "is_authoritative": authoritative > 0 and authoritative == len(asset_list),
    }
    if not asset_list:
        return InfrastructureExposure(
            normalized=None,
            available=False,
            explanation=(
                "No active infrastructure asset dataset is available; the "
                "infrastructure factor is excluded and remaining weights are "
                "renormalized."
            ),
            items=(),
            nearby_asset_count=0,
            by_type={},
            dependency_count=0,
            dataset=dataset,
        )

    nearby: list[tuple[RiskAsset, float]] = []
    for asset in asset_list:
        try:
            distance = geometry_distance_m(
                latitude, longitude, asset.geometry_wkt
            )
        except ValueError:
            continue
        if distance <= radius_m:
            nearby.append((asset, distance))
    nearby.sort(key=lambda item: item[1])
    by_type = dict(Counter(asset.asset_type.value for asset, _ in nearby))
    dependency_count = sum(
        dependency_counts.get(asset.id, 0) for asset, _ in nearby
    )
    weighted = sum(
        (max(0.0, min(10.0, asset.criticality_score)) / 10.0)
        * TYPE_EXPOSURE_WEIGHTS.get(asset.asset_type, 0.4)
        for asset, _ in nearby
    )
    normalized = min(1.0, weighted / 2.5)
    items = tuple(
        AssetExposureItem(
            id=asset.id,
            name=asset.name,
            asset_type=asset.asset_type.value,
            criticality_score=round(asset.criticality_score, 2),
            distance_m=round(distance, 1),
            dependency_count=dependency_counts.get(asset.id, 0),
            source=asset.source,
        )
        for asset, distance in nearby[:8]
    )
    if not nearby:
        explanation = (
            f"No active infrastructure assets are within {radius_m} m of the "
            "cell centre; observed incident activity is unaffected."
        )
    else:
        qualifier = (
            "authoritative"
            if dataset["is_authoritative"]
            else "development/unknown-provenance"
        )
        explanation = (
            f"{len(nearby)} active asset(s) within {radius_m} m "
            f"({qualifier} dataset); weighted criticality and type exposure "
            f"normalises to {normalized:.2f}. This is geospatial association, "
            "not confirmed service impact."
        )
    return InfrastructureExposure(
        normalized=round(normalized, 4),
        available=True,
        explanation=explanation,
        items=items,
        nearby_asset_count=len(nearby),
        by_type=by_type,
        dependency_count=dependency_count,
        dataset=dataset,
    )
