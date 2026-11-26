"""Weather-aware incident impact assessments.

Revision ID: 0026_weather_intelligence
Revises: 0025_workforce
Create Date: 2026-11-27

Additive and non-destructive. One new table, no seed rows, no data rewrite and
no change to existing tables. The table is RLS-protected and read-only to the
authenticated role; writes go through the trusted application role.

The FK to incidents is deliberately not declared in the database: incidents are
owned by another migration chain and a hard FK would complicate downgrade and
provider-independent local tests. Referential integrity is enforced by the
service layer, which always resolves a real incident before writing.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0026_weather_intelligence'
down_revision: Union[str, None] = '0025_workforce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'weather_assessments'
STATUSES = "'OK', 'STALE', 'ERROR', 'DISABLED'"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('incident_id', sa.Uuid(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('provider', sa.String(40), nullable=False),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('forecast_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('forecast_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('weather_snapshot', sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('assessment', sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('rule_engine_version', sa.String(40), nullable=False),
        sa.Column(
            'status',
            sa.String(20),
            sa.CheckConstraint(f"status IN ({STATUSES})", name='ck_weather_assessments_status'),
            nullable=False,
            server_default='OK',
        ),
        sa.Column('error_code', sa.String(80), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refresh_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('incident_id', name='uq_weather_assessments_incident'),
    )
    op.create_index('ix_weather_assessments_retrieved', TABLE, ['retrieved_at'])
    op.create_index('ix_weather_assessments_status', TABLE, ['status'])

    if op.get_bind().dialect.name == 'postgresql':
        op.execute(f'ALTER TABLE public.{TABLE} ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL PRIVILEGES ON TABLE public.{TABLE} FROM anon, authenticated')
        op.execute(f'GRANT SELECT ON TABLE public.{TABLE} TO authenticated')
        op.execute(
            f'CREATE POLICY {TABLE}_read_authenticated ON public.{TABLE} '
            'FOR SELECT TO authenticated USING (true)'
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        op.execute(f'DROP POLICY IF EXISTS {TABLE}_read_authenticated ON public.{TABLE}')
    op.drop_index('ix_weather_assessments_status', table_name=TABLE)
    op.drop_index('ix_weather_assessments_retrieved', table_name=TABLE)
    op.drop_table(TABLE)
