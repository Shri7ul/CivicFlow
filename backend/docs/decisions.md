# Decision intelligence and scenario planning (Phase 6)

Phase 6 adds a **staff-only planning workspace**. It turns explicit response
actions, dependencies, budgets, and resource assumptions into a bounded schedule,
then compares heuristic strategies. It does not dispatch units, assign work,
reserve resources, decrement inventory, or mutate incidents.

## Architecture

```text
decision_scenarios ── decision_actions ── action_resource_requirements
        │                    │                       │
        │                    └── target H3 / asset   └── response_resources
        └── decision_simulations (immutable planning result)
                         │
        bounded scheduler + strategy comparison
                         │
        current H3 risk context (read-only)
```

| Module | Responsibility |
| --- | --- |
| `app/models/decision.py` | Scenario, action, resource, requirement, and simulation tables |
| `app/decisions/config.py` | Versioned model, solver limit, objective weights, labels |
| `app/decisions/engine.py` | Deterministic constraint scheduling and strategy comparison |
| `app/decisions/service.py` | Scenario loading, risk context, simulation orchestration |
| `app/decisions/serialization.py` | Stable result shaping |
| `app/api/v1/endpoints/decisions.py` | Staff-only APIs and input validation |

## Resource availability is explicit

`response_resources` starts with `availability_status = UNKNOWN` and
`quantity_available = 0`. The API requires both `availability_source` and
`available_as_of` for any known, limited, unavailable, or planning-assumption
record. `PLANNING_ASSUMPTION` is a first-class status and is surfaced in every
simulation result.

The scheduler never invents inventory:

- `UNKNOWN` and `UNAVAILABLE` resources block actions that require them.
- Missing resources block the action with a reason code.
- A resource shared-capacity allocation cannot overlap beyond its quantity.
- A consumable resource cannot be consumed beyond its quantity.
- Actions without resource requirements are scheduled but flagged as not
  resource-modelled.
- No resource is reserved or decremented by a simulation.

## Constraints and scheduling

The scheduler is deterministic and deadline-bounded
(`DECISION_SOLVER_TIME_LIMIT_MS`). It models:

- action dependencies (cycles and missing dependencies are blocked);
- earliest start and horizon limits;
- priority;
- shared versus consumable resource capacity;
- optional budget limit and known costs;
- target H3 cells and current risk context.

Action result statuses are `SCHEDULED`, `BLOCKED`, `DEFERRED`, or
`UNSCHEDULED`. Every non-scheduled action carries a machine-readable reason such
as `resource_availability_unknown`, `budget_exceeded`,
`no_feasible_schedule_within_horizon`, `dependency_missing`, or
`solver_time_limit`.

Strategies are bounded heuristics, not an external MILP/CP solver:

| Strategy | Ordering intent |
| --- | --- |
| `PRIORITY` | Highest priority first |
| `RISK_REDUCTION` | Largest planner-supplied reduction first |
| `COST_EFFICIENT` | Reduction per unit cost first |
| `BALANCED` | Blended priority, reduction, duration, and cost |

`POST /scenarios/{id}/compare` runs each strategy against the same inputs and
solver budget, ranks by a transparent objective, and reports component scores.
The objective weights are exposed at `GET /decisions/config`.

## Planner-supplied values

Expected risk reduction, duration, cost, priority, and resource quantity are
**planning assumptions entered by staff**. They are not measured outcomes or
calibrated estimates. If an action targets a cell in the current risk context,
its planned reduction is capped at that cell's observed risk score. Unknown
costs produce a warning and are excluded from known-cost totals; they are not
silently treated as zero-cost facts.

## API

All endpoints require an active WORKER or ADMIN profile.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/decisions/config` | Model, solver limit, objective weights |
| GET | `/api/v1/decisions/metadata` | Labels for hazards/actions/resources |
| GET/POST | `/api/v1/decisions/resources` | Explicit resource inventory |
| PATCH | `/api/v1/decisions/resources/{id}` | Correct resource availability/provenance |
| GET/POST | `/api/v1/decisions/scenarios` | List/create planning scenarios |
| GET/PATCH | `/api/v1/decisions/scenarios/{id}` | Read/update a scenario |
| POST/PATCH | `/api/v1/decisions/scenarios/{id}/actions[/{action_id}]` | Add/update actions |
| POST | `/api/v1/decisions/scenarios/{id}/simulate` | Run and optionally persist a plan |
| POST | `/api/v1/decisions/scenarios/{id}/compare` | Compare all four strategies |
| GET | `/api/v1/decisions/scenarios/{id}/simulations` | Persisted run history |
| GET | `/api/v1/decisions/scenarios/{id}/simulations/{simulation_id}` | Full stored result |

Validation errors include `invalid_h3_cell`, `invalid_target_asset`,
`invalid_department`, `invalid_dependency`, `invalid_resource`,
`duplicate_resource_requirement`, `too_many_actions`, `invalid_horizon`, and
`scenario_archived`. Missing resources/scenarios/actions return opaque 404s;
Citizens receive 403.

## Persistence and RLS

Five staff-only tables are added by `0011_decision_intelligence`:

- `decision_scenarios`
- `decision_actions`
- `action_resource_requirements`
- `response_resources`
- `decision_simulations`

All five have RLS enabled with a `public.is_worker_or_admin()` SELECT policy.
Authenticated database roles have SELECT only; API writes use the backend
service role. Simulations store the model version, config hash, input risk
context, result, summary, solver metadata, requester, and timestamp.

## Safety and limitations

- Planning results are **not execution authorisation**. Every result includes
  `execution_authorized=false`, `dispatch_performed=false`, and
  `reservations_created=false`.
- No endpoint updates incident status, assigns an incident, changes an asset, or
  decrements a resource.
- The objective is a heuristic ranking, not a prediction of lives saved, cost
  saved, or operational success.
- The repository contains no authoritative resource inventory; staff must enter
  source and time for any known availability. UNKNOWN is the safe default.
- The scheduler is a bounded greedy heuristic with a hard time limit, not a
  proof of optimality.
- Travel time, crew certification, shift rules, procurement, and field safety
  constraints are not modelled.
