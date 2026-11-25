# Phase 14 — Pilot Monitoring and Incident Handling

Status: **WORKFLOW IMPLEMENTED / NO ACTIVE PILOT TO MONITOR**

## 1. Monitored signals

The Phase 14 monitoring view is composed of existing and new sources:

- existing `/health/live`, `/health/ready`, `/health/dependencies` and structured
  request logs with `X-Request-ID` (Phase 13);
- existing `/operations/dashboard`, alerts, data-quality and ingestion status;
- new `PilotIncident` records with severity and state (migration `0024`);
- new final readiness gate at `/governance/phase14/readiness`;
- new processing interlock at `/governance/phase14/incidents/pilot/{id}/processing`.

## 2. Incident severity and states

Severity: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
States: `OPEN` → `INVESTIGATING` → `MITIGATED` → `RESOLVED` → `CLOSED`.

Transitions are admin-only, require a written note, and append an immutable
`PilotIncidentEvent`. Worker/admin staff can open a pilot incident for a
governed pilot (APPROVED, ACTIVE or PAUSED).

## 3. Processing interlock

Opening a `CRITICAL` incident sets `processing_stopped = true`. While any such
incident is OPEN/INVESTIGATING/MITIGATED for that pilot,
`processing_allowed()` returns `{allowed: false, reasons: [critical_incident_processing_stop]}`.

The interlock stops **platform processing only**. It does not dispatch crews,
send alerts, allocate budgets, enforce rules, or contact any external system.
It can be lifted only by an admin after the incident is RESOLVED or CLOSED, with
a recorded justification and an append-only event.

## 4. Signals to watch during a future authorized pilot

| Signal | Source | Alert condition |
| --- | --- | --- |
| Evidence acquisition failures | Phase 11 snapshots / operations alerts | Any FAILED/QUARANTINED snapshot |
| Data freshness | readiness + data-quality snapshot | Beyond configured freshness window |
| Data quality | snapshot quality checks | WARN/FAIL checks |
| API / dependency failures | health endpoints, request logs, alerts | 5xx or dependency DOWN |
| Geographic scope violations | geography isolation APIs | Any cross-context key |
| Authorization failures | auth events / logs | Repeated 401/403 |
| Review backlog | review cases / observations | Growing PENDING_REVIEW count |
| Model errors and uncertainty | risk serialization / evaluation | Error or missing confidence |
| Reviewer disagreement | review events | Divergent decisions on same item |
| Operational incidents | pilot incidents | Any OPEN incident |
| Pauses / rollbacks | pilot transitions + shutdown records | Any PAUSED/TERMINATED |

## 5. Escalation

LOW/MEDIUM are recorded and reviewed in the normal cadence. HIGH requires an
admin investigation entry. CRITICAL engages the processing interlock and must
be reviewed before processing resumes. There is no automated real-world
emergency response.

## 6. Current state

| Item | Status |
| --- | --- |
| Incident workflow and interlock | IMPLEMENTED / AUTOMATED-TESTED |
| Health/monitoring endpoints | IMPLEMENTED / AUTOMATED-TESTED (live NOT_ASSESSED) |
| Active pilot or incidents | NONE (no approved pilot) |
| External log/sink integration | NOT_ASSESSED |
