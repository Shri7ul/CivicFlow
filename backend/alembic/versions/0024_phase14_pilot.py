"""Phase 14 controlled-pilot controls and shutdown.

Revision ID: 0024_phase14_pilot
Revises: 0023_phase12_geography
Create Date: 2026-11-25

Additive and non-destructive. No seed rows and no rewrites of historical
evidence. The only existing-table change is adding TERMINATED to the pilot
lifecycle CHECK constraints and three nullable shutdown columns on pilots.
All new tables are RLS-protected and read-only to the authenticated role;
writes use the server-side service role. The migration is offline-SQL safe:
no Python-side JSON binding and no seed INSERT with literal NULL values.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.models.base import point_geography_type

revision: str = '0024_phase14_pilot'
down_revision: Union[str, None] = '0023_phase12_geography'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TABLES = (
    "phase14_attestation_events",
    "phase14_attestations",
    "pilot_shutdowns",
    "baseline_comparisons",
    "pilot_incident_events",
    "pilot_incidents",
    "pilot_data_sources",
    "field_observation_events",
    "field_observations",
    "pilot_boundary_events",
    "pilot_boundaries",
)

PILOT_STATUSES_OLD = (
    "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'ACTIVE', 'PAUSED', "
    "'COMPLETED', 'REJECTED', 'ARCHIVED')"
)
PILOT_STATUSES_NEW = (
    "status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'ACTIVE', 'PAUSED', "
    "'COMPLETED', 'REJECTED', 'TERMINATED', 'ARCHIVED')"
)
PILOT_STATUSES_OLD_TIGHT = (
    "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','ACTIVE','PAUSED',"
    "'COMPLETED','REJECTED','ARCHIVED')"
)
PILOT_STATUSES_NEW_TIGHT = (
    "status IN ('DRAFT','PENDING_APPROVAL','APPROVED','ACTIVE','PAUSED',"
    "'COMPLETED','REJECTED','TERMINATED','ARCHIVED')"
)
TRANSITION_FROM_OLD = (
    "from_status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'ACTIVE', "
    "'PAUSED', 'COMPLETED', 'REJECTED', 'ARCHIVED')"
)
TRANSITION_FROM_NEW = (
    "from_status IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'ACTIVE', "
    "'PAUSED', 'COMPLETED', 'REJECTED', 'TERMINATED', 'ARCHIVED')"
)
TRANSITION_TO_OLD = TRANSITION_FROM_OLD.replace("from_status", "to_status")
TRANSITION_TO_NEW = TRANSITION_FROM_NEW.replace("from_status", "to_status")
ACTION_OLD = (
    "action IN ('CREATE', 'SUBMIT', 'APPROVE', 'REJECT', 'ACTIVATE', 'PAUSE', "
    "'RESUME', 'COMPLETE', 'ARCHIVE')"
)
ACTION_NEW = (
    "action IN ('CREATE', 'SUBMIT', 'APPROVE', 'REJECT', 'ACTIVATE', 'PAUSE', "
    "'RESUME', 'COMPLETE', 'TERMINATE', 'ARCHIVE')"
)


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def _id():
    return sa.Column('id', sa.Uuid(), primary_key=True)


def _timestamps():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def _event_timestamps():
    return sa.Column(
        'created_at', sa.DateTime(timezone=True), nullable=False,
        server_default=sa.text('CURRENT_TIMESTAMP'),
    )


def _replace_check(table: str, name: str, expression: str) -> None:
    if op.get_bind().dialect.name == "sqlite":
        # op.f() marks the name as literal; otherwise the metadata naming
        # convention prefixes the table name a second time.
        literal = op.f(name)
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(literal, type_="check")
            batch.create_check_constraint(literal, expression)
        return
    op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {name}")
    op.execute(f"ALTER TABLE public.{table} ADD CONSTRAINT {name} CHECK ({expression})")


def _add_shutdown_columns() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("pilots") as batch:
            batch.add_column(sa.Column('terminated_at', sa.DateTime(timezone=True), nullable=True))
            batch.add_column(sa.Column('terminated_by', sa.Uuid(), nullable=True))
            batch.add_column(sa.Column('termination_reason', sa.Text(), nullable=True))
        return
    op.execute("ALTER TABLE public.pilots ADD COLUMN terminated_at TIMESTAMPTZ")
    op.execute("ALTER TABLE public.pilots ADD COLUMN terminated_by UUID")
    op.execute("ALTER TABLE public.pilots ADD COLUMN termination_reason TEXT")


def _drop_shutdown_columns() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("pilots") as batch:
            batch.drop_column('termination_reason')
            batch.drop_column('terminated_by')
            batch.drop_column('terminated_at')
        return
    op.execute("ALTER TABLE public.pilots DROP COLUMN IF EXISTS termination_reason")
    op.execute("ALTER TABLE public.pilots DROP COLUMN IF EXISTS terminated_by")
    op.execute("ALTER TABLE public.pilots DROP COLUMN IF EXISTS terminated_at")


def _create_tables() -> None:
    op.create_table(
        'pilot_boundaries',
        _id(),
        sa.Column('boundary_key', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('pilot_id', sa.Uuid(), nullable=True),
        sa.Column('geographic_context_key', sa.String(length=32), nullable=False, server_default='UNKNOWN'),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('source_owner', sa.String(length=240), nullable=False),
        sa.Column('source_name', sa.String(length=240), nullable=False),
        sa.Column('source_url', sa.String(length=1000), nullable=True),
        sa.Column('source_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('boundary_version', sa.String(length=120), nullable=False),
        sa.Column('crs', sa.String(length=80), nullable=False),
        sa.Column('geometry_geojson', _json(), nullable=False),
        sa.Column('bbox_geojson', _json(), nullable=False),
        sa.Column('coordinate_validation', _json(), nullable=False, server_default='{}'),
        sa.Column('geometry_validation', _json(), nullable=False, server_default='{}'),
        sa.Column('provenance_note', sa.Text(), nullable=False),
        sa.Column('license_note', sa.Text(), nullable=False),
        sa.Column('integrity_sha256', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='UNVERIFIED'),
        sa.Column('submitted_by', sa.Uuid(), nullable=True),
        sa.Column('reviewed_by', sa.Uuid(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint('boundary_key', name='uq_pilot_boundaries_key'),
        sa.CheckConstraint('length(integrity_sha256) = 64', name='ck_pilot_boundaries_integrity_sha256'),
    )
    op.create_index('ix_pilot_boundaries_context_status', 'pilot_boundaries', ['geographic_context_key', 'status'])
    op.create_index('ix_pilot_boundaries_pilot', 'pilot_boundaries', ['pilot_id'])

    op.create_table(
        'pilot_boundary_events',
        _id(),
        sa.Column('boundary_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(length=60), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=True),
        sa.Column('to_status', sa.String(length=32), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('actor_email', sa.String(length=320), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        _event_timestamps(),
    )
    op.create_index('ix_pilot_boundary_events_boundary', 'pilot_boundary_events', ['boundary_id', 'created_at'])

    op.create_table(
        'field_observations',
        _id(),
        sa.Column('observation_key', sa.String(length=80), nullable=False),
        sa.Column('pilot_id', sa.Uuid(), nullable=True),
        sa.Column('geographic_context_key', sa.String(length=32), nullable=False, server_default='UNKNOWN'),
        sa.Column('observer_id', sa.Uuid(), nullable=False),
        sa.Column('observer_role_snapshot', sa.String(length=32), nullable=False),
        sa.Column('source_reference', sa.String(length=500), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('location', point_geography_type(), nullable=True),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('evidence_refs', _json(), nullable=False, server_default='[]'),
        sa.Column('evidence_sha256', sa.String(length=64), nullable=True),
        sa.Column('provenance_kind', sa.String(length=32), nullable=False, server_default='OPERATIONAL'),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='DRAFT'),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer_id', sa.Uuid(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision', sa.String(length=40), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('revision_notes', sa.Text(), nullable=True),
        sa.Column('duplicate_of_id', sa.Uuid(), nullable=True),
        sa.Column('ground_truth_record_id', sa.Uuid(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint('observation_key', name='uq_field_observations_key'),
        sa.UniqueConstraint('observer_id', 'source_reference', name='uq_field_observations_observer_ref'),
        sa.CheckConstraint(
            'confidence IS NULL OR (confidence >= 0 AND confidence <= 1)',
            name='ck_field_observations_confidence',
        ),
        sa.CheckConstraint(
            'latitude IS NULL OR longitude IS NULL OR '
            '(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)',
            name='ck_field_observations_coordinates',
        ),
    )
    op.create_index('ix_field_observations_context_status', 'field_observations', ['geographic_context_key', 'status'])
    op.create_index('ix_field_observations_pilot', 'field_observations', ['pilot_id'])
    op.create_index('ix_field_observations_observer', 'field_observations', ['observer_id'])
    op.create_index('ix_field_observations_reviewer', 'field_observations', ['reviewer_id'])

    op.create_table(
        'field_observation_events',
        _id(),
        sa.Column('observation_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(length=60), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=True),
        sa.Column('to_status', sa.String(length=32), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('actor_email', sa.String(length=320), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('evidence_sha256', sa.String(length=64), nullable=True),
        _event_timestamps(),
    )
    op.create_index('ix_field_observation_events_observation', 'field_observation_events', ['observation_id', 'created_at'])

    op.create_table(
        'pilot_data_sources',
        _id(),
        sa.Column('source_key', sa.String(length=80), nullable=False),
        sa.Column('geographic_context_key', sa.String(length=32), nullable=False, server_default='UNKNOWN'),
        sa.Column('pilot_id', sa.Uuid(), nullable=True),
        sa.Column('source_identity', sa.String(length=240), nullable=False),
        sa.Column('source_owner', sa.String(length=240), nullable=False),
        sa.Column('dataset_name', sa.String(length=240), nullable=False),
        sa.Column('dataset_description', sa.Text(), nullable=False),
        sa.Column('geographic_scope', sa.String(length=300), nullable=False),
        sa.Column('acquisition_method', sa.String(length=120), nullable=False),
        sa.Column('endpoint', sa.String(length=1000), nullable=True),
        sa.Column('access_authorization', sa.String(length=32), nullable=False, server_default='UNAUTHORIZED'),
        sa.Column('license_note', sa.Text(), nullable=False),
        sa.Column('license_ref', sa.String(length=500), nullable=True),
        sa.Column('timestamp_note', sa.Text(), nullable=False),
        sa.Column('update_frequency', sa.String(length=120), nullable=True),
        sa.Column('data_quality_note', sa.Text(), nullable=False),
        sa.Column('schema_version', sa.String(length=120), nullable=False),
        sa.Column('provenance_note', sa.Text(), nullable=False),
        sa.Column('raw_sha256', sa.String(length=64), nullable=True),
        sa.Column('normalized_sha256', sa.String(length=64), nullable=True),
        sa.Column('coverage_note', sa.Text(), nullable=False),
        sa.Column('missing_data_note', sa.Text(), nullable=False),
        sa.Column('confidence_note', sa.Text(), nullable=False),
        sa.Column('limitations', sa.Text(), nullable=False),
        sa.Column('authorized_by', sa.Uuid(), nullable=True),
        sa.Column('authorized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint('source_key', name='uq_pilot_data_sources_key'),
        sa.CheckConstraint('raw_sha256 IS NULL OR length(raw_sha256) = 64', name='ck_pilot_data_sources_raw_sha'),
        sa.CheckConstraint(
            'normalized_sha256 IS NULL OR length(normalized_sha256) = 64',
            name='ck_pilot_data_sources_normalized_sha',
        ),
    )
    op.create_index('ix_pilot_data_sources_context_status', 'pilot_data_sources', ['geographic_context_key', 'access_authorization'])

    op.create_table(
        'pilot_incidents',
        _id(),
        sa.Column('incident_key', sa.String(length=80), nullable=False),
        sa.Column('pilot_id', sa.Uuid(), nullable=False),
        sa.Column('geographic_context_key', sa.String(length=32), nullable=False, server_default='UNKNOWN'),
        sa.Column('title', sa.String(length=240), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='OPEN'),
        sa.Column('source', sa.String(length=60), nullable=False),
        sa.Column('related_observation_id', sa.Uuid(), nullable=True),
        sa.Column('processing_stopped', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('impact_summary', sa.Text(), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('investigating_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mitigated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint('incident_key', name='uq_pilot_incidents_key'),
    )
    op.create_index('ix_pilot_incidents_pilot_status', 'pilot_incidents', ['pilot_id', 'status'])
    op.create_index('ix_pilot_incidents_severity', 'pilot_incidents', ['severity', 'status'])

    op.create_table(
        'pilot_incident_events',
        _id(),
        sa.Column('incident_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(length=60), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=True),
        sa.Column('to_status', sa.String(length=32), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('actor_email', sa.String(length=320), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        _event_timestamps(),
    )
    op.create_index('ix_pilot_incident_events_incident', 'pilot_incident_events', ['incident_id', 'created_at'])

    op.create_table(
        'baseline_comparisons',
        _id(),
        sa.Column('comparison_key', sa.String(length=80), nullable=False),
        sa.Column('pilot_id', sa.Uuid(), nullable=True),
        sa.Column('geographic_context_key', sa.String(length=32), nullable=False, server_default='UNKNOWN'),
        sa.Column('comparison_type', sa.String(length=80), nullable=False),
        sa.Column('method', sa.String(length=240), nullable=False),
        sa.Column('baseline_name', sa.String(length=240), nullable=False),
        sa.Column('candidate_name', sa.String(length=240), nullable=False),
        sa.Column('label_source', sa.Text(), nullable=False),
        sa.Column('label_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sample_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('baseline_metrics', _json(), nullable=False, server_default='{}'),
        sa.Column('candidate_metrics', _json(), nullable=False, server_default='{}'),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('limitations', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint('comparison_key', name='uq_baseline_comparisons_key'),
    )
    op.create_index('ix_baseline_comparisons_context', 'baseline_comparisons', ['geographic_context_key', 'created_at'])
    op.create_index('ix_baseline_comparisons_pilot', 'baseline_comparisons', ['pilot_id'])

    op.create_table(
        'pilot_shutdowns',
        _id(),
        sa.Column('shutdown_key', sa.String(length=80), nullable=False),
        sa.Column('pilot_id', sa.Uuid(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('preserved_counts', _json(), nullable=False, server_default='{}'),
        sa.Column('evidence_preserved', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('audit_preserved', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('provenance_preserved', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('decisions_preserved', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('incidents_preserved', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('model_activation_disabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('reauthorization_required', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('performed_by', sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint('shutdown_key', name='uq_pilot_shutdowns_key'),
    )
    op.create_index('ix_pilot_shutdowns_pilot', 'pilot_shutdowns', ['pilot_id', 'created_at'])

    op.create_table(
        'phase14_attestations',
        _id(),
        sa.Column('category', sa.String(length=80), nullable=False),
        sa.Column('criterion_key', sa.String(length=120), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('evidence_refs', _json(), nullable=False, server_default='[]'),
        sa.Column('blocking', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('assessed_by', sa.Uuid(), nullable=True),
        sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint('category', 'criterion_key', name='uq_phase14_attestations_criterion'),
    )
    op.create_index('ix_phase14_attestations_category', 'phase14_attestations', ['category'])
    op.create_index('ix_phase14_attestations_status', 'phase14_attestations', ['status'])

    op.create_table(
        'phase14_attestation_events',
        _id(),
        sa.Column('attestation_id', sa.Uuid(), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=True),
        sa.Column('to_status', sa.String(length=32), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('actor_email', sa.String(length=320), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        _event_timestamps(),
    )
    op.create_index('ix_phase14_attestation_events_attestation', 'phase14_attestation_events', ['attestation_id', 'created_at'])


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
    _add_shutdown_columns()
    _replace_check('pilots', 'ck_pilots_ck_pilots_status', PILOT_STATUSES_NEW_TIGHT)
    _replace_check('pilots', 'ck_pilots_pilot_status', PILOT_STATUSES_NEW)
    _replace_check('pilot_transitions', 'ck_pilot_transitions_pilot_transition_from', TRANSITION_FROM_NEW)
    _replace_check('pilot_transitions', 'ck_pilot_transitions_pilot_transition_to', TRANSITION_TO_NEW)
    _replace_check('pilot_transitions', 'ck_pilot_transitions_pilot_transition_action', ACTION_NEW)


def downgrade() -> None:
    _replace_check('pilot_transitions', 'ck_pilot_transitions_pilot_transition_action', ACTION_OLD)
    _replace_check('pilot_transitions', 'ck_pilot_transitions_pilot_transition_to', TRANSITION_TO_OLD)
    _replace_check('pilot_transitions', 'ck_pilot_transitions_pilot_transition_from', TRANSITION_FROM_OLD)
    _replace_check('pilots', 'ck_pilots_pilot_status', PILOT_STATUSES_OLD)
    _replace_check('pilots', 'ck_pilots_ck_pilots_status', PILOT_STATUSES_OLD_TIGHT)
    _drop_shutdown_columns()
    _drop_rls()
    for table in NEW_TABLES:
        op.drop_table(table)
