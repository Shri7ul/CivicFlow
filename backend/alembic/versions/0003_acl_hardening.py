"""Phase 1.6 least-privilege hardening for Supabase table ACLs.

Revision ID: 0003_acl_hardening
Revises: 0002_auth_rls
Create Date: 2026-11-23

Supabase's default public-schema ACLs grant TRUNCATE, REFERENCES, TRIGGER,
and MAINTAIN to ``anon``/``authenticated`` on newly created tables. RLS does
not protect TRUNCATE. This migration replaces the inherited ACLs on CivicFlow
application tables with the minimum privileges needed by the Phase 1 API and
PostgREST policies.

service_role is intentionally left unchanged: it is a server-only Supabase
role and is never used by the frontend.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003_acl_hardening"
down_revision: Union[str, None] = "0002_auth_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_TABLES = (
    "profiles",
    "departments",
    "incidents",
    "incident_evidence",
    "incident_clusters",
    "incident_cluster_members",
    "infrastructure_assets",
    "dependency_edges",
    "risk_cells",
    "risk_assessments",
    "scenarios",
    "scenario_results",
    "role_change_audits",
)

INSERT_TABLES = ("incidents", "incident_evidence", "scenarios")
LEGACY_DEFAULT_PRIVILEGES = "TRUNCATE, REFERENCES, TRIGGER"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _grant_maintain_if_supported(roles: str) -> None:
    """MAINTAIN exists on PostgreSQL 17+, but not on older supported versions."""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF current_setting('server_version_num')::int >= 170000 THEN
                EXECUTE 'GRANT MAINTAIN ON TABLE {', '.join(f"public.{t}" for t in APP_TABLES)} TO {roles}';
            END IF;
        END;
        $$;
        """
    )


def upgrade() -> None:
    if not _is_postgres():
        return

    for table in APP_TABLES:
        # REVOKE ALL removes inherited default ACLs, including MAINTAIN where
        # supported. Column-level grants are revoked explicitly below.
        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE public.{table} "
            "FROM anon, authenticated"
        )
    op.execute(
        "REVOKE UPDATE (full_name, phone) ON TABLE public.profiles "
        "FROM anon, authenticated"
    )

    op.execute(
        "GRANT SELECT ON TABLE "
        + ", ".join(f"public.{table}" for table in APP_TABLES)
        + " TO authenticated"
    )
    op.execute(
        "GRANT INSERT ON TABLE "
        + ", ".join(f"public.{table}" for table in INSERT_TABLES)
        + " TO authenticated"
    )
    op.execute(
        "GRANT UPDATE (full_name, phone) ON TABLE public.profiles "
        "TO authenticated"
    )


def downgrade() -> None:
    if not _is_postgres():
        return

    # Restore the pre-0003 Supabase-style ACLs for development rollback only.
    op.execute(
        "GRANT SELECT ON TABLE "
        + ", ".join(f"public.{table}" for table in APP_TABLES)
        + " TO authenticated"
    )
    op.execute(
        "GRANT INSERT ON TABLE "
        + ", ".join(f"public.{table}" for table in INSERT_TABLES)
        + " TO authenticated"
    )
    op.execute(
        "GRANT UPDATE (full_name, phone) ON TABLE public.profiles "
        "TO authenticated"
    )
    op.execute(
        f"GRANT {LEGACY_DEFAULT_PRIVILEGES} ON TABLE "
        + ", ".join(f"public.{table}" for table in APP_TABLES)
        + " TO anon, authenticated"
    )
    _grant_maintain_if_supported("anon, authenticated")
