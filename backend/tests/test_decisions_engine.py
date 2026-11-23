"""Decision simulation engine unit tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import Settings
from app.decisions.config import DecisionConfig, DecisionConfigError
from app.decisions.engine import (
    ActionInput,
    RequirementInput,
    ResourceInput,
    RiskContext,
    compare_strategies,
    simulate_strategy,
)
from app.models import (
    DecisionStrategy,
    ResourceAllocationMode,
    ResourceAvailability,
)


def _config() -> DecisionConfig:
    return DecisionConfig.from_settings(Settings(_env_file=None, app_env="testing"))


def _resource(
    *,
    capacity: float = 2,
    status: ResourceAvailability = ResourceAvailability.AVAILABLE,
    mode: ResourceAllocationMode = ResourceAllocationMode.SHARED_CAPACITY,
) -> ResourceInput:
    return ResourceInput(
        id=uuid4(),
        name="Response truck",
        resource_type="VEHICLE",
        unit="vehicle",
        capacity=capacity,
        availability_status=status,
        allocation_mode=mode,
        availability_source="unit test inventory",
        available_as_of=None,
        department_id=None,
        is_active=True,
    )


def _action(
    *,
    title: str = "Action",
    priority: int = 3,
    duration: int = 60,
    reduction: float = 20,
    cost: float | None = 100,
    requirements: tuple[RequirementInput, ...] = (),
    depends_on=None,
    target: str | None = "883c13b05fffff",
    earliest: int = 0,
) -> ActionInput:
    return ActionInput(
        id=uuid4(),
        title=title,
        description=None,
        action_type="REPAIR",
        priority=priority,
        earliest_start_minutes=earliest,
        duration_minutes=duration,
        expected_risk_reduction=reduction,
        estimated_cost=cost,
        target_h3_cell_id=target,
        target_asset_id=None,
        target_asset_name=None,
        department_id=None,
        department_name=None,
        depends_on_action_id=depends_on,
        assumptions={},
        requirements=requirements,
    )


def _risk(score: float = 71.4) -> RiskContext:
    return RiskContext(
        available=True,
        resolution=8,
        window_hours=168,
        cells={"883c13b05fffff": score},
        cell_count=1,
        incident_count=3,
        limitations=(),
    )


def test_configuration_is_stable_and_validated() -> None:
    config = _config()
    assert config.model_version == "decision-v1"
    assert config.config_hash == _config().config_hash
    assert abs(
        sum(
            [
                config.weight_risk_reduction,
                config.weight_action_coverage,
                config.weight_cost_efficiency,
                config.weight_time_efficiency,
            ]
        )
        - 1.0
    ) < 1e-9
    with pytest.raises(DecisionConfigError):
        DecisionConfig(
            **{
                **config.__dict__,
                "weight_risk_reduction": 0.9,
            }
        )


def test_priority_schedules_actions_and_respects_shared_capacity() -> None:
    resource = _resource(capacity=1)
    first = _action(
        title="High priority",
        priority=5,
        requirements=(RequirementInput(resource.id, 1),),
    )
    second = _action(
        title="Low priority",
        priority=2,
        requirements=(RequirementInput(resource.id, 1),),
    )
    plan = simulate_strategy(
        actions=[first, second],
        resources=[resource],
        risk_context=_risk(),
        config=_config(),
        strategy=DecisionStrategy.PRIORITY,
        horizon_minutes=60,
        budget_limit=None,
    )
    assert plan.actions[0].status == "SCHEDULED"
    assert plan.actions[0].action.title == "High priority"
    assert plan.actions[1].status == "DEFERRED"
    assert "no_feasible_schedule_within_horizon" in plan.actions[1].reasons
    assert plan.metrics["scheduled_actions"] == 1
    assert plan.metrics["deferred_actions"] == 1


def test_unknown_resource_availability_blocks_instead_of_assuming() -> None:
    resource = _resource(
        status=ResourceAvailability.UNKNOWN, capacity=10
    )
    action = _action(
        requirements=(RequirementInput(resource.id, 1),),
    )
    plan = simulate_strategy(
        actions=[action],
        resources=[resource],
        risk_context=_risk(),
        config=_config(),
        strategy=DecisionStrategy.BALANCED,
        horizon_minutes=240,
        budget_limit=None,
    )
    assert plan.actions[0].status == "BLOCKED"
    assert plan.actions[0].reasons == ("resource_availability_unknown",)
    assert plan.metrics["scheduled_actions"] == 0
    assert any("UNKNOWN availability" in warning for warning in plan.warnings)


def test_dependencies_are_scheduled_after_predecessors() -> None:
    first = _action(title="Assess", duration=30)
    second = _action(
        title="Repair", duration=45, depends_on=first.id
    )
    plan = simulate_strategy(
        actions=[first, second],
        resources=[],
        risk_context=_risk(),
        config=_config(),
        strategy=DecisionStrategy.BALANCED,
        horizon_minutes=240,
        budget_limit=None,
    )
    assert all(item.status == "SCHEDULED" for item in plan.actions)
    assert plan.actions[1].start_minute == 30
    assert plan.metrics["makespan_minutes"] == 75


def test_budget_and_target_risk_cap_are_explicit() -> None:
    action = _action(reduction=90, cost=80)
    plan = simulate_strategy(
        actions=[action],
        resources=[],
        risk_context=_risk(score=40),
        config=_config(),
        strategy=DecisionStrategy.RISK_REDUCTION,
        horizon_minutes=120,
        budget_limit=50,
    )
    assert plan.actions[0].status == "DEFERRED"
    assert plan.actions[0].reasons == ("budget_exceeded",)

    uncapped = simulate_strategy(
        actions=[_action(reduction=90, cost=20)],
        resources=[],
        risk_context=_risk(score=40),
        config=_config(),
        strategy=DecisionStrategy.RISK_REDUCTION,
        horizon_minutes=120,
        budget_limit=50,
    )
    assert uncapped.actions[0].planned_reduction == 40
    assert any("capped" in warning for warning in uncapped.warnings)


def test_strategy_comparison_is_bounded_and_ranked() -> None:
    actions = [
        _action(title="A", priority=5, reduction=40, cost=200, duration=60),
        _action(title="B", priority=3, reduction=20, cost=20, duration=30),
        _action(title="C", priority=1, reduction=10, cost=10, duration=30),
    ]
    comparison = compare_strategies(
        actions=actions,
        resources=[],
        risk_context=_risk(),
        config=_config(),
        strategies=list(DecisionStrategy),
        horizon_minutes=120,
        budget_limit=100,
    )
    assert len(comparison.results) == 4
    assert comparison.winner is not None
    assert comparison.results[0].objective_score >= comparison.results[-1].objective_score
    assert comparison.solver["strategies_evaluated"] == 4
    assert comparison.solver["time_limit_ms"] >= 50


def test_no_resource_requirements_are_flagged_as_unmodelled() -> None:
    plan = simulate_strategy(
        actions=[_action(title="Public notice", reduction=5)],
        resources=[],
        risk_context=_risk(),
        config=_config(),
        strategy=DecisionStrategy.PRIORITY,
        horizon_minutes=120,
        budget_limit=None,
    )
    assert plan.actions[0].status == "SCHEDULED"
    assert any("no resource requirements" in warning for warning in plan.warnings)
