"""Supabase Row Level Security policies and profile privilege guards.

Revision ID: 0002_auth_rls
Revises: 0001_initial_schema
Create Date: 2026-11-23

This migration is intentionally Supabase-specific. It requires the Supabase
``auth`` schema/roles (``auth.uid()``, ``authenticated``). On non-PostgreSQL
dialects it is a no-op so isolated structural tests can still run.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_auth_rls"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = (
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

POLICIES = (
    ("profiles", "profiles_select_self", "SELECT",
     "id = auth.uid() OR public.is_admin()", None),
    ("profiles", "profiles_update_self", "UPDATE",
     "id = auth.uid()", "id = auth.uid()"),
    ("departments", "departments_read_authenticated", "SELECT",
     "is_active OR public.is_admin()", None),
    ("incidents", "incidents_read_owner_or_staff", "SELECT",
     "reporter_id = auth.uid() OR public.is_worker_or_admin()", None),
    ("incidents", "incidents_insert_own_open", "INSERT",
     None,
     "reporter_id = auth.uid() AND status = 'OPEN' "
     "AND assigned_department_id IS NULL"),
    ("incident_evidence", "evidence_read_visible_incident", "SELECT",
     "EXISTS (SELECT 1 FROM public.incidents i WHERE i.id = incident_id "
     "AND (i.reporter_id = auth.uid() OR public.is_worker_or_admin()))", None),
    ("incident_evidence", "evidence_insert_visible_incident", "INSERT",
     None,
     "uploaded_by = auth.uid() AND EXISTS (SELECT 1 FROM public.incidents i "
     "WHERE i.id = incident_id AND (i.reporter_id = auth.uid() "
     "OR public.is_worker_or_admin()))"),
    ("incident_clusters", "clusters_read_authenticated", "SELECT", "true", None),
    ("incident_cluster_members", "cluster_members_read_authenticated", "SELECT",
     "true", None),
    ("infrastructure_assets", "assets_read_authenticated", "SELECT",
     "is_active OR public.is_admin()", None),
    ("dependency_edges", "dependencies_read_authenticated", "SELECT", "true", None),
    ("risk_cells", "risk_cells_read_authenticated", "SELECT", "true", None),
    ("risk_assessments", "risk_assessments_read_staff", "SELECT",
     "public.is_worker_or_admin()", None),
    ("scenarios", "scenarios_read_owner_or_staff", "SELECT",
     "created_by = auth.uid() OR public.is_worker_or_admin()", None),
    ("scenarios", "scenarios_insert_own_draft", "INSERT",
     None, "created_by = auth.uid() AND status = 'DRAFT'"),
    ("scenario_results", "scenario_results_read_visible_scenario", "SELECT",
     "EXISTS (SELECT 1 FROM public.scenarios s WHERE s.id = scenario_id "
     "AND (s.created_by = auth.uid() OR public.is_worker_or_admin()))", None),
    ("role_change_audits", "role_audits_read_admin", "SELECT",
     "public.is_admin()", None),
)


def _create_policies() -> None:
    for table, name, command, using, check in POLICIES:
        clauses: list[str] = []
        if using is not None:
            clauses.append(f"USING ({using})")
        if check is not None:
            clauses.append(f"WITH CHECK ({check})")
        op.execute(
            f"CREATE POLICY {name} ON public.{table} FOR {command} "
            f"TO authenticated {' '.join(clauses)}"
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.current_app_role()
        RETURNS text
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT role::text
            FROM public.profiles
            WHERE id = auth.uid() AND is_active
            LIMIT 1
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.is_admin()
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$ SELECT public.current_app_role() = 'ADMIN' $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.is_worker_or_admin()
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$ SELECT public.current_app_role() IN ('WORKER', 'ADMIN') $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.prevent_profile_privileged_changes()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            -- Direct Supabase user updates carry auth.uid(). Backend service
            -- role operations have no end-user uid and remain allowed; backend
            -- authorization is still required.
            IF auth.uid() IS NOT NULL THEN
                IF NEW.id IS DISTINCT FROM OLD.id THEN
                    RAISE EXCEPTION 'profile identity is immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF NEW.role IS DISTINCT FROM OLD.role THEN
                    RAISE EXCEPTION 'role changes require backend authorization'
                        USING ERRCODE = '42501';
                END IF;
                IF NEW.is_active IS DISTINCT FROM OLD.is_active THEN
                    RAISE EXCEPTION 'activation changes require backend authorization'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER profiles_protect_privileged_fields
        BEFORE UPDATE ON public.profiles
        FOR EACH ROW EXECUTE FUNCTION public.prevent_profile_privileged_changes();
        """
    )

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")

    _create_policies()

    # Supabase normally grants table privileges to authenticated. Make it
    # explicit here so policies are not rendered ineffective by missing grants.
    op.execute(
        """
        GRANT SELECT ON public.profiles TO authenticated;
        GRANT UPDATE (full_name, phone) ON public.profiles TO authenticated;
        GRANT SELECT ON public.departments TO authenticated;
        GRANT SELECT, INSERT ON public.incidents TO authenticated;
        GRANT SELECT, INSERT ON public.incident_evidence TO authenticated;
        GRANT SELECT ON public.incident_clusters TO authenticated;
        GRANT SELECT ON public.incident_cluster_members TO authenticated;
        GRANT SELECT ON public.infrastructure_assets TO authenticated;
        GRANT SELECT ON public.dependency_edges TO authenticated;
        GRANT SELECT ON public.risk_cells TO authenticated;
        GRANT SELECT ON public.risk_assessments TO authenticated;
        GRANT SELECT, INSERT ON public.scenarios TO authenticated;
        GRANT SELECT ON public.scenario_results TO authenticated;
        GRANT SELECT ON public.role_change_audits TO authenticated;
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table, name, _command, _using, _check in reversed(POLICIES):
        op.execute(f"DROP POLICY IF EXISTS {name} ON public.{table}")

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")

    op.execute(
        "DROP TRIGGER IF EXISTS profiles_protect_privileged_fields "
        "ON public.profiles"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.prevent_profile_privileged_changes()"
    )
    op.execute("DROP FUNCTION IF EXISTS public.is_worker_or_admin()")
    op.execute("DROP FUNCTION IF EXISTS public.is_admin()")
    op.execute("DROP FUNCTION IF EXISTS public.current_app_role()")
