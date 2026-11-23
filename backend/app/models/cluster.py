"""Incident clustering schema foundations (no clustering engine)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    point_geography_type,
)
from app.models.enums import ClusterStatus, IncidentCategory
from app.models.types import enum_column


class IncidentCluster(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incident_clusters"
    __table_args__ = (
        Index("ix_incident_clusters_category", "category"),
        Index("ix_incident_clusters_status", "status"),
        Index(
            "ix_incident_clusters_centroid_gist",
            "centroid",
            postgresql_using="gist",
        ),
    )

    category: Mapped[IncidentCategory] = mapped_column(
        enum_column(IncidentCategory, "cluster_category"), nullable=False
    )
    centroid: Mapped[str] = mapped_column(
        point_geography_type(), nullable=False
    )
    status: Mapped[ClusterStatus] = mapped_column(
        enum_column(ClusterStatus, "cluster_status"),
        nullable=False,
        server_default=ClusterStatus.ACTIVE.value,
    )

    members: Mapped[list["IncidentClusterMember"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )


class IncidentClusterMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "incident_cluster_members"
    __table_args__ = (
        UniqueConstraint(
            "cluster_id", "incident_id", name="cluster_incident_unique"
        ),
        # Phase 1 policy: an incident belongs to at most one active cluster.
        UniqueConstraint("incident_id", name="incident_single_cluster"),
        Index("ix_incident_cluster_members_cluster_id", "cluster_id"),
        Index("ix_incident_cluster_members_incident_id", "incident_id"),
    )

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incident_clusters.id", ondelete="CASCADE"),
        nullable=False,
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    cluster: Mapped["IncidentCluster"] = relationship(back_populates="members")
    incident: Mapped["Incident"] = relationship(
        back_populates="cluster_membership"
    )
