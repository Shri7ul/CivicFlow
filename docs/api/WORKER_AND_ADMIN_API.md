# Worker & Admin API Reference

Date: 2026-11-26. Scope: the workforce layer under `/api/v1/workforce`, added by
migration `0025_workforce`. This document describes implemented code, not a plan.

## 1. Conventions

- All endpoints require a verified Supabase JWT (`Authorization: Bearer <token>`).
- Authorization always resolves the role from the database `profiles.role` column.
  No client-supplied role, `worker_id`, `actor_id`, `status` or decision is trusted.
- All mutating request schemas use `extra="forbid"`. Unknown fields are rejected.
- Errors use the existing structured envelope:
  `{"error": {"code": "...", "message": "..."}}` with an explicit HTTP status.
- Lists use `items`, `total`, `limit`, `offset`. Mutation responses return the
  updated record. All timestamps are ISO-8601 with timezone.
- No endpoint performs automatic dispatch or automatic incident resolution. Every
  consequential transition is an explicit authorized call.

## 2. Roles used by this API

| Role / state | Dependency | Meaning |
|---|---|---|
| CITIZEN (active) | `require_active_user` | May apply once and read own application, profile and notifications |
| WORKER + active `WorkerProfile` | `require_active_worker` | May act only on assignments owned by that worker |
| WORKER + suspended / no profile | rejected | No operational access (`worker_suspended` / `worker_profile_required`) |
| ADMIN | `require_admin` | Full control plane: review, suspend, assign, verify, read audit |

## 3. Worker application endpoints

| Method | Path | Caller | Request | Response |
|---|---|---|---|---|
| POST | `/applications` | active CITIZEN | `WorkerApplicationCreate` | `WorkerApplicationResponse` |
| GET | `/applications/mine` | active user | — | `WorkerApplicationResponse` (404 if none) |
| GET | `/applications` | ADMIN | `status`, `specialization`, `department_id`, `limit`, `offset` | `ApplicationListResponse` |
| GET | `/applications/{id}` | ADMIN | — | `WorkerApplicationResponse` |
| POST | `/applications/{id}/review` | ADMIN | `{"decision","note?"}` | `WorkerApplicationResponse` |

`decision` is one of `APPROVE`, `REJECT`, `REQUEST_INFO`, `UNDER_REVIEW`.
`REJECT` and `REQUEST_INFO` require a non-empty `note`. Approval atomically marks
the application `APPROVED`, grants `WORKER` through the audited
`change_profile_role()` service, and activates a `WorkerProfile`. Only a CITIZEN
may apply; duplicate applications are rejected with `duplicate_application`.

Application statuses: `PENDING`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`,
`ADDITIONAL_INFORMATION_REQUIRED`, `SUSPENDED`.

## 4. Worker management endpoints

| Method | Path | Caller | Request | Response |
|---|---|---|---|---|
| GET | `/workers` | ADMIN | `status`, `specialization`, `department_id`, `limit`, `offset` | `WorkerListResponse` |
| GET | `/workers/me` | active worker | — | `WorkerProfileResponse` |
| POST | `/workers/{id}/suspend` | ADMIN | `{"note?"}` | `WorkerProfileResponse` |
| POST | `/workers/{id}/reactivate` | ADMIN | — | `WorkerProfileResponse` |

Worker operational status is `ACTIVE` or `SUSPENDED`. Suspension removes
operational access immediately through `require_active_worker`; it does not change
the profile role. Suspension requires a reason when the API is used to record one.

## 5. Assignment endpoints

| Method | Path | Caller | Request | Response |
|---|---|---|---|---|
| GET | `/assignments/candidates` | ADMIN | `incident_id` | `{incident_id, items: Candidate[]}` |
| POST | `/assignments` | ADMIN | `{"incident_id","worker_profile_id","note?"}` | `AssignmentResponse` |
| GET | `/assignments` | active worker / ADMIN | `incident_id`, `status`, `limit`, `offset` | `AssignmentListResponse` |
| GET | `/assignments/{id}` | assigned worker / ADMIN | — | `AssignmentResponse` |
| POST | `/assignments/{id}/reassign` | ADMIN | `{"worker_profile_id","note?"}` | `AssignmentResponse` |
| POST | `/assignments/{id}/cancel` | ADMIN | `{"note"}` | `AssignmentResponse` |
| POST | `/assignments/{id}/accept` | assigned worker | `{"note?"}` | `AssignmentResponse` |
| POST | `/assignments/{id}/decline` | assigned worker | `{"note"}` | `AssignmentResponse` |
| POST | `/assignments/{id}/start` | assigned worker | `{"note?"}` | `AssignmentResponse` |
| POST | `/assignments/{id}/progress` | assigned worker | `{"note","progress_percent"}` | `AssignmentResponse` |
| POST | `/assignments/{id}/complete` | assigned worker | `{"note","evidence_note?"}` | `AssignmentResponse` |
| POST | `/assignments/{id}/verify` | ADMIN | `{"approve","note?"}` | `AssignmentResponse` |

Candidate ranking is deterministic and explainable: approval + active status,
service-area match, specialization match, no incompatible active assignment,
lowest active assignment count, then stable worker-id tie-break. Each candidate
returns `eligible` and a human-readable `rationale`. Nothing is auto-dispatched.

Assignment statuses: `OFFERED`, `ACCEPTED`, `DECLINED`, `IN_PROGRESS`,
`COMPLETION_SUBMITTED`, `VERIFIED_COMPLETED`, `CANCELLED`.

Verification with `approve=false` returns the assignment to `IN_PROGRESS` for
rework. Completion never resolves the incident by itself; only an ADMIN may move
an incident to `RESOLVED` after verification.

## 6. Incident lifecycle used by assignments

The existing incident state machine was extended, not replaced:

```
Legacy:  OPEN -> ACKNOWLEDGED -> IN_PROGRESS -> RESOLVED -> CLOSED
Workforce: OPEN -> VERIFIED -> ASSIGNED -> ACCEPTED -> IN_PROGRESS
           -> COMPLETION_SUBMITTED -> VERIFIED_COMPLETED -> RESOLVED -> CLOSED
Rework:  COMPLETION_SUBMITTED -> IN_PROGRESS
Reset:   ASSIGNED -> VERIFIED (reassign/cancel)
```

All transitions call `transition_incident()` and append immutable
`IncidentStatusEvent` rows.

## 7. Audit and notifications

| Method | Path | Caller | Description |
|---|---|---|---|
| GET | `/events` | ADMIN | Append-only `WorkforceEvent` records, filter by `entity_type`, paginated |
| GET | `/notifications` | active user | Own in-app notifications plus `unread` count |
| POST | `/notifications/{id}/read` | recipient | Marks one notification read |

There is no update or delete API for audit events. Notification kinds are a
closed set (`worker_application_*`, `worker_suspended`, `worker_reactivated`,
`incident_assigned`, `assignment_*`, `work_started`, `completion_*`,
`incident_resolved`). Notifications contain no credentials or private evidence
URLs. External email/push delivery is not configured; delivery is in-app only.

Audit metadata is persisted in `WorkforceEvent.detail` (database column
`metadata`) and is scrubbed of sensitive keys before write.

## 8. Representative error codes

`insufficient_role`, `worker_profile_required`, `worker_suspended`,
`application_not_allowed`, `duplicate_application`, `invalid_department`,
`application_already_decided`, `review_note_required`, `worker_not_found`,
`suspension_reason_required`, `assignment_not_found`, `worker_not_active`,
`worker_not_authorized`, `incident_not_assignable`, `incident_already_assigned`,
`assignment_not_active`, `same_worker`, `assignment_not_cancellable`,
`cancellation_reason_required`, `assignment_not_offered`, `decline_reason_required`,
`assignment_not_accepted`, `assignment_not_in_progress`, `completion_not_submitted`.

## 9. Frontend consumers

- `frontend/src/lib/api/workforce.ts` — one helper per endpoint; consumes only
  the routes above. Its contract is covered by `workforce.test.ts`.
- Routes: `/workforce/apply`, `/workforce/status`, `/admin`, `/worker`.
- Frontend role routing is a UX guard only; the backend remains authoritative.
