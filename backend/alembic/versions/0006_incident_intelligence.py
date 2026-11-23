"""Phase 4 incident intelligence relationships.

Revision ID: 0006_incident_intelligence
Revises: 0005_map_evidence_storage
Create Date: 2026-11-24

Adds reviewable incident-to-incident relationships. Suggestions are computed
on read; only WORKER/ADMIN review actions persist a CONFIRMED or DISMISSED row.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.base import jsonb_column_type

revision: str = "0006_incident_intelligence"
down_revision: Union[str, None] = "0005_map_evidence_storage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RELATIONSHIP_TYPES = "'RELATED', 'DUPLICATE', 'CONTEXT'"
RELATIONSHIP_STATUSES = "'CONFIRMED', 'DISMISSED'"


def upgrade() -> None:
    op.create_table(
        "incident_relationships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_a_id", sa.Uuid(), nullable=False),
        sa.Column("incident_b_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=9), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column(
            "confidence",
            sa.Numeric(precision=4, scale=3),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "signals",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "incident_a_id <> incident_b_id",
            name="different_incidents",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="confidence_range",
        ),
        sa.CheckConstraint(
            f"relationship_type IN ({RELATIONSHIP_TYPES})",
            name="relationship_type",
        ),
        sa.CheckConstraint(
            f"status IN ({RELATIONSHIP_STATUSES})",
            name="relationship_status",
        ),
        sa.ForeignKeyConstraint(
            ["incident_a_id"],
            ["incidents.id"],
            name="fk_incident_relationships_incident_a_id_incidents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_b_id"],
            ["incidents.id"],
            name="fk_incident_relationships_incident_b_id_incidents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["profiles.id"],
            name="fk_incident_relationships_reviewed_by_profiles",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_incident_relationships"),
        sa.UniqueConstraint(
            "incident_a_id",
            "incident_b_id",
            "relationship_type",
            name="relationship_logical_unique",
        ),
    )
    op.create_index(
        "ix_incident_relationships_a",
        "incident_relationships",
        ["incident_a_id"],
    )
    op.create_index(
        "ix_incident_relationships_b",
        "incident_relationships",
        ["incident_b_id"],
    )
    op.create_index(
        "ix_incident_relationships_status",
        "incident_relationships",
        ["status"],
    )
    op.create_index(
        "ix_incident_relationships_reviewed_by",
        "incident_relationships",
        ["reviewed_by"],
    )

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE public.incident_relationships ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY incident_relationships_read_visible_pair
        ON public.incident_relationships
        FOR SELECT
        TO authenticated
        USING (
            public.is_worker_or_admin()
            OR EXISTS (
                SELECT 1
                FROM public.incidents ia
                JOIN public.incidents ib
                  ON ib.id = incident_relationships.incident_b_id
                WHERE ia.id = incident_relationships.incident_a_id
                  AND ia.reporter_id = auth.uid()
                  AND ib.reporter_id = auth.uid()
            )
        )
        """
    )
    # Relationships are written by the backend after WORKER/ADMIN review.
    op.execute(
        "REVOKE ALL PRIVILEGES ON TABLE public.incident_relationships "
        "FROM anon, authenticated"
    )
    op.execute(
        "GRANT SELECT ON TABLE public.incident_relationships TO authenticated"
    )
    op.execute(
        """
        CREATE TRIGGER incident_relationships_set_updated_at
        BEFORE UPDATE ON public.incident_relationships
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS incident_relationships_set_updated_at "
            "ON public.incident_relationships"
        )
        op.execute(
            "DROP POLICY IF EXISTS incident_relationships_read_visible_pair "
            "ON public.incident_relationships"
        )
        op.execute(
            "ALTER TABLE public.incident_relationships "
            "DISABLE ROW LEVEL SECURITY"
        )
    op.drop_index(
        "ix_incident_relationships_reviewed_by",
        table_name="incident_relationships",
    )
    op.drop_index(
        "ix_incident_relationships_status",
        table_name="incident_relationships",
    )
    op.drop_index(
        "ix_incident_relationships_b",
        table_name="incident_relationships",
    )
    op.drop_index(
        "ix_incident_relationships_a",
        table_name="incident_relationships",
    )
    op.drop_table("incident_relationships")
