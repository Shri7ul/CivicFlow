"""Phase 8 empirical validation datasets and experiment records.

Revision ID: 0016_validation_workspace
Revises: 0015_ingested_provenance
Create Date: 2026-11-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_validation_workspace"
down_revision: Union[str, None] = "0015_ingested_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PHASE8_TABLES = ("validation_datasets", "validation_experiments")


def _json() -> sa.TypeEngine:
    return sa.JSON().with_variant(
        postgresql.JSONB(astext_type=sa.Text()), "postgresql"
    )


def _enable_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in PHASE8_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE public.{table} "
            "FROM anon, authenticated"
        )
        op.execute(f"GRANT SELECT ON TABLE public.{table} TO authenticated")
        op.execute(
            f"CREATE POLICY {table}_read_staff ON public.{table} "
            "FOR SELECT TO authenticated USING (public.is_worker_or_admin())"
        )


def upgrade() -> None:
    op.create_table(
        "validation_datasets",
        sa.Column("dataset_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=False),
        sa.Column("region", sa.String(length=200), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("snapshot_path", sa.String(length=1000), nullable=True),
        sa.Column(
            "record_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "REGISTERED",
                "VALIDATED",
                "INSUFFICIENT",
                name="validation_dataset_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="REGISTERED",
            nullable=False,
        ),
        sa.Column(
            "dataset_metadata",
            _json(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "record_count >= 0",
            name=op.f("ck_validation_datasets_ck_validation_datasets_count"),
        ),
        sa.CheckConstraint(
            "period_start IS NULL OR period_end IS NULL OR period_end >= period_start",
            name=op.f("ck_validation_datasets_ck_validation_datasets_period"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.id"],
            name=op.f("fk_validation_datasets_created_by_profiles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name=op.f(
                "fk_validation_datasets_ingestion_run_id_ingestion_runs"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["data_sources.id"],
            name=op.f("fk_validation_datasets_source_id_data_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_validation_datasets")),
        sa.UniqueConstraint("dataset_key", name="uq_validation_datasets_key"),
    )
    op.create_index(
        "ix_validation_datasets_source",
        "validation_datasets",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_validation_datasets_status",
        "validation_datasets",
        ["status"],
        unique=False,
    )

    op.create_table(
        "validation_experiments",
        sa.Column("experiment_key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=True),
        sa.Column("dataset_version", sa.String(length=160), nullable=True),
        sa.Column(
            "dataset_snapshot_sha256", sa.String(length=64), nullable=True
        ),
        sa.Column(
            "experiment_type",
            sa.Enum(
                "RISK_BACKTEST",
                "RISK_SENSITIVITY",
                "CORRELATION_SYNTHETIC",
                "DECISION_SIMULATION",
                name="validation_experiment_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "evidence_kind",
            sa.Enum(
                "EMPIRICAL_OBSERVATIONAL",
                "SYNTHETIC_FIXTURE",
                "SIMULATED_PLANNING",
                name="validation_evidence_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "RUNNING",
                "COMPLETED",
                "INSUFFICIENT_DATA",
                "FAILED",
                name="validation_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="RUNNING",
            nullable=False,
        ),
        sa.Column("method", sa.String(length=160), nullable=False),
        sa.Column("split_method", sa.String(length=160), nullable=True),
        sa.Column("region", sa.String(length=200), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "record_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(length=40), nullable=True),
        sa.Column("model_version", sa.String(length=80), nullable=True),
        sa.Column("config_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "metrics", _json(), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "baselines", _json(), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "findings", _json(), server_default=sa.text("'[]'"), nullable=False
        ),
        sa.Column(
            "limitations",
            _json(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "reproducibility",
            _json(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "record_count >= 0",
            name=op.f("ck_validation_experiments_ck_validation_experiments_count"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.id"],
            name=op.f("fk_validation_experiments_created_by_profiles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["validation_datasets.id"],
            name=op.f(
                "fk_validation_experiments_dataset_id_validation_datasets"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_validation_experiments")),
        sa.UniqueConstraint(
            "experiment_key", name="uq_validation_experiments_key"
        ),
    )
    op.create_index(
        "ix_validation_experiments_dataset_created",
        "validation_experiments",
        ["dataset_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_validation_experiments_type_status",
        "validation_experiments",
        ["experiment_type", "status"],
        unique=False,
    )
    op.create_index(
        "ix_validation_experiments_evidence",
        "validation_experiments",
        ["evidence_kind"],
        unique=False,
    )
    _enable_rls()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in reversed(PHASE8_TABLES):
            op.execute(
                f"DROP POLICY IF EXISTS {table}_read_staff ON public.{table}"
            )
    op.drop_index(
        "ix_validation_experiments_evidence",
        table_name="validation_experiments",
    )
    op.drop_index(
        "ix_validation_experiments_type_status",
        table_name="validation_experiments",
    )
    op.drop_index(
        "ix_validation_experiments_dataset_created",
        table_name="validation_experiments",
    )
    op.drop_table("validation_experiments")
    op.drop_index(
        "ix_validation_datasets_status", table_name="validation_datasets"
    )
    op.drop_index(
        "ix_validation_datasets_source", table_name="validation_datasets"
    )
    op.drop_table("validation_datasets")
