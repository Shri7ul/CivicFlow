"""Stable JSON shaping for decision simulations."""

from __future__ import annotations

from app.decisions.engine import (
    RiskContext,
    StrategyComparison,
    StrategyPlan,
)


def risk_context_payload(context: RiskContext) -> dict:
    return {
        "available": context.available,
        "resolution": context.resolution,
        "window_hours": context.window_hours,
        "cell_count": context.cell_count,
        "incident_count": context.incident_count,
        "cells": dict(context.cells),
        "limitations": list(context.limitations),
    }


def action_payload(item) -> dict:
    action = item.action
    return {
        "action_id": str(action.id),
        "title": action.title,
        "description": action.description,
        "action_type": action.action_type,
        "priority": action.priority,
        "status": item.status,
        "start_minute": item.start_minute,
        "end_minute": item.end_minute,
        "duration_minutes": action.duration_minutes,
        "expected_risk_reduction": action.expected_risk_reduction,
        "planned_reduction": item.planned_reduction,
        "target_h3_cell_id": action.target_h3_cell_id,
        "target_risk_score": item.target_risk_score,
        "target_asset_id": str(action.target_asset_id) if action.target_asset_id else None,
        "target_asset_name": action.target_asset_name,
        "department_id": str(action.department_id) if action.department_id else None,
        "department_name": action.department_name,
        "depends_on_action_id": (
            str(action.depends_on_action_id)
            if action.depends_on_action_id
            else None
        ),
        "estimated_cost": action.estimated_cost,
        "reasons": list(item.reasons),
        "resources": list(item.resources),
        "assumptions": dict(action.assumptions),
    }


def plan_payload(plan: StrategyPlan, *, rank: int | None = None) -> dict:
    payload = {
        "strategy": plan.strategy.value,
        "strategy_label": plan.strategy_label,
        "objective_score": plan.objective_score,
        "objective_components": plan.objective_components,
        "metrics": plan.metrics,
        "actions": [action_payload(item) for item in plan.actions],
        "resources": list(plan.resources),
        "solver": plan.solver,
        "assumptions": list(plan.assumptions),
        "warnings": list(plan.warnings),
        "limitations": list(plan.limitations),
        "execution_authorized": False,
        "dispatch_performed": False,
        "reservations_created": False,
    }
    if rank is not None:
        payload["rank"] = rank
    return payload


def comparison_payload(comparison: StrategyComparison) -> dict:
    return {
        "winner": comparison.winner.value if comparison.winner else None,
        "results": [
            plan_payload(plan, rank=index + 1)
            for index, plan in enumerate(comparison.results)
        ],
        "solver": comparison.solver,
        "assumptions": list(comparison.assumptions),
        "warnings": list(comparison.warnings),
        "limitations": [
            "Strategy comparison ranks planning heuristics against the same "
            "planner-supplied inputs; it does not authorize execution.",
            "A higher objective score is not a real-world outcome prediction.",
        ],
        "execution_authorized": False,
        "dispatch_performed": False,
        "reservations_created": False,
    }
