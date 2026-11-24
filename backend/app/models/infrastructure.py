"""Infrastructure assets and dependency edges."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    geometry_type,
    jsonb_column_type,
)
from app.models.enums import AssetType, DependencyType
from app.models.types import enum_column


class InfrastructureAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "infrastructure_assets"
    __table_args__ = (
        CheckConstraint(
            "criticality_score >= 0 AND criticality_score <= 10",
            name="criticality_score_range",
        ),
        Index("ix_infrastructure_assets_name", "name"),
        Index("ix_infrastructure_assets_asset_type", "asset_type"),
        Index("ix_infrastructure_assets_is_active", "is_active"),
        UniqueConstraint(
            "source_id", "external_id", name="uq_infrastructure_assets_source_external"
        ),
        Index("ix_infrastructure_assets_source", "source_id"),
        Index("ix_infrastructure_assets_snapshot", "snapshot_id"),
        Index(
            "ix_infrastructure_assets_location_gist",
            "location",
            postgresql_using="gist",
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        enum_column(AssetType, "asset_type"), nullable=False
    )
    # Generic GEOMETRY supports point facilities, line roads/drains, and
    # polygon compounds without forcing every object into a point.
    location: Mapped[str] = mapped_column(
        geometry_type("GEOMETRY"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    criticality_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("true")
    )
    # PostgreSQL column name is "metadata"; the Python attribute avoids the
    # reserved DeclarativeBase.metadata name.
    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        jsonb_column_type(),
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("infrastructure_sources.id", ondelete="RESTRICT"),
        nullable=True,
    )
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    outgoing_dependencies: Mapped[list["DependencyEdge"]] = relationship(
        back_populates="source_asset",
        foreign_keys="DependencyEdge.source_asset_id",
    )
    incoming_dependencies: Mapped[list["DependencyEdge"]] = relationship(
        back_populates="target_asset",
        foreign_keys="DependencyEdge.target_asset_id",
    )


class DependencyEdge(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "dependency_edges"
    __table_args__ = (
        CheckConstraint(
            "source_asset_id <> target_asset_id", name="no_self_dependency"
        ),
        CheckConstraint(
            "strength >= 0 AND strength <= 1", name="strength_range"
        ),
        UniqueConstraint(
            "source_asset_id",
            "target_asset_id",
            "dependency_type",
            name="dependency_logical_unique",
        ),
        Index("ix_dependency_edges_source_asset_id", "source_asset_id"),
        Index("ix_dependency_edges_target_asset_id", "target_asset_id"),
        Index("ix_dependency_edges_dependency_type", "dependency_type"),
    )

    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("infrastructure_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("infrastructure_assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dependency_type: Mapped[DependencyType] = mapped_column(
        enum_column(DependencyType, "dependency_type"), nullable=False
    )
    strength: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("1.0")
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    source_asset: Mapped["InfrastructureAsset"] = relationship(
        back_populates="outgoing_dependencies",
        foreign_keys=[source_asset_id],
    )
    target_asset: Mapped["InfrastructureAsset"] = relationship(
        back_populates="incoming_dependencies",
        foreign_keys=[target_asset_id],
    )
