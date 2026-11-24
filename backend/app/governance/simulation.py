"""Independent validation of persisted decision simulations.

The audit checks declared constraints and explicit unknowns. It never turns a
simulation into an operational instruction or a real resource claim.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.governance.serialization import iso
from app.models.decision import DecisionScenario, DecisionSimulation, ResponseResource
from app.models.enums import DecisionReviewStatus
from app.models.operations import DecisionReview


def _check(key: str, label: str, status: str, evidence: str) -> dict:
    return {"key": key, "label": label, "status": status, "evidence": evidence}


def _overall(checks: list[dict]) -> str:
    statuses = {item["status"] for item in checks}
    if "FAIL" in statuses:
        return "FAIL"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "PASS"


def build_simulation_audit(session: Session) -> dict:
    simulations = session.scalars(
        select(DecisionSimulation).order_by(DecisionSimulation.calculated_at.desc())
    ).all()
    scenarios = {
        item.id: item
        for item in session.scalars(
            select(DecisionScenario).where(
                DecisionScenario.id.in_(
                    [simulation.scenario_id for simulation in simulations]
                )
            )
        ).all()
    } if simulations else {}
    resources = {
        item.id: item for item in session.scalars(select(ResponseResource)).all()
    }
    reviews: dict = {}
    if simulations:
        rows = session.scalars(
            select(DecisionReview)
            .where(
                DecisionReview.simulation_id.in_(
                    [simulation.id for simulation in simulations]
                )
            )
            .order_by(DecisionReview.created_at)
        ).all()
        for row in rows:
            reviews.setdefault(row.simulation_id, []).append(row)
    payload = []
    for simulation in simulations:
        scenario = scenarios.get(simulation.scenario_id)
        result = simulation.result or {}
        action_rows = result.get("actions") or []
        resource_rows = result.get("resources") or []
        solver = result.get("solver") or simulation.solver or {}
        assumptions = result.get("assumptions") or []
        if isinstance(simulation.assumptions, dict):
            assumptions = assumptions or [
                f"{key}: {value}"
                for key, value in simulation.assumptions.items()
                if key
                in {"scenario_parameters", "risk_context", "planning_only"}
            ]
        objective = result.get("objective_score")
        components = result.get("objective_components") or {}
        unknown = [
            item
            for item in resource_rows
            if item.get("availability_status") == "UNKNOWN"
        ]
        changed_unknown = []
        for item in resource_rows:
            source = resources.get(item.get("resource_id"))
            if (
                item.get("availability_status") == "UNKNOWN"
                and source is not None
                and source.availability_status.value != "UNKNOWN"
            ):
                changed_unknown.append(item.get("name"))
        checks = [
            _check(
                "objective_declared",
                "Objective function and components are recorded",
                "PASS" if objective is not None and components else "FAIL",
                f"objective_score={objective}; components={sorted(components)}",
            ),
            _check(
                "constraints_recorded",
                "Solver, budget and planning constraints are explicit",
                "PASS"
                if solver and (assumptions or result.get("assumptions"))
                else "FAIL",
                f"solver={sorted(solver)}; assumptions={len(assumptions)}; "
                f"budget={((result.get('metrics') or {}).get('budget_limit'))}",
            ),
            _check(
                "reproducible_metadata",
                "Model version, config hash and solver are recorded",
                "PASS"
                if simulation.model_version
                and simulation.config_hash
                and solver.get("algorithm")
                else "FAIL",
                f"model={simulation.model_version}; config={simulation.config_hash[:12]}…; "
                f"algorithm={solver.get('algorithm')}",
            ),
            _check(
                "unknown_resources_preserved",
                "UNKNOWN resource availability is not converted to certainty",
                "NOT_APPLICABLE"
                if not resource_rows
                else ("FAIL" if changed_unknown else "PASS"),
                (
                    f"{len(unknown)} UNKNOWN resource(s) of {len(resource_rows)}; "
                    f"converted={changed_unknown}"
                    if resource_rows
                    else "The simulation references no response resources."
                ),
            ),
            _check(
                "no_execution_side_effects",
                "No dispatch, reservation or execution was performed",
                "PASS"
                if result.get("execution_authorized") is False
                and result.get("dispatch_performed") is False
                and result.get("reservations_created") is False
                else "FAIL",
                "execution_authorized=false; dispatch_performed=false; "
                "reservations_created=false",
            ),
        ]
        review_rows = reviews.get(simulation.id, [])
        approved = [
            item for item in review_rows if item.status == DecisionReviewStatus.APPROVED
        ]
        checks.append(
            _check(
                "human_review",
                "An independent human review approved this simulation",
                "PASS" if approved else "FAIL",
                (
                    f"{len(approved)} approved review(s) of {len(review_rows)}."
                    if review_rows
                    else "No decision review is recorded."
                ),
            )
        )
        risk_context = (
            (simulation.assumptions or {}).get("risk_context")
            if isinstance(simulation.assumptions, dict)
            else None
        )
        checks.append(
            _check(
                "risk_context_provenance",
                "Risk context is explicitly available or explicitly absent",
                "PASS"
                if isinstance(risk_context, dict)
                and "available" in risk_context
                else "UNKNOWN",
                (
                    f"risk_context.available={risk_context.get('available')}; "
                    f"cells={risk_context.get('cell_count')}; "
                    f"window_hours={risk_context.get('window_hours')}"
                    if isinstance(risk_context, dict)
                    else "No risk context provenance is recorded."
                ),
            )
        )
        status = _overall(checks)
        payload.append(
            {
                "id": str(simulation.id),
                "simulation_label": "SIMULATED",
                "scenario": {
                    "id": str(simulation.scenario_id),
                    "name": scenario.name if scenario else None,
                    "hazard_type": (
                        scenario.hazard_type.value if scenario else None
                    ),
                    "horizon_minutes": scenario.horizon_minutes if scenario else None,
                    "budget_limit": (
                        float(scenario.budget_limit)
                        if scenario and scenario.budget_limit is not None
                        else None
                    ),
                },
                "strategy": simulation.strategy.value,
                "status": simulation.status.value,
                "validation_status": status,
                "model_version": simulation.model_version,
                "config_hash": simulation.config_hash,
                "calculated_at": iso(simulation.calculated_at),
                "duration_ms": simulation.duration_ms,
                "objective": {"score": objective, "components": components},
                "plan_summary": {
                    "scheduled_actions": len(
                        [item for item in action_rows if item.get("status") == "SCHEDULED"]
                    ),
                    "total_actions": len(action_rows),
                    "resources_used": len(resource_rows),
                    "unknown_resources": len(unknown),
                    "metrics": result.get("metrics") or {},
                },
                "assumptions": assumptions,
                "solver": solver,
                "warnings": result.get("warnings") or [],
                "limitations": result.get("limitations") or [],
                "human_reviews": [
                    {
                        "id": str(item.id),
                        "status": item.status.value,
                        "reviewed_by": (
                            str(item.reviewed_by) if item.reviewed_by else None
                        ),
                        "created_at": iso(item.created_at),
                    }
                    for item in review_rows
                ],
                "checks": checks,
                "simulation_only": True,
                "dispatch_permitted": False,
                "resource_allocation_permitted": False,
                "note": (
                    "This is a planning simulation. Simulated availability is not "
                    "real availability and no action may be dispatched from it."
                ),
            }
        )
    review_counts = Counter(item["validation_status"] for item in payload)
    return {
        "protocol": "phase10-simulation-audit-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "simulations": len(payload),
            "pass": review_counts.get("PASS", 0),
            "fail": review_counts.get("FAIL", 0),
            "unknown": review_counts.get("UNKNOWN", 0),
            "with_approved_review": sum(
                1 for item in payload if any(
                    check["key"] == "human_review" and check["status"] == "PASS"
                    for check in item["checks"]
                )
            ),
        },
        "simulations": payload,
        "limitations": [
            "The audit verifies recorded metadata and explicit unknowns; it does "
            "not verify real-world resource availability.",
            "Planner-supplied expected risk reductions remain assumptions.",
            "A passing audit is not an execution authorization.",
            "Simulated plans are illustrative and are not emergency instructions.",
        ],
        "execution_authorized": False,
    }
