"""Normalize Phase 4 relationship CHECK constraint names.

Revision ID: 0007_relationship_checks
Revises: 0006_incident_intelligence
Create Date: 2026-11-24

The first application of 0006 on the live development database used explicit
``ck_`` names, which the project naming convention prefixed a second time.
Fresh installs now use short names in 0006; this migration repairs databases
that already applied the earlier form.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0007_relationship_checks"
down_revision: Union[str, None] = "0006_incident_intelligence"
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
            target_name TEXT;
        BEGIN
            FOR item IN
                SELECT conname, pg_get_constraintdef(oid) AS definition
                FROM pg_constraint
                WHERE conrelid = 'public.incident_relationships'::regclass
                  AND contype = 'c'
            LOOP
                target_name := CASE
                    WHEN item.definition LIKE '%incident_a_id <> incident_b_id%'
                        THEN 'ck_incident_relationships_different_incidents'
                    WHEN item.definition LIKE '%confidence >=%'
                        THEN 'ck_incident_relationships_confidence_range'
                    WHEN item.definition LIKE '%relationship_type%'
                        THEN 'ck_incident_relationships_relationship_type'
                    WHEN item.definition LIKE '%status%'
                        THEN 'ck_incident_relationships_relationship_status'
                    ELSE NULL
                END;
                IF target_name IS NOT NULL AND item.conname <> target_name THEN
                    EXECUTE format(
                        'ALTER TABLE public.incident_relationships '
                        'RENAME CONSTRAINT %I TO %I',
                        item.conname,
                        target_name
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    # Constraint names are metadata-only; 0006 downgrade drops the table.
    return
