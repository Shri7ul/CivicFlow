"""Staff-only decision intelligence and planning simulation APIs."""

from __future__ import annotations

import uuid
from typing import Annotated

import h3
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import AuthenticatedUser, require_worker
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.db.session import get_db_session
from app.decisions.config import (
    ACTION_TYPE_LABELS,
    HAZARD_LABELS,
    RESOURCE_STATUS_LABELS,
    RESOURCE_TYPE_LABELS,
    STRATEGY_LABELS,
    DecisionConfig,
)
from app.decisions.engine import DecisionError
from app.decisions.service import (
    compare,
    list_simulations,
    load_scenario,
    load_simulation,
    simulate,
)
from app.models import (
    ActionResourceRequirement,
    DecisionAction,
    DecisionScenario,
    DecisionSimulation,
    DecisionStrategy,
    Department,
    InfrastructureAsset,
    ResponseResource,
    ScenarioStatus,
)
from app.schemas.decisions import (
    ActionCreate,
    ActionResponse,
    ActionUpdate,
    ComparisonRequest,
    ComparisonResponse,
    DecisionConfigResponse,
    ResourceCreate,
    ResourceRequirementResponse,
    ResourceResponse,
    ResourceUpdate,
    ScenarioCreate,
    ScenarioDetailResponse,
    ScenarioSummaryResponse,
    ScenarioUpdate,
    SimulationListItem,
    SimulationRequest,
    SimulationResponse,
)

router = APIRouter()


def _decision_config(settings: Settings = Depends(get_settings)) -> DecisionConfig:
    return DecisionConfig.from_settings(settings)


def _scenario_or_404(session: Session, scenario_id: uuid.UUID) -> DecisionScenario:
    scenario = load_scenario(session, scenario_id)
    if scenario is None:
        raise AppError(
            "Decision scenario not found.",
            status_code=404,
            code="scenario_not_found",
        )
    return scenario


def _resource_or_404(session: Session, resource_id: uuid.UUID) -> ResponseResource:
    resource = session.get(ResponseResource, resource_id)
    if resource is None:
        raise AppError(
            "Response resource not found.",
            status_code=404,
            code="resource_not_found",
        )
    return resource


def _validate_h3(value: str | None) -> None:
    if value is not None and not h3.is_valid_cell(value):
        raise AppError(
            "target_h3_cell_id must be a valid H3 cell.",
            status_code=422,
            code="invalid_h3_cell",
        )


def _validate_action_references(
    session: Session,
    *,
    scenario_id: uuid.UUID,
    target_asset_id: uuid.UUID | None,
    department_id: uuid.UUID | None,
    depends_on_action_id: uuid.UUID | None,
    self_id: uuid.UUID | None = None,
) -> None:
    if target_asset_id is not None and session.get(
        InfrastructureAsset, target_asset_id
    ) is None:
        raise AppError(
            "Target infrastructure asset not found.",
            status_code=422,
            code="invalid_target_asset",
        )
    if department_id is not None and session.get(Department, department_id) is None:
        raise AppError(
            "Department not found.",
            status_code=422,
            code="invalid_department",
        )
    if depends_on_action_id is not None:
        if self_id is not None and depends_on_action_id == self_id:
            raise AppError(
                "An action cannot depend on itself.",
                status_code=422,
                code="invalid_dependency",
            )
        dependency = session.get(DecisionAction, depends_on_action_id)
        if dependency is None or dependency.scenario_id != scenario_id:
            raise AppError(
                "Dependency must be an action in the same scenario.",
                status_code=422,
                code="invalid_dependency",
            )


def _requirement_responses(
    action: DecisionAction, session: Session
) -> list[ResourceRequirementResponse]:
    resource_ids = [item.resource_id for item in action.requirements]
    resources = (
        {
            resource.id: resource
            for resource in session.scalars(
                select(ResponseResource).where(
                    ResponseResource.id.in_(resource_ids)
                )
            ).all()
        }
        if resource_ids
        else {}
    )
    return [
        ResourceRequirementResponse(
            resource_id=item.resource_id,
            resource_name=(
                resources[item.resource_id].name
                if item.resource_id in resources
                else "Unknown resource"
            ),
            resource_type=(
                resources[item.resource_id].resource_type.value
                if item.resource_id in resources
                else "OTHER"
            ),
            unit=(
                resources[item.resource_id].unit
                if item.resource_id in resources
                else "unit"
            ),
            quantity_required=float(item.quantity_required),
            availability_status=(
                resources[item.resource_id].availability_status
                if item.resource_id in resources
                else "UNKNOWN"
            ),
        )
        for item in action.requirements
    ]


def _action_response(action: DecisionAction, session: Session) -> ActionResponse:
    asset = (
        session.get(InfrastructureAsset, action.target_asset_id)
        if action.target_asset_id
        else None
    )
    department = (
        session.get(Department, action.department_id)
        if action.department_id
        else None
    )
    return ActionResponse(
        id=action.id,
        scenario_id=action.scenario_id,
        title=action.title,
        description=action.description,
        action_type=action.action_type,
        target_h3_cell_id=action.target_h3_cell_id,
        target_asset_id=action.target_asset_id,
        target_asset_name=asset.name if asset else None,
        department_id=action.department_id,
        department_name=department.name if department else None,
        priority=action.priority,
        earliest_start_minutes=action.earliest_start_minutes,
        duration_minutes=action.duration_minutes,
        expected_risk_reduction=float(action.expected_risk_reduction),
        estimated_cost=(
            float(action.estimated_cost)
            if action.estimated_cost is not None
            else None
        ),
        depends_on_action_id=action.depends_on_action_id,
        is_active=action.is_active,
        assumptions=action.assumptions or {},
        resource_requirements=_requirement_responses(action, session),
        created_at=action.created_at,
        updated_at=action.updated_at,
    )


def _scenario_summary(
    scenario: DecisionScenario, *, simulation_count: int = 0
) -> ScenarioSummaryResponse:
    return ScenarioSummaryResponse(
        id=scenario.id,
        name=scenario.name,
        description=scenario.description,
        hazard_type=scenario.hazard_type,
        status=scenario.status,
        horizon_minutes=scenario.horizon_minutes,
        budget_limit=(
            float(scenario.budget_limit)
            if scenario.budget_limit is not None
            else None
        ),
        resolution=scenario.resolution,
        risk_window_hours=scenario.risk_window_hours,
        parameters=scenario.parameters or {},
        action_count=len(scenario.actions),
        simulation_count=simulation_count,
        created_by=scenario.created_by,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
    )


def _scenario_detail(
    scenario: DecisionScenario, session: Session
) -> ScenarioDetailResponse:
    simulation_count = session.scalar(
        select(func.count(DecisionSimulation.id)).where(
            DecisionSimulation.scenario_id == scenario.id
        )
    ) or 0
    summary = _scenario_summary(
        scenario, simulation_count=int(simulation_count)
    )
    return ScenarioDetailResponse(
        **summary.model_dump(),
        actions=[
            _action_response(action, session) for action in scenario.actions
        ],
    )


NON_NULL_SCENARIO_FIELDS = {
    "name", "hazard_type", "horizon_minutes", "resolution",
    "risk_window_hours", "parameters", "status",
}
NON_NULL_ACTION_FIELDS = {
    "title", "action_type", "priority", "earliest_start_minutes",
    "duration_minutes", "expected_risk_reduction", "is_active",
    "assumptions",
}
NON_NULL_RESOURCE_FIELDS = {
    "name", "resource_type", "unit", "quantity_available",
    "availability_status", "allocation_mode", "is_active", "metadata",
}


def _reject_null_updates(payload, fields: set[str]) -> None:
    for field in payload.model_fields_set:
        if field in fields and getattr(payload, field) is None:
            raise AppError(
                f"{field} cannot be null.",
                status_code=422,
                code="invalid_field",
            )


def _resource_response(resource: ResponseResource) -> ResourceResponse:
    return ResourceResponse(
        id=resource.id,
        name=resource.name,
        resource_type=resource.resource_type,
        unit=resource.unit,
        quantity_available=float(resource.quantity_available),
        availability_status=resource.availability_status,
        availability_source=resource.availability_source,
        available_as_of=resource.available_as_of,
        allocation_mode=resource.allocation_mode,
        department_id=resource.department_id,
        is_active=resource.is_active,
        metadata=resource.metadata_json or {},
        created_at=resource.created_at,
        updated_at=resource.updated_at,
    )


@router.get("/config", response_model=DecisionConfigResponse)
def decision_config(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    config: Annotated[DecisionConfig, Depends(_decision_config)],
) -> DecisionConfigResponse:
    del user
    payload = config.as_dict()
    return DecisionConfigResponse(
        model_version=config.model_version,
        config_hash=config.config_hash,
        horizon_minutes=payload["horizon_minutes"],
        max_actions=config.max_actions,
        max_resources=config.max_resources,
        solver_time_limit_ms=config.solver_time_limit_ms,
        default_risk_window_hours=config.default_risk_window_hours,
        default_resolution=config.default_resolution,
        objective_weights=payload["objective_weights"],
        strategies=[
            {"value": strategy.value, "label": STRATEGY_LABELS[strategy]}
            for strategy in DecisionStrategy
        ],
        limitations=[
            "Planning simulation only: no dispatch, reservation, assignment, "
            "or incident mutation occurs.",
            "Expected risk reductions, durations, and costs are planner inputs, "
            "not measured outcomes.",
            "UNKNOWN resource availability is never assumed available; actions "
            "requiring it are blocked.",
            "Ranking heuristics are not a guarantee of real-world feasibility.",
        ],
    )


@router.get("/metadata", response_model=dict)
def decision_metadata(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
) -> dict:
    del user
    return {
        "hazards": [
            {"value": key.value, "label": label}
            for key, label in HAZARD_LABELS.items()
        ],
        "action_types": [
            {"value": key.value, "label": label}
            for key, label in ACTION_TYPE_LABELS.items()
        ],
        "resource_types": [
            {"value": key.value, "label": label}
            for key, label in RESOURCE_TYPE_LABELS.items()
        ],
        "resource_statuses": [
            {
                "value": key.value,
                "label": label,
                "is_assumption": key.value == "PLANNING_ASSUMPTION",
            }
            for key, label in RESOURCE_STATUS_LABELS.items()
        ],
        "strategies": [
            {"value": key.value, "label": label}
            for key, label in STRATEGY_LABELS.items()
        ],
        "planning_only": True,
    }


@router.get("/resources", response_model=list[ResourceResponse])
def list_resources(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[ResourceResponse]:
    del user
    return [
        _resource_response(resource)
        for resource in session.scalars(
            select(ResponseResource)
            .order_by(ResponseResource.name)
            .limit(limit)
        ).all()
    ]


@router.post("/resources", response_model=ResourceResponse, status_code=201)
def create_resource(
    payload: ResourceCreate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ResourceResponse:
    del user
    if payload.department_id is not None and session.get(
        Department, payload.department_id
    ) is None:
        raise AppError(
            "Department not found.",
            status_code=422,
            code="invalid_department",
        )
    resource = ResponseResource(
        name=payload.name,
        resource_type=payload.resource_type,
        unit=payload.unit,
        quantity_available=payload.quantity_available,
        availability_status=payload.availability_status,
        availability_source=(
            payload.availability_source.strip()
            if payload.availability_source
            else None
        ),
        available_as_of=payload.available_as_of,
        allocation_mode=payload.allocation_mode,
        department_id=payload.department_id,
        is_active=payload.is_active,
        metadata_json=payload.metadata,
    )
    session.add(resource)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(resource)
    return _resource_response(resource)


@router.patch("/resources/{resource_id}", response_model=ResourceResponse)
def update_resource(
    resource_id: uuid.UUID,
    payload: ResourceUpdate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ResourceResponse:
    del user
    resource = _resource_or_404(session, resource_id)
    _reject_null_updates(payload, NON_NULL_RESOURCE_FIELDS)
    values = {
        "name": resource.name,
        "resource_type": resource.resource_type,
        "unit": resource.unit,
        "quantity_available": float(resource.quantity_available),
        "availability_status": resource.availability_status,
        "availability_source": resource.availability_source,
        "available_as_of": resource.available_as_of,
        "allocation_mode": resource.allocation_mode,
        "department_id": resource.department_id,
        "is_active": resource.is_active,
        "metadata": resource.metadata_json or {},
    }
    for field in payload.model_fields_set:
        values[field] = getattr(payload, field)
    validated = ResourceCreate(**values)
    resource.name = validated.name
    resource.resource_type = validated.resource_type
    resource.unit = validated.unit
    resource.quantity_available = validated.quantity_available
    resource.availability_status = validated.availability_status
    resource.availability_source = (
        validated.availability_source.strip()
        if validated.availability_source
        else None
    )
    resource.available_as_of = validated.available_as_of
    resource.allocation_mode = validated.allocation_mode
    resource.department_id = validated.department_id
    resource.is_active = validated.is_active
    resource.metadata_json = validated.metadata
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(resource)
    return _resource_response(resource)


@router.get("/scenarios", response_model=list[ScenarioSummaryResponse])
def list_scenarios(
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    status: ScenarioStatus | None = None,
) -> list[ScenarioSummaryResponse]:
    del user
    statement = (
        select(DecisionScenario)
        .options(selectinload(DecisionScenario.actions))
        .order_by(DecisionScenario.updated_at.desc())
        .limit(limit)
    )
    if status is not None:
        statement = statement.where(DecisionScenario.status == status)
    scenarios = session.scalars(statement).all()
    counts = {}
    if scenarios:
        counts = {
            row[0]: row[1]
            for row in session.execute(
                select(
                    DecisionSimulation.scenario_id,
                    func.count(DecisionSimulation.id),
                )
                .where(
                    DecisionSimulation.scenario_id.in_(
                        [scenario.id for scenario in scenarios]
                    )
                )
                .group_by(DecisionSimulation.scenario_id)
            ).all()
        }
    return [
        _scenario_summary(
            scenario, simulation_count=counts.get(scenario.id, 0)
        )
        for scenario in scenarios
    ]


@router.post(
    "/scenarios", response_model=ScenarioDetailResponse, status_code=201
)
def create_scenario(
    payload: ScenarioCreate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ScenarioDetailResponse:
    scenario = DecisionScenario(
        name=payload.name,
        description=payload.description,
        hazard_type=payload.hazard_type,
        parameters=payload.parameters,
        horizon_minutes=payload.horizon_minutes,
        budget_limit=payload.budget_limit,
        resolution=payload.resolution,
        risk_window_hours=payload.risk_window_hours,
        status=ScenarioStatus.DRAFT,
        created_by=user.profile.id,
    )
    session.add(scenario)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(scenario)
    return _scenario_detail(_scenario_or_404(session, scenario.id), session)


@router.get(
    "/scenarios/{scenario_id}", response_model=ScenarioDetailResponse
)
def get_scenario(
    scenario_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ScenarioDetailResponse:
    del user
    return _scenario_detail(_scenario_or_404(session, scenario_id), session)


@router.patch(
    "/scenarios/{scenario_id}", response_model=ScenarioDetailResponse
)
def update_scenario(
    scenario_id: uuid.UUID,
    payload: ScenarioUpdate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ScenarioDetailResponse:
    del user
    scenario = _scenario_or_404(session, scenario_id)
    _reject_null_updates(payload, NON_NULL_SCENARIO_FIELDS)
    for field in payload.model_fields_set:
        value = getattr(payload, field)
        if field == "name" and value is not None:
            value = value.strip()
        setattr(scenario, field, value)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(scenario)
    return _scenario_detail(_scenario_or_404(session, scenario.id), session)


def _apply_requirements(
    session: Session, action: DecisionAction, requirements
) -> None:
    resource_ids = [item.resource_id for item in requirements]
    if len(resource_ids) != len(set(resource_ids)):
        raise AppError(
            "resource_requirements must not duplicate a resource.",
            status_code=422,
            code="duplicate_resource_requirement",
        )
    if resource_ids:
        found = {
            resource.id
            for resource in session.scalars(
                select(ResponseResource).where(
                    ResponseResource.id.in_(resource_ids)
                )
            ).all()
        }
        if set(resource_ids) - found:
            raise AppError(
                "One or more resource requirements reference unknown resources.",
                status_code=422,
                code="invalid_resource",
            )
    action.requirements.clear()
    for requirement in requirements:
        action.requirements.append(
            ActionResourceRequirement(
                resource_id=requirement.resource_id,
                quantity_required=requirement.quantity_required,
            )
        )


@router.post(
    "/scenarios/{scenario_id}/actions",
    response_model=ActionResponse,
    status_code=201,
)
def create_action(
    scenario_id: uuid.UUID,
    payload: ActionCreate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ActionResponse:
    del user
    scenario = _scenario_or_404(session, scenario_id)
    if scenario.status == ScenarioStatus.ARCHIVED:
        raise AppError(
            "Archived scenarios cannot be edited.",
            status_code=409,
            code="scenario_archived",
        )
    action_count = session.scalar(
        select(func.count(DecisionAction.id)).where(
            DecisionAction.scenario_id == scenario_id
        )
    ) or 0
    if int(action_count) >= DecisionConfig.from_settings(
        get_settings()
    ).max_actions:
        raise AppError(
            "Scenario action limit reached.",
            status_code=422,
            code="too_many_actions",
        )
    _validate_h3(payload.target_h3_cell_id)
    _validate_action_references(
        session,
        scenario_id=scenario_id,
        target_asset_id=payload.target_asset_id,
        department_id=payload.department_id,
        depends_on_action_id=payload.depends_on_action_id,
    )
    action = DecisionAction(
        scenario_id=scenario_id,
        title=payload.title,
        description=payload.description,
        action_type=payload.action_type,
        target_h3_cell_id=payload.target_h3_cell_id,
        target_asset_id=payload.target_asset_id,
        department_id=payload.department_id,
        priority=payload.priority,
        earliest_start_minutes=payload.earliest_start_minutes,
        duration_minutes=payload.duration_minutes,
        expected_risk_reduction=payload.expected_risk_reduction,
        estimated_cost=payload.estimated_cost,
        depends_on_action_id=payload.depends_on_action_id,
        assumptions=payload.assumptions,
    )
    _apply_requirements(session, action, payload.resource_requirements)
    session.add(action)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(action)
    return _action_response(action, session)


@router.patch(
    "/scenarios/{scenario_id}/actions/{action_id}",
    response_model=ActionResponse,
)
def update_action(
    scenario_id: uuid.UUID,
    action_id: uuid.UUID,
    payload: ActionUpdate,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ActionResponse:
    del user
    scenario = _scenario_or_404(session, scenario_id)
    if scenario.status == ScenarioStatus.ARCHIVED:
        raise AppError(
            "Archived scenarios cannot be edited.",
            status_code=409,
            code="scenario_archived",
        )
    action = session.get(DecisionAction, action_id)
    if action is None or action.scenario_id != scenario_id:
        raise AppError(
            "Decision action not found.",
            status_code=404,
            code="action_not_found",
        )
    _reject_null_updates(payload, NON_NULL_ACTION_FIELDS)
    if "target_h3_cell_id" in payload.model_fields_set:
        _validate_h3(payload.target_h3_cell_id)
    _validate_action_references(
        session,
        scenario_id=scenario_id,
        target_asset_id=(
            payload.target_asset_id
            if "target_asset_id" in payload.model_fields_set
            else action.target_asset_id
        ),
        department_id=(
            payload.department_id
            if "department_id" in payload.model_fields_set
            else action.department_id
        ),
        depends_on_action_id=(
            payload.depends_on_action_id
            if "depends_on_action_id" in payload.model_fields_set
            else action.depends_on_action_id
        ),
        self_id=action.id,
    )
    for field in payload.model_fields_set:
        if field != "resource_requirements":
            setattr(action, field, getattr(payload, field))
    if payload.resource_requirements is not None:
        _apply_requirements(session, action, payload.resource_requirements)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(action)
    return _action_response(action, session)


@router.post(
    "/scenarios/{scenario_id}/simulate",
    response_model=SimulationResponse,
)
def simulate_scenario(
    scenario_id: uuid.UUID,
    payload: SimulationRequest,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SimulationResponse:
    scenario = _scenario_or_404(session, scenario_id)
    try:
        outcome = simulate(
            session,
            scenario,
            strategy=payload.strategy,
            settings=settings,
            persist=payload.persist,
            requested_by=user.profile.id,
        )
    except DecisionError as error:
        raise AppError(str(error), status_code=422, code=error.code) from error
    return SimulationResponse(**outcome.payload)


@router.get(
    "/scenarios/{scenario_id}/simulations",
    response_model=list[SimulationListItem],
)
def simulations(
    scenario_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[SimulationListItem]:
    del user
    _scenario_or_404(session, scenario_id)
    return [
        SimulationListItem(
            id=simulation.id,
            scenario_id=simulation.scenario_id,
            strategy=simulation.strategy,
            status=simulation.status,
            model_version=simulation.model_version,
            config_hash=simulation.config_hash,
            duration_ms=simulation.duration_ms,
            calculated_at=simulation.calculated_at,
            summary=simulation.summary or {},
        )
        for simulation in list_simulations(session, scenario_id)
    ]


@router.get(
    "/scenarios/{scenario_id}/simulations/{simulation_id}",
    response_model=dict,
)
def simulation_detail(
    scenario_id: uuid.UUID,
    simulation_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    del user
    _scenario_or_404(session, scenario_id)
    simulation = load_simulation(session, scenario_id, simulation_id)
    if simulation is None:
        raise AppError(
            "Simulation not found.",
            status_code=404,
            code="simulation_not_found",
        )
    return {
        "id": str(simulation.id),
        "scenario_id": str(simulation.scenario_id),
        "strategy": simulation.strategy.value,
        "status": simulation.status.value,
        "model_version": simulation.model_version,
        "config_hash": simulation.config_hash,
        "summary": simulation.summary,
        "solver": simulation.solver,
        "result": simulation.result,
        "calculated_at": simulation.calculated_at.isoformat(),
        "execution_authorized": False,
        "dispatch_performed": False,
        "reservations_created": False,
    }


@router.post(
    "/scenarios/{scenario_id}/compare",
    response_model=ComparisonResponse,
)
def compare_scenario(
    scenario_id: uuid.UUID,
    payload: ComparisonRequest,
    user: Annotated[AuthenticatedUser, Depends(require_worker)],
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ComparisonResponse:
    del user
    scenario = _scenario_or_404(session, scenario_id)
    try:
        return ComparisonResponse(
            **compare(
                session,
                scenario,
                strategies=payload.strategies,
                settings=settings,
            )
        )
    except DecisionError as error:
        raise AppError(str(error), status_code=422, code=error.code) from error
