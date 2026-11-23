"""Decision intelligence, response actions, resources, and simulations.

Revision ID: 0011_decision_intelligence
Revises: 0010_risk_factor_default
Create Date: 2026-11-24

Staff-only planning tables. Simulation results are advisory and never dispatch
resources or create reservations.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.base import jsonb_column_type

revision: str = "0011_decision_intelligence"
down_revision: Union[str, None] = "0010_risk_factor_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

HAZARDS = "'FLOOD', 'DRAINAGE', 'ROAD', 'FIRE', 'HEALTH', 'UTILITY', 'MULTI_HAZARD', 'OTHER'"
ACTION_TYPES = (
    "'INSPECT', 'DISPATCH', 'REPAIR', 'CLEAN', 'EVACUATE', 'SHELTER', "
    "'MEDICAL', 'UTILITY', 'COMMUNICATION', 'OTHER'"
)
RESOURCE_TYPES = "'PERSONNEL', 'VEHICLE', 'EQUIPMENT', 'SUPPLY', 'FACILITY', 'OTHER'"
RESOURCE_STATUSES = (
    "'UNKNOWN', 'AVAILABLE', 'LIMITED', 'UNAVAILABLE', 'PLANNING_ASSUMPTION'"
)
ALLOCATION_MODES = "'SHARED_CAPACITY', 'CONSUMABLE'"
STRATEGIES = "'PRIORITY', 'RISK_REDUCTION', 'COST_EFFICIENT', 'BALANCED'"
SIMULATION_STATUSES = "'COMPLETED', 'PARTIAL', 'FAILED'"
SCENARIO_STATUSES = "'DRAFT', 'RUNNING', 'COMPLETED', 'FAILED', 'ARCHIVED'"


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def upgrade() -> None:
    op.create_table(
        "decision_scenarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("hazard_type", sa.String(length=32), nullable=False),
        sa.Column(
            "parameters",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "horizon_minutes", sa.Integer(), nullable=False, server_default=sa.text("1440")
        ),
        sa.Column("budget_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "resolution", sa.SmallInteger(), nullable=False, server_default=sa.text("8")
        ),
        sa.Column(
            "risk_window_hours", sa.Integer(), nullable=False, server_default=sa.text("168")
        ),
        sa.Column(
            "status",
            sa.String(length=9),
            nullable=False,
            server_default=sa.text("'DRAFT'"),
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            f"hazard_type IN ({HAZARDS})",
            name="ck_decision_scenarios_hazard_type",
        ),
        sa.CheckConstraint(
            "horizon_minutes >= 60 AND horizon_minutes <= 10080",
            name="ck_decision_scenarios_horizon_range",
        ),
        sa.CheckConstraint(
            "resolution >= 7 AND resolution <= 10",
            name="ck_decision_scenarios_resolution_range",
        ),
        sa.CheckConstraint(
            "risk_window_hours >= 1 AND risk_window_hours <= 2160",
            name="ck_decision_scenarios_risk_window_range",
        ),
        sa.CheckConstraint(
            "budget_limit IS NULL OR budget_limit >= 0",
            name="ck_decision_scenarios_budget_nonnegative",
        ),
        sa.CheckConstraint(
            f"status IN ({SCENARIO_STATUSES})",
            name="ck_decision_scenarios_scenario_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.id"],
            name="fk_decision_scenarios_created_by_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_decision_scenarios"),
    )
    op.create_index(
        "ix_decision_scenarios_created_by", "decision_scenarios", ["created_by"]
    )
    op.create_index("ix_decision_scenarios_status", "decision_scenarios", ["status"])
    op.create_index(
        "ix_decision_scenarios_created_at", "decision_scenarios", ["created_at"]
    )

    op.create_table(
        "response_resources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("resource_type", sa.String(length=16), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column(
            "quantity_available",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "availability_status",
            sa.String(length=24),
            nullable=False,
            server_default=sa.text("'UNKNOWN'"),
        ),
        sa.Column("availability_source", sa.String(length=300), nullable=True),
        sa.Column("available_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "allocation_mode",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'SHARED_CAPACITY'"),
        ),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "metadata_json",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            f"resource_type IN ({RESOURCE_TYPES})",
            name="ck_response_resources_resource_type",
        ),
        sa.CheckConstraint(
            f"availability_status IN ({RESOURCE_STATUSES})",
            name="ck_response_resources_availability_status",
        ),
        sa.CheckConstraint(
            f"allocation_mode IN ({ALLOCATION_MODES})",
            name="ck_response_resources_allocation_mode",
        ),
        sa.CheckConstraint(
            "quantity_available >= 0",
            name="ck_response_resources_quantity_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_response_resources_department_id_departments",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_response_resources"),
    )
    op.create_index("ix_response_resources_type", "response_resources", ["resource_type"])
    op.create_index(
        "ix_response_resources_status", "response_resources", ["availability_status"]
    )
    op.create_index(
        "ix_response_resources_department", "response_resources", ["department_id"]
    )

    op.create_table(
        "decision_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("action_type", sa.String(length=16), nullable=False),
        sa.Column("target_h3_cell_id", sa.String(length=32), nullable=True),
        sa.Column("target_asset_id", sa.Uuid(), nullable=True),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column(
            "earliest_start_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "duration_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column(
            "expected_risk_reduction",
            sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("estimated_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("depends_on_action_id", sa.Uuid(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "assumptions",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            f"action_type IN ({ACTION_TYPES})",
            name="ck_decision_actions_action_type",
        ),
        sa.CheckConstraint(
            "priority >= 1 AND priority <= 5",
            name="ck_decision_actions_priority_range",
        ),
        sa.CheckConstraint(
            "earliest_start_minutes >= 0",
            name="ck_decision_actions_earliest_nonnegative",
        ),
        sa.CheckConstraint(
            "duration_minutes >= 1 AND duration_minutes <= 10080",
            name="ck_decision_actions_duration_range",
        ),
        sa.CheckConstraint(
            "expected_risk_reduction >= 0 AND expected_risk_reduction <= 100",
            name="ck_decision_actions_reduction_range",
        ),
        sa.CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="ck_decision_actions_cost_nonnegative",
        ),
        sa.CheckConstraint(
            "target_h3_cell_id IS NULL OR length(target_h3_cell_id) BETWEEN 15 AND 17",
            name="ck_decision_actions_h3_length",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["decision_scenarios.id"],
            name="fk_decision_actions_scenario_id_decision_scenarios",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_asset_id"],
            ["infrastructure_assets.id"],
            name="fk_decision_actions_target_asset_id_infrastructure_assets",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_decision_actions_department_id_departments",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_action_id"],
            ["decision_actions.id"],
            name="fk_decision_actions_depends_on_action_id_decision_actions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_decision_actions"),
    )
    op.create_index(
        "ix_decision_actions_scenario", "decision_actions", ["scenario_id", "priority"]
    )
    op.create_index("ix_decision_actions_department", "decision_actions", ["department_id"])
    op.create_index("ix_decision_actions_target_asset", "decision_actions", ["target_asset_id"])
    op.create_index(
        "ix_decision_actions_depends_on", "decision_actions", ["depends_on_action_id"]
    )

    op.create_table(
        "action_resource_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_required", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint(
            "quantity_required > 0",
            name="ck_action_resource_requirements_quantity_positive",
        ),
        sa.ForeignKeyConstraint(
            ["action_id"],
            ["decision_actions.id"],
            name="fk_action_resource_requirements_action_id_decision_actions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["response_resources.id"],
            name="fk_action_resource_requirements_resource_id_response_resources",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_action_resource_requirements"),
        sa.UniqueConstraint(
            "action_id",
            "resource_id",
            name="uq_action_resource_requirements_action_resource",
        ),
    )
    op.create_index(
        "ix_action_resource_requirements_resource",
        "action_resource_requirements",
        ["resource_id"],
    )

    op.create_table(
        "decision_simulations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("strategy", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.String(length=9),
            nullable=False,
            server_default=sa.text("'COMPLETED'"),
        ),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "assumptions",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "result",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "summary",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "solver",
            jsonb_column_type(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "duration_ms", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            f"strategy IN ({STRATEGIES})",
            name="ck_decision_simulations_strategy",
        ),
        sa.CheckConstraint(
            f"status IN ({SIMULATION_STATUSES})",
            name="ck_decision_simulations_status",
        ),
        sa.CheckConstraint(
            "duration_ms >= 0",
            name="ck_decision_simulations_duration_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["decision_scenarios.id"],
            name="fk_decision_simulations_scenario_id_decision_scenarios",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["profiles.id"],
            name="fk_decision_simulations_requested_by_profiles",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_decision_simulations"),
    )
    op.create_index(
        "ix_decision_simulations_scenario",
        "decision_simulations",
        ["scenario_id", "calculated_at"],
    )
    op.create_index(
        "ix_decision_simulations_requested_by",
        "decision_simulations",
        ["requested_by"],
    )
    op.create_index(
        "ix_decision_simulations_strategy", "decision_simulations", ["strategy"]
    )

    if op.get_bind().dialect.name != "postgresql":
        return
    for table in (
        "decision_scenarios",
        "response_resources",
        "decision_actions",
        "action_resource_requirements",
        "decision_simulations",
    ):
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


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in (
            "decision_simulations",
            "action_resource_requirements",
            "decision_actions",
            "response_resources",
            "decision_scenarios",
        ):
            op.execute(
                f"DROP POLICY IF EXISTS {table}_read_staff ON public.{table}"
            )
    op.drop_index(
        "ix_action_resource_requirements_resource",
        table_name="action_resource_requirements",
    )
    op.drop_table("action_resource_requirements")
    op.drop_index("ix_decision_actions_depends_on", table_name="decision_actions")
    op.drop_index("ix_decision_actions_target_asset", table_name="decision_actions")
    op.drop_index("ix_decision_actions_department", table_name="decision_actions")
    op.drop_index("ix_decision_actions_scenario", table_name="decision_actions")
    op.drop_table("decision_actions")
    op.drop_index("ix_decision_simulations_strategy", table_name="decision_simulations")
    op.drop_index(
        "ix_decision_simulations_requested_by", table_name="decision_simulations"
    )
    op.drop_index(
        "ix_decision_simulations_scenario", table_name="decision_simulations"
    )
    op.drop_table("decision_simulations")
    op.drop_index("ix_response_resources_department", table_name="response_resources")
    op.drop_index("ix_response_resources_status", table_name="response_resources")
    op.drop_index("ix_response_resources_type", table_name="response_resources")
    op.drop_table("response_resources")
    op.drop_index("ix_decision_scenarios_created_at", table_name="decision_scenarios")
    op.drop_index("ix_decision_scenarios_status", table_name="decision_scenarios")
    op.drop_index("ix_decision_scenarios_created_by", table_name="decision_scenarios")
    op.drop_table("decision_scenarios")
