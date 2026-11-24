"""Classify evidence snapshots as operational, synthetic, mixed or unknown.

Revision ID: 0022_snapshot_provenance
Revises: 0021_gt_provenance
Create Date: 2026-11-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0022_snapshot_provenance'
down_revision: Union[str, None] = '0021_gt_provenance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("evidence_snapshots") as batch:
            batch.add_column(
                sa.Column(
                    "provenance_kind",
                    sa.String(length=16),
                    nullable=False,
                    server_default="OPERATIONAL",
                )
            )
            batch.create_check_constraint(
                "ck_evidence_snapshots_evidence_snapshot_provenance",
                "provenance_kind IN ('OPERATIONAL','SYNTHETIC','MIXED','UNKNOWN')",
            )
        return
    op.execute(
        "ALTER TABLE public.evidence_snapshots "
        "ADD COLUMN provenance_kind VARCHAR(16) NOT NULL DEFAULT 'OPERATIONAL'"
    )
    op.execute(
        "ALTER TABLE public.evidence_snapshots "
        "ADD CONSTRAINT ck_evidence_snapshots_evidence_snapshot_provenance "
        "CHECK (provenance_kind IN ('OPERATIONAL','SYNTHETIC','MIXED','UNKNOWN'))"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("evidence_snapshots") as batch:
            batch.drop_constraint(
                "ck_evidence_snapshots_evidence_snapshot_provenance",
                type_="check",
            )
            batch.drop_column("provenance_kind")
        return
    op.execute(
        "ALTER TABLE public.evidence_snapshots "
        "DROP CONSTRAINT ck_evidence_snapshots_evidence_snapshot_provenance"
    )
    op.execute(
        "ALTER TABLE public.evidence_snapshots DROP COLUMN provenance_kind"
    )
