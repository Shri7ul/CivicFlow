"""Bounded planning-only validation of the Phase 6 decision engine.

Inputs are explicitly synthetic but internally consistent. The engine is run
twice to check deterministic scheduling; no dispatch or resource reservation is
performed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import h3

from app.core.config import Settings
from app.decisions.config import DecisionConfig
from app.decisions.engine import (
    ActionInput,
    RequirementInput,
    ResourceInput,
    RiskContext,
    compare_strategies,
)
from app.models import (
    DecisionStrategy,
    ResourceAllocationMode,
    ResourceAvailability,
)


def _uid(number: int) -> uuid.UUID:
    return uuid.UUID(int=number)


def _scenario() -> tuple[list[ActionInput], list[ResourceInput], RiskContext]:
    cells = {
        h3.latlng_to_cell(40.690 + index * 0.001, -73.980, 8): 70.0 - index * 5
        for index in range(6)
    }
    cell_ids = list(cells)
    personnel = ResourceInput(
        id=_uid(100),
        name="Inspection crew",
        resource_type="PERSONNEL",
        unit="crew",
        capacity=2,
        availability_status=ResourceAvailability.AVAILABLE,
        allocation_mode=ResourceAllocationMode.SHARED_CAPACITY,
        availability_source="synthetic planning assumption",
        available_as_of=None,
        department_id=None,
        is_active=True,
    )
    vehicle = ResourceInput(
        id=_uid(101),
        name="Service vehicle",
        resource_type="VEHICLE",
        unit="vehicle",
        capacity=1,
        availability_status=ResourceAvailability.AVAILABLE,
        allocation_mode=ResourceAllocationMode.SHARED_CAPACITY,
        availability_source="synthetic planning assumption",
        available_as_of=None,
        department_id=None,
        is_active=True,
    )
    supply = ResourceInput(
        id=_uid(102),
        name="Barricade kits",
        resource_type="SUPPLY",
        unit="kit",
        capacity=8,
        availability_status=ResourceAvailability.LIMITED,
        allocation_mode=ResourceAllocationMode.CONSUMABLE,
        availability_source="synthetic planning assumption",
        available_as_of=None,
        department_id=None,
        is_active=True,
    )
    unknown_equipment = ResourceInput(
        id=_uid(103),
        name="Unknown specialty equipment",
        resource_type="EQUIPMENT",
        unit="unit",
        capacity=0,
        availability_status=ResourceAvailability.UNKNOWN,
        allocation_mode=ResourceAllocationMode.SHARED_CAPACITY,
        availability_source=None,
        available_as_of=None,
        department_id=None,
        is_active=True,
    )
    resources = [personnel, vehicle, supply, unknown_equipment]

    def action(
        number: int,
        title: str,
        action_type: str,
        priority: int,
        reduction: float,
        duration: int,
        cost: float,
        requirements: list[tuple[ResourceInput, float]],
        *,
        depends_on: int | None = None,
        target_index: int = 0,
        assumptions: dict | None = None,
    ) -> ActionInput:
        return ActionInput(
            id=_uid(number),
            title=title,
            description="Synthetic planning validation action.",
            action_type=action_type,
            priority=priority,
            earliest_start_minutes=0,
            duration_minutes=duration,
            expected_risk_reduction=reduction,
            estimated_cost=cost,
            target_h3_cell_id=cell_ids[target_index % len(cell_ids)],
            target_asset_id=None,
            target_asset_name=None,
            department_id=None,
            department_name=None,
            depends_on_action_id=_uid(depends_on) if depends_on else None,
            assumptions=assumptions or {"basis": "synthetic planning assumption"},
            requirements=tuple(
                RequirementInput(resource_id=resource.id, quantity=quantity)
                for resource, quantity in requirements
            ),
        )

    actions = [
        action(1, "Inspect flooded drain", "INSPECT", 5, 5.0, 60, 100, [(personnel, 1), (vehicle, 1)]),
        action(2, "Clean blocked drain", "CLEAN", 5, 8.0, 120, 200, [(personnel, 2), (supply, 2)], depends_on=1),
        action(3, "Repair failed signal", "REPAIR", 4, 7.0, 120, 250, [(personnel, 2), (vehicle, 1), (unknown_equipment, 1)], target_index=1),
        action(4, "Barricade damaged curb", "OTHER", 3, 3.0, 30, 40, [(supply, 1)], target_index=2),
        action(5, "Inspect streetlight", "INSPECT", 3, 4.0, 45, 60, [(personnel, 1)], target_index=3),
        action(6, "Communicate road closure", "COMMUNICATION", 2, 2.0, 20, 20, [(supply, 1)], target_index=4),
        action(7, "Repair utility cover", "UTILITY", 4, 6.0, 90, 180, [(personnel, 1), (vehicle, 1)], target_index=5),
    ]
    return actions, resources, RiskContext(
        available=True,
        resolution=8,
        window_hours=168,
        cells=cells,
        cell_count=len(cells),
        incident_count=42,
        limitations=(
            "Synthetic risk context; not an observed incident forecast.",
            "Resource availability is a planning assumption.",
        ),
    )


def _signature(plan) -> list[tuple]:
    return [
        (
            str(item.action.id),
            item.status,
            item.start_minute,
            item.end_minute,
            round(item.planned_reduction, 4),
        )
        for item in plan.actions
    ]


def run_decision_validation(
    settings: Settings, config: DecisionConfig | None = None
) -> dict:
    actions, resources, risk_context = _scenario()
    config = config or DecisionConfig.from_settings(settings)
    comparison = compare_strategies(
        actions=actions,
        resources=resources,
        risk_context=risk_context,
        config=config,
        strategies=list(DecisionStrategy),
        horizon_minutes=480,
        budget_limit=500,
    )
    strategies = {}
    signatures = {}
    for plan in comparison.results:
        signatures[plan.strategy.value] = _signature(plan)
        strategies[plan.strategy.value] = {
            **plan.metrics,
            "solver": plan.solver,
            "assumptions": list(plan.assumptions),
            "warnings": list(plan.warnings),
            "limitations": list(plan.limitations),
            "actions": [
                {
                    "title": item.action.title,
                    "status": item.status,
                    "start_minute": item.start_minute,
                    "end_minute": item.end_minute,
                    "planned_reduction": item.planned_reduction,
                    "reasons": list(item.reasons),
                }
                for item in plan.actions
            ],
        }
    repeat = compare_strategies(
        actions=actions,
        resources=resources,
        risk_context=risk_context,
        config=config,
        strategies=list(DecisionStrategy),
        horizon_minutes=480,
        budget_limit=500,
    )
    repeat_signatures = {
        plan.strategy.value: _signature(plan) for plan in repeat.results
    }
    deterministic = all(
        signatures[strategy] == repeat_signatures[strategy]
        for strategy in signatures
    )
    return {
        "status": "COMPLETED",
        "scenario": {
            "name": "Synthetic multi-hazard planning fixture",
            "action_count": len(actions),
            "resource_count": len(resources),
            "budget_limit": 500,
            "horizon_minutes": 480,
            "risk_cell_count": risk_context.cell_count,
            "assumptions": list(risk_context.limitations),
        },
        "strategies": strategies,
        "winner": comparison.winner.value if comparison.winner else None,
        "deterministic_schedule": deterministic,
        "determinism_note": (
            "Scheduling signatures exclude elapsed solver time and are "
            "compared across two independent runs."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
