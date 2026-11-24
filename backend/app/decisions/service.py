"""Decision scenario loading and planning-only simulation orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from time import monotonic
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.decisions.engine import (
    ActionInput,
    DecisionError,
    RequirementInput,
    ResourceInput,
    RiskContext,
    StrategyComparison,
    StrategyPlan,
    compare_strategies,
    simulate_strategy,
)
from app.decisions.serialization import (
    comparison_payload,
    plan_payload,
    risk_context_payload,
)
from app.models import (
    DecisionAction,
    DecisionScenario,
    DecisionSimulation,
    DecisionStrategy,
    InfrastructureAsset,
    Department,
    ResponseResource,
    SimulationStatus,
)
from app.governance.service import resolve_decision_config, resolve_risk_config
from app.ingestion.service import stale_data_warnings
from app.risk.engine import RiskEngine, RiskQuery, RiskQueryError


@dataclass(frozen=True)
class SimulationOutcome:
    plan: StrategyPlan
    risk_context: RiskContext
    payload: dict
    simulation: DecisionSimulation | None


def load_scenario(session: Session, scenario_id: UUID) -> DecisionScenario | None:
    return session.scalar(
        select(DecisionScenario)
        .where(DecisionScenario.id == scenario_id)
        .options(
            selectinload(DecisionScenario.actions).selectinload(
                DecisionAction.requirements
            )
        )
    )


def load_simulation(
    session: Session, scenario_id: UUID, simulation_id: UUID
) -> DecisionSimulation | None:
    return session.scalar(
        select(DecisionSimulation).where(
            DecisionSimulation.id == simulation_id,
            DecisionSimulation.scenario_id == scenario_id,
        )
    )


def list_simulations(
    session: Session, scenario_id: UUID, *, limit: int = 50
) -> list[DecisionSimulation]:
    return list(
        session.scalars(
            select(DecisionSimulation)
            .where(DecisionSimulation.scenario_id == scenario_id)
            .order_by(DecisionSimulation.calculated_at.desc())
            .limit(limit)
        ).all()
    )


def _build_risk_context(
    session: Session,
    scenario: DecisionScenario,
    *,
    settings: Settings,
) -> RiskContext:
    risk_config = resolve_risk_config(session, settings)
    query = RiskQuery(
        resolution=scenario.resolution,
        window_hours=scenario.risk_window_hours,
        bbox=None,
        limit=risk_config.max_cells,
    )
    try:
        computation = RiskEngine(session, risk_config).compute(query)
    except RiskQueryError as error:
        return RiskContext(
            available=False,
            resolution=scenario.resolution,
            window_hours=scenario.risk_window_hours,
            cells={},
            cell_count=0,
            incident_count=0,
            limitations=(
                "Risk context could not be loaded for this scenario; action "
                f"reductions are not capped by observed cell risk ({error.code}).",
            ),
        )
    return RiskContext(
        available=True,
        resolution=scenario.resolution,
        window_hours=scenario.risk_window_hours,
        cells={
            cell.h3_cell_id: cell.risk_score for cell in computation.cells
        },
        cell_count=len(computation.cells),
        incident_count=len(computation.current_incidents),
        limitations=tuple(computation.limitations),
    )


def _action_input(
    action: DecisionAction,
    *,
    asset_names: dict[UUID, str],
    department_names: dict[UUID, str],
) -> ActionInput:
    return ActionInput(
        id=action.id,
        title=action.title,
        description=action.description,
        action_type=action.action_type.value,
        priority=action.priority,
        earliest_start_minutes=action.earliest_start_minutes,
        duration_minutes=action.duration_minutes,
        expected_risk_reduction=float(action.expected_risk_reduction),
        estimated_cost=(
            float(action.estimated_cost)
            if action.estimated_cost is not None
            else None
        ),
        target_h3_cell_id=action.target_h3_cell_id,
        target_asset_id=action.target_asset_id,
        target_asset_name=(
            asset_names.get(action.target_asset_id)
            if action.target_asset_id
            else None
        ),
        department_id=action.department_id,
        department_name=(
            department_names.get(action.department_id)
            if action.department_id
            else None
        ),
        depends_on_action_id=action.depends_on_action_id,
        assumptions=action.assumptions or {},
        requirements=tuple(
            RequirementInput(
                resource_id=requirement.resource_id,
                quantity=float(requirement.quantity_required),
            )
            for requirement in action.requirements
        ),
    )


def _resource_inputs(session: Session) -> list[ResourceInput]:
    resources = session.scalars(select(ResponseResource)).all()
    return [
        ResourceInput(
            id=resource.id,
            name=resource.name,
            resource_type=resource.resource_type.value,
            unit=resource.unit,
            capacity=float(resource.quantity_available),
            availability_status=resource.availability_status,
            allocation_mode=resource.allocation_mode,
            availability_source=resource.availability_source,
            available_as_of=resource.available_as_of,
            department_id=resource.department_id,
            is_active=resource.is_active,
        )
        for resource in resources
    ]


def input_context(
    session: Session,
    scenario: DecisionScenario,
    *,
    settings: Settings,
) -> tuple[list[ActionInput], list[ResourceInput], RiskContext]:
    asset_ids = {
        action.target_asset_id
        for action in scenario.actions
        if action.target_asset_id is not None
    }
    department_ids = {
        action.department_id
        for action in scenario.actions
        if action.department_id is not None
    }
    asset_names: dict[UUID, str] = {}
    if asset_ids:
        asset_names = {
            asset.id: asset.name
            for asset in session.scalars(
                select(InfrastructureAsset).where(
                    InfrastructureAsset.id.in_(asset_ids)
                )
            ).all()
        }
    department_names: dict[UUID, str] = {}
    if department_ids:
        department_names = {
            department.id: department.name
            for department in session.scalars(
                select(Department).where(Department.id.in_(department_ids))
            ).all()
        }
    actions = [
        _action_input(
            action,
            asset_names=asset_names,
            department_names=department_names,
        )
        for action in scenario.actions
        if action.is_active
    ]
    return actions, _resource_inputs(session), _build_risk_context(
        session, scenario, settings=settings
    )


def _simulation_summary(
    plan: StrategyPlan, context: RiskContext, scenario: DecisionScenario
) -> dict:
    return {
        "scenario_id": str(scenario.id),
        "scenario_name": scenario.name,
        "strategy": plan.strategy.value,
        "status": (
            SimulationStatus.PARTIAL.value
            if plan.solver.get("timed_out")
            else SimulationStatus.COMPLETED.value
        ),
        "metrics": plan.metrics,
        "risk_context": {
            "available": context.available,
            "resolution": context.resolution,
            "window_hours": context.window_hours,
            "cell_count": context.cell_count,
            "incident_count": context.incident_count,
        },
        "warnings": list(plan.warnings),
        "execution_authorized": False,
        "dispatch_performed": False,
        "reservations_created": False,
    }


def simulate(
    session: Session,
    scenario: DecisionScenario,
    *,
    strategy: DecisionStrategy,
    settings: Settings,
    persist: bool = True,
    requested_by: UUID | None = None,
) -> SimulationOutcome:
    config = resolve_decision_config(session, settings)
    actions, resources, risk_context = input_context(
        session, scenario, settings=settings
    )
    started = monotonic()
    plan = simulate_strategy(
        actions=actions,
        resources=resources,
        risk_context=risk_context,
        config=config,
        strategy=strategy,
        horizon_minutes=scenario.horizon_minutes,
        budget_limit=(
            float(scenario.budget_limit)
            if scenario.budget_limit is not None
            else None
        ),
    )
    quality_warnings = stale_data_warnings(session)
    if quality_warnings:
        plan = replace(
            plan,
            warnings=tuple(
                dict.fromkeys((*plan.warnings, *quality_warnings))
            ),
        )
    payload = {
        "scenario_id": str(scenario.id),
        "scenario_name": scenario.name,
        "strategy": plan.strategy.value,
        "status": (
            SimulationStatus.PARTIAL.value
            if plan.solver.get("timed_out")
            else SimulationStatus.COMPLETED.value
        ),
        "model_version": config.model_version,
        "config_hash": config.config_hash,
        "risk_context": risk_context_payload(risk_context),
        "plan": plan_payload(plan),
        "assumptions": list(plan.assumptions),
        "warnings": list(plan.warnings),
        "limitations": list(plan.limitations),
        "execution_authorized": False,
        "dispatch_performed": False,
        "reservations_created": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    simulation: DecisionSimulation | None = None
    if persist:
        simulation = DecisionSimulation(
            scenario_id=scenario.id,
            strategy=strategy,
            status=(
                SimulationStatus.PARTIAL
                if plan.solver.get("timed_out")
                else SimulationStatus.COMPLETED
            ),
            model_version=config.model_version,
            config_hash=config.config_hash,
            assumptions={
                "scenario_parameters": scenario.parameters or {},
                "risk_context": risk_context_payload(risk_context),
                "planning_only": True,
            },
            result=payload,
            summary=_simulation_summary(plan, risk_context, scenario),
            solver=plan.solver,
            duration_ms=int((monotonic() - started) * 1000),
            requested_by=requested_by,
        )
        session.add(simulation)
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise
        session.refresh(simulation)
        payload["simulation_id"] = str(simulation.id)
        payload["calculated_at"] = simulation.calculated_at.isoformat()
    else:
        payload["simulation_id"] = None
        payload["calculated_at"] = None
    return SimulationOutcome(
        plan=plan,
        risk_context=risk_context,
        payload=payload,
        simulation=simulation,
    )


def compare(
    session: Session,
    scenario: DecisionScenario,
    *,
    strategies: list[DecisionStrategy],
    settings: Settings,
) -> dict:
    config = resolve_decision_config(session, settings)
    actions, resources, risk_context = input_context(
        session, scenario, settings=settings
    )
    comparison: StrategyComparison = compare_strategies(
        actions=actions,
        resources=resources,
        risk_context=risk_context,
        config=config,
        strategies=strategies,
        horizon_minutes=scenario.horizon_minutes,
        budget_limit=(
            float(scenario.budget_limit)
            if scenario.budget_limit is not None
            else None
        ),
    )
    quality_warnings = stale_data_warnings(session)
    if quality_warnings:
        comparison = replace(
            comparison,
            warnings=tuple(
                dict.fromkeys((*comparison.warnings, *quality_warnings))
            ),
        )
    payload = {
        "scenario_id": str(scenario.id),
        "scenario_name": scenario.name,
        "model_version": config.model_version,
        "config_hash": config.config_hash,
        "risk_context": risk_context_payload(risk_context),
        "comparison": comparison_payload(comparison),
        "data_quality_warnings": stale_data_warnings(session),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return payload


def ensure_scenario(session: Session, scenario_id: UUID) -> DecisionScenario:
    scenario = load_scenario(session, scenario_id)
    if scenario is None:
        raise DecisionError(
            "Decision scenario not found.",
            code="scenario_not_found",
        )
    return scenario
