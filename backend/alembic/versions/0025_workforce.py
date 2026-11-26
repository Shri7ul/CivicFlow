"""Municipal workforce applications, workers and assignments.

Revision ID: 0025_workforce
Revises: 0024_phase14_pilot
Create Date: 2026-11-26

Additive and non-destructive. No seed rows, no data rewrites and no drops of
existing user data. The only existing-table change is extending three CHECK
constraints for the incident status enum. All new tables are RLS-protected and
read-only to the authenticated role; writes use the server-side service role.
The migration is offline-SQL safe: no Python-side JSON binding and no literal
NULL INSERT.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0025_workforce'
down_revision: Union[str, None] = '0024_phase14_pilot'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TABLES = (
    'worker_applications',
    'worker_profiles',
    'incident_assignments',
    'incident_assignment_events',
    'workforce_events',
    'workforce_notifications',
)

INCIDENT_STATUSES_OLD = "'OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'"
INCIDENT_STATUSES_NEW = (
    "'OPEN', 'VERIFIED', 'ASSIGNED', 'ACCEPTED', 'ACKNOWLEDGED', 'IN_PROGRESS', "
    "'COMPLETION_SUBMITTED', 'VERIFIED_COMPLETED', 'RESOLVED', 'CLOSED'"
)
APPLICATION_STATUSES = (
    "'PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', "
    "'ADDITIONAL_INFORMATION_REQUIRED', 'SUSPENDED'"
)
WORKER_STATUSES = "'ACTIVE', 'SUSPENDED'"
ASSIGNMENT_STATUSES = (
    "'OFFERED', 'ACCEPTED', 'DECLINED', 'IN_PROGRESS', "
    "'COMPLETION_SUBMITTED', 'VERIFIED_COMPLETED', 'CANCELLED'"
)


def _replace_check(table: str, name: str, expression: str) -> None:
    """Replace a status CHECK, tolerating the historical double-prefixed name."""
    prefixed = f"ck_{table}_{name}"
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        from sqlalchemy import inspect

        existing = {
            constraint["name"] for constraint in inspect(bind).get_check_constraints(table)
        }
        actual = prefixed if prefixed in existing else name
        literal = op.f(actual)
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(literal, type_="check")
            batch.create_check_constraint(literal, expression)
        return
    op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {prefixed}")
    op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {name}")
    op.execute(f"ALTER TABLE public.{table} ADD CONSTRAINT {prefixed} CHECK ({expression})")


def _create_tables() -> None:
    op.create_table(
        'worker_applications',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('applicant_id', sa.Uuid(), sa.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('full_name', sa.String(200), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('email', sa.String(254), nullable=True),
        sa.Column('specialization', sa.String(80), nullable=False),
        sa.Column('department_id', sa.Uuid(), sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('service_area', sa.String(200), nullable=False),
        sa.Column('address', sa.String(500), nullable=True),
        sa.Column('experience', sa.Text(), nullable=True),
        sa.Column('credentials_note', sa.Text(), nullable=True),
        sa.Column(
            'status',
            sa.String(30),
            sa.CheckConstraint(f"status IN ({APPLICATION_STATUSES})", name='ck_worker_applications_status'),
            nullable=False,
            server_default='PENDING',
        ),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('reviewer_id', sa.Uuid(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('applicant_id', name='uq_worker_applications_applicant'),
    )
    op.create_index('ix_worker_applications_status_created', 'worker_applications', ['status', 'created_at'])
    op.create_index('ix_worker_applications_department', 'worker_applications', ['department_id'])

    op.create_table(
        'worker_profiles',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('profile_id', sa.Uuid(), sa.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('application_id', sa.Uuid(), sa.ForeignKey('worker_applications.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('specialization', sa.String(80), nullable=False),
        sa.Column('department_id', sa.Uuid(), sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('service_area', sa.String(200), nullable=False),
        sa.Column(
            'status',
            sa.String(20),
            sa.CheckConstraint(f"status IN ({WORKER_STATUSES})", name='ck_worker_profiles_status'),
            nullable=False,
            server_default='ACTIVE',
        ),
        sa.Column('approved_by', sa.Uuid(), sa.ForeignKey('profiles.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('profile_id', name='uq_worker_profiles_profile'),
        sa.UniqueConstraint('application_id', name='uq_worker_profiles_application'),
    )
    op.create_index('ix_worker_profiles_status_area', 'worker_profiles', ['status', 'service_area'])
    op.create_index('ix_worker_profiles_department', 'worker_profiles', ['department_id'])

    op.create_table(
        'incident_assignments',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('incident_id', sa.Uuid(), sa.ForeignKey('incidents.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('worker_id', sa.Uuid(), sa.ForeignKey('worker_profiles.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('assigned_by', sa.Uuid(), sa.ForeignKey('profiles.id', ondelete='RESTRICT'), nullable=False),
        sa.Column(
            'status',
            sa.String(30),
            sa.CheckConstraint(f"status IN ({ASSIGNMENT_STATUSES})", name='ck_incident_assignments_status'),
            nullable=False,
            server_default='OFFERED',
        ),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('completion_note', sa.Text(), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint(
            'deadline IS NULL OR created_at IS NULL OR deadline >= created_at',
            name='ck_incident_assignments_deadline_after_creation',
        ),
    )
    op.create_index('ix_incident_assignments_incident', 'incident_assignments', ['incident_id', 'created_at'])
    op.create_index('ix_incident_assignments_worker_status', 'incident_assignments', ['worker_id', 'status'])
    op.create_index('ix_incident_assignments_status', 'incident_assignments', ['status'])

    op.create_table(
        'incident_assignment_events',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('assignment_id', sa.Uuid(), sa.ForeignKey('incident_assignments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('profiles.id', ondelete='RESTRICT'), nullable=False),
        sa.Column(
            'from_status',
            sa.String(30),
            sa.CheckConstraint(f"from_status IS NULL OR from_status IN ({ASSIGNMENT_STATUSES})", name='ck_assignment_events_from'),
            nullable=True,
        ),
        sa.Column(
            'to_status',
            sa.String(30),
            sa.CheckConstraint(f"to_status IN ({ASSIGNMENT_STATUSES})", name='ck_assignment_events_to'),
            nullable=False,
        ),
        sa.Column('note', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_incident_assignment_events_assignment', 'incident_assignment_events', ['assignment_id', 'created_at'])
    op.create_index('ix_incident_assignment_events_actor', 'incident_assignment_events', ['actor_id'])

    op.create_table(
        'workforce_events',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(80), nullable=False),
        sa.Column('entity_type', sa.String(60), nullable=False),
        sa.Column('entity_id', sa.Uuid(), nullable=False),
        sa.Column('previous_state', sa.String(80), nullable=True),
        sa.Column('new_state', sa.String(80), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_workforce_events_entity', 'workforce_events', ['entity_type', 'entity_id'])
    op.create_index('ix_workforce_events_actor', 'workforce_events', ['actor_id'])
    op.create_index('ix_workforce_events_created', 'workforce_events', ['created_at'])

    op.create_table(
        'workforce_notifications',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('recipient_id', sa.Uuid(), sa.ForeignKey('profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(80), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.String(60), nullable=True),
        sa.Column('entity_id', sa.Uuid(), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_workforce_notifications_recipient_read', 'workforce_notifications', ['recipient_id', 'read_at'])
    op.create_index('ix_workforce_notifications_created', 'workforce_notifications', ['created_at'])


def _apply_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM anon, authenticated")
        op.execute(f"GRANT SELECT ON TABLE public.{table} TO authenticated")
        op.execute(
            f"CREATE POLICY {table}_read_authenticated ON public.{table} "
            "FOR SELECT TO authenticated USING (true)"
        )


def _drop_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_read_authenticated ON public.{table}")


def upgrade() -> None:
    _create_tables()
    _apply_rls()
    _replace_check('incidents', 'ck_incidents_incident_status', f"status IN ({INCIDENT_STATUSES_NEW})")
    _replace_check(
        'incident_status_events',
        'ck_incident_status_events_incident_status_event_from',
        f"from_status IS NULL OR from_status IN ({INCIDENT_STATUSES_NEW})",
    )
    _replace_check(
        'incident_status_events',
        'ck_incident_status_events_incident_status_event_to',
        f"to_status IN ({INCIDENT_STATUSES_NEW})",
    )


def downgrade() -> None:
    _replace_check('incidents', 'ck_incidents_incident_status', f"status IN ({INCIDENT_STATUSES_OLD})")
    _replace_check(
        'incident_status_events',
        'ck_incident_status_events_incident_status_event_from',
        f"from_status IS NULL OR from_status IN ({INCIDENT_STATUSES_OLD})",
    )
    _replace_check(
        'incident_status_events',
        'ck_incident_status_events_incident_status_event_to',
        f"to_status IN ({INCIDENT_STATUSES_OLD})",
    )
    _drop_rls()
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
