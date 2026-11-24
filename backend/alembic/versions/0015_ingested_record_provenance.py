"""Persist source-record timestamps and provenance explicitly.

Revision ID: 0015_ingested_provenance
Revises: 0014_model_version_uniqueness
Create Date: 2026-11-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_ingested_provenance"
down_revision: Union[str, None] = "0014_model_version_uniqueness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingested_records",
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ingested_records",
        sa.Column(
            "provenance",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ingested_records", "provenance")
    op.drop_column("ingested_records", "observed_at")
