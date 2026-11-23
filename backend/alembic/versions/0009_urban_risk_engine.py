"""Phase 5 urban risk engine persistence and staff-only RLS.

Revision ID: 0009_urban_risk_engine
Revises: 0008_confidence_check_name
Create Date: 2026-11-24

Risk calculations are normally computed on demand. WORKER/ADMIN users may
persist an explicit run for audit/history; snapshots retain the exact model
version, configuration hash, window, and H3 resolution used.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.base import geometry_type, jsonb_column_type

revision: str = "0009_urban_risk_engine"
down_revision: Union[str, None] = "0008_confidence_check_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RISK_CATEGORIES = "'MINIMAL', 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'"


def upgrade() -> None:
    op.create_table(
        "risk_model_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("resolution", sa.SmallInteger(), nullable=False),
        sa.Column("window_hours", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "query_parameters",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("incident_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cell_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "summary",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "resolution >= 5 AND resolution <= 12", name="run_resolution_range"
        ),
        sa.CheckConstraint("window_hours >= 1", name="run_window_positive"),
        sa.CheckConstraint(
            "cell_count >= 0", name="run_cell_count_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["profiles.id"],
            name="fk_risk_model_runs_requested_by_profiles",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_model_runs"),
    )
    op.create_index("ix_risk_model_runs_calculated_at", "risk_model_runs", ["calculated_at"])
    op.create_index("ix_risk_model_runs_model_version", "risk_model_runs", ["model_version"])
    op.create_index("ix_risk_model_runs_requested_by", "risk_model_runs", ["requested_by"])

    op.create_table(
        "risk_cell_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("h3_cell_id", sa.String(length=32), nullable=False),
        sa.Column("resolution", sa.SmallInteger(), nullable=False),
        sa.Column("boundary", geometry_type("POLYGON"), nullable=False),
        sa.Column("risk_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column(
            "incident_activity_score",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
        ),
        sa.Column("risk_category", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("incident_count", sa.Integer(), nullable=False),
        sa.Column("active_count", sa.Integer(), nullable=False),
        sa.Column("adjusted_incident_count", sa.Integer(), nullable=False),
        sa.Column(
            "severity_distribution",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "category_distribution",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "factor_contributions",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "available_factors",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "infrastructure_exposure",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "trend",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "resolution >= 5 AND resolution <= 12",
            name="snapshot_resolution_range",
        ),
        sa.CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100",
            name="snapshot_score_range",
        ),
        sa.CheckConstraint(
            "incident_activity_score >= 0 AND incident_activity_score <= 100",
            name="snapshot_activity_score_range",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="snapshot_confidence_range",
        ),
        sa.CheckConstraint(
            "incident_count >= 0", name="snapshot_incident_count_nonnegative"
        ),
        sa.CheckConstraint(
            f"risk_category IN ({RISK_CATEGORIES})",
            name="snapshot_risk_category",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["risk_model_runs.id"],
            name="fk_risk_cell_snapshots_run_id_risk_model_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_cell_snapshots"),
        sa.UniqueConstraint(
            "run_id", "h3_cell_id", name="snapshot_run_cell_unique"
        ),
    )
    op.create_index(
        "ix_risk_cell_snapshots_run_score", "risk_cell_snapshots", ["run_id", "risk_score"]
    )
    op.create_index(
        "ix_risk_cell_snapshots_h3_cell_id", "risk_cell_snapshots", ["h3_cell_id"]
    )
    op.create_index(
        "ix_risk_cell_snapshots_resolution", "risk_cell_snapshots", ["resolution"]
    )
    op.create_index(
        "ix_risk_cell_snapshots_boundary_gist",
        "risk_cell_snapshots",
        ["boundary"],
        postgresql_using="gist",
    )

    if op.get_bind().dialect.name != "postgresql":
        return
    for table in ("risk_model_runs", "risk_cell_snapshots"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE public.{table} "
            "FROM anon, authenticated"
        )
        op.execute(
            f"GRANT SELECT ON TABLE public.{table} TO authenticated"
        )
    op.execute(
        """
        CREATE POLICY risk_model_runs_read_staff
        ON public.risk_model_runs
        FOR SELECT
        TO authenticated
        USING (public.is_worker_or_admin())
        """
    )
    op.execute(
        """
        CREATE POLICY risk_cell_snapshots_read_staff
        ON public.risk_cell_snapshots
        FOR SELECT
        TO authenticated
        USING (public.is_worker_or_admin())
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP POLICY IF EXISTS risk_cell_snapshots_read_staff "
            "ON public.risk_cell_snapshots"
        )
        op.execute(
            "DROP POLICY IF EXISTS risk_model_runs_read_staff "
            "ON public.risk_model_runs"
        )
    op.drop_index("ix_risk_cell_snapshots_boundary_gist", table_name="risk_cell_snapshots")
    op.drop_index("ix_risk_cell_snapshots_resolution", table_name="risk_cell_snapshots")
    op.drop_index("ix_risk_cell_snapshots_h3_cell_id", table_name="risk_cell_snapshots")
    op.drop_index("ix_risk_cell_snapshots_run_score", table_name="risk_cell_snapshots")
    op.drop_table("risk_cell_snapshots")
    op.drop_index("ix_risk_model_runs_requested_by", table_name="risk_model_runs")
    op.drop_index("ix_risk_model_runs_model_version", table_name="risk_model_runs")
    op.drop_index("ix_risk_model_runs_calculated_at", table_name="risk_model_runs")
    op.drop_table("risk_model_runs")
