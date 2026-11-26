# Admin Workforce Workflow — Full Repository Audit

Date: 2026-11-26. Baseline: `c11d1dd` on `main`, clean worktree, synced with `origin/main`.

Method: read-only inspection of backend models/schemas/services/endpoints/auth/migrations,
frontend routes/components/API modules/tests, and deployment configuration. Test
counts below were produced by the audit agents running focused backend suites:
**81 passed** across auth, incidents, operations, recovery contracts, phase10 and
phase14 test modules.

## 1. What already exists and can be reused

| Capability | Evidence | Status |
|---|---|---|
| Three-role model `CITIZEN/WORKER/ADMIN` | `backend/app/models/enums.py:8-11` | VERIFIED WORKING |
| JWT verification (RS256/ES256, JWKS, aud/iss/exp) | `backend/app/auth/jwt.py:32,69-141` | VERIFIED WORKING |
| DB-profile-based role resolution (never JWT role claims) | `backend/app/auth/dependencies.py:79-93` | VERIFIED WORKING |
| `require_admin`, `require_worker` dependencies | `backend/app/auth/dependencies.py:114-132` | VERIFIED WORKING |
| Idempotent CITIZEN-only provisioning | `backend/app/services/profiles.py:31-76` | VERIFIED WORKING |
| Admin-only, audited role changes with self/last-admin guards | `backend/app/services/profiles.py:122-166`; `endpoints/admin.py:20-37` | VERIFIED WORKING |
| RLS trigger blocking browser-side role changes | `backend/alembic/versions/0002_auth_rls.py:139-172`; `0003_acl_hardening.py:79-115` | VERIFIED WORKING |
| Incident model, PostGIS location, evidence, status history | `backend/app/models/incident.py:33-180` | VERIFIED WORKING |
| Five-state incident lifecycle with validated transitions | `backend/app/models/enums.py:32-37`; `backend/app/services/incidents.py:42-54,240-290` | VERIFIED WORKING |
| Visibility/ownership rules and staff transition endpoint | `backend/app/services/incidents.py:96-105`; `endpoints/incidents.py:208-222` | VERIFIED WORKING |
| Departments (only existing assignment primitive) | `backend/app/models/department.py:12`; `services/incidents.py:258-273,388-402` | VERIFIED WORKING |
| Operations ingestion, alert rules, alert fan-out, in-app notifications | `backend/app/operations/alerts.py:51-140`; `endpoints/operations.py:162-481` | VERIFIED WORKING |
| Notification model and preferences | `backend/app/models/operations.py:489-552` | VERIFIED WORKING (alert-scoped) |
| Append-only event tables per domain (role, status, reviews, pilots) | `backend/app/models/audit.py`, `incident.py:145`, `pilot.py`, `phase14.py` | VERIFIED WORKING |
| Phase14 governed review workflow with ADMIN-only transitions | `backend/app/api/v1/endpoints/phase14.py:419,434` | VERIFIED WORKING |
| Research geography / geographic contexts registry | `backend/app/models/geo.py:16-43`; `backend/app/geo/contexts.py:136-166` | PARTIALLY WORKING (research-only) |
| Frontend auth provider, 401 handling, AuthGuard, typed API client | `frontend/src/components/auth/auth-provider.tsx:38-58,226-232`; `auth-guard.tsx:29-125` | VERIFIED WORKING |
| Existing incident list/detail forms, filters, pagination, history timeline | `frontend/src/app/incidents/incidents-view.tsx:95-187`; `incident-detail-view.tsx:432-463` | VERIFIED WORKING |
| Reusable UI primitives (`Card`, `EmptyState`, `ErrorNotice`, `LoadingBlock`, `StatusPill`) | `frontend/src/components/pilot/pilot-ui.tsx:72-185` | VERIFIED WORKING |

## 2. Gaps and defects

### Backend — NOT IMPLEMENTED

1. **No Worker entity of any kind.** No `workers`, `worker_applications`, `assignments`,
   `work_orders` or completion tables exist in `backend/app/models` or any of the
   24 Alembic revisions. No worker-specific service, schema or endpoint exists.
2. **No worker application lifecycle.** Citizens have no path to apply for worker
   status; there are no application states, review operations, review history or
   rejection reasons.
3. **No incident-to-worker assignment.** The only assignment primitive is
   `incidents.assigned_department_id` (`models/incident.py:69-73`). There is no
   worker eligibility evaluation, no service-area matching, no workload check,
   no assignment/reassignment history and no per-worker ownership enforcement.
4. **Any staff member can transition any incident.** `transition_incident()`
   (`services/incidents.py:240-290`) checks only role via the endpoint dependency;
   there is no assigned-worker ownership check.
5. **Missing incident states.** `IncidentStatus` (`models/enums.py:32-37`) has only
   `OPEN, ACKNOWLEDGED, IN_PROGRESS, RESOLVED, CLOSED`. There is no `VERIFIED`,
   `ASSIGNED`, `ACCEPTED`, `COMPLETION_SUBMITTED` or `VERIFIED_COMPLETED`, and no
   completion verification step; `IN_PROGRESS → RESOLVED` is a direct staff action.
6. **No triage/verification distinction.** Submitted reports go straight to `OPEN`;
   there is no verified-awaiting-assignment queue or completion-review queue.
7. **No admin operations overview over workforce data.** `GET /operations/dashboard`
   (`operations/dashboard.py`) covers incidents/risk/data quality/models/alerts only.
8. **External notification delivery is a stub.** `operations/notifications.py:37-42`
   always raises `NotificationAdapterUnavailable`; only `IN_APP` exists
   (`enums.py:245-247`). The existing `notifications` table requires an `alert_id`
   FK, so it cannot carry arbitrary lifecycle messages without creating an alert.
9. **No generic immutable workforce audit log.** Domain-specific event tables exist,
   but no event stream covers application review, assignment, worker actions or
   completion verification.
10. **No ward model or configured service areas.** `geo/contexts.py` provides research
    screening bboxes only; `is_pilot_eligible` is false for both contexts. Assigning
    by ward is not possible from existing data.

### Frontend — PARTIALLY WORKING / NOT IMPLEMENTED

11. `navigationForRole()` (`frontend/src/lib/auth/routing.ts:72-89`) gives WORKER and
    ADMIN identical menus; there are no ADMIN-only or WORKER-only destinations.
12. `/operations` (`components/operations/operations-dashboard.tsx:236-239`) explicitly
    states "No dispatch, assignment, reservation, or incident mutation is available
    anywhere in this view." It is a read/governance console, not an operations
    control plane.
13. No worker application, worker dashboard, admin application review, worker
    management, assignment or completion-verification route exists.
14. No worker types in `frontend/src/types/*`; `Incident` has `assigned_department`
    but no assignee field.
15. No tests for `auth-nav`, `AuthGuard`, `AuthProvider` or the operations/incident
    views; 38 test files exist but they cover pure helpers and presentational views.
    Test environment is `node` + `renderToStaticMarkup` (no jsdom/testing-library).

### Environment / operator dependencies

16. No users or profiles are seeded (`backend/app/seed.py:1-6`); an operator must
    bootstrap an identity and grant the first ADMIN through the trusted path.
17. Departments come only from `backend/app/seed.py:27-31`; they must be loaded
    before department-requiring transitions succeed.
18. Migrations through `0024_phase14_pilot` are the current head; production
    migration status must be verified separately. No production migration is
    authorised by this sprint.

## 3. Design constraints adopted for implementation

- Extend the **existing** `IncidentStatus` enum and `ALLOWED_TRANSITIONS` table rather
  than creating a parallel state machine.
- Reuse `change_profile_role()` for the WORKER grant so role transitions remain
  audited and cannot be forged from the browser.
- Reuse `transition_incident()` for incident state changes so the existing status
  event history remains authoritative.
- Add a dedicated `workforce_notifications` table because the existing
  `notifications` table is bound to `alerts` by a non-null FK.
- Add a single append-only `workforce_events` table for cross-domain audit history.
- Use explicitly configured `service_area` strings for eligibility, because no
  authoritative ward boundaries exist. No boundaries are invented.
- All new tables follow the RLS/grant pattern used in migration `0024`.

## 4. Verdict

The platform has a sound identity/RBAC/incident foundation, but the entire
municipal workforce layer — worker applications, approval, assignment, worker
execution and completion verification — is **NOT IMPLEMENTED**. This sprint adds
that layer without replacing working systems.
