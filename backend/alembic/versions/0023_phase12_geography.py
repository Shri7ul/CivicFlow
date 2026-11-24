"""Phase 12 geographic contexts and explicit geographic labelling.

Revision ID: 0023_phase12_geography
Revises: 0022_snapshot_provenance
Create Date: 2026-11-25

Additive and non-rewriting. Historical NYC rows are labelled ``US-NYC`` from
their already-persisted source keys/regions. No hash, record, snapshot file or
historical provenance value is modified. Rows that cannot be classified remain
``UNKNOWN`` rather than being guessed.
"""
from __future__ import annotations

import json
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.geo.contexts import all_contexts

revision: str = '0023_phase12_geography'
down_revision: Union[str, None] = '0022_snapshot_provenance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TAGGED_TABLES = (
    "evidence_snapshots",
    "validation_datasets",
    "ground_truth_records",
    "correlation_universes",
    "pilots",
)


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def _add_context_label(table: str) -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column(
                    "geographic_context_key",
                    sa.String(length=32),
                    nullable=False,
                    server_default="UNKNOWN",
                )
            )
        return
    op.execute(
        f"ALTER TABLE public.{table} "
        "ADD COLUMN geographic_context_key VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN'"
    )


def _index_context_label(table: str) -> None:
    op.create_index(
        f"ix_{table}_geographic_context_key",
        table,
        ["geographic_context_key"],
        unique=False,
    )


def upgrade() -> None:
    op.create_table(
        'geographic_contexts',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('context_key', sa.String(length=32), nullable=False),
        sa.Column('display_name', sa.String(length=240), nullable=False),
        sa.Column('country_code', sa.String(length=8), nullable=False),
        sa.Column('country_name', sa.String(length=120), nullable=False),
        sa.Column('context_kind', sa.String(length=32), nullable=False),
        sa.Column('bbox_geojson', _json(), nullable=False),
        sa.Column('center_geojson', _json(), nullable=False),
        sa.Column('crs', sa.String(length=40), nullable=False),
        sa.Column('provenance_basis', sa.Text(), nullable=False),
        sa.Column('boundary_basis', sa.Text(), nullable=False),
        sa.Column('boundary_status', sa.String(length=32), nullable=False),
        sa.Column('operational_authority', sa.String(length=240), nullable=True),
        sa.Column('is_pilot_eligible', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('source_urls', _json(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('context_key', name='uq_geographic_contexts_key'),
    )
    op.create_index('ix_geographic_contexts_country', 'geographic_contexts', ['country_code'])

    connection = op.get_bind()

    def _json_value(value: object) -> str:
        # Bind JSON as text on both dialects. Psycopg adapts Python list/dict
        # to arrays/hstore, which would fail against a JSONB column; an
        # explicit JSON string is interpreted correctly by PostgreSQL.
        return json.dumps(value)

    for context in all_contexts():
        connection.execute(
            sa.text(
                "INSERT INTO geographic_contexts "
                "(id, context_key, display_name, country_code, country_name, "
                " context_kind, bbox_geojson, center_geojson, crs, "
                " provenance_basis, boundary_basis, boundary_status, "
                " operational_authority, is_pilot_eligible, source_urls, notes) "
                "VALUES (:id, :key, :display, :cc, :cn, :kind, :bbox, :center, :crs, "
                " :provenance, :boundary, :boundary_status, :authority, :eligible, "
                " :urls, :notes)"
            ),
            {
                "id": str(uuid.uuid4()),
                "key": context.key,
                "display": context.display_name,
                "cc": context.country_code,
                "cn": context.country_name,
                "kind": context.kind.value,
                "bbox": _json_value(context.bbox.as_geojson()),
                "center": _json_value(
                    {
                        "latitude": context.center_latitude,
                        "longitude": context.center_longitude,
                    }
                ),
                "crs": context.crs,
                "provenance": context.provenance_basis,
                "boundary": context.boundary_basis,
                "boundary_status": context.boundary_status.value,
                "authority": context.operational_authority,
                "eligible": context.is_pilot_eligible,
                "urls": _json_value(list(context.source_urls)),
                "notes": context.notes,
            },
        )

    if connection.dialect.name == "postgresql":
        op.execute("ALTER TABLE public.geographic_contexts ENABLE ROW LEVEL SECURITY")
        op.execute(
            "REVOKE ALL PRIVILEGES ON TABLE public.geographic_contexts "
            "FROM anon, authenticated"
        )
        op.execute("GRANT SELECT ON TABLE public.geographic_contexts TO authenticated")
        op.execute(
            "CREATE POLICY geographic_contexts_read_authenticated "
            "ON public.geographic_contexts FOR SELECT TO authenticated USING (true)"
        )

    for table in TAGGED_TABLES:
        _add_context_label(table)
        _index_context_label(table)

    op.execute(
        "UPDATE evidence_snapshots SET geographic_context_key = 'US-NYC' "
        "WHERE source_key LIKE 'nyc%' "
        "OR lower(COALESCE(geographic_coverage, '')) LIKE '%new york%'"
    )
    op.execute(
        "UPDATE validation_datasets SET geographic_context_key = 'US-NYC' "
        "WHERE dataset_key LIKE 'nyc311-%' "
        "OR lower(region) LIKE '%new york%'"
    )
    op.execute(
        "UPDATE pilots SET geographic_context_key = 'BD-DHAKA' "
        "WHERE lower(region) LIKE '%dhaka%'"
    )


def downgrade() -> None:
    for table in reversed(TAGGED_TABLES):
        op.drop_index(f"ix_{table}_geographic_context_key", table_name=table)
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table(table) as batch:
                batch.drop_column("geographic_context_key")
        else:
            op.execute(
                f"ALTER TABLE public.{table} DROP COLUMN geographic_context_key"
            )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP POLICY IF EXISTS geographic_contexts_read_authenticated "
            "ON public.geographic_contexts"
        )
    op.drop_index('ix_geographic_contexts_country', table_name='geographic_contexts')
    op.drop_table('geographic_contexts')
