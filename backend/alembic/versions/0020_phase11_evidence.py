"""Phase 11 evidence snapshots, ground truth and correlation universes.

Revision ID: 0020_phase11_evidence
Revises: 0019_phase10_correlation
Create Date: 2026-11-25

Additive migration. Raw acquired bytes are retained for independent hash and
count recomputation. Snapshot/ground-truth event tables are append-only.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.models.base import geometry_type

revision: str = '0020_phase11_evidence'
down_revision: Union[str, None] = '0019_phase10_correlation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PHASE11_TABLES = (
    "evidence_snapshots",
    "evidence_snapshot_events",
    "ground_truth_records",
    "ground_truth_events",
    "correlation_universes",
)

APPEND_ONLY_TABLES = (
    "evidence_snapshot_events",
    "ground_truth_events",
)


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def _enable_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in PHASE11_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE public.{table} "
            "FROM anon, authenticated"
        )
        op.execute(f"GRANT SELECT ON TABLE public.{table} TO authenticated")
        op.execute(
            f"CREATE POLICY {table}_read_staff ON public.{table} "
            "FOR SELECT TO authenticated USING (public.is_worker_or_admin())"
        )


def _enable_append_only_guards() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_append_only "
            f"BEFORE UPDATE OR DELETE ON public.{table} "
            "FOR EACH ROW EXECUTE FUNCTION "
            "public.civicflow_prevent_append_only_mutation()"
        )


def upgrade() -> None:
    op.create_table(
        'evidence_snapshots',
        sa.Column('snapshot_key', sa.String(length=120), nullable=False),
        sa.Column('kind', sa.Enum('RESEARCH_DATASET', 'INFRASTRUCTURE', name='evidence_snapshot_kind', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('status', sa.Enum('FETCHING', 'VALIDATED', 'FAILED', 'QUARANTINED', 'SUPERSEDED', name='evidence_snapshot_status', native_enum=False, create_constraint=True), server_default='FETCHING', nullable=False),
        sa.Column('source_key', sa.String(length=80), nullable=False),
        sa.Column('source_url', sa.String(length=1000), nullable=False),
        sa.Column('provider', sa.String(length=240), nullable=False),
        sa.Column('license_note', sa.Text(), nullable=False),
        sa.Column('dataset_version', sa.String(length=120), nullable=False),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('snapshot_sha256', sa.String(length=64), nullable=True),
        sa.Column('raw_sha256', sa.String(length=64), nullable=True),
        sa.Column('schema_version', sa.String(length=40), nullable=False),
        sa.Column('schema_fingerprint', sa.String(length=64), nullable=True),
        sa.Column('record_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('raw_record_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('duplicate_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('invalid_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('missing_fields', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('byte_size', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('media_type', sa.String(length=80), server_default='application/json', nullable=False),
        sa.Column('crs', sa.String(length=40), nullable=True),
        sa.Column('bbox', _json(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('data_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('data_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('geographic_coverage', sa.Text(), nullable=True),
        sa.Column('quality_status', sa.Enum('PASS', 'WARN', 'FAIL', 'UNKNOWN', name='evidence_quality_status', native_enum=False, create_constraint=True), server_default='UNKNOWN', nullable=False),
        sa.Column('quality_checks', _json(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('lineage', _json(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('verification_status', sa.Enum('PENDING', 'AUTOMATED_RECOMPUTATION', 'FAILED', name='snapshot_verification_status', native_enum=False, create_constraint=True), server_default='PENDING', nullable=False),
        sa.Column('verification_checks', _json(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('verification_note', sa.Text(), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_current', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('supersedes_snapshot_id', sa.Uuid(), nullable=True),
        sa.Column('validation_dataset_id', sa.Uuid(), nullable=True),
        sa.Column('infrastructure_source_id', sa.Uuid(), nullable=True),
        sa.Column('raw_content', sa.LargeBinary(), nullable=True),
        sa.Column('normalized_content', sa.LargeBinary(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.CheckConstraint('record_count >= 0 AND raw_record_count >= 0 AND duplicate_count >= 0 AND invalid_count >= 0 AND missing_fields >= 0 AND byte_size >= 0', name='ck_evidence_snapshots_counts'),
        sa.CheckConstraint('validation_dataset_id IS NULL OR infrastructure_source_id IS NULL', name='ck_evidence_snapshots_single_link'),
        sa.CheckConstraint("status <> 'VALIDATED' OR (snapshot_sha256 IS NOT NULL AND length(snapshot_sha256) = 64)", name='ck_evidence_snapshots_valid_hash'),
        sa.ForeignKeyConstraint(['created_by'], ['profiles.id'], name='fk_evidence_snapshots_created_by_profiles', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['infrastructure_source_id'], ['infrastructure_sources.id'], name='fk_evidence_snapshots_infra_source', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['supersedes_snapshot_id'], ['evidence_snapshots.id'], name='fk_evidence_snapshots_supersedes_snapshot_id_evidence_snapshots', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['validation_dataset_id'], ['validation_datasets.id'], name='fk_evidence_snapshots_validation_dataset_id_validation_datasets', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='pk_evidence_snapshots'),
        sa.UniqueConstraint('snapshot_key', name='uq_evidence_snapshots_key'),
        sa.UniqueConstraint('source_key', 'snapshot_sha256', name='uq_evidence_snapshots_source_hash'),
    )
    op.create_index('ix_evidence_snapshots_source_retrieved', 'evidence_snapshots', ['source_key', 'retrieved_at'], unique=False)
    op.create_index('ix_evidence_snapshots_kind_status', 'evidence_snapshots', ['kind', 'status'], unique=False)
    op.create_index('ix_evidence_snapshots_current', 'evidence_snapshots', ['source_key', 'is_current'], unique=False)
    op.create_index('ix_evidence_snapshots_dataset', 'evidence_snapshots', ['validation_dataset_id'], unique=False)
    op.create_index('ix_evidence_snapshots_infra', 'evidence_snapshots', ['infrastructure_source_id'], unique=False)

    op.create_table(
        'evidence_snapshot_events',
        sa.Column('snapshot_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('from_status', sa.Enum('FETCHING', 'VALIDATED', 'FAILED', 'QUARANTINED', 'SUPERSEDED', name='snapshot_event_from', native_enum=False, create_constraint=True), nullable=True),
        sa.Column('to_status', sa.Enum('FETCHING', 'VALIDATED', 'FAILED', 'QUARANTINED', 'SUPERSEDED', name='snapshot_event_to', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('actor_email', sa.String(length=320), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['profiles.id'], name='fk_evidence_snapshot_events_actor_id_profiles', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['snapshot_id'], ['evidence_snapshots.id'], name='fk_evidence_snapshot_events_snapshot_id_evidence_snapshots', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='pk_evidence_snapshot_events'),
    )
    op.create_index('ix_evidence_snapshot_events_snapshot', 'evidence_snapshot_events', ['snapshot_id', 'created_at'], unique=False)

    op.create_table(
        'ground_truth_records',
        sa.Column('record_key', sa.String(length=120), nullable=False),
        sa.Column('incident_id', sa.Uuid(), nullable=True),
        sa.Column('source_type', sa.Enum('CITIZEN_REPORT', 'AI_PREDICTION', 'HUMAN_OBSERVATION', 'FIELD_OBSERVATION', 'RESOLUTION_EVIDENCE', 'INDEPENDENT_EVIDENCE', 'OFFICIAL_RECORD', name='ground_truth_source_type', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('source_name', sa.String(length=240), nullable=False),
        sa.Column('source_reference', sa.String(length=500), nullable=True),
        sa.Column('incident_type', sa.String(length=80), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('uncertainty', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('location', geometry_type('POINT'), nullable=True),
        sa.Column('sensitive', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('status', sa.Enum('UNVERIFIED', 'IN_REVIEW', 'VERIFIED', 'REJECTED', 'INSUFFICIENT_EVIDENCE', name='ground_truth_status', native_enum=False, create_constraint=True), server_default='UNVERIFIED', nullable=False),
        sa.Column('verification_method', sa.String(length=120), nullable=True),
        sa.Column('verified_by', sa.Uuid(), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('evidence_refs', _json(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('verification_evidence_refs', _json(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('verification_note', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('uncertainty IS NULL OR (uncertainty >= 0 AND uncertainty <= 1)', name='ck_ground_truth_uncertainty'),
        sa.CheckConstraint("status IN ('UNVERIFIED','IN_REVIEW') OR (verified_by IS NOT NULL AND verified_at IS NOT NULL AND verification_method IS NOT NULL)", name='ck_ground_truth_decision_identity'),
        sa.ForeignKeyConstraint(['created_by'], ['profiles.id'], name='fk_ground_truth_records_created_by_profiles', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], name='fk_ground_truth_records_incident_id_incidents', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['verified_by'], ['profiles.id'], name='fk_ground_truth_records_verified_by_profiles', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_ground_truth_records'),
        sa.UniqueConstraint('record_key', name='uq_ground_truth_records_key'),
        sa.UniqueConstraint('source_type', 'source_reference', name='uq_ground_truth_source_reference'),
    )
    op.create_index('ix_ground_truth_status_created', 'ground_truth_records', ['status', 'created_at'], unique=False)
    op.create_index('ix_ground_truth_incident', 'ground_truth_records', ['incident_id'], unique=False)
    op.create_index('ix_ground_truth_location_gist', 'ground_truth_records', ['location'], unique=False, postgresql_using='gist')

    op.create_table(
        'ground_truth_events',
        sa.Column('record_id', sa.Uuid(), nullable=False),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('from_status', sa.Enum('UNVERIFIED', 'IN_REVIEW', 'VERIFIED', 'REJECTED', 'INSUFFICIENT_EVIDENCE', name='ground_truth_event_from', native_enum=False, create_constraint=True), nullable=True),
        sa.Column('to_status', sa.Enum('UNVERIFIED', 'IN_REVIEW', 'VERIFIED', 'REJECTED', 'INSUFFICIENT_EVIDENCE', name='ground_truth_event_to', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('actor_email', sa.String(length=320), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('evidence_refs', _json(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['profiles.id'], name='fk_ground_truth_events_actor_id_profiles', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['record_id'], ['ground_truth_records.id'], name='fk_ground_truth_events_record_id_ground_truth_records', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='pk_ground_truth_events'),
    )
    op.create_index('ix_ground_truth_events_record', 'ground_truth_events', ['record_id', 'created_at'], unique=False)

    op.create_table(
        'correlation_universes',
        sa.Column('universe_key', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=240), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.String(length=40), nullable=False),
        sa.Column('provenance_kind', sa.Enum('OPERATIONAL', 'SYNTHETIC', 'MIXED', 'UNKNOWN', name='correlation_universe_provenance', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('reference_complete', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('reference_size', sa.Integer(), nullable=True),
        sa.Column('reference_note', sa.Text(), nullable=True),
        sa.Column('candidate_method', sa.String(length=80), nullable=False),
        sa.Column('candidate_method_version', sa.String(length=40), nullable=False),
        sa.Column('reference_dataset_snapshot_id', sa.Uuid(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.CheckConstraint('reference_size IS NULL OR reference_size >= 0', name='ck_correlation_universes_size'),
        sa.CheckConstraint('reference_complete = false OR (reference_size IS NOT NULL AND reference_note IS NOT NULL)', name='ck_correlation_universes_complete'),
        sa.ForeignKeyConstraint(['created_by'], ['profiles.id'], name='fk_correlation_universes_created_by_profiles', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reference_dataset_snapshot_id'], ['evidence_snapshots.id'], name='fk_correlation_universes_reference_snapshot', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='pk_correlation_universes'),
        sa.UniqueConstraint('universe_key', name='uq_correlation_universes_key'),
    )
    op.create_index('ix_correlation_universes_provenance', 'correlation_universes', ['provenance_kind'], unique=False)

    if op.get_bind().dialect.name == "sqlite":
        # SQLite cannot ALTER constraints in place; batch mode recreates the
        # table for the migration-integrity tests only.
        with op.batch_alter_table("infrastructure_assets") as batch:
            batch.add_column(sa.Column("source_id", sa.Uuid(), nullable=True))
            batch.add_column(sa.Column("snapshot_id", sa.Uuid(), nullable=True))
            batch.add_column(sa.Column("external_id", sa.String(length=120), nullable=True))
            batch.create_foreign_key(
                "fk_evidence_assets_source",
                "infrastructure_sources",
                ["source_id"],
                ["id"],
                ondelete="RESTRICT",
            )
            batch.create_foreign_key(
                "fk_evidence_assets_snapshot",
                "evidence_snapshots",
                ["snapshot_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_unique_constraint(
                "uq_infrastructure_assets_source_external",
                ["source_id", "external_id"],
            )
            # SQLite reflection re-applies the naming convention and cannot
            # reliably drop the legacy CHECK. Production PostgreSQL uses the
            # exact raw SQL below; SQLite is a structural test mirror only.
        op.create_index(
            "ix_infrastructure_assets_source",
            "infrastructure_assets",
            ["source_id"],
            unique=False,
        )
        op.create_index(
            "ix_infrastructure_assets_snapshot",
            "infrastructure_assets",
            ["snapshot_id"],
            unique=False,
        )
    else:
        op.add_column('infrastructure_assets', sa.Column('source_id', sa.Uuid(), nullable=True))
        op.add_column('infrastructure_assets', sa.Column('snapshot_id', sa.Uuid(), nullable=True))
        op.add_column('infrastructure_assets', sa.Column('external_id', sa.String(length=120), nullable=True))
        op.create_foreign_key('fk_infrastructure_assets_source_id_infrastructure_sources', 'infrastructure_assets', 'infrastructure_sources', ['source_id'], ['id'], ondelete='RESTRICT')
        op.create_foreign_key('fk_infrastructure_assets_snapshot_id_evidence_snapshots', 'infrastructure_assets', 'evidence_snapshots', ['snapshot_id'], ['id'], ondelete='SET NULL')
        op.create_unique_constraint('uq_infrastructure_assets_source_external', 'infrastructure_assets', ['source_id', 'external_id'])
        op.create_index('ix_infrastructure_assets_source', 'infrastructure_assets', ['source_id'], unique=False)
        op.create_index('ix_infrastructure_assets_snapshot', 'infrastructure_assets', ['snapshot_id'], unique=False)
        op.execute(
            "ALTER TABLE public.infrastructure_assets "
            "DROP CONSTRAINT ck_infrastructure_assets_ck_infrastructure_assets_asset_type"
        )
        op.execute(
            "ALTER TABLE public.infrastructure_assets "
            "ADD CONSTRAINT ck_infrastructure_assets_ck_infrastructure_assets_asset_type "
            "CHECK (asset_type IN ('ROAD','DRAIN','HOSPITAL','SCHOOL','SHELTER',"
            "'FIRE_STATION','WATER_FACILITY','POWER_FACILITY','BRIDGE','OTHER'))"
        )

    _enable_rls()
    _enable_append_only_guards()


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in APPEND_ONLY_TABLES:
            op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON public.{table}")
        for table in PHASE11_TABLES:
            op.execute(f"DROP POLICY IF EXISTS {table}_read_staff ON public.{table}")
            op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")

    if op.get_bind().dialect.name == "sqlite":
        op.drop_index('ix_infrastructure_assets_snapshot', table_name='infrastructure_assets')
        op.drop_index('ix_infrastructure_assets_source', table_name='infrastructure_assets')
        with op.batch_alter_table("infrastructure_assets") as batch:
            batch.drop_column('external_id')
            batch.drop_column('snapshot_id')
            batch.drop_column('source_id')
    else:
        op.execute(
            "ALTER TABLE public.infrastructure_assets "
            "DROP CONSTRAINT ck_infrastructure_assets_ck_infrastructure_assets_asset_type"
        )
        op.execute(
            "ALTER TABLE public.infrastructure_assets "
            "ADD CONSTRAINT ck_infrastructure_assets_ck_infrastructure_assets_asset_type "
            "CHECK (asset_type IN ('ROAD','DRAIN','HOSPITAL','SCHOOL','SHELTER',"
            "'FIRE_STATION','WATER_FACILITY','POWER_FACILITY','OTHER'))"
        )
        op.drop_index('ix_infrastructure_assets_snapshot', table_name='infrastructure_assets')
        op.drop_index('ix_infrastructure_assets_source', table_name='infrastructure_assets')
        op.drop_constraint('uq_infrastructure_assets_source_external', 'infrastructure_assets', type_='unique')
        op.drop_constraint('fk_infrastructure_assets_snapshot_id_evidence_snapshots', 'infrastructure_assets', type_='foreignkey')
        op.drop_constraint('fk_infrastructure_assets_source_id_infrastructure_sources', 'infrastructure_assets', type_='foreignkey')
        op.drop_column('infrastructure_assets', 'external_id')
        op.drop_column('infrastructure_assets', 'snapshot_id')
        op.drop_column('infrastructure_assets', 'source_id')

    op.drop_index('ix_correlation_universes_provenance', table_name='correlation_universes')
    op.drop_table('correlation_universes')
    op.drop_index('ix_ground_truth_events_record', table_name='ground_truth_events')
    op.drop_table('ground_truth_events')
    op.drop_index('ix_ground_truth_location_gist', table_name='ground_truth_records')
    op.drop_index('ix_ground_truth_incident', table_name='ground_truth_records')
    op.drop_index('ix_ground_truth_status_created', table_name='ground_truth_records')
    op.drop_table('ground_truth_records')
    op.drop_index('ix_evidence_snapshot_events_snapshot', table_name='evidence_snapshot_events')
    op.drop_table('evidence_snapshot_events')
    op.drop_index('ix_evidence_snapshots_infra', table_name='evidence_snapshots')
    op.drop_index('ix_evidence_snapshots_dataset', table_name='evidence_snapshots')
    op.drop_index('ix_evidence_snapshots_current', table_name='evidence_snapshots')
    op.drop_index('ix_evidence_snapshots_kind_status', table_name='evidence_snapshots')
    op.drop_index('ix_evidence_snapshots_source_retrieved', table_name='evidence_snapshots')
    op.drop_table('evidence_snapshots')
