"""Decision-intelligence scenarios, response actions, resources, and simulations.

These tables are deliberately separate from the generic Phase 1 ``scenarios``
foundation. Decision planning is staff-only and never dispatches units, reserves
resources, or mutates an incident.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    jsonb_column_type,
)
from app.models.enums import (
    DecisionStrategy,
    ResourceAllocationMode,
    ResourceAvailability,
    ResourceType,
    ResponseActionType,
    ScenarioHazard,
    ScenarioStatus,
    SimulationStatus,
)
from app.models.types import enum_column


class DecisionScenario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "decision_scenarios"
    __table_args__ = (
        CheckConstraint(
            "horizon_minutes >= 60 AND horizon_minutes <= 10080",
            name="ck_decision_scenarios_horizon_range",
        ),
        CheckConstraint(
            "resolution >= 7 AND resolution <= 10",
            name="ck_decision_scenarios_resolution_range",
        ),
        CheckConstraint(
            "risk_window_hours >= 1 AND risk_window_hours <= 2160",
            name="ck_decision_scenarios_risk_window_range",
        ),
        CheckConstraint(
            "budget_limit IS NULL OR budget_limit >= 0",
            name="ck_decision_scenarios_budget_nonnegative",
        ),
        Index("ix_decision_scenarios_created_by", "created_by"),
        Index("ix_decision_scenarios_status", "status"),
        Index("ix_decision_scenarios_created_at", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hazard_type: Mapped[ScenarioHazard] = mapped_column(
        enum_column(ScenarioHazard, "scenario_hazard"), nullable=False
    )
    parameters: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    horizon_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1440")
    )
    budget_limit: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    resolution: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("8")
    )
    risk_window_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("168")
    )
    status: Mapped[ScenarioStatus] = mapped_column(
        enum_column(ScenarioStatus, "scenario_status"),
        nullable=False,
        server_default=ScenarioStatus.DRAFT.value,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )

    creator: Mapped["Profile"] = relationship(foreign_keys=[created_by])
    actions: Mapped[list["DecisionAction"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="DecisionAction.priority.desc(), DecisionAction.created_at",
    )
    simulations: Mapped[list["DecisionSimulation"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )


class ResponseResource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Explicit planning inventory. Unknown availability is the safe default."""

    __tablename__ = "response_resources"
    __table_args__ = (
        CheckConstraint(
            "quantity_available >= 0",
            name="ck_response_resources_quantity_nonnegative",
        ),
        Index("ix_response_resources_type", "resource_type"),
        Index("ix_response_resources_status", "availability_status"),
        Index("ix_response_resources_department", "department_id"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[ResourceType] = mapped_column(
        enum_column(ResourceType, "resource_type"), nullable=False
    )
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity_available: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    availability_status: Mapped[ResourceAvailability] = mapped_column(
        enum_column(ResourceAvailability, "resource_availability"),
        nullable=False,
        server_default=ResourceAvailability.UNKNOWN.value,
    )
    availability_source: Mapped[str | None] = mapped_column(
        String(300), nullable=True
    )
    available_as_of: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    allocation_mode: Mapped[ResourceAllocationMode] = mapped_column(
        enum_column(ResourceAllocationMode, "resource_allocation_mode"),
        nullable=False,
        server_default=ResourceAllocationMode.SHARED_CAPACITY.value,
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    metadata_json: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )

    requirements: Mapped[list["ActionResourceRequirement"]] = relationship(
        back_populates="resource"
    )


class DecisionAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "decision_actions"
    __table_args__ = (
        CheckConstraint(
            "priority >= 1 AND priority <= 5",
            name="ck_decision_actions_priority_range",
        ),
        CheckConstraint(
            "earliest_start_minutes >= 0",
            name="ck_decision_actions_earliest_nonnegative",
        ),
        CheckConstraint(
            "duration_minutes >= 1 AND duration_minutes <= 10080",
            name="ck_decision_actions_duration_range",
        ),
        CheckConstraint(
            "expected_risk_reduction >= 0 AND expected_risk_reduction <= 100",
            name="ck_decision_actions_reduction_range",
        ),
        CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="ck_decision_actions_cost_nonnegative",
        ),
        CheckConstraint(
            "target_h3_cell_id IS NULL OR length(target_h3_cell_id) BETWEEN 15 AND 17",
            name="ck_decision_actions_h3_length",
        ),
        Index("ix_decision_actions_scenario", "scenario_id", "priority"),
        Index("ix_decision_actions_department", "department_id"),
        Index("ix_decision_actions_target_asset", "target_asset_id"),
        Index("ix_decision_actions_depends_on", "depends_on_action_id"),
    )

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("decision_scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_type: Mapped[ResponseActionType] = mapped_column(
        enum_column(ResponseActionType, "response_action_type"), nullable=False
    )
    target_h3_cell_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    target_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("infrastructure_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("3")
    )
    earliest_start_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("60")
    )
    expected_risk_reduction: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0")
    )
    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    depends_on_action_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("decision_actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    assumptions: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )

    scenario: Mapped["DecisionScenario"] = relationship(back_populates="actions")
    requirements: Mapped[list["ActionResourceRequirement"]] = relationship(
        back_populates="action", cascade="all, delete-orphan"
    )


class ActionResourceRequirement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "action_resource_requirements"
    __table_args__ = (
        CheckConstraint(
            "quantity_required > 0",
            name="ck_action_resource_requirements_quantity_positive",
        ),
        UniqueConstraint(
            "action_id",
            "resource_id",
            name="uq_action_resource_requirements_action_resource",
        ),
        Index("ix_action_resource_requirements_resource", "resource_id"),
    )

    action_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("decision_actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("response_resources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity_required: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    action: Mapped["DecisionAction"] = relationship(back_populates="requirements")
    resource: Mapped["ResponseResource"] = relationship(
        back_populates="requirements"
    )


class DecisionSimulation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "decision_simulations"
    __table_args__ = (
        CheckConstraint(
            "duration_ms >= 0",
            name="ck_decision_simulations_duration_nonnegative",
        ),
        Index("ix_decision_simulations_scenario", "scenario_id", "calculated_at"),
        Index("ix_decision_simulations_requested_by", "requested_by"),
        Index("ix_decision_simulations_strategy", "strategy"),
    )

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("decision_scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    strategy: Mapped[DecisionStrategy] = mapped_column(
        enum_column(DecisionStrategy, "decision_strategy"), nullable=False
    )
    status: Mapped[SimulationStatus] = mapped_column(
        enum_column(SimulationStatus, "simulation_status"),
        nullable=False,
        server_default=SimulationStatus.COMPLETED.value,
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    assumptions: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    result: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    summary: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    solver: Mapped[dict] = mapped_column(
        jsonb_column_type(), nullable=False, default=dict, server_default=text("'{}'")
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    scenario: Mapped["DecisionScenario"] = relationship(
        back_populates="simulations"
    )
