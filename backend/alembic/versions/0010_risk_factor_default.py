"""Normalize the risk snapshot factor-contribution default.

Revision ID: 0010_risk_factor_default
Revises: 0009_urban_risk_engine
Create Date: 2026-11-24

The model stores factor contributions as a JSON array. Keep the database
default aligned with that contract for live installs created by the earlier
0009 revision. SQLite test migrations have no production default contract and
skip the PostgreSQL-only ALTER.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_risk_factor_default"
down_revision: Union[str, None] = "0009_urban_risk_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "risk_cell_snapshots",
        "factor_contributions",
        existing_type=sa.JSON(),
        existing_nullable=False,
        server_default=sa.text("'[]'"),
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.alter_column(
        "risk_cell_snapshots",
        "factor_contributions",
        existing_type=sa.JSON(),
        existing_nullable=False,
        server_default=sa.text("'{}'"),
    )
