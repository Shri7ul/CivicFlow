"""Read-only infrastructure reference endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, require_active_user
from app.db.session import get_db_session
from app.models import AssetType
from app.schemas.intelligence import InfrastructureAssetResponse
from app.services.intelligence import list_infrastructure_assets

router = APIRouter()


@router.get(
    "/assets",
    response_model=list[InfrastructureAssetResponse],
    summary="List active infrastructure assets",
)
def infrastructure_assets(
    user: Annotated[AuthenticatedUser, Depends(require_active_user)],
    session: Annotated[Session, Depends(get_db_session)],
    asset_type: AssetType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[InfrastructureAssetResponse]:
    del user
    assets = list_infrastructure_assets(
        session,
        asset_type=asset_type.value if asset_type else None,
        limit=limit,
    )
    return [
        InfrastructureAssetResponse(
            id=asset.id,
            name=asset.name,
            asset_type=asset.asset_type.value,
            location_wkt=asset.location,
            description=asset.description,
            criticality_score=float(asset.criticality_score),
            is_active=asset.is_active,
            metadata=asset.metadata_json or {},
        )
        for asset in assets
    ]
