"""API schemas for staff-only decision intelligence and scenario planning."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import (
    DecisionStrategy,
    ResourceAllocationMode,
    ResourceAvailability,
    ResourceType,
    ResponseActionType,
    ScenarioHazard,
    ScenarioStatus,
    SimulationStatus,
)


class DecisionConfigResponse(BaseModel):
    model_version: str
    config_hash: str
    horizon_minutes: dict[str, int]
    max_actions: int
    max_resources: int
    solver_time_limit_ms: int
    default_risk_window_hours: int
    default_resolution: int
    objective_weights: dict[str, float]
    strategies: list[dict]
    limitations: list[str]


class ResourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    resource_type: ResourceType
    unit: str = Field(min_length=1, max_length=32)
    quantity_available: float = Field(default=0, ge=0, le=1_000_000)
    availability_status: ResourceAvailability = ResourceAvailability.UNKNOWN
    availability_source: str | None = Field(default=None, max_length=300)
    available_as_of: datetime | None = None
    allocation_mode: ResourceAllocationMode = ResourceAllocationMode.SHARED_CAPACITY
    department_id: uuid.UUID | None = None
    is_active: bool = True
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _availability_provenance(self) -> "ResourceCreate":
        self.name = self.name.strip()
        self.unit = self.unit.strip()
        if not self.name or not self.unit:
            raise ValueError("name and unit must not be empty")
        if self.availability_status != ResourceAvailability.UNKNOWN:
            if not (self.availability_source or "").strip():
                raise ValueError(
                    "availability_source is required for known or assumed availability"
                )
            if self.available_as_of is None:
                raise ValueError(
                    "available_as_of is required for known or assumed availability"
                )
        if self.availability_status in {
            ResourceAvailability.AVAILABLE,
            ResourceAvailability.LIMITED,
            ResourceAvailability.PLANNING_ASSUMPTION,
        } and self.quantity_available <= 0:
            raise ValueError("available/limited resources require a positive quantity")
        if self.availability_status == ResourceAvailability.UNAVAILABLE:
            self.quantity_available = 0
        return self


class ResourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    resource_type: ResourceType | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    quantity_available: float | None = Field(default=None, ge=0, le=1_000_000)
    availability_status: ResourceAvailability | None = None
    availability_source: str | None = Field(default=None, max_length=300)
    available_as_of: datetime | None = None
    allocation_mode: ResourceAllocationMode | None = None
    department_id: uuid.UUID | None = None
    is_active: bool | None = None
    metadata: dict | None = None


class ResourceRequirementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: uuid.UUID
    quantity_required: float = Field(gt=0, le=1_000_000)


class ResourceRequirementResponse(BaseModel):
    resource_id: uuid.UUID
    resource_name: str
    resource_type: str
    unit: str
    quantity_required: float
    availability_status: ResourceAvailability


class ResourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    resource_type: ResourceType
    unit: str
    quantity_available: float
    availability_status: ResourceAvailability
    availability_source: str | None
    available_as_of: datetime | None
    allocation_mode: ResourceAllocationMode
    department_id: uuid.UUID | None
    is_active: bool
    metadata: dict
    created_at: datetime
    updated_at: datetime


class ScenarioCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    hazard_type: ScenarioHazard
    horizon_minutes: int = Field(default=1440, ge=60, le=10080)
    budget_limit: float | None = Field(default=None, ge=0, le=1_000_000_000)
    resolution: int = Field(default=8, ge=7, le=10)
    risk_window_hours: int = Field(default=168, ge=1, le=2160)
    parameters: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalise(self) -> "ScenarioCreate":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name must not be empty")
        return self


class ScenarioUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    hazard_type: ScenarioHazard | None = None
    horizon_minutes: int | None = Field(default=None, ge=60, le=10080)
    budget_limit: float | None = Field(default=None, ge=0, le=1_000_000_000)
    resolution: int | None = Field(default=None, ge=7, le=10)
    risk_window_hours: int | None = Field(default=None, ge=1, le=2160)
    parameters: dict | None = None
    status: ScenarioStatus | None = None


class ActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    action_type: ResponseActionType
    target_h3_cell_id: str | None = Field(default=None, max_length=32)
    target_asset_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    priority: int = Field(default=3, ge=1, le=5)
    earliest_start_minutes: int = Field(default=0, ge=0, le=10080)
    duration_minutes: int = Field(default=60, ge=1, le=10080)
    expected_risk_reduction: float = Field(default=0, ge=0, le=100)
    estimated_cost: float | None = Field(default=None, ge=0, le=1_000_000_000)
    depends_on_action_id: uuid.UUID | None = None
    assumptions: dict = Field(default_factory=dict)
    resource_requirements: list[ResourceRequirementCreate] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def _normalise(self) -> "ActionCreate":
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("title must not be empty")
        if self.target_h3_cell_id is not None:
            self.target_h3_cell_id = self.target_h3_cell_id.strip() or None
        keys = [str(item.resource_id) for item in self.resource_requirements]
        if len(keys) != len(set(keys)):
            raise ValueError("resource_requirements must not duplicate a resource")
        return self


class ActionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    action_type: ResponseActionType | None = None
    target_h3_cell_id: str | None = Field(default=None, max_length=32)
    target_asset_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    earliest_start_minutes: int | None = Field(default=None, ge=0, le=10080)
    duration_minutes: int | None = Field(default=None, ge=1, le=10080)
    expected_risk_reduction: float | None = Field(default=None, ge=0, le=100)
    estimated_cost: float | None = Field(default=None, ge=0, le=1_000_000_000)
    depends_on_action_id: uuid.UUID | None = None
    is_active: bool | None = None
    assumptions: dict | None = None
    resource_requirements: list[ResourceRequirementCreate] | None = None


class ActionResponse(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    title: str
    description: str | None
    action_type: ResponseActionType
    target_h3_cell_id: str | None
    target_asset_id: uuid.UUID | None
    target_asset_name: str | None
    department_id: uuid.UUID | None
    department_name: str | None
    priority: int
    earliest_start_minutes: int
    duration_minutes: int
    expected_risk_reduction: float
    estimated_cost: float | None
    depends_on_action_id: uuid.UUID | None
    is_active: bool
    assumptions: dict
    resource_requirements: list[ResourceRequirementResponse]
    created_at: datetime
    updated_at: datetime


class ScenarioSummaryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    hazard_type: ScenarioHazard
    status: ScenarioStatus
    horizon_minutes: int
    budget_limit: float | None
    resolution: int
    risk_window_hours: int
    parameters: dict
    action_count: int
    simulation_count: int
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ScenarioDetailResponse(ScenarioSummaryResponse):
    actions: list[ActionResponse]


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: DecisionStrategy = DecisionStrategy.BALANCED
    persist: bool = True


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategies: list[DecisionStrategy] = Field(
        default_factory=lambda: list(DecisionStrategy)
    )

    @model_validator(mode="after")
    def _nonempty(self) -> "ComparisonRequest":
        if not self.strategies:
            raise ValueError("at least one strategy is required")
        if len(self.strategies) != len(set(self.strategies)):
            raise ValueError("strategies must not contain duplicates")
        return self


class SimulationListItem(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    strategy: DecisionStrategy
    status: SimulationStatus
    model_version: str
    config_hash: str
    duration_ms: int
    calculated_at: datetime
    summary: dict


class SimulationResponse(BaseModel):
    simulation_id: uuid.UUID | None
    scenario_id: uuid.UUID
    scenario_name: str
    strategy: DecisionStrategy
    status: SimulationStatus
    model_version: str
    config_hash: str
    risk_context: dict
    plan: dict
    assumptions: list[str]
    warnings: list[str]
    limitations: list[str]
    execution_authorized: Literal[False] = False
    dispatch_performed: Literal[False] = False
    reservations_created: Literal[False] = False
    generated_at: datetime
    calculated_at: datetime | None = None


class ComparisonResponse(BaseModel):
    scenario_id: uuid.UUID
    scenario_name: str
    model_version: str
    config_hash: str
    risk_context: dict
    comparison: dict
    generated_at: datetime
