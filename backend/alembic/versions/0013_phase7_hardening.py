"""Phase 7 hardening: active-model/review uniqueness and recipient RLS.

Revision ID: 0013_phase7_hardening
Revises: 0012_operational_maturity
Create Date: 2026-11-24

The application already serializes most writes. These database invariants make
the critical lifecycle guarantees explicit and prevent concurrent activation or
review decisions from creating duplicate active state. Notification rows are
narrowed from staff-wide SELECT to the recipient only.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_phase7_hardening"
down_revision: Union[str, None] = "0012_operational_maturity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_model_versions_one_active",
        "model_versions",
        ["model_name"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        sqlite_where=sa.text("is_active"),
    )
    op.create_index(
        "uq_decision_reviews_active_simulation",
        "decision_reviews",
        ["scenario_id", "simulation_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('SUBMITTED', 'APPROVED', 'REVISION_REQUESTED')"
        ),
        sqlite_where=sa.text(
            "status IN ('SUBMITTED', 'APPROVED', 'REVISION_REQUESTED')"
        ),
    )
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        "DROP POLICY IF EXISTS notifications_read_staff ON public.notifications"
    )
    op.execute(
        "CREATE POLICY notifications_read_recipient ON public.notifications "
        "FOR SELECT TO authenticated USING ("
        "recipient_id = auth.uid() AND public.is_worker_or_admin())"
    )
    op.execute(
        "DROP POLICY IF EXISTS notification_preferences_read_staff "
        "ON public.notification_preferences"
    )
    op.execute(
        "CREATE POLICY notification_preferences_read_own "
        "ON public.notification_preferences "
        "FOR SELECT TO authenticated USING ("
        "profile_id = auth.uid() AND public.is_worker_or_admin())"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP POLICY IF EXISTS notifications_read_recipient "
            "ON public.notifications"
        )
        op.execute(
            "CREATE POLICY notifications_read_staff ON public.notifications "
            "FOR SELECT TO authenticated USING (public.is_worker_or_admin())"
        )
        op.execute(
            "DROP POLICY IF EXISTS notification_preferences_read_own "
            "ON public.notification_preferences"
        )
        op.execute(
            "CREATE POLICY notification_preferences_read_staff "
            "ON public.notification_preferences "
            "FOR SELECT TO authenticated USING (public.is_worker_or_admin())"
        )
    op.drop_index(
        "uq_decision_reviews_active_simulation", table_name="decision_reviews"
    )
    op.drop_index("uq_model_versions_one_active", table_name="model_versions")
