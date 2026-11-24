"""Add explicit synthetic provenance to correlation candidates.

Revision ID: 0019_phase10_correlation
Revises: 0018_phase10_pilot_governance
Create Date: 2026-11-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0019_phase10_correlation"
down_revision: Union[str, None] = "0018_phase10_pilot_governance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "correlation_candidates",
        sa.Column("synthetic_fixture", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("correlation_candidates", "synthetic_fixture")
