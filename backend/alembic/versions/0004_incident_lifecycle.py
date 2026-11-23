"""Incident lifecycle history (Phase 2, Goal 05).

Revision ID: 0004_incident_lifecycle
Revises: 0003_acl_hardening
Create Date: 2026-11-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_incident_lifecycle"
down_revision: Union[str, None] = "0003_acl_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUS_VALUES = "'OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'"


def upgrade() -> None:
    op.create_table(
        "incident_status_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("from_status", sa.String(length=12), nullable=True),
        sa.Column("to_status", sa.String(length=12), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN ({STATUS_VALUES})",
            name="ck_incident_status_events_incident_status_event_from",
        ),
        sa.CheckConstraint(
            f"to_status IN ({STATUS_VALUES})",
            name="ck_incident_status_events_incident_status_event_to",
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status <> to_status",
            name="ck_incident_status_events_status_change_required",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name="fk_incident_status_events_incident_id_incidents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["profiles.id"],
            name="fk_incident_status_events_actor_id_profiles",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_incident_status_events"),
    )
    op.create_index(
        "ix_incident_status_events_incident_created",
        "incident_status_events",
        ["incident_id", "created_at"],
    )
    op.create_index(
        "ix_incident_status_events_actor_id",
        "incident_status_events",
        ["actor_id"],
    )

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        "ALTER TABLE public.incident_status_events ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY incident_status_events_read_visible_incident
        ON public.incident_status_events
        FOR SELECT
        TO authenticated
        USING (
            EXISTS (
                SELECT 1
                FROM public.incidents AS i
                WHERE i.id = incident_id
                  AND (
                      i.reporter_id = auth.uid()
                      OR public.is_worker_or_admin()
                  )
            )
        )
        """
    )
    # The API writes lifecycle events; direct user inserts are not exposed.
    op.execute(
        "REVOKE ALL PRIVILEGES ON TABLE public.incident_status_events "
        "FROM anon, authenticated"
    )
    op.execute(
        "GRANT SELECT ON TABLE public.incident_status_events TO authenticated"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP POLICY IF EXISTS incident_status_events_read_visible_incident "
            "ON public.incident_status_events"
        )
        op.execute(
            "ALTER TABLE public.incident_status_events "
            "DISABLE ROW LEVEL SECURITY"
        )
    op.drop_index(
        "ix_incident_status_events_actor_id",
        table_name="incident_status_events",
    )
    op.drop_index(
        "ix_incident_status_events_incident_created",
        table_name="incident_status_events",
    )
    op.drop_table("incident_status_events")
