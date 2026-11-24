"""Validated, versioned configuration for decision planning simulations."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Mapping

from app.core.config import Settings
from app.models import (
    DecisionStrategy,
    ResourceAvailability,
    ResourceType,
    ResponseActionType,
    ScenarioHazard,
    SimulationStatus,
)

STRATEGY_LABELS: Mapping[DecisionStrategy, str] = {
    DecisionStrategy.PRIORITY: "Priority-first",
    DecisionStrategy.RISK_REDUCTION: "Risk reduction",
    DecisionStrategy.COST_EFFICIENT: "Cost efficient",
    DecisionStrategy.BALANCED: "Balanced",
}

ACTION_TYPE_LABELS: Mapping[ResponseActionType, str] = {
    ResponseActionType.INSPECT: "Inspection",
    ResponseActionType.DISPATCH: "Dispatch",
    ResponseActionType.REPAIR: "Repair",
    ResponseActionType.CLEAN: "Clean / clear",
    ResponseActionType.EVACUATE: "Evacuation",
    ResponseActionType.SHELTER: "Shelter",
    ResponseActionType.MEDICAL: "Medical response",
    ResponseActionType.UTILITY: "Utility response",
    ResponseActionType.COMMUNICATION: "Public communication",
    ResponseActionType.OTHER: "Other",
}

HAZARD_LABELS: Mapping[ScenarioHazard, str] = {
    ScenarioHazard.FLOOD: "Flood",
    ScenarioHazard.DRAINAGE: "Drainage",
    ScenarioHazard.ROAD: "Road",
    ScenarioHazard.FIRE: "Fire",
    ScenarioHazard.HEALTH: "Health",
    ScenarioHazard.UTILITY: "Utility",
    ScenarioHazard.MULTI_HAZARD: "Multi-hazard",
    ScenarioHazard.OTHER: "Other",
}

RESOURCE_TYPE_LABELS: Mapping[ResourceType, str] = {
    ResourceType.PERSONNEL: "Personnel",
    ResourceType.VEHICLE: "Vehicle",
    ResourceType.EQUIPMENT: "Equipment",
    ResourceType.SUPPLY: "Supply",
    ResourceType.FACILITY: "Facility",
    ResourceType.OTHER: "Other",
}

RESOURCE_STATUS_LABELS: Mapping[ResourceAvailability, str] = {
    ResourceAvailability.UNKNOWN: "Unknown availability",
    ResourceAvailability.AVAILABLE: "Available",
    ResourceAvailability.LIMITED: "Limited",
    ResourceAvailability.UNAVAILABLE: "Unavailable",
    ResourceAvailability.PLANNING_ASSUMPTION: "Planning assumption",
}

SIMULATION_STATUS_LABELS: Mapping[SimulationStatus, str] = {
    SimulationStatus.COMPLETED: "Completed",
    SimulationStatus.PARTIAL: "Partial / time-limited",
    SimulationStatus.FAILED: "Failed",
}

ACTION_STATUS_LABELS: Mapping[str, str] = {
    "SCHEDULED": "Scheduled",
    "BLOCKED": "Blocked",
    "DEFERRED": "Deferred",
    "UNSCHEDULED": "Unscheduled",
}


class DecisionConfigError(ValueError):
    """Raised when decision configuration is internally inconsistent."""


@dataclass(frozen=True)
class DecisionConfig:
    model_version: str
    min_horizon_minutes: int
    max_horizon_minutes: int
    max_actions: int
    max_resources: int
    solver_time_limit_ms: int
    default_risk_window_hours: int
    default_resolution: int
    weight_risk_reduction: float
    weight_action_coverage: float
    weight_cost_efficiency: float
    weight_time_efficiency: float

    def __post_init__(self) -> None:
        if not self.model_version.strip():
            raise DecisionConfigError("decision model version must not be empty")
        if not 1 <= self.min_horizon_minutes <= self.max_horizon_minutes:
            raise DecisionConfigError("decision horizon bounds must be ordered")
        if self.max_actions < 1 or self.max_resources < 1:
            raise DecisionConfigError(
                "decision action/resource caps must be positive"
            )
        if not 50 <= self.solver_time_limit_ms <= 10_000:
            raise DecisionConfigError("solver time limit must be within 50..10000 ms")
        if not 1 <= self.default_risk_window_hours <= 2160:
            raise DecisionConfigError("default risk window must be within 1..2160 hours")
        if not 7 <= self.default_resolution <= 10:
            raise DecisionConfigError("default risk resolution must be within 7..10")
        weights = (
            self.weight_risk_reduction,
            self.weight_action_coverage,
            self.weight_cost_efficiency,
            self.weight_time_efficiency,
        )
        if any(not math.isfinite(weight) or weight < 0 for weight in weights):
            raise DecisionConfigError(
                "decision objective weights must be finite and non-negative"
            )
        if abs(sum(weights) - 1.0) > 1e-6:
            raise DecisionConfigError("decision objective weights must sum to 1.0")

    @classmethod
    def from_settings(cls, settings: Settings) -> "DecisionConfig":
        return cls(
            model_version=settings.decision_model_version,
            min_horizon_minutes=settings.decision_min_horizon_minutes,
            max_horizon_minutes=settings.decision_max_horizon_minutes,
            max_actions=settings.decision_max_actions,
            max_resources=settings.decision_max_resources,
            solver_time_limit_ms=settings.decision_solver_time_limit_ms,
            default_risk_window_hours=settings.decision_default_risk_window_hours,
            default_resolution=settings.decision_default_resolution,
            weight_risk_reduction=settings.decision_weight_risk_reduction,
            weight_action_coverage=settings.decision_weight_action_coverage,
            weight_cost_efficiency=settings.decision_weight_cost_efficiency,
            weight_time_efficiency=settings.decision_weight_time_efficiency,
        )

    @classmethod
    def from_dict(cls, payload: Mapping) -> "DecisionConfig":
        """Rehydrate a persisted decision model configuration."""
        horizon = payload.get("horizon_minutes", {})
        weights = payload.get("objective_weights", {})
        return cls(
            model_version=str(payload["model_version"]),
            min_horizon_minutes=int(horizon["min"]),
            max_horizon_minutes=int(horizon["max"]),
            max_actions=int(payload["max_actions"]),
            max_resources=int(payload["max_resources"]),
            solver_time_limit_ms=int(payload["solver_time_limit_ms"]),
            default_risk_window_hours=int(payload["default_risk_window_hours"]),
            default_resolution=int(payload["default_resolution"]),
            weight_risk_reduction=float(weights["risk_reduction"]),
            weight_action_coverage=float(weights["action_coverage"]),
            weight_cost_efficiency=float(weights["cost_efficiency"]),
            weight_time_efficiency=float(weights["time_efficiency"]),
        )

    def as_dict(self) -> dict:
        return {
            "model_version": self.model_version,
            "horizon_minutes": {
                "min": self.min_horizon_minutes,
                "max": self.max_horizon_minutes,
            },
            "max_actions": self.max_actions,
            "max_resources": self.max_resources,
            "solver_time_limit_ms": self.solver_time_limit_ms,
            "default_risk_window_hours": self.default_risk_window_hours,
            "default_resolution": self.default_resolution,
            "objective_weights": {
                "risk_reduction": self.weight_risk_reduction,
                "action_coverage": self.weight_action_coverage,
                "cost_efficiency": self.weight_cost_efficiency,
                "time_efficiency": self.weight_time_efficiency,
            },
        }

    @property
    def config_hash(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
