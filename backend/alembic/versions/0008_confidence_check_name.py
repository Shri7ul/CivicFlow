"""Finish normalizing the confidence CHECK name.

Revision ID: 0008_confidence_check_name
Revises: 0007_relationship_checks
Create Date: 2026-11-24
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0008_confidence_check_name"
down_revision: Union[str, None] = "0007_relationship_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        DO $$
        DECLARE
            item RECORD;
        BEGIN
            FOR item IN
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'public.incident_relationships'::regclass
                  AND contype = 'c'
                  AND conname LIKE 'ck_incident_relationships_ck_incident_relationships_%'
                  AND pg_get_constraintdef(oid) LIKE '%confidence%'
            LOOP
                EXECUTE format(
                    'ALTER TABLE public.incident_relationships '
                    'RENAME CONSTRAINT %I TO %I',
                    item.conname,
                    'ck_incident_relationships_confidence_range'
                );
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    return
