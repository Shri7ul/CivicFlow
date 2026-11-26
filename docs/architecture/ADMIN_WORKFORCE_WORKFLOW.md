# Admin & Workforce Workflow Architecture

Date: 2026-11-26. Status: implementation design derived from the audit in
`docs/audit/ADMIN_WORKFORCE_WORKFLOW_AUDIT.md`.

## 1. Principles

1. **Extend, do not duplicate.** The existing `IncidentStatus` enum and
   `ALLOWED_TRANSITIONS` table are extended with the workforce states. No parallel
   incident state machine is introduced.
2. **Role truth lives in the database.** The profile's `role` column, resolved from
   the verified JWT `sub`, is the only authorization source. No client-submitted
   role is ever accepted.
3. **Privileged changes go through existing guarded services.** Granting WORKER
   calls `change_profile_role()`, which is admin-only, self-change guarded and
   audited.
4. **State changes go through existing guarded services.** Incident transitions call
   `transition_incident()`, which validates transitions and writes
   `IncidentStatusEvent` rows.
5. **Every consequential action is deliberate and authorized.** No automatic dispatch.
6. **Geography is explicit.** Eligibility uses configured `service_area` strings and
   department membership. No ward boundaries are inferred or fabricated.

## 2. Roles and effective access

| Role | Backend dependency | Effective access |
|---|---|---|
| CITIZEN | `require_active_user` | Own reports, incident creation, own worker application, own notifications |
| WORKER (approved, active) | `require_active_worker` | Assigned incidents only; accept/decline/start/progress/complete |
| WORKER (suspended / no profile) | rejected by `require_active_worker` | No operational access |
| ADMIN | `require_admin` | All incidents, applications, workers, assignments, verification, audit |

`require_worker` remains for legacy read-only staff endpoints. Worker operational
endpoints use the stricter `require_active_worker`, which requires both the WORKER
role and an active `WorkerProfile`.

## 3. Data model (migration `0025_workforce`)

```
profiles ──< worker_applications ──< worker_profiles ──< incident_assignments
    │                                      │                    │
    │                                      │                    └──< incident_assignment_events
    ├──< workforce_events (actor)          └── incidents
    └──< workforce_notifications (recipient)
```

New tables:

- `worker_applications` — applicant, contact details, specialization, department,
  service area, address, experience, credentials note, status, review note,
  reviewer, timestamps. One application per applicant (unique `applicant_id`).
- `worker_profiles` — approved worker operational profile: specialization,
  department, authorized service area, status (`ACTIVE`/`SUSPENDED`), approving
  admin, approval timestamp.
- `incident_assignments` — incident, worker, assigning admin, status
  (`OFFERED`/`ACCEPTED`/`DECLINED`/`IN_PROGRESS`/`COMPLETION_SUBMITTED`/
  `VERIFIED_COMPLETED`/`CANCELLED`), note, deadline, timestamps.
- `incident_assignment_events` — append-only assignment state history.
- `workforce_events` — append-only cross-domain audit events with actor, action,
  entity type/id, previous/new state and metadata. No update or delete API.
- `workforce_notifications` — direct in-app messages with read state.

New enums (VARCHAR + CHECK, following `app/models/types.py`):
`WorkerApplicationStatus`, `WorkerStatus`, `AssignmentStatus`.

Extended enum: `IncidentStatus` gains `VERIFIED`, `ASSIGNED`, `ACCEPTED`,
`COMPLETION_SUBMITTED`, `VERIFIED_COMPLETED`. The migration updates the three
existing CHECK constraints (`incidents.status`, `incident_status_events.from_status`,
`incident_status_events.to_status`) additively.

## 4. Incident lifecycle (single state machine)

```
Legacy path (preserved):
  OPEN ──> ACKNOWLEDGED ──> IN_PROGRESS ──> RESOLVED ──> CLOSED

Workforce path (added):
  OPEN ──> VERIFIED ──> ASSIGNED ──> ACCEPTED ──> IN_PROGRESS
        ──> COMPLETION_SUBMITTED ──> VERIFIED_COMPLETED ──> RESOLVED ──> CLOSED

Other permitted transitions:
  VERIFIED ──> REJECTED-equivalent: OPEN remains the rejection target (no new enum)
  ASSIGNED ──> VERIFIED (reassignment/cancellation)
  COMPLETION_SUBMITTED ──> IN_PROGRESS (rework)
```

The department requirement is preserved for `ACKNOWLEDGED` and for legacy
`OPEN → IN_PROGRESS`; it is not imposed on `ACCEPTED → IN_PROGRESS`, because the
worker assignment itself carries authorization.

## 5. Service layer

- `app/workforce/applications.py` — submit, list/filter, review decisions, status.
  Approval performs three atomic steps: mark application approved, call
  `change_profile_role(..., WORKER)`, create/activate `WorkerProfile`.
- `app/workforce/assignments.py` — candidate ranking and eligibility, assign,
  reassign, cancel, accept, decline, start, progress, submit completion, verify
  completion (approve or rework). Every step writes assignment events, incident
  status events and workforce audit events.
- `app/workforce/audit.py` / `app/workforce/notifications.py` — append-only event
  emission and direct in-app notifications.

Eligibility ranking (deterministic, explainable):

1. application approved and worker profile active;
2. service-area match with the incident's configured area/department;
3. specialization match with incident category;
4. no incompatible active assignment;
5. lowest active assignment count (workload);
6. stable tie-break by worker id.

A rationale string is returned with each candidate. Nothing is auto-dispatched.

## 6. API surface (`/api/v1/workforce`)

| Method | Path | Role |
|---|---|---|
| POST | `/applications` | active user |
| GET | `/applications/mine` | active user |
| GET | `/applications`, `/applications/{id}` | ADMIN |
| POST | `/applications/{id}/review` | ADMIN |
| GET | `/workers` | ADMIN |
| GET | `/workers/me` | approved worker |
| POST | `/workers/{id}/suspend`, `/reactivate` | ADMIN |
| GET | `/admin/overview` | ADMIN |
| GET | `/assignments/candidates` | ADMIN |
| POST | `/assignments`, `/assignments/{id}/reassign`, `/cancel` | ADMIN |
| GET | `/assignments`, `/assignments/{id}` | active worker / ADMIN |
| POST | `/assignments/{id}/accept`, `/decline`, `/start`, `/progress`, `/complete` | active worker |
| POST | `/assignments/{id}/verify` | ADMIN |
| GET | `/events` | ADMIN |
| GET | `/notifications`, `/notifications/{id}/read` | active user |

All mutating schemas use `extra="forbid"`; errors use the existing structured
`AppError` envelope with stable `code` values and explicit status codes.

## 7. Frontend

- `routing.ts` gains distinct ADMIN/WORKER path sets; `AuthGuard` uses
  `canAccessPath` for UX enforcement while the backend remains authoritative.
- New API module `lib/api/workforce.ts` consumes only real endpoints.
- New routes: `/workforce/apply`, `/workforce/status`, `/admin`, `/worker`.
- Reuse: `AuthProvider.apiRequest`, `AuthGuard`, `StatusBadge`, filter/pagination
  patterns and `pilot-ui` primitives.

## 8. Security boundaries

- No browser-supplied `role`, `status`, `worker_id`, `actor_id` or decision is trusted.
- Worker actions are limited to assignments owned by that worker.
- Audit and notification APIs are read-only except for marking a notification read.
- No private evidence URLs are placed in notifications or audit metadata.
- No production migration, user creation, role grant or pilot activation is performed
  by this sprint; those remain operator actions.

## 9. Verification strategy

- Unit/service tests against in-memory SQLite for all state transitions and guards.
- API tests with dependency overrides for real JWT verification and role profiles.
- Frontend tests for role routing, API contracts and pure view rendering.
- Full backend/frontend suites, typecheck, lint, production builds, Alembic single-head
  check, secret scan and route audit before commit.
