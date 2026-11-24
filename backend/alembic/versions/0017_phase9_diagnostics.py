"""Phase 9 diagnostic, ablation, robustness, and external-validation records.

Revision ID: 0017_phase9_diagnostics
Revises: 0016_validation_workspace
Create Date: 2026-11-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_phase9_diagnostics"
down_revision: Union[str, None] = "0016_validation_workspace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TYPE_CONSTRAINT = "ck_validation_experiments_validation_experiment_type"
TYPES = (
    "RISK_BACKTEST",
    "RISK_SENSITIVITY",
    "RISK_DIAGNOSTIC",
    "RISK_ABLATION",
    "RISK_ROBUSTNESS",
    "RISK_GEOGRAPHIC",
    "RISK_TEMPORAL",
    "CORRELATION_SYNTHETIC",
    "DECISION_SIMULATION",
)


def _type_check() -> str:
    values = ", ".join(f"'{value}'" for value in TYPES)
    return f"experiment_type IN ({values})"


def upgrade() -> None:
    op.add_column(
        "validation_experiments",
        sa.Column("protocol_key", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "validation_experiments",
        sa.Column("variant_key", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ix_validation_experiments_protocol",
        "validation_experiments",
        ["protocol_key", "variant_key"],
        unique=False,
    )
    # SQLite is a test-only migration target and rebuilds constraints on table
    # reflection. The enum extension is a PostgreSQL/production requirement.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            f"ALTER TABLE public.validation_experiments "
            f"DROP CONSTRAINT IF EXISTS {TYPE_CONSTRAINT}"
        )
        op.execute(
            f"ALTER TABLE public.validation_experiments "
            f"ADD CONSTRAINT {TYPE_CONSTRAINT} CHECK ({_type_check()})"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            f"ALTER TABLE public.validation_experiments "
            f"DROP CONSTRAINT IF EXISTS {TYPE_CONSTRAINT}"
        )
        op.execute(
            f"ALTER TABLE public.validation_experiments "
            f"ADD CONSTRAINT {TYPE_CONSTRAINT} CHECK ("
            "experiment_type IN ('RISK_BACKTEST','RISK_SENSITIVITY',"
            "'CORRELATION_SYNTHETIC','DECISION_SIMULATION'))"
        )
    op.drop_index(
        "ix_validation_experiments_protocol",
        table_name="validation_experiments",
    )
    op.drop_column("validation_experiments", "variant_key")
    op.drop_column("validation_experiments", "protocol_key")
