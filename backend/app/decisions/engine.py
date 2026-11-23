"""Bounded, explainable decision-plan simulation.

The engine is intentionally deterministic and planning-only. It never
dispatches units, reserves resources, changes an incident, or claims that a
predicted risk reduction is an observed outcome.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable, Mapping
from uuid import UUID

from app.decisions.config import DecisionConfig, STRATEGY_LABELS
from app.models import (
    DecisionStrategy,
    ResourceAllocationMode,
    ResourceAvailability,
)

EPSILON = 1e-9


class DecisionError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResourceInput:
    id: UUID
    name: str
    resource_type: str
    unit: str
    capacity: float
    availability_status: ResourceAvailability
    allocation_mode: ResourceAllocationMode
    availability_source: str | None
    available_as_of: object | None
    department_id: UUID | None
    is_active: bool


@dataclass(frozen=True)
class RequirementInput:
    resource_id: UUID
    quantity: float


@dataclass(frozen=True)
class ActionInput:
    id: UUID
    title: str
    description: str | None
    action_type: str
    priority: int
    earliest_start_minutes: int
    duration_minutes: int
    expected_risk_reduction: float
    estimated_cost: float | None
    target_h3_cell_id: str | None
    target_asset_id: UUID | None
    target_asset_name: str | None
    department_id: UUID | None
    department_name: str | None
    depends_on_action_id: UUID | None
    assumptions: Mapping[str, object]
    requirements: tuple[RequirementInput, ...]


@dataclass(frozen=True)
class RiskContext:
    available: bool
    resolution: int
    window_hours: int
    cells: Mapping[str, float]
    cell_count: int
    incident_count: int
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class _Allocation:
    start: int
    end: int
    quantity: float


@dataclass(frozen=True)
class ScheduledAction:
    action: ActionInput
    status: str
    start_minute: int | None
    end_minute: int | None
    planned_reduction: float
    target_risk_score: float | None
    reasons: tuple[str, ...]
    resources: tuple[dict, ...]


@dataclass(frozen=True)
class StrategyPlan:
    strategy: DecisionStrategy
    strategy_label: str
    actions: tuple[ScheduledAction, ...]
    metrics: dict
    objective_score: float
    objective_components: dict
    solver: dict
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    resources: tuple[dict, ...]


@dataclass(frozen=True)
class StrategyComparison:
    results: tuple[StrategyPlan, ...]
    winner: DecisionStrategy | None
    solver: dict
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]


def _utc_text(value: object | None) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _resource_capacity(resource: ResourceInput) -> float:
    if resource.availability_status in {
        ResourceAvailability.AVAILABLE,
        ResourceAvailability.LIMITED,
        ResourceAvailability.PLANNING_ASSUMPTION,
    }:
        return max(0.0, resource.capacity)
    return 0.0


def _strategy_order(action: ActionInput, strategy: DecisionStrategy) -> tuple:
    cost = action.estimated_cost if action.estimated_cost is not None else 0.0
    if strategy == DecisionStrategy.RISK_REDUCTION:
        return (
            -action.expected_risk_reduction,
            -action.priority,
            action.duration_minutes,
            str(action.id),
        )
    if strategy == DecisionStrategy.COST_EFFICIENT:
        return (
            -(action.expected_risk_reduction / (cost + 1.0)),
            -action.expected_risk_reduction,
            -action.priority,
            str(action.id),
        )
    if strategy == DecisionStrategy.BALANCED:
        duration_penalty = 1.0 / (action.duration_minutes + 60.0)
        return (
            -(
                action.expected_risk_reduction * 0.6
                + action.priority * 8.0
                + duration_penalty * 100.0
                - cost * 0.001
            ),
            -action.priority,
            str(action.id),
        )
    return (
        -action.priority,
        -action.expected_risk_reduction,
        action.duration_minutes,
        str(action.id),
    )


def _cycle_actions(actions: Iterable[ActionInput]) -> set[UUID]:
    action_map = {action.id: action for action in actions}
    indegree = {action.id: 0 for action in action_map.values()}
    edges: dict[UUID, list[UUID]] = {
        action.id: [] for action in action_map.values()
    }
    for action in action_map.values():
        dependency = action.depends_on_action_id
        if dependency is not None and dependency in action_map:
            edges[dependency].append(action.id)
            indegree[action.id] += 1
    ready = [action_id for action_id, degree in indegree.items() if degree == 0]
    visited: set[UUID] = set()
    while ready:
        current = ready.pop()
        visited.add(current)
        for dependent in edges[current]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    return set(action_map) - visited


def _fits(
    *,
    start: int,
    end: int,
    requirements: tuple[RequirementInput, ...],
    resources: Mapping[UUID, ResourceInput],
    allocations: Mapping[UUID, list[_Allocation]],
    consumed: Mapping[UUID, float],
) -> bool:
    for requirement in requirements:
        resource = resources[requirement.resource_id]
        capacity = _resource_capacity(resource)
        if resource.allocation_mode == ResourceAllocationMode.CONSUMABLE:
            if consumed.get(resource.id, 0.0) + requirement.quantity > capacity + EPSILON:
                return False
            continue
        overlapping = sum(
            allocation.quantity
            for allocation in allocations.get(resource.id, [])
            if allocation.start < end and allocation.end > start
        )
        if overlapping + requirement.quantity > capacity + EPSILON:
            return False
    return True


def _candidate_starts(
    *,
    earliest: int,
    duration: int,
    horizon: int,
    requirements: tuple[RequirementInput, ...],
    allocations: Mapping[UUID, list[_Allocation]],
) -> list[int]:
    candidate = max(0, earliest)
    candidates = {candidate}
    for requirement in requirements:
        for allocation in allocations.get(requirement.resource_id, []):
            if allocation.end >= candidate:
                candidates.add(max(candidate, allocation.end))
    return sorted(
        start for start in candidates if start + duration <= horizon
    )


def _schedule(
    *,
    actions: tuple[ActionInput, ...],
    resources: Mapping[UUID, ResourceInput],
    risk_context: RiskContext,
    config: DecisionConfig,
    strategy: DecisionStrategy,
    horizon_minutes: int,
    budget_limit: float | None,
    deadline: float,
    solver_limit_ms: int,
    algorithm: str,
) -> StrategyPlan:
    started = time.monotonic()
    warnings: list[str] = []
    assumptions: list[str] = [
        "Expected risk reductions are planner-supplied planning assumptions, "
        "not measured outcomes or guarantees.",
        "Resource availability is used exactly as recorded; UNKNOWN or "
        "UNAVAILABLE resources block actions that require them.",
        "No resource is reserved or consumed, and no unit is dispatched.",
        "The simulation does not change incidents, departments, or assets.",
    ]
    limitations: list[str] = [
        "Scenario plans are decision support, not approved operational orders.",
        "Risk context is the current explainable risk model output; it is not "
        "a forecast of the scenario outcome.",
        "Durations, costs, and expected reductions depend on planner inputs.",
        "The planner cannot prove resource availability, travel time, or field "
        "feasibility.",
    ]
    warnings_seen: set[str] = set()
    for resource in resources.values():
        if resource.availability_status == ResourceAvailability.PLANNING_ASSUMPTION:
            text = (
                f"Resource '{resource.name}' is a planning assumption, not "
                "verified inventory."
            )
            assumptions.append(text)
        elif resource.availability_status == ResourceAvailability.UNKNOWN:
            text = (
                f"Resource '{resource.name}' has UNKNOWN availability; actions "
                "requiring it will be blocked."
            )
            warnings.append(text)
            warnings_seen.add(text)

    action_map = {action.id: action for action in actions}
    cycles = _cycle_actions(actions)
    blocked: dict[UUID, list[str]] = {}
    for action in actions:
        dependency = action.depends_on_action_id
        if dependency is not None and dependency not in action_map:
            blocked[action.id] = ["dependency_missing"]
    for action_id in cycles:
        blocked[action_id] = ["dependency_cycle"]

    pending = [action for action in actions if action.id not in blocked]
    scheduled: dict[UUID, ScheduledAction] = {}
    allocations: dict[UUID, list[_Allocation]] = {}
    consumed: dict[UUID, float] = {}
    total_cost = 0.0
    unknown_cost_actions = 0
    timed_out = False

    while pending:
        if time.monotonic() >= deadline:
            timed_out = True
            for action in pending:
                blocked[action.id] = ["solver_time_limit"]
            pending = []
            break
        ready = []
        for action in pending:
            dependency = action.depends_on_action_id
            if dependency is None:
                ready.append(action)
            elif dependency in scheduled:
                ready.append(action)
            elif dependency in blocked:
                blocked[action.id] = ["dependency_blocked"]
        for action in list(blocked):
            if action in {item.id for item in pending}:
                pending = [item for item in pending if item.id != action]
        ready.sort(key=lambda action: _strategy_order(action, strategy))
        if not ready:
            for action in pending:
                blocked[action.id] = ["dependency_cycle"]
                pending = []
            break
        action = ready[0]
        pending = [item for item in pending if item.id != action.id]

        if action.requirements:
            resource_problem: str | None = None
            for requirement in action.requirements:
                resource = resources.get(requirement.resource_id)
                if resource is None or not resource.is_active:
                    resource_problem = "resource_missing"
                    break
                if resource.availability_status == ResourceAvailability.UNKNOWN:
                    resource_problem = "resource_availability_unknown"
                    break
                if resource.availability_status == ResourceAvailability.UNAVAILABLE:
                    resource_problem = "resource_unavailable"
                    break
                if _resource_capacity(resource) <= 0:
                    resource_problem = "resource_capacity_zero"
                    break
                if requirement.quantity > _resource_capacity(resource) + EPSILON:
                    resource_problem = "resource_quantity_exceeds_capacity"
                    break
                if (
                    resource.allocation_mode == ResourceAllocationMode.CONSUMABLE
                    and consumed.get(resource.id, 0.0) + requirement.quantity
                    > _resource_capacity(resource) + EPSILON
                ):
                    resource_problem = "resource_consumption_exceeds_capacity"
                    break
            if resource_problem is not None:
                blocked[action.id] = [resource_problem]
                continue
        else:
            text = (
                f"Action '{action.title}' has no resource requirements; "
                "resource feasibility is not modelled for it."
            )
            if text not in warnings_seen:
                warnings.append(text)
                warnings_seen.add(text)

        if action.estimated_cost is None:
            unknown_cost_actions += 1
            cost = 0.0
            text = (
                f"Action '{action.title}' has no estimated cost; budget "
                "constraints are incomplete for this action."
            )
            if text not in warnings_seen:
                warnings.append(text)
                warnings_seen.add(text)
        else:
            cost = max(0.0, action.estimated_cost)
        if (
            budget_limit is not None
            and action.estimated_cost is not None
            and total_cost + cost > budget_limit + EPSILON
        ):
            blocked[action.id] = ["budget_exceeded"]
            continue

        dependency_end = 0
        if action.depends_on_action_id is not None:
            dependency = scheduled.get(action.depends_on_action_id)
            if dependency is None or dependency.end_minute is None:
                blocked[action.id] = ["dependency_not_scheduled"]
                continue
            dependency_end = dependency.end_minute
        earliest = max(action.earliest_start_minutes, dependency_end)
        start: int | None = None
        for candidate in _candidate_starts(
            earliest=earliest,
            duration=action.duration_minutes,
            horizon=horizon_minutes,
            requirements=action.requirements,
            allocations=allocations,
        ):
            end = candidate + action.duration_minutes
            if _fits(
                start=candidate,
                end=end,
                requirements=action.requirements,
                resources=resources,
                allocations=allocations,
                consumed=consumed,
            ):
                start = candidate
                break
        if start is None:
            blocked[action.id] = ["no_feasible_schedule_within_horizon"]
            continue

        end = start + action.duration_minutes
        target_score = (
            risk_context.cells.get(action.target_h3_cell_id)
            if action.target_h3_cell_id
            else None
        )
        reduction = max(0.0, action.expected_risk_reduction)
        if action.target_h3_cell_id and target_score is None:
            text = (
                f"Action '{action.title}' targets an H3 cell that is not in the "
                "current risk context; its reduction is not capped by observed "
                "cell risk."
            )
            if text not in warnings_seen:
                warnings.append(text)
                warnings_seen.add(text)
        if target_score is not None and reduction > target_score + EPSILON:
            reduction = target_score
            text = (
                f"Action '{action.title}' reduction was capped at the target "
                f"cell's current risk score ({target_score:.2f})."
            )
            if text not in warnings_seen:
                warnings.append(text)
                warnings_seen.add(text)
        resource_plan = []
        for requirement in action.requirements:
            resource = resources[requirement.resource_id]
            resource_plan.append(
                {
                    "resource_id": str(resource.id),
                    "name": resource.name,
                    "resource_type": resource.resource_type,
                    "unit": resource.unit,
                    "quantity_required": requirement.quantity,
                    "availability_status": resource.availability_status.value,
                    "availability_source": resource.availability_source,
                    "planned_only": True,
                }
            )
            allocations.setdefault(resource.id, []).append(
                _Allocation(start=start, end=end, quantity=requirement.quantity)
            )
            if resource.allocation_mode == ResourceAllocationMode.CONSUMABLE:
                consumed[resource.id] = consumed.get(resource.id, 0.0) + requirement.quantity
        scheduled[action.id] = ScheduledAction(
            action=action,
            status="SCHEDULED",
            start_minute=start,
            end_minute=end,
            planned_reduction=round(reduction, 2),
            target_risk_score=round(target_score, 2) if target_score is not None else None,
            reasons=(
                "Planner-supplied expected reduction.",
                "Resource capacity and timing constraints satisfied.",
            ),
            resources=tuple(resource_plan),
        )
        total_cost += cost

    results: list[ScheduledAction] = []
    for action in actions:
        planned = scheduled.get(action.id)
        if planned is not None:
            results.append(planned)
            continue
        reasons = blocked.get(action.id, ["not_scheduled"])
        if reasons[0] == "solver_time_limit":
            status = "UNSCHEDULED"
        elif reasons[0] in {
            "budget_exceeded",
            "no_feasible_schedule_within_horizon",
        }:
            status = "DEFERRED"
        else:
            status = "BLOCKED"
        results.append(
            ScheduledAction(
                action=action,
                status=status,
                start_minute=None,
                end_minute=None,
                planned_reduction=0.0,
                target_risk_score=(
                    round(risk_context.cells[action.target_h3_cell_id], 2)
                    if action.target_h3_cell_id
                    and action.target_h3_cell_id in risk_context.cells
                    else None
                ),
                reasons=tuple(reasons),
                resources=(),
            )
        )

    scheduled_items = [
        item for item in results if item.status == "SCHEDULED"
    ]
    blocked_items = [
        item for item in results if item.status == "BLOCKED"
    ]
    deferred_items = [
        item for item in results if item.status in {"DEFERRED", "UNSCHEDULED"}
    ]
    makespan = max(
        (item.end_minute or 0 for item in scheduled_items), default=0
    )
    total_actions = len(actions)
    total_priority = sum(action.priority for action in actions)
    scheduled_priority = sum(item.action.priority for item in scheduled_items)
    max_possible_reduction = sum(
        max(0.0, action.expected_risk_reduction) for action in actions
    )
    planned_reduction = sum(item.planned_reduction for item in scheduled_items)
    action_coverage = (
        len(scheduled_items) / total_actions if total_actions else 0.0
    )
    reduction_rate = (
        planned_reduction / max_possible_reduction
        if max_possible_reduction > 0
        else 0.0
    )
    if budget_limit is not None and budget_limit > 0:
        cost_efficiency = max(0.0, 1.0 - total_cost / budget_limit)
    elif total_cost > 0:
        cost_efficiency = 1.0 / (1.0 + total_cost / 10_000.0)
    else:
        cost_efficiency = 1.0
    time_efficiency = max(
        0.0, 1.0 - (makespan / horizon_minutes if horizon_minutes else 0.0)
    )
    objective_components = {
        "risk_reduction": round(reduction_rate, 4),
        "action_coverage": round(action_coverage, 4),
        "cost_efficiency": round(cost_efficiency, 4),
        "time_efficiency": round(time_efficiency, 4),
    }
    objective = (
        config.weight_risk_reduction * reduction_rate
        + config.weight_action_coverage * action_coverage
        + config.weight_cost_efficiency * cost_efficiency
        + config.weight_time_efficiency * time_efficiency
    )
    resource_summaries = []
    for resource in resources.values():
        if resource.allocation_mode == ResourceAllocationMode.CONSUMABLE:
            used = consumed.get(resource.id, 0.0)
        else:
            used = sum(
                allocation.quantity
                for allocation in allocations.get(resource.id, [])
            )
        resource_summaries.append(
            {
                "resource_id": str(resource.id),
                "name": resource.name,
                "resource_type": resource.resource_type,
                "unit": resource.unit,
                "capacity": round(_resource_capacity(resource), 2),
                "used": round(used, 2),
                "remaining": round(
                    max(0.0, _resource_capacity(resource) - used), 2
                ),
                "availability_status": resource.availability_status.value,
                "allocation_mode": resource.allocation_mode.value,
                "availability_source": resource.availability_source,
                "available_as_of": _utc_text(resource.available_as_of),
                "planned_only": True,
            }
        )
    if unknown_cost_actions:
        warnings.append(
            f"{unknown_cost_actions} action(s) have unknown cost; budget "
            "enforcement is incomplete."
        )
    if timed_out:
        warnings.append(
            "The solver time limit was reached; remaining actions were marked "
            "UNSCHEDULED."
        )
    metrics = {
        "total_actions": total_actions,
        "scheduled_actions": len(scheduled_items),
        "blocked_actions": len(blocked_items),
        "deferred_actions": len(deferred_items),
        "action_coverage": round(action_coverage, 4),
        "priority_coverage": round(
            scheduled_priority / total_priority if total_priority else 0.0, 4
        ),
        "planned_reduction": round(planned_reduction, 2),
        "max_possible_reduction": round(max_possible_reduction, 2),
        "reduction_rate": round(reduction_rate, 4),
        "total_known_cost": round(total_cost, 2),
        "budget_limit": budget_limit,
        "makespan_minutes": makespan,
        "horizon_minutes": horizon_minutes,
        "time_efficiency": round(time_efficiency, 4),
        "cost_efficiency": round(cost_efficiency, 4),
        "unknown_cost_actions": unknown_cost_actions,
        "objective_score": round(objective, 4),
    }
    elapsed_ms = int((time.monotonic() - started) * 1000)
    solver = {
        "algorithm": algorithm,
        "time_limit_ms": solver_limit_ms,
        "elapsed_ms": elapsed_ms,
        "timed_out": timed_out,
        "strategy": strategy.value,
    }
    return StrategyPlan(
        strategy=strategy,
        strategy_label=STRATEGY_LABELS[strategy],
        actions=tuple(results),
        metrics=metrics,
        objective_score=round(objective, 4),
        objective_components=objective_components,
        solver=solver,
        assumptions=tuple(assumptions),
        warnings=tuple(warnings),
        limitations=tuple(limitations),
        resources=tuple(resource_summaries),
    )


def simulate_strategy(
    *,
    actions: Iterable[ActionInput],
    resources: Iterable[ResourceInput],
    risk_context: RiskContext,
    config: DecisionConfig,
    strategy: DecisionStrategy,
    horizon_minutes: int,
    budget_limit: float | None,
    deadline: float | None = None,
    solver_limit_ms: int | None = None,
) -> StrategyPlan:
    action_list = tuple(actions)
    resource_map = {resource.id: resource for resource in resources}
    if len(action_list) > config.max_actions:
        raise DecisionError(
            f"Scenario has more than {config.max_actions} actions.",
            code="too_many_actions",
        )
    if len(resource_map) > config.max_resources:
        raise DecisionError(
            f"Scenario has more than {config.max_resources} resources.",
            code="too_many_resources",
        )
    if not config.min_horizon_minutes <= horizon_minutes <= config.max_horizon_minutes:
        raise DecisionError(
            f"horizon_minutes must be between {config.min_horizon_minutes} "
            f"and {config.max_horizon_minutes}.",
            code="invalid_horizon",
        )
    limit = solver_limit_ms or config.solver_time_limit_ms
    effective_deadline = deadline or (time.monotonic() + limit / 1000.0)
    return _schedule(
        actions=action_list,
        resources=resource_map,
        risk_context=risk_context,
        config=config,
        strategy=strategy,
        horizon_minutes=horizon_minutes,
        budget_limit=budget_limit,
        deadline=effective_deadline,
        solver_limit_ms=limit,
        algorithm="bounded_greedy_scheduler_v1",
    )


def compare_strategies(
    *,
    actions: Iterable[ActionInput],
    resources: Iterable[ResourceInput],
    risk_context: RiskContext,
    config: DecisionConfig,
    strategies: Iterable[DecisionStrategy],
    horizon_minutes: int,
    budget_limit: float | None,
    deadline: float | None = None,
) -> StrategyComparison:
    action_list = tuple(actions)
    resource_list = tuple(resources)
    strategy_list = tuple(dict.fromkeys(strategies))
    if not strategy_list:
        raise DecisionError("At least one strategy is required.", code="invalid_strategy")
    now = time.monotonic()
    total_deadline = deadline or (now + config.solver_time_limit_ms / 1000.0)
    per_strategy_ms = max(
        50, config.solver_time_limit_ms // max(1, len(strategy_list))
    )
    results: list[StrategyPlan] = []
    for strategy in strategy_list:
        result = simulate_strategy(
            actions=action_list,
            resources=resource_list,
            risk_context=risk_context,
            config=config,
            strategy=strategy,
            horizon_minutes=horizon_minutes,
            budget_limit=budget_limit,
            deadline=min(total_deadline, time.monotonic() + per_strategy_ms / 1000.0),
            solver_limit_ms=per_strategy_ms,
        )
        results.append(result)
    results.sort(
        key=lambda item: (
            -item.objective_score,
            -item.metrics["reduction_rate"],
            item.strategy.value,
        )
    )
    winner = results[0].strategy if results else None
    assumptions = tuple(
        dict.fromkeys(
            assumption
            for result in results
            for assumption in result.assumptions
        )
    )
    warnings = tuple(
        dict.fromkeys(
            warning for result in results for warning in result.warnings
        )
    )
    solver = {
        "algorithm": "strategy_comparison_v1",
        "time_limit_ms": config.solver_time_limit_ms,
        "elapsed_ms": int((time.monotonic() - now) * 1000),
        "timed_out": any(result.solver["timed_out"] for result in results),
        "strategies_evaluated": len(results),
    }
    return StrategyComparison(
        results=tuple(results),
        winner=winner,
        solver=solver,
        assumptions=assumptions,
        warnings=warnings,
    )
