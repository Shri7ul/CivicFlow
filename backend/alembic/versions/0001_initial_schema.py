"""Initial CivicFlow schema (Goal 03).

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.base import geometry_type, jsonb_column_type, point_geography_type

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_VALUES = "'CITIZEN', 'WORKER', 'ADMIN'"
CATEGORY_VALUES = (
    "'ROADS', 'DRAINAGE', 'SANITATION', 'UTILITIES', 'PUBLIC_SAFETY', "
    "'HEALTH', 'ENVIRONMENT', 'OTHER'"
)
SEVERITY_VALUES = "'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'"
INCIDENT_STATUS_VALUES = "'OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'"
CLUSTER_STATUS_VALUES = "'ACTIVE', 'RESOLVED', 'ARCHIVED'"
ASSET_VALUES = (
    "'ROAD', 'DRAIN', 'HOSPITAL', 'SCHOOL', 'SHELTER', 'FIRE_STATION', "
    "'WATER_FACILITY', 'POWER_FACILITY', 'OTHER'"
)
DEPENDENCY_VALUES = (
    "'CONNECTS_TO', 'FEEDS', 'SERVES', 'DEPENDS_ON', 'ADJACENT_TO', "
    "'PROTECTS', 'OTHER'"
)
RISK_LEVEL_VALUES = "'LOW', 'MODERATE', 'HIGH', 'SEVERE', 'EXTREME'"
RISK_ENTITY_VALUES = (
    "'INCIDENT', 'INFRASTRUCTURE_ASSET', 'DEPARTMENT', 'RISK_CELL', 'SCENARIO'"
)
SCENARIO_STATUS_VALUES = "'DRAFT', 'RUNNING', 'COMPLETED', 'FAILED', 'ARCHIVED'"


def _timestamp(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        # Idempotent. On Supabase this extension must be enabled by an owner or
        # via Database > Extensions before running this migration.
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column(
            "role",
            sa.String(length=7),
            nullable=False,
            server_default=sa.text("'CITIZEN'"),
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            "length(trim(full_name)) > 0", name="ck_profiles_full_name_not_blank"
        ),
        sa.CheckConstraint(
            f"role IN ({ROLE_VALUES})", name="ck_profiles_profile_role"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_profiles"),
    )
    op.create_index("ix_profiles_role_is_active", "profiles", ["role", "is_active"])

    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.PrimaryKeyConstraint("id", name="pk_departments"),
    )
    op.create_index(
        "uq_departments_name_lower",
        "departments",
        [sa.text("lower(name)")],
        unique=True,
    )
    op.create_index("ix_departments_is_active", "departments", ["is_active"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=13), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=False),
        sa.Column(
            "status",
            sa.String(length=12),
            nullable=False,
            server_default=sa.text("'OPEN'"),
        ),
        sa.Column("location", point_geography_type(), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_department_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            f"category IN ({CATEGORY_VALUES})",
            name="ck_incidents_incident_category",
        ),
        sa.CheckConstraint(
            f"severity IN ({SEVERITY_VALUES})",
            name="ck_incidents_incident_severity",
        ),
        sa.CheckConstraint(
            f"status IN ({INCIDENT_STATUS_VALUES})",
            name="ck_incidents_incident_status",
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= created_at",
            name="ck_incidents_resolved_after_created",
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"],
            ["profiles.id"],
            name="fk_incidents_reporter_id_profiles",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_department_id"],
            ["departments.id"],
            name="fk_incidents_assigned_department_id_departments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_incidents"),
    )
    op.create_index(
        "ix_incidents_status_severity", "incidents", ["status", "severity"]
    )
    op.create_index("ix_incidents_category", "incidents", ["category"])
    op.create_index("ix_incidents_reporter_id", "incidents", ["reporter_id"])
    op.create_index(
        "ix_incidents_assigned_department_id",
        "incidents",
        ["assigned_department_id"],
    )
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])
    op.create_index(
        "ix_incidents_location_gist",
        "incidents",
        ["location"],
        postgresql_using="gist",
    )

    op.create_table(
        "incident_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=127), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "file_size > 0", name="ck_incident_evidence_file_size_positive"
        ),
        sa.UniqueConstraint("storage_path", name="storage_path_unique"),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name="fk_incident_evidence_incident_id_incidents",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["profiles.id"],
            name="fk_incident_evidence_uploaded_by_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_incident_evidence"),
    )
    op.create_index(
        "ix_incident_evidence_incident_id",
        "incident_evidence",
        ["incident_id"],
    )
    op.create_index(
        "ix_incident_evidence_uploaded_by", "incident_evidence", ["uploaded_by"]
    )
    op.create_index(
        "ix_incident_evidence_created_at", "incident_evidence", ["created_at"]
    )

    op.create_table(
        "incident_clusters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=13), nullable=False),
        sa.Column("centroid", point_geography_type(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=8),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            f"category IN ({CATEGORY_VALUES})",
            name="ck_incident_clusters_cluster_category",
        ),
        sa.CheckConstraint(
            f"status IN ({CLUSTER_STATUS_VALUES})",
            name="ck_incident_clusters_cluster_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_incident_clusters"),
    )
    op.create_index(
        "ix_incident_clusters_category", "incident_clusters", ["category"]
    )
    op.create_index("ix_incident_clusters_status", "incident_clusters", ["status"])
    op.create_index(
        "ix_incident_clusters_centroid_gist",
        "incident_clusters",
        ["centroid"],
        postgresql_using="gist",
    )

    op.create_table(
        "incident_cluster_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cluster_id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "cluster_id", "incident_id", name="cluster_incident_unique"
        ),
        sa.UniqueConstraint("incident_id", name="incident_single_cluster"),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["incident_clusters.id"],
            name="fk_incident_cluster_members_cluster_id_incident_clusters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name="fk_incident_cluster_members_incident_id_incidents",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_incident_cluster_members"),
    )
    op.create_index(
        "ix_incident_cluster_members_cluster_id",
        "incident_cluster_members",
        ["cluster_id"],
    )
    op.create_index(
        "ix_incident_cluster_members_incident_id",
        "incident_cluster_members",
        ["incident_id"],
    )

    op.create_table(
        "infrastructure_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("asset_type", sa.String(length=14), nullable=False),
        sa.Column("location", geometry_type("GEOMETRY"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "criticality_score",
            sa.Numeric(precision=4, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "metadata",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            f"asset_type IN ({ASSET_VALUES})",
            name="ck_infrastructure_assets_asset_type",
        ),
        sa.CheckConstraint(
            "criticality_score >= 0 AND criticality_score <= 10",
            name="ck_infrastructure_assets_criticality_score_range",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_infrastructure_assets"),
    )
    op.create_index("ix_infrastructure_assets_name", "infrastructure_assets", ["name"])
    op.create_index(
        "ix_infrastructure_assets_asset_type", "infrastructure_assets", ["asset_type"]
    )
    op.create_index(
        "ix_infrastructure_assets_is_active", "infrastructure_assets", ["is_active"]
    )
    op.create_index(
        "ix_infrastructure_assets_location_gist",
        "infrastructure_assets",
        ["location"],
        postgresql_using="gist",
    )

    op.create_table(
        "dependency_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("target_asset_id", sa.Uuid(), nullable=False),
        sa.Column("dependency_type", sa.String(length=12), nullable=False),
        sa.Column(
            "strength",
            sa.Numeric(precision=4, scale=3),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "source_asset_id <> target_asset_id",
            name="ck_dependency_edges_no_self_dependency",
        ),
        sa.CheckConstraint(
            "strength >= 0 AND strength <= 1",
            name="ck_dependency_edges_strength_range",
        ),
        sa.CheckConstraint(
            f"dependency_type IN ({DEPENDENCY_VALUES})",
            name="ck_dependency_edges_dependency_type",
        ),
        sa.UniqueConstraint(
            "source_asset_id",
            "target_asset_id",
            "dependency_type",
            name="dependency_logical_unique",
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"],
            ["infrastructure_assets.id"],
            name="fk_dependency_edges_source_asset_id_infrastructure_assets",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_asset_id"],
            ["infrastructure_assets.id"],
            name="fk_dependency_edges_target_asset_id_infrastructure_assets",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dependency_edges"),
    )
    op.create_index(
        "ix_dependency_edges_source_asset_id", "dependency_edges", ["source_asset_id"]
    )
    op.create_index(
        "ix_dependency_edges_target_asset_id", "dependency_edges", ["target_asset_id"]
    )
    op.create_index(
        "ix_dependency_edges_dependency_type", "dependency_edges", ["dependency_type"]
    )

    op.create_table(
        "risk_cells",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("h3_cell_id", sa.String(length=32), nullable=False),
        sa.Column("resolution", sa.SmallInteger(), nullable=False),
        sa.Column("boundary", geometry_type("POLYGON"), nullable=False),
        sa.Column(
            "current_risk_score",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "incident_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            "resolution >= 0 AND resolution <= 15",
            name="ck_risk_cells_resolution_range",
        ),
        sa.CheckConstraint(
            "current_risk_score >= 0 AND current_risk_score <= 100",
            name="ck_risk_cells_risk_score_range",
        ),
        sa.CheckConstraint(
            "incident_count >= 0", name="ck_risk_cells_incident_count_nonnegative"
        ),
        sa.UniqueConstraint("h3_cell_id", name="h3_cell_unique"),
        sa.PrimaryKeyConstraint("id", name="pk_risk_cells"),
    )
    op.create_index("ix_risk_cells_resolution", "risk_cells", ["resolution"])
    op.create_index(
        "ix_risk_cells_current_risk_score", "risk_cells", ["current_risk_score"]
    )
    op.create_index(
        "ix_risk_cells_boundary_gist",
        "risk_cells",
        ["boundary"],
        postgresql_using="gist",
    )

    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=21), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("risk_level", sa.String(length=8), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("explanation", jsonb_column_type(), nullable=False),
        sa.Column(
            "assessed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            f"entity_type IN ({RISK_ENTITY_VALUES})",
            name="ck_risk_assessments_risk_entity_type",
        ),
        sa.CheckConstraint(
            f"risk_level IN ({RISK_LEVEL_VALUES})",
            name="ck_risk_assessments_risk_level",
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_risk_assessments_assessment_score_range",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_assessments"),
    )
    op.create_index(
        "ix_risk_assessments_entity",
        "risk_assessments",
        ["entity_type", "entity_id", "assessed_at"],
    )
    op.create_index(
        "ix_risk_assessments_model_version", "risk_assessments", ["model_version"]
    )
    op.create_index(
        "ix_risk_assessments_risk_level", "risk_assessments", ["risk_level"]
    )

    op.create_table(
        "scenarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "parameters",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=9),
            nullable=False,
            server_default=sa.text("'DRAFT'"),
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            f"status IN ({SCENARIO_STATUS_VALUES})",
            name="ck_scenarios_scenario_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.id"],
            name="fk_scenarios_created_by_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scenarios"),
    )
    op.create_index("ix_scenarios_created_by", "scenarios", ["created_by"])
    op.create_index("ix_scenarios_status", "scenarios", ["status"])
    op.create_index("ix_scenarios_created_at", "scenarios", ["created_at"])

    op.create_table(
        "scenario_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("result", jsonb_column_type(), nullable=False),
        sa.Column("summary", jsonb_column_type(), nullable=True),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.id"],
            name="fk_scenario_results_scenario_id_scenarios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scenario_results"),
    )
    op.create_index(
        "ix_scenario_results_scenario_id", "scenario_results", ["scenario_id"]
    )
    op.create_index(
        "ix_scenario_results_calculated_at", "scenario_results", ["calculated_at"]
    )

    op.create_table(
        "role_change_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("target_profile_id", sa.Uuid(), nullable=True),
        sa.Column("old_role", sa.String(length=7), nullable=False),
        sa.Column("new_role", sa.String(length=7), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            f"old_role IN ({ROLE_VALUES})",
            name="ck_role_change_audits_audit_old_role",
        ),
        sa.CheckConstraint(
            f"new_role IN ({ROLE_VALUES})",
            name="ck_role_change_audits_audit_new_role",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["profiles.id"],
            name="fk_role_change_audits_actor_id_profiles",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_profile_id"],
            ["profiles.id"],
            name="fk_role_change_audits_target_profile_id_profiles",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_role_change_audits"),
    )
    op.create_index(
        "ix_role_change_audits_actor_id", "role_change_audits", ["actor_id"]
    )
    op.create_index(
        "ix_role_change_audits_target_profile_id",
        "role_change_audits",
        ["target_profile_id"],
    )
    op.create_index(
        "ix_role_change_audits_created_at", "role_change_audits", ["created_at"]
    )

    if is_postgres:
        op.execute(
            """
            CREATE OR REPLACE FUNCTION public.set_updated_at()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$;
            """
        )
        for table in (
            "profiles",
            "departments",
            "incidents",
            "incident_clusters",
            "infrastructure_assets",
            "risk_cells",
            "scenarios",
        ):
            op.execute(
                f"""
                CREATE TRIGGER {table}_set_updated_at
                BEFORE UPDATE ON public.{table}
                FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
                """
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        for table in (
            "profiles",
            "departments",
            "incidents",
            "incident_clusters",
            "infrastructure_assets",
            "risk_cells",
            "scenarios",
        ):
            op.execute(
                f"DROP TRIGGER IF EXISTS {table}_set_updated_at ON public.{table}"
            )
        op.execute("DROP FUNCTION IF EXISTS public.set_updated_at()")

    for table in (
        "role_change_audits",
        "scenario_results",
        "scenarios",
        "risk_assessments",
        "risk_cells",
        "dependency_edges",
        "infrastructure_assets",
        "incident_cluster_members",
        "incident_clusters",
        "incident_evidence",
        "incidents",
        "departments",
        "profiles",
    ):
        op.drop_table(table)

    # Never drop PostGIS: it may be shared with other Supabase schemas.
