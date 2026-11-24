"""Database-backed registry of geographic contexts.

The Python registry in ``app.geo.contexts`` remains the authoritative
definition; this table persists a readable, API-visible copy seeded by
migration 0023. It is never used to relabel historical evidence.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, jsonb_column_type


class GeographicContextRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "geographic_contexts"
    __table_args__ = (
        UniqueConstraint("context_key", name="uq_geographic_contexts_key"),
        Index("ix_geographic_contexts_country", "country_code"),
    )

    context_key: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False)
    country_name: Mapped[str] = mapped_column(String(120), nullable=False)
    context_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    bbox_geojson: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict
    )
    center_geojson: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict
    )
    crs: Mapped[str] = mapped_column(String(40), nullable=False)
    provenance_basis: Mapped[str] = mapped_column(Text, nullable=False)
    boundary_basis: Mapped[str] = mapped_column(Text, nullable=False)
    boundary_status: Mapped[str] = mapped_column(String(32), nullable=False)
    operational_authority: Mapped[str | None] = mapped_column(String(240), nullable=True)
    is_pilot_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_urls: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
