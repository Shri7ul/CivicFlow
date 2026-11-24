"""Add explicit provenance classification to ground-truth assertions.

Revision ID: 0021_gt_provenance
Revises: 0020_phase11_evidence
Create Date: 2026-11-25

Operational assertions are separated from synthetic test fixtures. API-created
records are always OPERATIONAL; synthetic rows can only be inserted by fixtures.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0021_gt_provenance'
down_revision: Union[str, None] = '0020_phase11_evidence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("ground_truth_records") as batch:
            batch.add_column(
                sa.Column(
                    "provenance_kind",
                    sa.String(length=16),
                    nullable=False,
                    server_default="OPERATIONAL",
                )
            )
            batch.create_check_constraint(
                "ck_ground_truth_records_ground_truth_provenance",
                "provenance_kind IN ('OPERATIONAL','SYNTHETIC','MIXED','UNKNOWN')",
            )
        return
    op.execute(
        "ALTER TABLE public.ground_truth_records "
        "ADD COLUMN provenance_kind VARCHAR(16) NOT NULL DEFAULT 'OPERATIONAL'"
    )
    op.execute(
        "ALTER TABLE public.ground_truth_records "
        "ADD CONSTRAINT ck_ground_truth_records_ground_truth_provenance "
        "CHECK (provenance_kind IN ('OPERATIONAL','SYNTHETIC','MIXED','UNKNOWN'))"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("ground_truth_records") as batch:
            batch.drop_constraint(
                "ck_ground_truth_records_ground_truth_provenance",
                type_="check",
            )
            batch.drop_column("provenance_kind")
        return
    op.execute(
        "ALTER TABLE public.ground_truth_records "
        "DROP CONSTRAINT ck_ground_truth_records_ground_truth_provenance"
    )
    op.execute(
        "ALTER TABLE public.ground_truth_records DROP COLUMN provenance_kind"
    )
